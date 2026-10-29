"""HTTP transport for the existing newline-delimited event contract."""
import json
from fastapi.responses import StreamingResponse
from app.core.runtime import generation_lock as check_lock

def event(kind, **data):  # Builds one line of the live progress stream
    return json.dumps({"type": kind, **data}) + "\n"  # One JSON object per line

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

    return StreamingResponse(stream(), media_type="application/x-ndjson")  # Send lines as they are produced
