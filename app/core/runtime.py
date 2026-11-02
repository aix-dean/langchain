"""Process-wide coordination for a single backend worker."""
import threading
from app.core.config import MAX_CONCURRENT_REQUESTS

generation_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)


def generation_busy():
    """Whether all processing slots are currently occupied."""
    if generation_slots.acquire(blocking=False):
        generation_slots.release()
        return False
    return True
