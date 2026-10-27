"""OpenAPI descriptions and shared response metadata; no workflow behavior."""
import json
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

API_DESCRIPTION = """Local API for Aida's ASC and MACEA guidelines assistant.

### Using this API
- Chat, image checks, document uploads and reports accept **multipart/form-data**.
- `history` and report `data` are **JSON encoded strings inside form fields**.
- Chat, image checks and uploads return **application/x-ndjson**: one JSON object
  per line. This is a stream, not a JSON array or Server-Sent Events.
- Chat/check success ends with `done`; a processing `error` ends the stream.
  Uploads end with `done`, `duplicate` (confirmation required), or `error`.
- Validation failures use an HTTP error status before streaming starts.
  A processing failure after streaming starts remains HTTP 200 with an `error` event.
- Swagger's **Try it out** can call the local API. It may display streaming results
  only after completion. Use a streaming HTTP client for incremental progress.

### Services and processing
Ollama provides generation and embeddings; Qdrant stores the guideline passages.
Generation is serialized within this backend process. Document ingestion has its
own process-local lock. An image check can take several minutes. Closing a browser
request does not guarantee that generation or document ingestion stops.

### Review outcomes
Image results are `COMPLIANT`, `NON-COMPLIANT`, `NEEDS_REVIEW`, or `ERROR`.
The result is a pre-screen and requires human review.

The Swagger UI assets are served locally. The OpenAPI schema is available at
`/openapi.json`. These docs describe the existing API and add no authentication.
"""

TAGS = [
    {"name": "status", "description": "Readiness of Ollama, installed models, Qdrant and the ASC collection."},
    {"name": "chat", "description": "Guideline questions, follow-ups and optional ASC ad-image checks."},
    {"name": "ad-review", "description": "Standalone ASC image pre-screen with progress and evidence verification."},
    {"name": "documents", "description": "Upload and explicitly replace searchable MACEA guideline documents."},
    {"name": "reports", "description": "Generate a PDF containing an image result and a human review decision."},
]

SWAGGER_PARAMETERS = {"displayRequestDuration": True, "persistAuthorization": False, "defaultModelsExpandDepth": 0, "tryItOutEnabled": False, "validatorUrl": None}


class NDJSONResponse(StreamingResponse):
    media_type = "application/x-ndjson"


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable request validation error.")


def error_response(description):
    return {"model": ErrorResponse, "description": description}


def stream_response(description, events):
    return {200: {"description": description, "content": {
        "application/x-ndjson": {"schema": {"type": "string"},
        "example": "\n".join(json.dumps(event) for event in events) + "\n"}
    }}}


CHAT_RESPONSES = {
    **stream_response("Streaming events. Types include queued, stage, describe, token, thinking, search, tokens, warning, result, done and error. Image result fields are flattened into the result event.", [
        {"type": "token", "text": "Hi! I can help with ASC and MACEA guidelines."},
        {"type": "done"},
    ]),
    400: error_response("No message or image, unsupported image type, or oversized image."),
    409: error_response("The supplied conversation exceeds the configured chat memory limit."),
}

CHECK_RESPONSES = {
    **stream_response("Image stages: describe, judge, verify. Searches contain query/result fields; thinking and describe events contain text. A result event includes the verdict, findings, observations, timings and total seconds. An error event is terminal.", [
        {"type": "stage", "value": "describe"},
        {"type": "describe", "text": "1. ALL TEXT: Unreadable fine print"},
        {"type": "stage", "value": "judge"},
        {"type": "search", "query": "ASC: general standards", "result": "Retrieved ASC passage", "authority": "ASC"},
        {"type": "stage", "value": "verify"},
        {"type": "result", "result": "NEEDS_REVIEW", "message": "Fine print could not be read.", "reasons": [], "checks_passed": [], "seconds": 42},
        {"type": "done"},
    ]),
    400: error_response("Unsupported image type or image exceeds MAX_IMAGE_MB."),
}

DOCUMENT_RESPONSES = {
    **stream_response("Upload events: stage (message), progress (stage/completed/total), duplicate (filename/passages/message), done (filename/passages/replaced), or error (message). On duplicate, send the same file with replace=true only after explicit confirmation.", [
        {"type": "stage", "message": "Validating document"},
        {"type": "progress", "stage": "embedding", "completed": 1, "total": 1},
        {"type": "done", "filename": "guidelines.txt", "passages": 1, "replaced": False},
    ]),
    400: error_response("Invalid filename, unsupported format, empty upload, or upload exceeds MAX_DOCUMENT_MB. Extraction/storage failures after streaming starts are error events."),
}

REPORT_DATA_EXAMPLE = '{"result":{"result":"NEEDS_REVIEW","message":"Fine print is unreadable.","reasons":[],"checks_passed":[]},"decision":"Revise","notes":"Supply a clearer image.","file_name":"ad.png"}'
REPORT_RESPONSES = {
    200: {"description": "Downloadable PDF report.", "headers": {"Content-Disposition": {"description": "attachment; filename=ASC-prescreen-<image>-<date>.pdf", "schema": {"type": "string"}}}, "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
    400: error_response("The data field is not valid JSON."),
}
