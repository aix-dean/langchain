import time  # Standard library module for measuring how long each step takes
import hashlib
from datetime import datetime  # Standard library module for the date and time of the check

from app.features.ad_review.checks import approval_reason, error_result, finalize  # Step 3: verify the judge's answer
from app.core.config import IMAGE_SEED, IMAGE_JUDGE_REASONING, JUDGE_MODEL, VISION_MODEL, read_prompt
from app.features.ad_review.judgment import judge_stream  # Step 2: judge the description against the ASC rules
from app.infrastructure.ollama.vision import describe_image  # Step 1: describe the image
from app.features.ad_review.audit import audit_judgment


def check_image(image_bytes, note=""):  # Runs the whole check on one image (note: optional text the user sent with it); yields (kind, data) events
    start = time.perf_counter()
    timings = {}

    yield "stage", "describe"  # Step 1 starts
    description = ""  # The vision model's description, built up piece by piece
    for piece in describe_image(image_bytes):  # Each piece of the description
        description += piece  # Add it
        yield "describe", piece  # Show it live on the page
    if not description.strip():  # The vision model said nothing
        yield "result", {**error_result("The vision model returned no description. Please try again."), "seconds": round(time.perf_counter() - start)}  # Stop
        return  # Done

    timings['describe'] = round(time.perf_counter() - start, 2)
    judge_start = time.perf_counter()
    yield "stage", "judge"  # Step 2 starts
    raw = ""  # The judge's final answer
    retrieved = []
    for kind, data in judge_stream(description, note):  # The judge's thinking, searches and answer
        if kind == "answer":  # The final answer
            raw = data  # Keep it
        elif kind != "token":  # Thinking, a guideline search, or memory use (the raw JSON text isn't shown)
            if kind == 'search':
                retrieved.append(data['result'])
            yield kind, data  # Show it on the page

    timings['judge'] = round(time.perf_counter() - judge_start, 2)
    verify_start = time.perf_counter()
    yield "stage", "verify"  # Step 3 starts
    result = finalize(raw, description)  # Validate evidence and record uncertainty as notes.
    if result['result'] in {'COMPLIANT', 'NON-COMPLIANT'}:
        audit_issues = audit_judgment(result, description, retrieved)
        if audit_issues:
            issues = result.get('review_issues', []) + audit_issues
            result.update(review_issues=issues, notes=list(dict.fromkeys(issues)), message=' '.join(issues))
            if result['result'] == 'COMPLIANT':
                result['approval_summary'] = approval_reason(result.get('checks_passed') or [])
            result['explanation'] = (result.get('approval_summary') if result['result'] == 'COMPLIANT'
                                     else result.get('explanation', 'Not approved: verified violations were found.'))
            result['explanation'] += ' Notes: ' + ' '.join(audit_issues)
    result["description"] = description  # Include the description, for the reviewer
    timings['verify'] = round(time.perf_counter() - verify_start, 2)
    result['timings'] = timings
    digest = lambda text: hashlib.sha256(text.encode('utf-8')).hexdigest()
    result['analysis'] = {
        'image_sha256': hashlib.sha256(image_bytes).hexdigest(),
        'description_sha256': digest(description),
        'sources_sha256': digest('\n'.join(retrieved)),
        'instructions_sha256': digest(read_prompt('describe.md') + read_prompt('describe_system.md') + read_prompt('judge.md')),
        'seed': IMAGE_SEED, 'reasoning': IMAGE_JUDGE_REASONING,
    }
    result["seconds"] = round(time.perf_counter() - start)
    result["checked_at"] = datetime.now().strftime("%B %d, %Y %I:%M %p")  # When it was checked, e.g. "October 23, 2026 10:15 AM"
    result["vision_model"], result["judge_model"] = VISION_MODEL, JUDGE_MODEL  # Which models made this result (for the report)
    yield "result", result  # The final result
