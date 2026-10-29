# MACEA services API — phase 1 PRD and contract

Implemented on `feature/macea-services-phase1`. Date: 29 October 2026.
Companion UI: `aix-dean/AIDA`, same branch, `docs/macea-services-prd.md`.

## Scope

Text-only MACEA service selection, letter drafting, pasted-letter review, submission checklists, response-to-comments drafting and requirements questions. Case data is supplied per request; the backend does not create case records, accept private attachments, write to Qdrant, submit applications or issue approvals. The frontend persists submitted case snapshots using its existing authenticated Firebase message/history workflow.

## Endpoint

`POST /api/macea`, `Content-Type: application/json`.

```json
{
  "context": {
    "version": 1,
    "authority": "macea",
    "task": "draft_letter",
    "topic": "signage",
    "facts": {
      "applicant": "Example Company",
      "role": "Tenant",
      "address": "Example Building, Makati",
      "scope": "Replace the lobby identification sign",
      "schedule": "",
      "contractor": "",
      "signatory": "",
      "attachments": "Dimensioned layout: being prepared",
      "letter": "",
      "reviewer_comments": ""
    }
  },
  "message": "Draft a request with placeholders for the missing details.",
  "history": []
}
```

Tasks: `find_service`, `draft_letter`, `review_letter`, `submission_checklist`, `respond_comments`, `requirements`.

Topics: `unsure`, `signage`, `renovation`, `exterior_works`, `work_at_height`, `sidewalk_scaffolding`, `vehicle`, `road_closure`, `utilities`, `drone`, `construction`, `development`.

Facts default to empty strings. Short facts are bounded to 500 characters; scope 2,500; attachment inventory 2,000; letter 8,000; comments 4,000. Message is nonblank and at most 4,000 characters. History is at most 12 user/assistant turns of 6,000 characters each. Total serialized request is at most 24,000 characters, with a second guard on the complete model input including retrieved text and instructions. Extra fields are forbidden; multipart/images are not accepted.

Input validation returns HTTP 422 before streaming. The endpoint returns `application/x-ndjson` using the existing AI limiter. Events include `queued`, `warning` (text), `stage` (value), `search` (query/result/authority), `token` (text), `done`, and `error` (message). A processing exception after headers is an HTTP 200 stream ending with `error`, without `done`.

Missing task input produces a helpful text answer ending in `done` without retrieval or generation. Required fields: letter for letter review; reviewer comments for comment response; work scope for selection, drafting and submission checklist. Requirements questions can use the message alone.

## Grounding and generation

Retrieve the selected topic and work scope (or question) from `macea_guidelines`, requiring results before generation. Preserve the source authority and reference text in search events. Read the MACEA review prompt plus the new `macea_services.md`; do not invoke the ASC judge or its result schema. Case facts and pasted content remain data, and an inventory does not establish that files were inspected.

If retrieval fails, return an unavailable-source explanation without calling the model. A visible limitation states that the 2026-002 EGD and Signages V2 has not been verified. Do not infer supersession or current applicability of historical checklist items. Model instructions require citations for specific requirements, placeholders for unknown facts, separation of editorial advice, and no fabricated approvals/fees/deadlines. Human review remains required.

Request-letter drafting returns a factual template after retrieval, without calling the model. It inserts the submitted work scope and known facts, leaves unknowns as placeholders, labels the document inventory as unverified, and links retrieved source labels. This avoids generating unsupported endorsement or approval statements in the draft. Revise its wording in the frontend's local editor or regenerate after updating case fields. Free-form style requests do not alter this template; the other five tasks remain model-assisted.

Generic `/api/chat` additionally rejects images when the request or user history selects MACEA, before calling ASC `check_image`. An explicit new ASC request can still use the existing ASC path.

General text chat selects its authority per question: physical/site requirements use MACEA, advertising content uses ASC, and a question requesting both uses both. Clear current intent overrides old topics; genuine follow-ups can inherit the prior user's intent. Ambiguous wording uses a bounded semantic routing decision, then asks for clarification if necessary. There is no ASC fallback. MACEA-only chat excludes the ASC checklist, and the search loop exposes and dispatches only the selected authority's tools. A previous assistant answer cannot authorize another source.

## Operational boundaries

No new dependencies or environment variables. Existing Ollama/Qdrant and AI concurrency configuration apply. This branch does not change the live service, install models or populate databases. FastAPI retains its existing private-network deployment assumption; the Next.js same-origin proxy checks Firebase authentication, but this does not add backend authentication. Keep backend access restricted to the existing trusted deployment path.

Deploy the backend before the matching frontend, and deploy the companion Firestore rules before saving MACEA turns. Excluded: private files/OCR/images, official submission, payments, case queues, structured MACEA verdicts, and source-version conflict resolution.

## Validation

`python -m unittest discover -s tests -q` covers the endpoint and existing regressions. New cases check strict contracts, missing input, source failure, task routing, preserved facts, no shared-library ingestion, model-error termination and preventing MACEA images from reaching ASC. Tests use mocked model output; live model quality requires a target-environment review using synthetic cases.
