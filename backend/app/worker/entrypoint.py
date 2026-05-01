"""marketer-worker のエントリポイント。

PM2 で `python -m app.worker.entrypoint` として常駐起動する。
APScheduler の AsyncIOScheduler を回し続け、cron トリガーでジョブを発火する。
"""

import asyncio
import contextlib
import signal

from app.scheduler.scheduler import build_scheduler
from app.utils.logger import configure_logging, get_logger


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)

    scheduler = build_scheduler()
    scheduler.start()
    log.info("worker_started", jobs=[j.id for j in scheduler.get_jobs()])

    stop_event = asyncio.Event()

    def _shutdown(*_args) -> None:
        log.info("worker_shutdown_signal")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _shutdown)

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
