"""HTTP transport for the existing newline-delimited event contract."""
import json
from fastapi.responses import StreamingResponse
from app.core.runtime import generation_lock as check_lock

def event(kind, **data):  # Builds one line of the live progress stream
    return json.dumps({"type": kind, **data}) + "\n"  # One JSON object per line

def stream_events(make_events):  # Runs a check or chat answer (one at a time) and sends its events as lines of JSON
    def stream():  # Produces the live progress
        if not check_lock.acquire(blocking=False):  # Another check or answer is running
            yield event("queued")  # Tell the page it has to wait
            check_lock.acquire()  # Wait for our turn
        try:  # Always release the lock, even if something fails
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
            check_lock.release()  # Let the next one run

    return StreamingResponse(stream(), media_type="application/x-ndjson")  # Send lines as they are produced
