import asyncio
import logging
from app.workers.queue_config import KafkaConsumerService
from app.workers.tasks import process_ingestion_job

logger = logging.getLogger("workers.worker")

async def main():
    logger.info("🚀 Starting Kafka ingestion worker...")
    consumer = KafkaConsumerService(group_id="ingestion_worker_group")
    await consumer.start(process_ingestion_job)

if __name__ == "__main__":
    asyncio.run(main())
