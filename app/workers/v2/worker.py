"""Worker with Prometheus metrics support"""
import asyncio
from app.utils.logger import get_logger, setup_logging
from app.utils.metrics import start_metrics_server
from app.workers.v2.consumer import KafkaConsumer
from app.workers.v2.tasks import process_ingestion_job

setup_logging(level='INFO', console=True, file=True)
logger = get_logger("workers.v2.worker")

async def main():
    # Start Prometheus metrics server
    try:
        start_metrics_server(port=8001)
        logger.info("Prometheus metrics server started on port 8001")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
    
    logger.info("Starting Kafka ingestion worker (v2)...")
    logger.info("Connecting to Kafka broker...")
    
    consumer = KafkaConsumer(group_id="ingestion_worker_group_v2")
    logger.info("Kafka consumer initialized, starting message processing...")
    
    await consumer.start(process_ingestion_job)

if __name__ == "__main__":
    asyncio.run(main())
