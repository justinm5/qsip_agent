from __future__ import annotations

import json
import logging
from typing import Any, Callable

from confluent_kafka import Consumer, KafkaError, Producer, TopicPartition

logger = logging.getLogger(__name__)


class KafkaProducer:
    def __init__(self, brokers: str):
        self.producer = Producer({
            "bootstrap.servers": brokers,
            "client.id": "qsip-python-producer",
            "compression.type": "lz4",
            "batch.size": 65536,
            "linger.ms": 10,
        })

    def send(self, topic: str, key: str, payload: dict[str, Any]) -> None:
        try:
            self.producer.produce(
                topic,
                key=key.encode(),
                value=json.dumps(payload).encode(),
                headers={"source": b"qsip"},
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error("kafka produce error: %s", e)

    def flush(self, timeout: float = 10.0) -> None:
        self.producer.flush(timeout)

    def close(self) -> None:
        self.producer.flush()


class KafkaConsumer:
    def __init__(self, brokers: str, group_id: str, topics: list[str]):
        self.consumer = Consumer({
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "max.poll.interval.ms": 300000,
        })
        self.consumer.subscribe(topics)
        self.running = True

    def consume(self, handler: Callable[[dict[str, Any]], None]) -> None:
        while self.running:
            msg = self.consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka consumer error: %s", msg.error())
                continue
            try:
                payload = json.loads(msg.value().decode())
                handler(payload)
            except Exception as e:
                logger.exception("message handler failed: %s", e)

    def stop(self) -> None:
        self.running = False
        self.consumer.close()
