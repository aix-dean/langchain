import json
import queue
import threading
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from app.api.streaming import event
from app.features.documents.service import UPLOAD_COLLECTION, ingest_document, read_upload, source_name

router = APIRouter(tags=["documents"])

@router.post("/api/documents")
def upload_document(file: UploadFile = File(...), replace: bool = Form(False)):
    try:
        name = source_name(file.filename)
        data = read_upload(file.file)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        file.file.close()
    events = queue.SimpleQueue()
    def work():
        try:
            for item in ingest_document(data, name, replace, collection=UPLOAD_COLLECTION):
                events.put(item)
        except Exception as exc:
            events.put({'type': 'error', 'message': str(exc)})
        finally:
            events.put(None)
    threading.Thread(target=work, daemon=True).start()
    def stream():
        yield event('stage', message='Waiting for ingestion')
        while True:
            item = events.get()
            if item is None:
                return
            yield json.dumps(item) + '\n'
    return StreamingResponse(stream(), media_type='application/x-ndjson')
