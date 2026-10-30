"""One chat entry point for questions and progressive applicant assistance."""
import re
from app.features.chat.routing import direct_authorities, required_authorities
from app.features.chat.service import chat_stream
from app.features.macea.schemas import AssistanceRequest, CaseContext
from app.features.macea.service import assistance_stream


def unified_stream(message, history, context=None):
    selected = direct_authorities(message)
    if 'asc' in selected:
        yield from chat_stream(message, history)
        return
    task = None
    for pattern, value in [
        (r'review.*letter|check.*letter', 'review_letter'),
        (r'draft.*letter|write.*letter', 'draft_letter'),
        (r'respond.*comments|reply.*comments', 'respond_comments'),
        (r'prepare.*submission|submission checklist', 'submission_checklist'),
        (r'find.*service', 'find_service'),
    ]:
        if re.search(pattern, message, re.I):
            task = value
            break
    if context or (task and 'macea' in (selected or required_authorities(message, history))):
        case = context.model_copy(deep=True) if context else CaseContext(task=task)
        if task:
            case.task = task
        elif selected == ['macea'] and re.search(r'^(?:what|how|which|does|is|are|can)\b', message, re.I):
            case.task = 'requirements'
        # Match the bounded intake contract while retaining applicant facts in full.
        recent = []
        used = 0
        for turn in reversed(history[-12:]):
            content = str(turn.get('content', ''))
            if len(content) > 6000 or used + len(content) > 6000:
                break
            if turn.get('role') in ('user', 'assistant'):
                recent.insert(0, {'role': turn['role'], 'content': content})
                used += len(content)
        yield from assistance_stream(AssistanceRequest(context=case, message=message, history=recent))
        return
    yield from chat_stream(message, history)
