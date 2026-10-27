# Backend architecture

This backend uses feature-oriented packages with separated HTTP, workflow and
integration responsibilities. It is a practical modular application, rather
than a strict Clean Architecture implementation with an interface for every
function. Feature workflows currently call concrete adapters; those seams can
be replaced with injected ports if multiple implementations become necessary.

## Responsibilities

- `app/main.py` composes routers and exposes `create_app(warm_models=False)` for
  tests and tooling. `app/bootstrap.py` owns startup wiring. Importing the app
  does not launch a thread, call a model, or start the embedding service.
- `app/features/<feature>/routes.py` owns HTTP concerns: multipart fields,
  validation, status codes, filenames, streaming responses and PDF headers.
- Feature services own conversation, image-check, ingestion, reporting and
  guideline-source workflows. Feature logic does not depend on FastAPI.
- `app/infrastructure/ollama/` owns Ollama and LangChain client construction,
  capability detection, vision calls and the processor-only embedding server.
- `app/infrastructure/qdrant/` owns vector-store connections and search adapters.
- `app/core/` owns settings, resource paths, context compaction and the generation
  lock. Infrastructure and core must not import features or HTTP modules.
- `app/api/streaming.py` owns the shared NDJSON transport, queue events, error
  events and release of the shared generation lock.
- `app/cli/` calls the same feature workflows as HTTP. Root scripts are thin
  compatibility commands, with no duplicated implementation.

## Feature boundaries

Chat uses the guideline service for authority-aware grounding. Image review uses
that service plus the Ollama adapters, deterministic checks and independent audit.
Chat can invoke image review for messages with attachments. Documents use the
Qdrant adapter for extraction/embedding/storage; reports build PDFs from results.
These are explicit service imports, not imports of another feature's HTTP router.

The scope classifier and chat reasoning loop belong to chat. Image judgment and
evidence verification belong to ad review. Model configuration and client
construction belong to infrastructure and do not import those features.

## Adding a feature

1. Create `app/features/<name>/` with an `__init__.py`.
2. Put workflows in `service.py` and focused modules when they need separate
   responsibilities; keep HTTP types and exceptions in `routes.py`.
3. Define an `APIRouter` and register it in `create_app()` in `app/main.py`.
4. Reuse an existing integration adapter or add one under infrastructure.
5. Add feature tests under `tests/`, mocking the adapter where the service uses it.
   Use `create_app(warm_models=False)` for HTTP contract tests.

Do not add repository classes, base services, factories or interface layers merely
for folder symmetry. Add an abstraction when it creates a useful boundary.

## Behavior and deployment

The endpoints remain `/api/chat`, `/api/check`, `/api/documents`, `/api/report`
and `/api/status`. Streaming remains NDJSON, uploads remain multipart and reports
remain PDF. The original HTML pages at `/` and `/upload` remain available; Next.js
continues to use the same Python API.

The model and reasoning settings still come from the existing `.env`. The prompts,
source documents, Qdrant collections and downloaded Ollama models are unchanged.
The runtime still assumes one backend worker: generation and document-ingestion
locks are process-local. Multiple workers would require external coordination.
This reorganization does not introduce authentication, persistent server-side chat
storage, or a performance optimization.

## Verification

Run `uv run -m unittest discover -s tests -p "test_*.py"` and
`node --test tests/test_chat_stream.cjs` from the backend root. Architecture checks
protect dependency direction and startup behavior; HTTP contract checks cover
chat events, image results, file validation, document replacement and PDF responses.
