import asyncio
import json
import threading
import unittest
from unittest.mock import patch
from app.core.runtime import GenerationLimiter
from app.api.streaming import stream_events


class ConcurrencyTests(unittest.TestCase):
    def test_two_jobs_overlap_and_third_waits_for_capacity(self):
        limiter = GenerationLimiter(2)
        started = threading.Barrier(3)
        finish = threading.Event()
        errors = []
        def job():
            try:
                with limiter:
                    started.wait(timeout=3)
                    if not finish.wait(3):
                        raise RuntimeError("Test job did not finish")
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=job) for _ in range(2)]
        for thread in threads:
            thread.start()
        try:
            started.wait(timeout=3)
            self.assertEqual(limiter.snapshot()["active_jobs"], 2)
            self.assertFalse(limiter.acquire(blocking=False))
        finally:
            finish.set()
            for thread in threads:
                thread.join(4)
        self.assertFalse(errors)
        self.assertEqual(limiter.snapshot()["active_jobs"], 0)

    def test_waiting_job_runs_after_slot_released(self):
        limiter = GenerationLimiter(1)
        limiter.acquire()
        entered = threading.Event()
        def waiter():
            with limiter:
                entered.set()
        thread = threading.Thread(target=waiter)
        thread.start()
        limiter.release()
        thread.join(3)
        self.assertTrue(entered.is_set())
        self.assertEqual(limiter.snapshot()["queued_jobs"], 0)
        self.assertFalse(limiter.locked())

    def test_queue_timeout_cleans_up_without_releasing_active_job(self):
        limiter = GenerationLimiter(1, queue_timeout=0.01)
        with limiter:
            with self.assertRaises(TimeoutError):
                limiter.acquire()
            self.assertEqual(limiter.snapshot()["active_jobs"], 1)
            self.assertEqual(limiter.snapshot()["queued_jobs"], 0)

    def test_full_queue_rejects_without_leaking_capacity(self):
        limiter = GenerationLimiter(1, max_queued=0)
        with limiter:
            with self.assertRaisesRegex(RuntimeError, "queue is full"):
                limiter.acquire()
        self.assertFalse(limiter.locked())

    def test_stream_failure_releases_slot(self):
        limiter = GenerationLimiter(2)
        def failing():
            yield "token", "partial"
            raise RuntimeError("model failed")
        async def read():
            response = stream_events(failing)
            return [json.loads(line) async for line in response.body_iterator]
        with patch("app.api.streaming.check_lock", limiter):
            events = asyncio.run(read())
        self.assertEqual(events[-1]["type"], "error")
        self.assertFalse(limiter.locked())

    def test_queue_failure_is_reported_without_releasing_another_job(self):
        limiter = GenerationLimiter(1, max_queued=0)
        async def read():
            response = stream_events(lambda: iter([]))
            return [json.loads(line) async for line in response.body_iterator]
        with limiter, patch("app.api.streaming.check_lock", limiter):
            events = asyncio.run(read())
            self.assertEqual([event["type"] for event in events], ["queued", "error"])
            self.assertEqual(limiter.snapshot()["active_jobs"], 1)

    def test_invalid_settings_fail_at_startup(self):
        for settings in ((0, 16, 120), (2, -1, 120), (2, 16, 0)):
            with self.assertRaises(ValueError):
                GenerationLimiter(*settings)
