import os
import json
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import TopicAlreadyExistsError
from app.core.config import settings
import asyncio
import logging

logger = logging.getLogger("workers.queue")

KAFKA_BROKER = settings.KAFKA_BROKER
TOPIC_INGESTION = settings.KAFKA_TOPIC

def ensure_kafka_topic(topic_name: str, partitions: int = 3):
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
    try:
        topic = NewTopic(name=topic_name, num_partitions=partitions, replication_factor=1)
        admin.create_topics([topic])
        logger.info(f"Created Kafka topic: {topic_name}")
    except TopicAlreadyExistsError:
        logger.info(f"Kafka topic already exists: {topic_name}")
    finally:
        admin.close()


class KafkaProducerService:
    def __init__(self):
        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)

    async def start(self):
        await self.producer.start()

    async def stop(self):
        await self.producer.stop()

    async def publish_job(self, job_data: dict):
        """Send JSON-encoded ingestion job to Kafka."""
        msg = json.dumps(job_data).encode("utf-8")
        await self.producer.send_and_wait(TOPIC_INGESTION, msg)
        logger.info(f"Published job to Kafka: {job_data.get('job_id')}")


class KafkaConsumerService:
    def __init__(self, group_id="ingestion_worker_group"):
        self.consumer = AIOKafkaConsumer(
            TOPIC_INGESTION,
            bootstrap_servers=KAFKA_BROKER,
            group_id=group_id,
            enable_auto_commit=True,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )

    async def start(self, process_func):
        ensure_kafka_topic(TOPIC_INGESTION)
        await self.consumer.start()
        logger.info("Kafka consumer started... listening for ingestion jobs")
        try:
            async for msg in self.consumer:
                try:
                    job_data = msg.value
                    await process_func(job_data)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        finally:
            await self.consumer.stop()
