package config

import (
	"os"
	"time"
)

type Config struct {
	KafkaBrokers string
	DBDSN        string
	RedisAddr    string
	UserAgent    string
	OTELEndpoint string
	ListenAddr   string
	MetricsAddr  string
	PollInterval time.Duration
}

func Load() Config {
	return Config{
		KafkaBrokers: getEnv("KAFKA_BROKERS", "localhost:9092"),
		DBDSN:        getEnv("TIMESCALEDB_DSN", "postgres://qsip:qsip@localhost:5432/qsip?sslmode=disable"),
		RedisAddr:    getEnv("REDIS_ADDR", "localhost:6379"),
		UserAgent:    getEnv("SEC_USER_AGENT", "QSIP contact@example.com"),
		OTELEndpoint: getEnv("OTEL_ENDPOINT", ""),
		ListenAddr:   getEnv("LISTEN_ADDR", ":8080"),
		MetricsAddr:  getEnv("METRICS_ADDR", ":9091"),
		PollInterval: parseDuration(getEnv("POLL_INTERVAL", "60s")),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func parseDuration(s string) time.Duration {
	d, err := time.ParseDuration(s)
	if err != nil {
		return 60 * time.Second
	}
	return d
}
