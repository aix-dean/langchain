"""Process-wide coordination for a single backend worker."""
import threading

generation_lock = threading.Lock()
