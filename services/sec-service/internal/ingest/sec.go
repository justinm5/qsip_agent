package ingest

import (
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/justinm5/qsip_agent/services/sec-service/internal/publisher"
	"github.com/justinm5/qsip_agent/services/sec-service/internal/store"
)

const (
	Form4RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&start=0&count=100&output=atom"
	Form8KRSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=100&output=atom"
)

type Feed struct {
	XMLName xml.Name `xml:"feed"`
	Entries []Entry  `xml:"entry"`
}

type Entry struct {
	Title     string   `xml:"title"`
	Link      Link     `xml:"link"`
	Updated   string   `xml:"updated"`
	Category  Category `xml:"category"`
	Summary   string   `xml:"summary"`
	Accession string   `xml:"accession-number"`
}

type Link struct {
	Href string `xml:"href,attr"`
}

type Category struct {
	Label string `xml:"label,attr"`
	Term  string `xml:"term,attr"`
}

type SECIngester struct {
	client    *http.Client
	userAgent string
	pub       *publisher.KafkaPublisher
	db        *store.DB
}

func New(pub *publisher.KafkaPublisher, db *store.DB, userAgent string) *SECIngester {
	return &SECIngester{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		userAgent: userAgent,
		pub:       pub,
		db:        db,
	}
}

func (s *SECIngester) Run(ctx context.Context) error {
	slog.Info("starting SEC EDGAR ingestion")
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	s.ingest(ctx, Form4RSS)
	s.ingest(ctx, Form8KRSS)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			s.ingest(ctx, Form4RSS)
			s.ingest(ctx, Form8KRSS)
		}
	}
}

func (s *SECIngester) ingest(ctx context.Context, url string) {
	r, err := s.fetch(ctx, url)
	if err != nil {
		slog.Error("sec fetch failed", "url", url, "err", err)
		return
	}
	defer r.Close()

	body, err := io.ReadAll(io.LimitReader(r, 10*1024*1024))
	if err != nil {
		slog.Error("read sec response", "err", err)
		return
	}

	var feed Feed
	if err := xml.Unmarshal(body, &feed); err != nil {
		slog.Error("unmarshal sec feed", "err", err)
		return
	}

	for _, e := range feed.Entries {
		ticker := extractTicker(e.Title)
		cik := extractCIK(e.Summary)
		filing := store.Filing{
			AccessionNumber: e.Accession,
			FormType:        e.Category.Term,
			Ticker:          ticker,
			CIK:             cik,
			FiledAt:         parseTime(e.Updated),
			ReportedAt:      parseTime(e.Updated),
			Payload: map[string]any{
				"title":   e.Title,
				"link":    e.Link.Href,
				"summary": e.Summary,
				"term":    e.Category.Term,
			},
		}
		if err := s.db.UpsertFiling(ctx, filing); err != nil {
			slog.Error("upsert filing", "err", err)
		}

		ev := publisher.Event{
			EventID:   e.Accession,
			Source:    "sec",
			EventType: strings.ToLower(e.Category.Term),
			Ticker:    ticker,
			Timestamp: e.Updated,
			Payload: map[string]any{
				"title":      e.Title,
				"link":       e.Link.Href,
				"summary":    e.Summary,
				"term":       e.Category.Term,
				"accession":  e.Accession,
				"cik":        cik,
			},
			Metadata: map[string]any{"source_url": url},
		}
		if err := s.pub.Publish(ctx, ev); err != nil {
			slog.Error("publish sec event", "err", err)
		}
	}
	slog.Info("sec ingestion complete", "url", url, "entries", len(feed.Entries))
}

func (s *SECIngester) fetch(ctx context.Context, url string) (io.ReadCloser, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", s.userAgent)
	req.Header.Set("Accept", "application/atom+xml")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		return nil, fmt.Errorf("sec returned %d", resp.StatusCode)
	}
	return resp.Body, nil
}

var tickerRe = regexp.MustCompile(`\(([A-Z]{1,5})\)`)
var cikRe = regexp.MustCompile(`CIK[:\s]+(\d{10})`)

func extractTicker(title string) string {
	m := tickerRe.FindStringSubmatch(title)
	if len(m) > 1 {
		return m[1]
	}
	return ""
}

func extractCIK(summary string) string {
	m := cikRe.FindStringSubmatch(summary)
	if len(m) > 1 {
		return m[1]
	}
	return ""
}

func parseTime(s string) time.Time {
	t, _ := time.Parse(time.RFC3339, s)
	if t.IsZero() {
		t = time.Now().UTC()
	}
	return t
}
