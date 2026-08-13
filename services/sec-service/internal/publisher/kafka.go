package publisher

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"

	"github.com/twmb/franz-go/pkg/kgo"
)

type Event struct {
	EventID   string         `json:"event_id"`
	Source    string         `json:"source"`
	EventType string         `json:"event_type"`
	Ticker    string         `json:"ticker,omitempty"`
	Timestamp string         `json:"timestamp"`
	Payload   map[string]any `json:"payload"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

type KafkaPublisher struct {
	client *kgo.Client
	topic  string
}

func New(brokers, topic string) (*KafkaPublisher, error) {
	opts := []kgo.Opt{
		kgo.SeedBrokers(brokers),
		kgo.AllowAutoTopicCreation(),
		kgo.ProducerBatchMaxBytes(1024 * 1024),
	}
	client, err := kgo.NewClient(opts...)
	if err != nil {
		return nil, fmt.Errorf("create kafka client: %w", err)
	}
	return &KafkaPublisher{client: client, topic: topic}, nil
}

func (p *KafkaPublisher) Publish(ctx context.Context, ev Event) error {
	b, err := json.Marshal(ev)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}
	key := ev.Ticker
	if key == "" {
		key = ev.EventID
	}
	p.client.Produce(ctx, &kgo.Record{
		Topic: p.topic,
		Key:   []byte(key),
		Value: b,
		Headers: []kgo.RecordHeader{
			{Key: "source", Value: []byte(ev.Source)},
			{Key: "event_type", Value: []byte(ev.EventType)},
		},
	}, func(r *kgo.Record, err error) {
		if err != nil {
			slog.Error("kafka produce failed", "err", err, "topic", r.Topic)
		}
	})
	return nil
}

func (p *KafkaPublisher) Close() {
	p.client.Close()
}
