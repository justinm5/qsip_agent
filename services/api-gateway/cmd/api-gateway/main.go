package main

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"os"
	"os/signal"
	"sort"
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
	protected.Get("/api/v1/stocks/{ticker}/recommendation", gw.stockRecommendation)
	protected.Get("/api/v1/stocks/trending", gw.trendingStocks)
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

		next.ServeHTTP(w, r)
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
			_ = json.Unmarshal(features, &s)
		}
		var meta map[string]any
		if len(metadata) > 0 {
			_ = json.Unmarshal(metadata, &meta)
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
			_ = json.Unmarshal(metadata, &meta)
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
		_ = json.Unmarshal(shap, &shapMap)
	}
	var topList []map[string]any
	if len(top) > 0 {
		_ = json.Unmarshal(top, &topList)
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
		_ = json.Unmarshal(features, &f)
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
			_ = json.Unmarshal(top, &features)
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
	_, _ = w.Write(data)
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
	_, _ = io.Copy(w, resp.Body)
}

func (g *Gateway) paperAccount(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/account") }
func (g *Gateway) paperPositions(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/positions") }
func (g *Gateway) paperOrders(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/orders") }
func (g *Gateway) paperTrades(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/trades") }
func (g *Gateway) paperCreateOrder(w http.ResponseWriter, r *http.Request) { g.proxyPaper(w, r, "/paper/order") }

var trendingUniverse = []string{
	"AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM",
	"XOM", "JNJ", "V", "PG", "UNH", "HD", "MA", "BAC", "ABBV", "PFE",
	"KO", "PEP", "COST", "TMO", "AVGO", "DIS", "WMT", "MRK", "CVX",
	"ABT", "MCD", "ACN", "ADBE", "CRM", "NKE", "TXN", "VZ", "NFLX",
	"PM", "BMY", "QCOM", "RTX",
}

func (g *Gateway) stockRecommendation(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	rec, err := g.recommendationForTicker(r.Context(), ticker)
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"%s"}`, err.Error()), http.StatusInternalServerError)
		return
	}
	writeJSON(w, rec)
}

func (g *Gateway) trendingStocks(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 || limit > len(trendingUniverse) {
		limit = 12
	}

	type result struct {
		idx  int
		rec  map[string]any
		err  error
	}
	ch := make(chan result, limit)
	var wg sync.WaitGroup
	for i, t := range trendingUniverse[:limit] {
		wg.Add(1)
		go func(idx int, ticker string) {
			defer wg.Done()
			rec, err := g.recommendationForTicker(r.Context(), ticker)
			ch <- result{idx: idx, rec: rec, err: err}
		}(i, t)
	}
	wg.Wait()
	close(ch)

	out := make([]map[string]any, 0, limit)
	for res := range ch {
		if res.err != nil || res.rec == nil || res.rec["price"] == nil {
			continue
		}
		out = append(out, res.rec)
	}
	// Sort by score descending
	sort.Slice(out, func(i, j int) bool {
		si, _ := out[i]["score"].(float64)
		sj, _ := out[j]["score"].(float64)
		return si > sj
	})
	writeJSON(w, out)
}

type finnhubQuote struct {
	C  float64 `json:"c"`
	D  float64 `json:"d"`
	DP float64 `json:"dp"`
	H  float64 `json:"h"`
	L  float64 `json:"l"`
	O  float64 `json:"o"`
	PC float64 `json:"pc"`
}

type finnhubRec struct {
	Buy        int    `json:"buy"`
	Hold       int    `json:"hold"`
	Period     string `json:"period"`
	Sell       int    `json:"sell"`
	StrongBuy  int    `json:"strongBuy"`
	StrongSell int    `json:"strongSell"`
}

type finnhubCandles struct {
	S string    `json:"s"`
	C []float64 `json:"c"`
	V []int64   `json:"v"`
	T []int64   `json:"t"`
}

func (g *Gateway) recommendationForTicker(ctx context.Context, ticker string) (map[string]any, error) {
	ticker = strings.ToUpper(strings.TrimSpace(ticker))
	cacheKey := "rec:" + ticker

	if cached, err := g.redis.Get(ctx, cacheKey).Result(); err == nil && cached != "" {
		var rec map[string]any
		if json.Unmarshal([]byte(cached), &rec) == nil {
			return rec, nil
		}
	}

	apiKey := getEnv("FINNHUB_KEY", "")
	if apiKey == "" {
		rec := noDataRec(ticker)
		g.cacheRec(ctx, cacheKey, rec)
		return rec, nil
	}

	httpClient := &http.Client{Timeout: 10 * time.Second}

	quote, err := g.finnhubQuote(ctx, httpClient, ticker, apiKey)
	if err != nil {
		slog.Warn("finnhub quote failed", "ticker", ticker, "err", err)
	}

	recs, err := g.finnhubRecommendations(ctx, httpClient, ticker, apiKey)
	if err != nil {
		slog.Warn("finnhub recommendation failed", "ticker", ticker, "err", err)
	}

	candles, err := g.finnhubCandles(ctx, httpClient, ticker, apiKey)
	if err != nil {
		slog.Warn("finnhub candles failed", "ticker", ticker, "err", err)
	}

	rec := buildRecommendation(ticker, quote, recs, candles)
	g.cacheRec(ctx, cacheKey, rec)
	return rec, nil
}

func (g *Gateway) cacheRec(ctx context.Context, key string, rec map[string]any) {
	b, _ := json.Marshal(rec)
	_ = g.redis.Set(ctx, key, string(b), 5*time.Minute).Err()
}

func (g *Gateway) finnhubQuote(ctx context.Context, client *http.Client, ticker, apiKey string) (*finnhubQuote, error) {
	url := fmt.Sprintf("https://finnhub.io/api/v1/quote?symbol=%s&token=%s", ticker, apiKey)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	var q finnhubQuote
	if err := json.NewDecoder(resp.Body).Decode(&q); err != nil {
		return nil, err
	}
	return &q, nil
}

func (g *Gateway) finnhubRecommendations(ctx context.Context, client *http.Client, ticker, apiKey string) ([]finnhubRec, error) {
	url := fmt.Sprintf("https://finnhub.io/api/v1/stock/recommendation?symbol=%s&token=%s", ticker, apiKey)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	var recs []finnhubRec
	if err := json.NewDecoder(resp.Body).Decode(&recs); err != nil {
		return nil, err
	}
	return recs, nil
}

func (g *Gateway) finnhubCandles(ctx context.Context, client *http.Client, ticker, apiKey string) (*finnhubCandles, error) {
	to := time.Now().Unix()
	from := time.Now().AddDate(0, 0, -90).Unix()
	url := fmt.Sprintf("https://finnhub.io/api/v1/stock/candle?symbol=%s&resolution=D&from=%d&to=%d&token=%s", ticker, from, to, apiKey)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	var c finnhubCandles
	if err := json.NewDecoder(resp.Body).Decode(&c); err != nil {
		return nil, err
	}
	if c.S != "ok" {
		return nil, fmt.Errorf("candle status %s", c.S)
	}
	return &c, nil
}

func noDataRec(ticker string) map[string]any {
	return map[string]any{
		"ticker":         ticker,
		"name":           ticker,
		"price":          nil,
		"change_pct":     0.0,
		"analyst_rating": "No data",
		"analyst_count":  0,
		"recommendation": "No data",
		"score":          0.0,
		"summary":        "We don't have data for this ticker right now. Add a Finnhub API key or try again later.",
		"signals":        []map[string]any{},
	}
}

func buildRecommendation(ticker string, quote *finnhubQuote, recs []finnhubRec, candles *finnhubCandles) map[string]any {
	var price any = nil
	changePct := 0.0
	if quote != nil && quote.C > 0 {
		price = round2(quote.C)
		changePct = quote.DP
	}

	analystScore := 0.0
	analystRating := "No analyst data"
	analystCount := 0
	if len(recs) > 0 {
		latest := recs[0]
		for _, r := range recs {
			if r.Period > latest.Period {
				latest = r
			}
		}
		total := latest.StrongBuy + latest.Buy + latest.Hold + latest.Sell + latest.StrongSell
		if total > 0 {
			analystCount = total
			weighted := float64(latest.StrongBuy*2+latest.Buy*1+latest.Sell*-1+latest.StrongSell*-2) / float64(total)
			analystScore = weighted / 2.0 // normalize -1..1
			if analystScore >= 0.5 {
				analystRating = "Strong Buy"
			} else if analystScore >= 0.2 {
				analystRating = "Buy"
			} else if analystScore <= -0.5 {
				analystRating = "Strong Sell"
			} else if analystScore <= -0.2 {
				analystRating = "Sell"
			} else {
				analystRating = "Hold"
			}
		}
	}

	momentumScore := 0.0
	return20 := 0.0
	return60 := 0.0
	volumeRatio := 1.0
	rsi := 50.0
	if candles != nil && len(candles.C) >= 21 && len(candles.V) >= 21 {
		closes := candles.C
		volumes := candles.V
		return20 = (closes[len(closes)-1] - closes[len(closes)-21]) / closes[len(closes)-21]
		if len(closes) >= 61 && len(volumes) >= 61 {
			return60 = (closes[len(closes)-1] - closes[len(closes)-60]) / closes[len(closes)-60]
		}
		avgVol := int64(0)
		window := 20
		if len(volumes) < window {
			window = len(volumes)
		}
		for _, v := range volumes[len(volumes)-window:] {
			avgVol += v
		}
		avgVol /= int64(window)
		if avgVol > 0 {
			volumeRatio = float64(volumes[len(volumes)-1]) / float64(avgVol)
		}
		rsi = computeRSI(closes, 14)

		momentumScore = (return20*1.5 + return60*0.5 + clamp((volumeRatio-1)/3, -0.5, 0.5) + (rsi-50)/100) / 2.5
		momentumScore = clamp(momentumScore, -1, 1)
	}

	combined := 0.6*analystScore + 0.4*momentumScore
	combined = clamp(combined, -1, 1)
	recommendation := labelRecommendation(combined)

	signals := []map[string]any{}
	if analystRating != "No analyst data" {
		signals = append(signals, map[string]any{
			"label":  "Analyst consensus",
			"value":  analystRating,
			"detail": fmt.Sprintf("Based on %d analyst ratings", analystCount),
		})
	}
	if candles != nil && len(candles.C) >= 21 {
		signals = append(signals, map[string]any{
			"label":  "20-day price trend",
			"value":  fmt.Sprintf("%+.1f%%", return20*100),
			"detail": "How the price has moved over the last month",
		})
	}
	if candles != nil && len(candles.C) >= 61 {
		signals = append(signals, map[string]any{
			"label":  "3-month trend",
			"value":  fmt.Sprintf("%+.1f%%", return60*100),
			"detail": "Longer-term price direction",
		})
	}
	if candles != nil && len(candles.C) >= 21 && len(candles.V) >= 21 {
		signals = append(signals, map[string]any{
			"label":  "Volume vs average",
			"value":  fmt.Sprintf("%.1fx", volumeRatio),
			"detail": "Recent volume compared to the 20-day average",
		})
		signals = append(signals, map[string]any{
			"label":  "Momentum (RSI)",
			"value":  fmt.Sprintf("%.0f", rsi),
			"detail": "Above 70 can mean overbought; below 30 can mean oversold",
		})
	}

	summary := fmt.Sprintf("Overall recommendation is %s. ", recommendation)
	if analystRating != "No analyst data" {
		summary += fmt.Sprintf("Wall Street analysts say %s. ", analystRating)
	}
	if candles != nil && len(candles.C) >= 21 {
		direction := "up"
		if return20 < 0 {
			direction = "down"
		}
		summary += fmt.Sprintf("Price is %s %.1f%% over the last 20 trading days.", direction, mathAbs(return20)*100)
	}
	if volumeRatio > 2 {
		summary += " Trading volume is unusually high."
	}

	return map[string]any{
		"ticker":         ticker,
		"name":           ticker,
		"price":          price,
		"change_pct":     round2(changePct),
		"analyst_rating": analystRating,
		"analyst_count":  analystCount,
		"recommendation": recommendation,
		"score":          round2(combined),
		"summary":        summary,
		"signals":        signals,
	}
}

func computeRSI(prices []float64, window int) float64 {
	if len(prices) < window+1 {
		return 50.0
	}
	gain, loss := 0.0, 0.0
	for i := len(prices) - window; i < len(prices); i++ {
		change := prices[i] - prices[i-1]
		if change > 0 {
			gain += change
		} else {
			loss += -change
		}
	}
	avgGain := gain / float64(window)
	avgLoss := loss / float64(window)
	if avgLoss == 0 {
		return 100.0
	}
	rs := avgGain / avgLoss
	return 100.0 - (100.0 / (1.0 + rs))
}

func clamp(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func mathAbs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}

func labelRecommendation(score float64) string {
	if score >= 0.5 {
		return "Strong Buy"
	}
	if score >= 0.2 {
		return "Buy"
	}
	if score <= -0.5 {
		return "Strong Sell"
	}
	if score <= -0.2 {
		return "Sell"
	}
	return "Hold"
}

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
