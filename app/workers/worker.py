import asyncio
from app.workers.queue_config import KafkaConsumerService
from app.workers.tasks import process_ingestion_job
from app.utils.logger import get_logger, setup_logging

setup_logging(level='INFO', console=True, file=True)
logger = get_logger("workers.worker")

async def main():
    logger.info("Starting Kafka ingestion worker...")
    logger.info("Connecting to Kafka broker...")
    consumer = KafkaConsumerService(group_id="ingestion_worker_group_v2")
    logger.info("Kafka consumer initialized, starting message processing...")
    await consumer.start(process_ingestion_job)

if __name__ == "__main__":
    asyncio.run(main())
