import json
import logging
import os
import threading
import time
from datetime import datetime

from prometheus_client import Counter, Histogram, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaConsumer, KafkaProducer
from qsip.redis_client import RedisClient
from qsip.replay import EventArchiver
from qsip.validation import DataValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALIDATED = Counter("events_validated_total", "Events validated", ["source", "event_type"])
REJECTED = Counter("events_rejected_total", "Events rejected", ["issue_type"])
VALIDATION_LATENCY = Histogram("validation_seconds", "Validation latency")


class DataValidationService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.redis = RedisClient(self.cfg.redis_addr)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.validator = DataValidator(self.db, self.redis)
        self.archiver = None
        if self.cfg.minio_endpoint:
            try:
                self.archiver = EventArchiver(
                    self.cfg.minio_endpoint,
                    self.cfg.minio_access_key,
                    self.cfg.minio_secret_key,
                )
            except Exception as e:
                logger.warning("minio not available, disabling archive: %s", e)
        self._buffer: list[dict] = []
        self._lock = threading.Lock()

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        threading.Thread(target=self._flush_archive, daemon=True).start()
        consumer = KafkaConsumer(
            self.cfg.kafka_brokers,
            "data-validation-service",
            ["raw-events"],
        )
        try:
            consumer.consume(self._on_event)
        finally:
            consumer.stop()

    def _on_event(self, event: dict):
        with VALIDATION_LATENCY.time():
            is_valid, issues = self.validator.validate(event)
            for issue in issues:
                self.db.insert_data_quality_issue(issue)
                if issue["severity"] == "critical":
                    REJECTED.labels(issue_type=issue["issue_type"]).inc()
                    logger.warning("critical issue: %s %s", issue["issue_type"], issue.get("reason"))
            if not is_valid:
                return

            # Enrich with validation metadata
            event["metadata"] = event.get("metadata", {})
            event["metadata"]["validated_at"] = datetime.utcnow().isoformat()
            self.producer.send("validated-events", event.get("ticker", ""), event)
            VALIDATED.labels(source=event.get("source"), event_type=event.get("event_type")).inc()

            with self._lock:
                self._buffer.append(event)

    def _flush_archive(self):
        while True:
            time.sleep(60)
            with self._lock:
                if not self._buffer:
                    continue
                batch = self._buffer
                self._buffer = []
            if self.archiver:
                try:
                    path = self.archiver.archive("validated", "events", batch)
                    self.db.insert_archive_metadata({
                        "archive_id": f"validated-{datetime.utcnow().isoformat()}",
                        "source": "validated",
                        "event_type": "events",
                        "date_from": batch[0].get("timestamp"),
                        "date_to": batch[-1].get("timestamp"),
                        "object_path": path,
                        "record_count": len(batch),
                    })
                    logger.info("archived %d events to %s", len(batch), path)
                except Exception as e:
                    logger.error("archive failed: %s", e)


if __name__ == "__main__":
    DataValidationService().run()
