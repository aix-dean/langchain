"""JSON-only assistance endpoint: applicant evidence cannot enter shared Qdrant here."""
from fastapi import APIRouter

from app.api.documentation import NDJSONResponse, stream_response
from app.api.streaming import stream_events
from app.features.macea.schemas import AssistanceRequest
from app.features.macea.service import assistance_stream

router = APIRouter(tags=['MACEA services'])


@router.post('/api/macea', summary='Draft and review MACEA application text',
             operation_id='macea_text_assistance',
             response_class=NDJSONResponse,
             responses=stream_response('MACEA text assistance. warning, stage, search and token events precede done; error is terminal.', [
                 {'type': 'stage', 'value': 'macea_sources'},
                 {'type': 'token', 'text': 'Draft for applicant review'},
                 {'type': 'done'},
             ]),
             description='Text-only assistance with explicit task and case facts. Streams NDJSON. '
                         'Does not ingest applicant data, issue approvals, submit applications, or review images.')
def assist(request: AssistanceRequest):
    return stream_events(lambda: assistance_stream(request))
