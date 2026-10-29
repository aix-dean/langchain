"""Bounded AI admission for one backend worker; keep Uvicorn at one worker."""
import threading
from app.core.config import MAX_CONCURRENT_AI, MAX_QUEUED_AI, AI_QUEUE_TIMEOUT_SECONDS


class GenerationLimiter:
    def __init__(self, capacity, max_queued=16, queue_timeout=120):
        if capacity < 1 or max_queued < 0 or queue_timeout <= 0:
            raise ValueError("Invalid AI concurrency or queue settings")
        self.capacity = capacity
        self.max_queued = max_queued
        self.queue_timeout = queue_timeout
        self._condition = threading.Condition()
        self._active = 0
        self._queued = 0

    def acquire(self, blocking=True):
        with self._condition:
            if self._active >= self.capacity:
                if not blocking:
                    return False
                if self._queued >= self.max_queued:
                    raise RuntimeError("AI queue is full. Please retry shortly.")
                self._queued += 1
                try:
                    if not self._condition.wait_for(
                        lambda: self._active < self.capacity, self.queue_timeout
                    ):
                        raise TimeoutError("AI queue wait timed out. Please retry.")
                finally:
                    self._queued -= 1
            self._active += 1
            return True

    def release(self):
        with self._condition:
            if not self._active:
                raise RuntimeError("No active AI job to release")
            self._active -= 1
            self._condition.notify()

    def snapshot(self):
        with self._condition:
            return {"active_jobs": self._active, "queued_jobs": self._queued,
                    "max_concurrent_jobs": self.capacity}

    def locked(self):
        return self.snapshot()["active_jobs"] > 0

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


# Retained name for existing warm-up and stream callers.
generation_lock = GenerationLimiter(MAX_CONCURRENT_AI, MAX_QUEUED_AI, AI_QUEUE_TIMEOUT_SECONDS)
