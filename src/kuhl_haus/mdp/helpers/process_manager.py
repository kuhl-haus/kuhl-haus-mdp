from multiprocessing import Process, Queue
from queue import Empty, Full
from multiprocessing.synchronize import Event as MPEvent
from typing import Dict, Type, Any
import signal
import asyncio
import logging

logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages worker processes for MDP components"""

    def __init__(self):
        self.processes: Dict[str, Process] = {}
        self.shutdown_events: Dict[str, MPEvent] = {}
        self.status_queues: Dict[str, Queue] = {}

    def start_worker(self, name: str, worker_class: Type, **kwargs):
        """Start any worker class in a separate process"""
        import multiprocessing as mp  # Keep factory import local

        shutdown_event = mp.Event()  # Factory call
        status_queue = mp.Queue(maxsize=1)

        process = Process(
            target=self._run_worker,
            args=(worker_class, shutdown_event, status_queue),
            kwargs=kwargs,
            name=name,
            daemon=False
        )

        self.processes[name] = process
        self.shutdown_events[name] = shutdown_event
        self.status_queues[name] = status_queue

        process.start()
        logger.info(f"Started process: {name} (PID: {process.pid})")

    @staticmethod
    def _run_worker(
        worker_class: Type[Any],
        shutdown_event: MPEvent,
        status_queue: Queue,
        **kwargs: Any
    ) -> None:
        """Generic worker process entry point with async event loop management"""

        # Signal handlers for graceful shutdown
        def shutdown_handler(signum, frame):
            shutdown_event.set()

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        # Create new event loop for this process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create asyncio event for coordinating shutdown
        async_shutdown = asyncio.Event()

        async def monitor_shutdown():
            """Monitor multiprocessing shutdown_event and set async event"""
            while not shutdown_event.is_set():
                await asyncio.sleep(0.1)  # Poll frequently without blocking
            async_shutdown.set()
            logger.info(f"Shutdown signal detected for {worker_class.__name__}")

        async def status_reporter(worker_instance):
            """Periodically report worker status to parent process"""
            while not async_shutdown.is_set():
                try:
                    status = {
                        "processed": getattr(worker_instance, 'processed', 0),
                        "errors": getattr(worker_instance, 'errors', getattr(worker_instance, 'error', 0)),
                        "decoding_errors": getattr(worker_instance, 'decoding_errors', 0),
                        "dropped": getattr(worker_instance, 'dropped', 0),
                        "duplicated": getattr(worker_instance, 'duplicated', 0),
                        "mdq_connected": getattr(worker_instance, 'mdq_connected', False),
                        "mdc_connected": getattr(worker_instance, 'mdc_connected', False),
                        "restarts": getattr(worker_instance, 'restarts', 0),
                        "running": getattr(worker_instance, 'running', False),
                    }

                    try:
                        status_queue.put_nowait(status)
                    except Full:
                        pass  # Queue full, skip this update
                except Exception as ex:
                    logger.error(f"Error updating status for {worker_class.__name__}: {ex}")

                # Wait 1 second before next status update
                try:
                    await asyncio.wait_for(async_shutdown.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass  # Expected - just continue loop

        async def run_worker():
            """Main worker coroutine that manages worker lifecycle"""
            worker = None

            try:
                # Instantiate worker
                worker = worker_class(**kwargs)
                logger.info(f"Instantiated {worker_class.__name__}")

                # Start monitoring and status tasks
                monitor_task = asyncio.create_task(monitor_shutdown())
                status_task = asyncio.create_task(status_reporter(worker))

                # Start the worker (may block indefinitely or return immediately)
                logger.info(f"Starting {worker_class.__name__}")
                worker_task = asyncio.create_task(worker.start())

                # Wait for shutdown signal while worker and status tasks run
                await async_shutdown.wait()

                logger.info(f"Shutdown initiated for {worker_class.__name__}")

                # Signal worker to stop if it has a running flag
                if hasattr(worker, 'running'):
                    worker.running = False
                    logger.debug(f"Set running=False for {worker_class.__name__}")

                # Cancel worker task if it's still running
                if not worker_task.done():
                    logger.info(f"Cancelling worker task for {worker_class.__name__}")
                    worker_task.cancel()
                    try:
                        await asyncio.wait_for(worker_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.warning(f"Worker task cancellation timeout for {worker_class.__name__}")
                    except Exception as ex:
                        logger.error(f"Error during worker task cancellation: {ex}")

                # Call worker's stop method for cleanup
                logger.info(f"Calling stop() for {worker_class.__name__}")
                await worker.stop()

                # Cancel monitoring tasks
                monitor_task.cancel()
                status_task.cancel()

                # Wait for cleanup with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(monitor_task, status_task, return_exceptions=True),
                        timeout=2.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Monitoring task cleanup timeout for {worker_class.__name__}")

                logger.info(f"Worker {worker_class.__name__} stopped cleanly")

            except Exception as ex:
                logger.error(f"Worker error in {worker_class.__name__}: {ex}", exc_info=True)
            finally:
                # Ensure stop is called even if errors occurred
                if worker is not None:
                    try:
                        await worker.stop()
                    except Exception as ex:
                        logger.error(f"Error during final stop() call: {ex}", exc_info=True)

        # Run the worker coroutine
        try:
            loop.run_until_complete(run_worker())
        except Exception as e:
            logger.error(f"Fatal error in worker process {worker_class.__name__}: {e}", exc_info=True)
        finally:
            try:
                # Cancel any remaining tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # Give tasks a chance to clean up
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.error(f"Error during event loop cleanup: {e}")
            finally:
                loop.close()

    def stop_process(self, name: str, timeout: float = 10.0):
        """Stop a specific worker process"""
        if name not in self.processes:
            return

        process = self.processes[name]
        shutdown_event = self.shutdown_events[name]

        logger.info(f"Stopping process: {name}")
        shutdown_event.set()

        process.join(timeout=timeout)
        if process.is_alive():
            logger.warning(f"Force killing process: {name}")
            process.kill()
            process.join()

    def stop_all(self, timeout: float = 10.0):
        """Stop all worker processes"""
        for name in list(self.processes.keys()):
            self.stop_process(name, timeout)

    def get_status(self, name: str) -> dict:
        """Get status from worker process (non-blocking)"""
        if name not in self.processes:
            return {"alive": False}

        process = self.processes[name]
        status_queue = self.status_queues[name]

        status = {"alive": process.is_alive(), "pid": process.pid}

        try:
            worker_status = status_queue.get_nowait()
            status.update(worker_status)
        except Empty:
            pass
        except Exception as e:
            logger.error(f"Error getting status for process name {name}: {e}", exc_info=True)

        return status
