"""Source-grounded MACEA assistance; no ingestion, submission or file persistence."""
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import CHAT_REASONING, JUDGE_NUM_CTX, read_prompt
from app.features.guidelines.service import GuidelineSourceUnavailable, retrieve_guidelines
from app.features.macea.schemas import AssistanceRequest
from app.infrastructure.ollama.models import get_judge

TOPICS = {
    'unsure': 'application services work scope required documents',
    'signage': 'signage installation replacement repair cleaning requirements',
    'renovation': 'interior fit-out renovation alteration requirements',
    'exterior_works': 'facade repainting waterproofing repair cleaning requirements',
    'work_at_height': 'work at heights safety officer equipment documentation',
    'sidewalk_scaffolding': 'sidewalk scaffolding work affected area requirements',
    'vehicle': 'vehicle passage stationing request requirements',
    'road_closure': 'road closure lifting traffic management request requirements',
    'utilities': 'utility excavation manhole telecom installation requirements',
    'drone': 'drone video photoshoot request requirements',
    'construction': 'construction crane safety net board-up hoist requirements',
    'development': 'outline application final plans as-built development approval',
}
VERSION_NOTICE = ('MACEA 2026-002 EGD and Signages V2 has not been verified in this source library. '
                  'Signage requirements may be incomplete; confirm current requirements with MACEA.')


def draft_letter(context, sources):
    """A factual template cannot turn a missing endorsement into a claimed approval."""
    facts = context.facts
    missing = [label for key, label in (
        ('applicant', 'Applicant / company'), ('address', 'Property / building address'),
        ('schedule', 'Proposed dates and hours'), ('signatory', 'Signatory / position'),
    ) if not getattr(facts, key).strip()]
    value = lambda key, placeholder: getattr(facts, key).strip() or f'[{placeholder}]'
    sections = [
        '**Draft for applicant review**',
        f"[Date]\n\nThe General Manager\nMakati Central Estate Association (MACEA)\n\n"
        f"Subject: Request for review of proposed works at {value('address', 'property / building address')}\n\n"
        f"Dear Sir/Madam,\n\n"
        f"We, {value('applicant', 'applicant / company')}, request MACEA's review and guidance regarding "
        f"the following proposed works at {value('address', 'property / building address')}:\n\n"
        f"{facts.scope.strip()}\n\n"
        f"Proposed schedule: {value('schedule', 'proposed dates and hours, subject to required clearances')}.\n"
        f"Applicant's role: {value('role', 'owner / tenant / authorized representative')}.\n"
        f"Contractor: {value('contractor', 'contractor, if applicable')}.\n\n"
        f"Please advise on the applicable requirements, supporting documents and approvals for this request. "
        f"This letter requests review and does not represent permission to start work.\n\n"
        f"Thank you for your consideration.\n\nSincerely,\n\n{value('signatory', 'signatory name and position')}\n"
        f"{value('applicant', 'applicant / company')}\n[Contact details]",
        '**Document inventory — applicant declared; not verified attachments**\n\n' +
        (facts.attachments.strip() or '[List document names and whether each is available or being prepared.]'),
        '**Before using this draft**\n\n' +
        ('Complete: ' + ', '.join(missing) + '. ' if missing else '') +
        'Confirm the date, contact details, signatory authority, any applicable building-admin endorsement and current MACEA requirements. '
        'Edit the work description for the intended recipient. No endorsement, document receipt or approval has been assumed.',
    ]
    labels = list(dict.fromkeys(label for source in sources for label in
                               re.findall(r'^\[MACEA Passage \d+\] \(([^)]+)\)', source, re.M)))
    if labels:
        sections.append('**Retrieved references for review**\n\n' + '\n'.join(f'- {label}' for label in labels))
    return '\n\n---\n\n'.join(sections)


def assistance_stream(request: AssistanceRequest):
    context = request.context
    facts = context.facts
    if context.task == 'review_letter' and not facts.letter.strip():
        yield 'token', 'Paste your letter in the Letter text field, then send your review request. Private file and image review is not available in this service yet.'
        return
    if context.task == 'respond_comments' and not facts.reviewer_comments.strip():
        yield 'token', 'Paste the reviewer comments in the Reviewer comments field so I can help prepare a response.'
        return
    if context.task != 'requirements' and not facts.scope.strip() and context.task not in ('review_letter', 'respond_comments'):
        yield 'token', 'Describe the proposed work in Work description. Include the property or building address if known; unknown details can remain blank.'
        return
    yield 'warning', VERSION_NOTICE
    yield 'stage', 'macea_sources'
    queries = [TOPICS[context.topic]]
    evidence_query = facts.scope.strip() or facts.letter.strip() or facts.reviewer_comments.strip() or request.message
    queries.append(evidence_query[:500])
    sources = []
    try:
        for query in dict.fromkeys(queries):
            source = retrieve_guidelines('macea_guidelines', query, require_sources=True)
            sources.append(source)
            yield 'search', {'query': f'MACEA: {query}', 'result': source, 'authority': 'MACEA'}
    except GuidelineSourceUnavailable:
        yield 'token', ('I could not retrieve the MACEA source material needed for this request. '
                        'Your case facts have not been added to the guideline library. Please retry when sources are available.')
        return
    if context.task == 'draft_letter':
        yield 'stage', 'macea_draft'
        yield 'token', draft_letter(context, sources)
        return
    data = {
        'case': context.model_dump(),
        'prior_conversation': [turn.model_dump() for turn in request.history],
        'request': request.message,
        'source_passages': sources,
    }
    instructions = read_prompt('macea.md') + '\n\n' + read_prompt('macea_services.md')
    payload = json.dumps(data, ensure_ascii=False)
    # Bound the complete model input, including retrieved text and instructions.
    # Reject instead of silently losing confirmed case facts.
    if len(instructions) + len(payload) > max(6000, (JUDGE_NUM_CTX - 3000) * 3):
        yield 'token', 'This case exceeds the model context budget. Shorten the letter or prior conversation, keeping the confirmed case facts.'
        return
    yield 'stage', 'macea_draft'
    model = get_judge(temperature=0.1, effort=CHAT_REASONING)
    produced = False
    for chunk in model.stream([SystemMessage(instructions), HumanMessage(payload)]):
        if chunk.text:
            produced = True
            yield 'token', chunk.text
    if not produced:
        raise RuntimeError('The model returned no answer. Please retry.')
