from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError, KafkaError
from app.core.config import settings
from app.utils.logger import get_logger, log_kafka_message
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = get_logger("workers.v2.queue")

KAFKA_BROKER = settings.KAFKA_BROKER
TOPIC_INGESTION = settings.KAFKA_TOPIC
TOPIC_DLQ = f"{TOPIC_INGESTION}.dlq"  # Dead Letter Queue
TOPIC_RETRY = f"{TOPIC_INGESTION}.retry"  # Retry topic


class KafkaTopicManager:
    """Manages Kafka topics creation and configuration"""

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((KafkaError, ConnectionError))
    )
    async def ensure_topics():
        """Create all required Kafka topics with proper configuration"""
        admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
        try:
            await admin.start()

            topics = [
                NewTopic(
                    name=TOPIC_INGESTION,
                    num_partitions=10,
                    replication_factor=1,
                    topic_configs={
                        "retention.ms": "604800000",  # 7 days
                        "cleanup.policy": "delete"
                    }
                ),
                NewTopic(
                    name=TOPIC_DLQ,
                    num_partitions=3,
                    replication_factor=1,
                    topic_configs={
                        "retention.ms": "2592000000",  # 30 days
                        "cleanup.policy": "compact"
                    }
                ),
                NewTopic(
                    name=TOPIC_RETRY,
                    num_partitions=5,
                    replication_factor=1,
                    topic_configs={
                        "retention.ms": "86400000",  # 1 day
                        "cleanup.policy": "delete"
                    }
                )
            ]

            for topic in topics:
                try:
                    await admin.create_topics([topic])
                    logger.info(f"Created Kafka topic: {topic.name}")
                except TopicAlreadyExistsError:
                    logger.debug(f"Kafka topic already exists: {topic.name}")

        except Exception as e:
            logger.error(f"Error creating Kafka topics: {e}")
            raise
        finally:
            await admin.close()
