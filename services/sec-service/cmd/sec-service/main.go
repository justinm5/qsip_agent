package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/justinm5/qsip_agent/services/sec-service/internal/config"
	"github.com/justinm5/qsip_agent/services/sec-service/internal/ingest"
	"github.com/justinm5/qsip_agent/services/sec-service/internal/publisher"
	"github.com/justinm5/qsip_agent/services/sec-service/internal/store"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})))

	cfg := config.Load()

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	db, err := store.New(ctx, cfg.DBDSN)
	if err != nil {
		slog.Error("db init failed", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	pub, err := publisher.New(cfg.KafkaBrokers, "raw-events")
	if err != nil {
		slog.Error("kafka init failed", "err", err)
		os.Exit(1)
	}
	defer pub.Close()

	ing := ingest.New(pub, db, cfg.UserAgent)

	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })

	srv := &http.Server{Addr: cfg.MetricsAddr, Handler: mux}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("metrics server failed", "err", err)
		}
	}()

	go func() {
		<-ctx.Done()
		shutdownCtx, done := context.WithTimeout(context.Background(), 5*time.Second)
		defer done()
		_ = srv.Shutdown(shutdownCtx)
	}()

	if err := ing.Run(ctx); err != nil {
		slog.Error("ingester stopped", "err", err)
	}
}
