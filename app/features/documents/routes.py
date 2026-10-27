import json
import queue
import threading
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from app.api.streaming import event
from app.api.documentation import NDJSONResponse, DOCUMENT_RESPONSES
from app.features.documents.service import UPLOAD_COLLECTION, ingest_document, read_upload, source_name

router = APIRouter(tags=["documents"])

@router.post(
    "/api/documents", summary="Upload searchable MACEA guidelines", operation_id="upload_guidelines",
    description="Extract, embed and store passages in macea_guidelines. Accepts PDF, UTF-8 TXT/MD, DOCX and XLSX; default maximum 20 MB. Scanned PDFs need external OCR. Excel uses cached values and does not execute formulas. Original files are not retained. An existing basename produces duplicate; resubmit with replace=true only after confirmation. Closing the request does not cancel ingestion. Replacement is not an atomic Qdrant transaction.",
    response_class=NDJSONResponse, responses=DOCUMENT_RESPONSES,
)
def upload_document(file: UploadFile = File(..., description="One PDF, TXT, MD, DOCX or XLSX document; maximum MAX_DOCUMENT_MB."), replace: bool = Form(False, description="Explicitly replace passages belonging to the same basename. Leave false until replacement is confirmed.")):
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
