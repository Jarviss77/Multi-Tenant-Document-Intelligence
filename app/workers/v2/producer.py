import json
import base64
from typing import Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum

from aiokafka import AIOKafkaProducer
from app.core.config import settings
from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger("producer.v2.queue")

KAFKA_TOPIC = settings.KAFKA_TOPIC
KAFKA_BROKER = settings.KAFKA_BROKER

def _to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (bytes, bytearray, memoryview)):
        buf = obj if isinstance(obj, (bytes, bytearray)) else obj.tobytes()
        return base64.b64encode(bytes(buf)).decode("ascii")
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    return str(obj)

class KafkaProducerService:
    def __init__(self) -> None:
        self.producer: AIOKafkaProducer | None = None
        self.bootstrap_servers = (
            KAFKA_BROKER
        )
        self.topic = KAFKA_TOPIC

    async def start(self) -> None:
        if self.producer:
            return
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                acks="all",
                linger_ms=5,
                retry_backoff_ms=200,
                request_timeout_ms=30000,
                value_serializer=lambda v: json.dumps(
                    _to_jsonable(v), ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8"),
                key_serializer=lambda k: (
                    k.encode("utf-8") if isinstance(k, str) else k
                ),
            )
            await self.producer.start()
            logger.info("Kafka producer started")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            self.producer = None
            raise

    async def publish_job(self, payload: dict, key: str | None = None) -> None:
        if not self.producer:
            raise RuntimeError("Kafka producer not started")
        try:
            await self.producer.send_and_wait(self.topic, value=payload, key=key)
        except Exception as e:
            logger.error(f"Unexpected error publishing job {payload.get('job_id')}: {e}")
            raise

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()
            self.producer = None
            logger.info("Kafka producer stopped")
