import json
import asyncio
import time
from typing import Optional, Dict, Any
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.core.config import settings
from app.utils.logger import get_logger
from app.workers.v2.kafka_config import KafkaTopicManager
from app.utils.metrics import (
    kafka_messages_consumed,
    kafka_messages_processed,
    kafka_messages_failed,
    kafka_message_processing_duration,
    kafka_messages_in_flight,
    kafka_messages_produced
)

logger = get_logger("workers.v2.queue")

KAFKA_BROKER = settings.KAFKA_BROKER
TOPIC_INGESTION = settings.KAFKA_TOPIC
TOPIC_DLQ = f"{TOPIC_INGESTION}.dlq"  # Dead Letter Queue
TOPIC_RETRY = f"{TOPIC_INGESTION}.retry"  # Retry topic

class KafkaConsumer:

    def __init__(self, group_id: str = "ingestion_worker_group", topics: list = None):
        self.group_id = group_id
        self.topics = topics or [TOPIC_INGESTION]
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._is_running = False
        self._processed_messages = 0
        self._failed_messages = 0

        # Consumer configuration
        self.consumer_config = {
            "bootstrap_servers": KAFKA_BROKER,
            "group_id": self.group_id,
            "enable_auto_commit": False,  # Manual commit for better control
            "auto_offset_reset": "earliest",
            "max_poll_records": 50,  # Process in batches
            "session_timeout_ms": 30000,
            "heartbeat_interval_ms": 10000,
            "max_poll_interval_ms": 300000,
            "value_deserializer": self._deserialize_message
        }

    def _deserialize_message(self, value: bytes) -> Dict[str, Any]:
        """Deserialize Kafka message without raising on validation errors.

        Returns the parsed dict. If validation fails, returns a dict with `_invalid` set
        and `validation_error` describing the problem so the consumer loop can handle it
        and forward the message to DLQ instead of crashing.
        """
        try:
            decoded = value.decode("utf-8")
            data = json.loads(decoded)

            # Validate required fields but do not raise — mark invalid instead
            required_fields = ['job_id', 'tenant_id', 'chunk_id', 'chunk_content']
            missing = [f for f in required_fields if f not in data]
            if missing:
                err = f"Missing required field(s): {', '.join(missing)}"
                logger.error(f"Message validation failed: {err}")
                # Attach diagnostic info so caller can send to DLQ
                return {
                    **data,
                    "_invalid": True,
                    "validation_error": err,
                    "_raw": decoded,
                }

            return data

        except json.JSONDecodeError as e:
            decoded = None
            try:
                decoded = value.decode("utf-8", errors="replace")
            except Exception:
                decoded = None
            logger.error(f"Failed to decode JSON message: {e}")
            return {
                "_invalid": True,
                "validation_error": f"JSONDecodeError: {e}",
                "_raw": decoded,
            }
        except Exception as e:
            # Generic safety: do not let any exception escape deserializer
            decoded = None
            try:
                decoded = value.decode("utf-8", errors="replace")
            except Exception:
                decoded = None
            logger.error(f"Unexpected error deserializing message: {e}")
            return {
                "_invalid": True,
                "validation_error": str(e),
                "_raw": decoded,
            }

    async def start(self, process_func):
        """Start consuming messages with enhanced error handling"""
        await KafkaTopicManager.ensure_topics()

        self.consumer = AIOKafkaConsumer(*self.topics, **self.consumer_config)

        try:
            await self.consumer.start()
            self._is_running = True
            logger.info(f"Kafka consumer started (group: {self.group_id}, topics: {self.topics})")

            async for msg in self.consumer:
                if not self._is_running:
                    break

                # Track consumed message
                kafka_messages_consumed.labels(consumer_group=self.group_id, topic=msg.topic).inc()
                
                await self._process_message_with_retry(msg, process_func)

        except Exception as e:
            logger.error(f"Consumer loop failed: {e}")
            raise
        finally:
            await self._safe_stop()

    async def _process_message_with_retry(self, msg, process_func):
        job_id = msg.value.get('job_id', 'unknown')

        try:
            # If message was marked invalid by deserializer, send to DLQ and skip processing
            if msg.value.get('_invalid'):
                validation_error = msg.value.get('validation_error')
                logger.warning(f"Invalid message for job {job_id}: {validation_error} - sending to DLQ")
                dlq_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
                try:
                    await dlq_producer.start()
                    dlq_payload = {
                        **{k: v for k, v in msg.value.items() if k != '_raw'},
                        'dlq_reason': validation_error or 'invalid_message',
                        'dlq_timestamp': asyncio.get_event_loop().time(),
                    }
                    # Include raw payload separately if present
                    if '_raw' in msg.value:
                        dlq_payload['_raw'] = msg.value['_raw']

                    await dlq_producer.send_and_wait(TOPIC_DLQ, json.dumps(dlq_payload).encode())
                    logger.info(f"Sent invalid job {job_id} to DLQ")
                except Exception as e:
                    logger.error(f"Failed to publish invalid message {job_id} to DLQ: {e}")
                finally:
                    await dlq_producer.stop()

                # Count as failed and commit offset so we don't re-process
                self._failed_messages += 1
                kafka_messages_failed.labels(consumer_group=self.group_id, topic=msg.topic, error_type='validation').inc()
                await self.consumer.commit()
                return

            # Process the message
            start_time = time.time()
            
            # Increment in-flight gauge
            kafka_messages_in_flight.labels(consumer_group=self.group_id, topic=msg.topic).inc()
            
            try:
                await process_func(msg.value)
                self._processed_messages += 1
                
                # Record success metrics
                kafka_messages_processed.labels(consumer_group=self.group_id, topic=msg.topic).inc()
            except Exception as e:
                self._failed_messages += 1
                kafka_messages_failed.labels(consumer_group=self.group_id, topic=msg.topic, error_type=type(e).__name__).inc()
                raise
            finally:
                # Record duration and decrement in-flight
                duration = time.time() - start_time
                kafka_message_processing_duration.labels(consumer_group=self.group_id, topic=msg.topic).observe(duration)
                kafka_messages_in_flight.labels(consumer_group=self.group_id, topic=msg.topic).dec()

            # Commit offset only after successful processing
            await self.consumer.commit()

            logger.debug(f"Successfully processed job: {job_id}")

        except Exception as e:
            self._failed_messages += 1
            await self._handle_processing_error(msg, e, process_func)

    async def _handle_processing_error(self, msg, error, process_func):
        """Handle message processing errors with retry logic"""
        job_id = msg.value.get('job_id', 'unknown')
        attempt = msg.value.get('_metadata', {}).get('attempt', 1)

        logger.error(f"Failed to process job {job_id} (attempt {attempt}): {error}")

        if attempt <= 3:  # Max 3 retries
            # Increment attempt and republish to retry topic
            retry_data = {
                **msg.value,
                "_metadata": {
                    **msg.value.get('_metadata', {}),
                    "attempt": attempt + 1,
                    "last_error": str(error),
                    "retry_timestamp": asyncio.get_event_loop().time()
                }
            }

            # Use a simple producer for retry (avoid circular import)
            retry_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
            try:
                await retry_producer.start()
                await retry_producer.send_and_wait(TOPIC_RETRY, json.dumps(retry_data).encode())
                logger.info(f"Sent job {job_id} to retry topic (attempt {attempt + 1})")
            finally:
                await retry_producer.stop()

            # Commit offset since we've handled the error
            await self.consumer.commit()

        else:
            # Max retries exceeded, send to DLQ
            logger.error(f"Max retries exceeded for job {job_id}, sending to DLQ")

            dlq_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
            try:
                await dlq_producer.start()

                dlq_data = {
                    **msg.value,
                    "dlq_reason": f"Max retries exceeded: {error}",
                    "dlq_timestamp": asyncio.get_event_loop().time()
                }

                await dlq_producer.send_and_wait(TOPIC_DLQ, json.dumps(dlq_data).encode())
                logger.warning(f"Sent job {job_id} to DLQ after {attempt} failed attempts")
            finally:
                await dlq_producer.stop()

            # Commit offset since we've handled the error
            await self.consumer.commit()

    async def _safe_stop(self):
        if self.consumer:
            await self.consumer.stop()
            self._is_running = False

            total_messages = self._processed_messages + self._failed_messages
            if total_messages > 0:
                success_rate = (self._processed_messages / total_messages) * 100
                logger.info(f"Consumer stopped. Processed: {self._processed_messages}, "
                            f"Failed: {self._failed_messages}, Success rate: {success_rate:.1f}%")

    def get_stats(self) -> Dict[str, int]:
        return {
            "processed_messages": self._processed_messages,
            "failed_messages": self._failed_messages,
            "total_messages": self._processed_messages + self._failed_messages
        }

KafkaConsumerService = KafkaConsumer