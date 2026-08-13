package main

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

type Gateway struct {
	db         *pgxpool.Pool
	redis      *redis.Client
	jwtSecret  []byte
	rateLimits map[string]*rateLimiter
	rateMu     sync.Mutex
}

type rateLimiter struct {
	tokens    float64
	last      time.Time
	max       float64
	perSecond float64
}

type Claims struct {
	Username string `json:"username"`
	Role     string `json:"role"`
	jwt.RegisteredClaims
}

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	dsn := getEnv("TIMESCALEDB_DSN", "postgres://qsip:qsip@localhost:5432/qsip?sslmode=disable")
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	db, err := pgxpool.New(ctx, dsn)
	if err != nil {
		slog.Error("db connect failed", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	rdb := redis.NewClient(&redis.Options{Addr: getEnv("REDIS_ADDR", "localhost:6379")})
	defer rdb.Close()

	gw := &Gateway{
		db:         db,
		redis:      rdb,
		jwtSecret:  []byte(getEnv("JWT_SECRET", "change-me")),
		rateLimits: make(map[string]*rateLimiter),
	}

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders: []string{"*"},
	}))

	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	r.Get("/metrics", promhttp.Handler().ServeHTTP)

	r.Post("/api/v1/auth/register", gw.register)
	r.Post("/api/v1/auth/login", gw.login)

	r.Group(func(protected chi.Router) {
		protected.Use(gw.authMiddleware)
		protected.Get("/api/v1/signals", gw.listSignals)
		protected.Get("/api/v1/signals/{ticker}", gw.listSignalsByTicker)
		protected.Get("/api/v1/signals/{signal_id}/explain", gw.explainSignal)
		protected.Get("/api/v1/backtest/{ticker}", gw.backtestSummary)
		protected.Get("/api/v1/market/{ticker}", gw.marketData)
		protected.Get("/api/v1/features/{ticker}", gw.featureStore)
		protected.Get("/api/v1/portfolio/{strategy}", gw.portfolioSummary)
		protected.Post("/api/v1/replay", gw.replayEvents)
		protected.Get("/api/v1/stream/signals", gw.streamSignals)
	protected.Get("/api/v1/top-recommendations", gw.topRecommendations)
	protected.Get("/api/v1/research/performance", gw.researchPerformance)
	protected.Get("/api/v1/paper/account", gw.paperAccount)
	protected.Get("/api/v1/paper/positions", gw.paperPositions)
	protected.Get("/api/v1/paper/orders", gw.paperOrders)
	protected.Get("/api/v1/paper/trades", gw.paperTrades)
	protected.Post("/api/v1/paper/order", gw.paperCreateOrder)
	})

	httpAddr := getEnv("HTTP_ADDR", ":8083")
	srv := &http.Server{Addr: httpAddr, Handler: r}
	go func() {
		slog.Info("api gateway listening", "addr", httpAddr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("http server failed", "err", err)
		}
	}()

	<-ctx.Done()
	shutdownCtx, done := context.WithTimeout(context.Background(), 5*time.Second)
	defer done()
	_ = srv.Shutdown(shutdownCtx)
}

func (g *Gateway) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tokenStr := r.Header.Get("Authorization")
		if tokenStr == "" {
			http.Error(w, `{"error":"missing authorization"}`, http.StatusUnauthorized)
			return
		}
		tokenStr = strings.TrimPrefix(tokenStr, "Bearer ")
		token, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(token *jwt.Token) (interface{}, error) {
			return g.jwtSecret, nil
		})
		if err != nil || !token.Valid {
			http.Error(w, `{"error":"invalid token"}`, http.StatusUnauthorized)
			return
		}
		claims, ok := token.Claims.(*Claims)
		if !ok {
			http.Error(w, `{"error":"invalid claims"}`, http.StatusUnauthorized)
			return
		}

		// Rate limit by user
		if !g.allowRequest(claims.Username, 100, 60) {
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}

		ctx := context.WithValue(r.Context(), "claims", claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func (g *Gateway) allowRequest(key string, maxReq int, windowSeconds int) bool {
	g.rateMu.Lock()
	defer g.rateMu.Unlock()
	lim, ok := g.rateLimits[key]
	if !ok {
		lim = &rateLimiter{tokens: float64(maxReq), max: float64(maxReq), perSecond: float64(maxReq) / float64(windowSeconds)}
		g.rateLimits[key] = lim
	}
	now := time.Now()
	elapsed := now.Sub(lim.last).Seconds()
	lim.tokens = min(lim.max, lim.tokens+elapsed*lim.perSecond)
	lim.last = now
	if lim.tokens < 1 {
		return false
	}
	lim.tokens--
	return true
}

func (g *Gateway) register(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
		Role     string `json:"role"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if req.Role == "" {
		req.Role = "viewer"
	}
	hash := fmt.Sprintf("%x", sha256Sum(req.Password))
	_, err := g.redis.HSet(r.Context(), "user:"+req.Username, map[string]interface{}{
		"password": hash,
		"role":     req.Role,
	}).Result()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{"username": req.Username, "role": req.Role})
}

func (g *Gateway) login(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	stored, err := g.redis.HGetAll(r.Context(), "user:"+req.Username).Result()
	if err != nil || len(stored) == 0 {
		http.Error(w, `{"error":"invalid credentials"}`, http.StatusUnauthorized)
		return
	}
	hash := fmt.Sprintf("%x", sha256Sum(req.Password))
	if stored["password"] != hash {
		http.Error(w, `{"error":"invalid credentials"}`, http.StatusUnauthorized)
		return
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, &Claims{
		Username: req.Username,
		Role:     stored["role"],
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
		},
	})
	tokenStr, err := token.SignedString(g.jwtSecret)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{"token": tokenStr})
}

func (g *Gateway) listSignals(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 || limit > 1000 {
		limit = 100
	}
	rows, err := g.db.Query(r.Context(), `
		SELECT signal_id, timestamp, ticker, signal_type, direction, score, features, ml_score, metadata
		FROM signals ORDER BY timestamp DESC LIMIT $1`, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var out []map[string]any
	for rows.Next() {
		var s map[string]any
		var sid string
		var ts time.Time
		var ticker, stype, dir string
		var score, ml *float64
		var features []byte
		var metadata []byte
		if err := rows.Scan(&sid, &ts, &ticker, &stype, &dir, &score, &features, &ml, &metadata); err != nil {
			continue
		}
		if len(features) > 0 {
			json.Unmarshal(features, &s)
		}
		var meta map[string]any
		if len(metadata) > 0 {
			json.Unmarshal(metadata, &meta)
		}
		out = append(out, map[string]any{
			"signal_id": sid, "timestamp": ts, "ticker": ticker, "signal_type": stype,
			"direction": dir, "score": coalesceFloat64(score), "features": s, "ml_score": coalesceFloat64(ml), "metadata": meta,
		})
	}
	writeJSON(w, out)
}

func (g *Gateway) listSignalsByTicker(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 || limit > 1000 {
		limit = 100
	}
	rows, err := g.db.Query(r.Context(), `
		SELECT signal_id, timestamp, signal_type, direction, score, ml_score, metadata
		FROM signals WHERE ticker=$1 ORDER BY timestamp DESC LIMIT $2`, ticker, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var out []map[string]any
	for rows.Next() {
		var sid string
		var ts time.Time
		var stype, dir string
		var score, ml *float64
		var metadata []byte
		if err := rows.Scan(&sid, &ts, &stype, &dir, &score, &ml, &metadata); err != nil {
			continue
		}
		var meta map[string]any
		if len(metadata) > 0 {
			json.Unmarshal(metadata, &meta)
		}
		out = append(out, map[string]any{
			"signal_id": sid, "timestamp": ts, "signal_type": stype,
			"direction": dir, "score": coalesceFloat64(score), "ml_score": coalesceFloat64(ml), "metadata": meta,
		})
	}
	writeJSON(w, out)
}

func (g *Gateway) explainSignal(w http.ResponseWriter, r *http.Request) {
	signalID := chi.URLParam(r, "signal_id")
	row := g.db.QueryRow(r.Context(), `
		SELECT shap_values, top_features, summary FROM signal_explanations WHERE signal_id=$1`, signalID)
	var shap []byte
	var top []byte
	var summary string
	if err := row.Scan(&shap, &top, &summary); err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	var shapMap map[string]any
	if len(shap) > 0 {
		json.Unmarshal(shap, &shapMap)
	}
	var topList []map[string]any
	if len(top) > 0 {
		json.Unmarshal(top, &topList)
	}
	writeJSON(w, map[string]any{
		"signal_id":    signalID,
		"shap_values":  shapMap,
		"top_features": topList,
		"summary":      summary,
	})
}

func (g *Gateway) backtestSummary(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	row := g.db.QueryRow(r.Context(), `
		SELECT
			COUNT(*),
			AVG(CASE WHEN return_pct > 0 THEN 1.0 ELSE 0.0 END),
			AVG(return_pct),
			AVG(excess_return_pct),
			MIN(max_drawdown_pct)
		FROM backtest_results WHERE ticker=$1`, ticker)
	var count int64
	var win, avg, excess, dd *float64
	if err := row.Scan(&count, &win, &avg, &excess, &dd); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{
		"ticker":        ticker,
		"total_signals": count,
		"win_rate":      coalesceFloat64(win),
		"avg_return":    coalesceFloat64(avg),
		"avg_excess":    coalesceFloat64(excess),
		"max_drawdown":  coalesceFloat64(dd),
	})
}

func (g *Gateway) marketData(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 || limit > 5000 {
		limit = 252
	}
	rows, err := g.db.Query(r.Context(), `
		SELECT time, open, high, low, close, volume
		FROM market_data WHERE ticker=$1 ORDER BY time DESC LIMIT $2`, ticker, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var out []map[string]any
	for rows.Next() {
		var t time.Time
		var o, h, l, c, v *float64
		if err := rows.Scan(&t, &o, &h, &l, &c, &v); err != nil {
			continue
		}
		out = append(out, map[string]any{"time": t, "open": coalesceFloat64(o), "high": coalesceFloat64(h), "low": coalesceFloat64(l), "close": coalesceFloat64(c), "volume": coalesceFloat64(v)})
	}
	writeJSON(w, out)
}

func (g *Gateway) featureStore(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	version := r.URL.Query().Get("version")
	if version == "" {
		version = "v1"
	}
	row := g.db.QueryRow(r.Context(), `
		SELECT features, timestamp FROM feature_store
		WHERE ticker=$1 AND feature_version=$2 ORDER BY timestamp DESC LIMIT 1`, ticker, version)
	var features []byte
	var ts time.Time
	if err := row.Scan(&features, &ts); err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	var f map[string]any
	if len(features) > 0 {
		json.Unmarshal(features, &f)
	}
	writeJSON(w, map[string]any{"ticker": ticker, "version": version, "timestamp": ts, "features": f})
}

func (g *Gateway) portfolioSummary(w http.ResponseWriter, r *http.Request) {
	strategy := chi.URLParam(r, "strategy")
	row := g.db.QueryRow(r.Context(), `
		SELECT strategy, timestamp, nav, total_value, sharpe, sortino, max_drawdown, alpha, beta
		FROM portfolio_snapshots WHERE strategy=$1 ORDER BY timestamp DESC LIMIT 1`, strategy)
	var s, ts, nav, total, sharpe, sortino, dd, alpha, beta interface{}
	if err := row.Scan(&s, &ts, &nav, &total, &sharpe, &sortino, &dd, &alpha, &beta); err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	writeJSON(w, map[string]any{
		"strategy":     s,
		"timestamp":    ts,
		"nav":          nav,
		"total_value":  total,
		"sharpe":       sharpe,
		"sortino":      sortino,
		"max_drawdown": dd,
		"alpha":        alpha,
		"beta":         beta,
	})
}

func (g *Gateway) replayEvents(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Source    string `json:"source"`
		EventType string `json:"event_type"`
		DateFrom  string `json:"date_from"`
		DateTo    string `json:"date_to"`
		Topic     string `json:"topic"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	// Forward to replay-service
	replayURL := getEnv("REPLAY_SERVICE_URL", "http://replay-service:8087/replay")
	body, _ := json.Marshal(req)
	resp, err := http.Post(replayURL, "application/json", strings.NewReader(string(body)))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	w.WriteHeader(resp.StatusCode)
	_ = json.NewEncoder(w).Encode(map[string]any{"status": "forwarded", "replay_service_status": resp.StatusCode})
}

func (g *Gateway) streamSignals(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}
	pubsub := g.redis.Subscribe(r.Context(), "signals")
	defer pubsub.Close()
	ch := pubsub.Channel()
	for {
		select {
		case <-r.Context().Done():
			return
		case msg := <-ch:
			fmt.Fprintf(w, "data: %s\n\n", msg.Payload)
			flusher.Flush()
		}
	}
}

func (g *Gateway) topRecommendations(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 || limit > 50 {
		limit = 10
	}
	rows, err := g.db.Query(r.Context(), `
		SELECT s.signal_id, s.timestamp, s.ticker, s.signal_type, s.direction, s.score, s.ml_score, e.top_features, e.summary
		FROM signals s
		LEFT JOIN signal_explanations e ON s.signal_id = e.signal_id
		WHERE s.direction = 'long'
		ORDER BY s.score * s.ml_score DESC
		LIMIT $1`, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var out []map[string]any
	for rows.Next() {
		var sid, ticker, stype, dir string
		var ts time.Time
		var score, ml *float64
		var top []byte
		var summary string
		if err := rows.Scan(&sid, &ts, &ticker, &stype, &dir, &score, &ml, &top, &summary); err != nil {
			continue
		}
		var features []map[string]any
		if len(top) > 0 {
			json.Unmarshal(top, &features)
		}
		out = append(out, map[string]any{
			"signal_id": sid, "timestamp": ts, "ticker": ticker, "signal_type": stype,
			"direction": dir, "score": coalesceFloat64(score), "ml_score": coalesceFloat64(ml), "confidence": coalesceFloat64(score) * coalesceFloat64(ml),
			"top_features": features, "summary": summary,
		})
	}
	writeJSON(w, out)
}

func (g *Gateway) researchPerformance(w http.ResponseWriter, r *http.Request) {
	// Serve static research results JSON
	data, err := os.ReadFile(getEnv("RESEARCH_RESULTS_PATH", "research/signal_performance.json"))
	if err != nil {
		http.Error(w, `{"error":"research results not available"}`, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func (g *Gateway) proxyPaper(w http.ResponseWriter, r *http.Request, path string) {
	base := getEnv("PAPER_TRADING_SERVICE_URL", "http://paper-trading-service:8088")
	url := base + path + "?" + r.URL.RawQuery
	var body *strings.Reader
	if r.Body != nil {
		b, _ := io.ReadAll(r.Body)
		body = strings.NewReader(string(b))
	}
	method := r.Method
	if method == "" {
		method = "GET"
	}
	req, err := http.NewRequest(method, url, body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func (g *Gateway) paperAccount(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/account") }
func (g *Gateway) paperPositions(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/positions") }
func (g *Gateway) paperOrders(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/orders") }
func (g *Gateway) paperTrades(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/trades") }
func (g *Gateway) paperCreateOrder(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/order") }

func coalesceFloat64(v *float64) float64 {
	if v == nil {
		return 0
	}
	return *v
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func sha256Sum(s string) []byte {
	h := sha256.New()
	h.Write([]byte(s))
	return h.Sum(nil)
}
