"""HTTP transport for the existing newline-delimited event contract."""
import json
import anyio
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from app.core.runtime import generation_slots


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
