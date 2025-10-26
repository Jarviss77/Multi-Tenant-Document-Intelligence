# app/workers/workers.py
import asyncio
import signal
import time
from typing import Dict, Any
from app.workers.v2.consumer import KafkaConsumer
from app.workers.v2.tasks import task_processor, process_ingestion_job
from app.utils.logger import get_logger, setup_logging

setup_logging(level='INFO', console=True, file=True)
logger = get_logger("workers.worker")


class HealthMonitor:

    def __init__(self):
        self.start_time = time.time()
        self._last_health_check = self.start_time
        self._is_healthy = True

    async def check_health(self) -> Dict[str, Any]:
        current_time = time.time()
        uptime = current_time - self.start_time

        consumer_stats = getattr(self.consumer, 'get_stats', lambda: {})()
        processor_stats = task_processor.get_stats()

        health_status = {
            "status": "healthy" if self._is_healthy else "unhealthy",
            "uptime_seconds": round(uptime, 2),
            "timestamp": current_time,
            "consumer": consumer_stats,
            "producer": processor_stats
        }

        if processor_stats.get('failed_jobs', 0) > processor_stats.get('processed_jobs', 0) * 0.5:
            # More than 50% failure rate
            self._is_healthy = False
            health_status["status"] = "degraded"
            health_status["issue"] = "High failure rate"

        self._last_health_check = current_time
        return health_status


class IngestionWorker:

    def __init__(self):
        self.consumer = KafkaConsumer(group_id="ingestion_worker_group_v3")
        self.health_monitor = HealthMonitor()
        self.health_monitor.consumer = self.consumer
        self._shutdown_requested = False
        self._health_check_task = None

    async def start_health_monitoring(self):
        while not self._shutdown_requested:
            try:
                health_status = await self.health_monitor.check_health()

                if health_status["status"] != "healthy":
                    logger.warning(f"Worker health status: {health_status}")
                else:
                    logger.debug(f"Worker health check passed: {health_status}")

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)  # Retry sooner on error

    async def handle_shutdown(self, signal_name):
        logger.info(f"Received {signal_name}, shutting down gracefully...")
        self._shutdown_requested = True

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        try:
            final_health = await self.health_monitor.check_health()
            logger.info(f"Final health status: {final_health}")
        except Exception as e:
            logger.error(f"Final health check failed: {e}")

    async def run(self):
        """Main worker entry point"""
        logger.info("Starting Enhanced Kafka Ingestion Worker...")
        logger.info("Initializing components...")

        try:
            # Start all tasks together
            signal_task = asyncio.create_task(self._signal_watcher())
            self._health_check_task = asyncio.create_task(self.start_health_monitoring())

            logger.info("Connecting to Kafka broker...")
            logger.info("Starting message processing loop...")

            await asyncio.gather(
                self.consumer.start(process_ingestion_job),
                signal_task,
                self._health_check_task
            )

        except Exception as e:
            logger.error(f"Worker failed to start or crashed: {e}")
            raise
        finally:
            await self.handle_shutdown("COMPLETION")

    async def _signal_watcher(self):
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _on_signal():
            logger.info("Received termination signal")
            stop_event.set()

        try:
            for sig in [signal.SIGINT, signal.SIGTERM]:
                loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            logger.warning("Signal handlers not supported; using async wait instead")
            asyncio.create_task(self._keyboard_listener(stop_event))

        await stop_event.wait()
        await self.handle_shutdown("SIGNAL")

    async def _keyboard_listener(self, stop_event):
        """Fallback listener for Ctrl+C on macOS/Windows"""
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
            stop_event.set()


async def main():
    worker = IngestionWorker()

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        raise
    finally:
        logger.info("Worker process ended")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        logger.info("Shutdown requested, exiting gracefully")
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal application error: {e}")
        exit(1)

    finally:
        logger.info("Worker process ended")