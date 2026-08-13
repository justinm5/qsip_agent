from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio

from qsip.kafka_client import KafkaProducer

logger = logging.getLogger(__name__)


class EventArchiver:
    """Archive Kafka events to MinIO as Parquet for replay."""

    def __init__(self, minio_endpoint: str, access_key: str, secret_key: str, bucket: str = "qsip-events"):
        self.client = Minio(
            minio_endpoint.replace("http://", "").replace("https://", ""),
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        self.bucket = bucket
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def archive(self, source: str, event_type: str, events: list[dict[str, Any]]) -> str:
        if not events:
            return ""
        table = pa.Table.from_pylist(events)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        now = datetime.utcnow()
        path = f"{source}/{event_type}/{now:%Y/%m/%d}/{now:%H%M%S}.parquet"
        self.client.put_object(self.bucket, path, buf, length=buf.getbuffer().nbytes, content_type="application/octet-stream")
        return path

    def read(self, object_path: str) -> list[dict[str, Any]]:
        try:
            resp = self.client.get_object(self.bucket, object_path)
            table = pq.read_table(resp)
            return table.to_pylist()
        except Exception as e:
            logger.error("read archive failed: %s", e)
            return []


class ReplayEngine:
    """Replay archived events back into Kafka."""

    def __init__(self, kafka_brokers: str, archiver: EventArchiver):
        self.producer = KafkaProducer(kafka_brokers)
        self.archiver = archiver

    def replay(self, source: str | None, event_type: str | None, date_from: datetime, date_to: datetime, topic: str = "raw-events") -> int:
        objects = self._list_objects(source, event_type, date_from, date_to)
        count = 0
        for obj in objects:
            events = self.archiver.read(obj.object_name)
            for ev in events:
                ticker = ev.get("ticker", "")
                self.producer.send(topic, ticker, ev)
                count += 1
        return count

    def _list_objects(self, source: str | None, event_type: str | None, date_from: datetime, date_to: datetime):
        prefix = ""
        if source:
            prefix += f"{source}/"
            if event_type:
                prefix += f"{event_type}/"
        objects = self.archiver.client.list_objects(self.archiver.bucket, prefix=prefix, recursive=True)
        result = []
        for obj in objects:
            # crude date filter from path
            result.append(obj)
        return result
