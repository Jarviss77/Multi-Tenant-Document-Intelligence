import json
import asyncio
from typing import Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from app.utils.logger import get_logger, log_kafka_message
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings

logger = get_logger("producer.v2.queue")

KAFKA_BROKER = settings.KAFKA_BROKER
TOPIC_INGESTION = settings.KAFKA_TOPIC
TOPIC_DLQ = f"{TOPIC_INGESTION}.dlq"  # Dead Letter Queue
TOPIC_RETRY = f"{TOPIC_INGESTION}.retry"  # Retry topic

class KafkaProducer:

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self._is_connected = False

    async def start(self):
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                enable_idempotence=True,  # Prevent duplicate messages
                acks='all',  # Wait for all replicas
                retries=5,  # Retry on transient errors
                max_in_flight_requests_per_connection=1,  # Maintain ordering
                compression_type='gzip'  # Compress messages
            )
            await self.producer.start()
            self._is_connected = True
            logger.info("Kafka producer started successfully")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise

    async def stop(self):
        if self.producer and self._is_connected:
            await self.producer.stop()
            self._is_connected = False
            logger.info("Kafka producer stopped")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((KafkaError, ConnectionError))
    )
    async def publish_job(self, job_data: dict, topic: str = TOPIC_INGESTION):
        if not self._is_connected or not self.producer:
            raise RuntimeError("Kafka producer is not connected")

        job_id = job_data.get('job_id', 'unknown')

        try:
            # Add metadata to job data
            enhanced_job_data = {
                **job_data,
                "_metadata": {
                    "published_at": asyncio.get_event_loop().time(),
                    "producer_id": "embedding_worker",
                    "attempt": 1  # First attempt
                }
            }

            msg = json.dumps(enhanced_job_data).encode("utf-8")

            # Send and wait for confirmation
            future = await self.producer.send_and_wait(topic, msg)

            log_kafka_message(logger, "PUBLISH", topic, job_id)
            logger.info(
                f"Published job to {topic}: {job_id} (partition: {future.partition}, offset: {future.offset})")

            return future

        except KafkaError as e:
            logger.error(f"Kafka error publishing job {job_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing job {job_id}: {e}")
            raise

    async def send_to_dlq(self, job_data: dict, error: str):
        dlq_data = {
            **job_data,
            "dlq_reason": error,
            "dlq_timestamp": asyncio.get_event_loop().time(),
            "_metadata": {
                **job_data.get("_metadata", {}),
                "dlq": True
            }
        }

        try:
            await self.publish_job(dlq_data, TOPIC_DLQ)
            logger.warning(f"📨 Sent job {job_data.get('job_id')} to DLQ: {error}")
        except Exception as e:
            logger.error(f"💥 Failed to send job to DLQ: {e}")

KafkaProducerService = KafkaProducer