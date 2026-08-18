from __future__ import annotations

import threading
from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler


class SyncScheduler:
    def __init__(
        self,
        sync_fn: Callable[[str], None],
        intervals: dict[str, int],
        run_once_at_start: bool = True,
    ):
        self.sync_fn = sync_fn
        self.intervals = intervals
        self.run_once_at_start = run_once_at_start
        self._locks: dict[str, threading.Lock] = {
            source: threading.Lock() for source in intervals
        }
        self._scheduler = BlockingScheduler()

    def sync_source(self, source: str) -> None:
        lock = self._locks.get(source)
        if lock is None or not lock.acquire(blocking=False):
            return
        try:
            self.sync_fn(source)
        except Exception as exc:  # noqa: BLE001 - scheduler must stay alive
            print(f"[scheduler] sync for '{source}' failed: {exc}")
        finally:
            lock.release()

    def start(self) -> None:
        for source, interval_minutes in self.intervals.items():
            self._scheduler.add_job(
                self.sync_source,
                trigger="interval",
                minutes=max(1, int(interval_minutes)),
                args=[source],
                id=f"sync-{source}",
                replace_existing=True,
                misfire_grace_time=60,
            )
            if self.run_once_at_start:
                self.sync_source(source)
        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
