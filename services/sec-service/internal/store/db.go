package store

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Filing struct {
	AccessionNumber string
	FormType        string
	Ticker          string
	CIK             string
	FiledAt         time.Time
	ReportedAt      time.Time
	Payload         map[string]any
}

type DB struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*DB, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse dsn: %w", err)
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("connect db: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return &DB{pool: pool}, nil
}

func (d *DB) UpsertFiling(ctx context.Context, f Filing) error {
	payload, err := json.Marshal(f.Payload)
	if err != nil {
		return err
	}
	_, err = d.pool.Exec(ctx, `
		INSERT INTO sec_filings (accession_number, form_type, ticker, cik, filed_at, reported_at, payload)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		ON CONFLICT (accession_number) DO UPDATE SET
			payload = EXCLUDED.payload,
			created_at = NOW()
	`, f.AccessionNumber, f.FormType, f.Ticker, f.CIK, f.FiledAt, f.ReportedAt, payload)
	return err
}

func (d *DB) Close() {
	d.pool.Close()
}
