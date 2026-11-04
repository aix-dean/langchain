"""HTTP transport for the existing newline-delimited event contract."""
import json
import anyio
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from app.core.runtime import generation_slots
from app.core.runtime import generation_lock as check_lock


def stream_events(make_events):  # Runs a check or chat answer within the configured concurrency limit and sends its events as lines of JSON
    def stream():
        acquired = False
        try:
            acquired = check_lock.acquire(blocking=False)
            if not acquired:
                yield event("queued")
                acquired = check_lock.acquire()
            for kind, payload in make_events():  # Each event
                if isinstance(payload, dict):  # "search" and "result" are already dictionaries
                    yield event(kind, **payload)  # Send their fields
                elif kind in ("stage", "tokens"):  # Simple values
                    yield event(kind, value=payload)  # Send the value
                else:  # Text: description, thinking, answer text, warning
                    yield event(kind, text=payload)  # Send the text
            yield event("done")  # Finished
        except Exception as e:  # Something went wrong (e.g. Ollama or Qdrant not running)
            yield event("error", message=str(e))  # Show the error on the page
        finally:  # Whatever happened
            if acquired:
                check_lock.release()  # Always return an acquired slot.
def event(kind, **data):
    return json.dumps({"type": kind, **data}) + "\n"


def stream_events(make_events):
    async def stream():
        acquired = False
        events = None
        try:
            acquired = generation_slots.acquire(blocking=False)
            if not acquired:
                yield event("queued")
                while not acquired:
                    await anyio.sleep(0.05)
                    acquired = generation_slots.acquire(blocking=False)
            events = iter(make_events())
            async for kind, payload in iterate_in_threadpool(events):
                if isinstance(payload, dict):
                    yield event(kind, **payload)
                elif kind in ("stage", "tokens"):
                    yield event(kind, value=payload)
                else:
                    yield event(kind, text=payload)
            yield event("done")
        except Exception as exc:
            yield event("error", message=str(exc))
        finally:
            try:
                if events is not None and hasattr(events, "close"):
                    events.close()
            finally:
                if acquired:
                    generation_slots.release()

    return StreamingResponse(stream(), media_type="application/x-ndjson")
