"""Integration tests using mocked Kafka/DB."""

from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaProducer
from qsip.validation import DataValidator


def test_duplicate_filing_only_one_stored(monkeypatch):
    stored = []

    class FakeDB:
        def insert_data_quality_issue(self, issue):
            pass

    class FakeRedis:
        class client:
            @staticmethod
            def exists(key):
                return False

            @staticmethod
            def set(*args, **kwargs):
                pass

    validator = DataValidator(FakeDB(), FakeRedis())
    event = {"event_id": "x", "source": "sec", "event_type": "4", "ticker": "A", "timestamp": "2024-08-13T12:00:00", "payload": {}}
    validator.validate(event)
    validator.validate(event)
    _, issues = validator.validate(event)
    assert sum(1 for i in issues if i["issue_type"] == "duplicate") == 1


def test_news_sentiment_positive():
    from qsip.earnings import EarningsTranscriptClient
    client = EarningsTranscriptClient()
    score = client._sentiment_word_ratio("strong growth confident robust opportunity", positive=True)
    assert score > 0.5
