# BigGraph Full Refactor Acceptance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring BigGraph from a runnable prototype into a maintainable, testable, secure RAG + PPT Agent application with clear backend boundaries, reliable background jobs, consistent frontend API usage, and measurable acceptance gates.

**Architecture:** This is a master refactor plan, not a single oversized implementation task. The work is split into independently testable tracks: application composition, security and authorization, knowledge-base lifecycle, ingestion/search, PPT background tasks, frontend API/state cleanup, observability, tests, and deployment readiness. Each track must leave the system runnable and verifiable before the next track begins.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL, Redis, Qdrant, Elasticsearch, LangGraph, Vue 3, Vite, Pinia, Element Plus, Pytest, npm/Vite build.

---

## Current Baseline

The project is currently a mixed FastAPI + Vue/Vite application with RAG, document ingestion, authentication, chat sessions, and PPT generation.

Known verified state on 2026-06-22:

- `pytest -q` returns `8 passed, 2 failed, 1 warning`.
- The two failing tests are `tests/test_backend_delete_knowledge_base.py::test_delete_knowledge_base_route_exists_before_static_fallback` and `tests/test_backend_delete_knowledge_base.py::test_delete_knowledge_base_requires_owner_and_cleans_related_data`.
- `npm run build` in `frontend/` succeeds.
- The frontend build warns that the main JavaScript chunk is larger than 500 kB.
- The frontend build warns that `src/api/document.js` is dynamically imported by `SettingsDrawer.vue` but also statically imported by `stores/chat.js`, so that dynamic import does not split a chunk.
- Working tree already contains user changes in `frontend/src/api/knowledgeBase.js`, `frontend/src/views/chat/SettingsDrawer.vue`, added tests under `tests/`, and untracked `emb/`.

The plan must preserve user changes unless the user explicitly asks to discard them.

---

## Non-Goals

- Do not rewrite the entire product in another framework.
- Do not change `ppt_creator/skills/ppt-master` internals unless a later child plan proves it is required.
- Do not introduce Kubernetes, service mesh, or multi-repo deployment in this refactor.
- Do not add billing, teams, analytics, or unrelated product features.
- Do not optimize UI aesthetics as a primary goal; this plan focuses on correctness, maintainability, and operability.

---

## Target Architecture

### Backend Composition

Create an explicit FastAPI application factory and route modules:

- `api/main.py`: app factory, middleware, exception handlers, router registration, lifespan.
- `api/routers/auth.py`: authentication endpoints.
- `api/routers/knowledge_bases.py`: knowledge-base CRUD, sharing, membership, authorization.
- `api/routers/documents.py`: upload, document status, document delete.
- `api/routers/search.py`: RAG search endpoint.
- `api/routers/chat.py`: chat and chat session endpoints.
- `api/routers/ppt.py`: PPT Agent endpoints.
- `api/dependencies.py`: request-scoped dependencies such as current user and services.

Keep compatibility during migration:

- `api/ragControll.py` may remain temporarily as a compatibility import wrapper.
- Existing frontend endpoints should continue to work until the frontend is migrated to unified `/api/*` paths.

### Service Layer

Move business behavior out of route functions:

- `services/auth_service.py`: token/session behavior that is not HTTP-specific.
- `services/kb_service.py`: knowledge-base ownership, membership, deletion cascade.
- `services/ingestion_service.py`: upload processing, parsing, chunking, embedding, indexing.
- `services/search_service.py`: hybrid retrieval and result shaping.
- `services/chat_service.py`: chat history ownership and LLM invocation.
- `services/ppt_service.py`: PPT state transitions and task submission.

### Storage Layer

Keep storage modules focused on persistence:

- `storage/postgres.py`: repositories and transaction helpers.
- `storage/qdrant.py`: vector storage operations.
- `storage/elasticsearch.py`: text index operations.
- `storage/redis_client.py`: Redis primitives and namespaced state helpers.

The storage layer must not contain HTTP exceptions or user-facing messages except where already required for compatibility during migration.

### Background Jobs

Long-running work must move behind a task boundary:

- Document ingestion becomes a job with explicit states.
- PPT generation becomes a job with explicit states.
- API endpoints submit work and return a task/session identifier.
- Status endpoints report progress, completion, failure, and retryability.
- The first implementation may use an in-process task runner if necessary, but the service interface must allow Celery/RQ/Arq replacement without changing API routes.

### Frontend

Use one API convention:

- All backend calls should use `/api/...`.
- Vite proxy should forward `/api` without route-by-route duplication.
- Auth state, chat state, RAG state, and PPT task state should be separate Pinia stores or focused composables.

### Security

Production must require environment-provided secrets:

- JWT signing secret.
- PostgreSQL password or `DATABASE_URL`.
- Elasticsearch password.
- Embedding API key.
- SMTP password when email code sending is enabled.

Authorization must be centralized:

- Owner-only operations use a single owner guard.
- Member-readable operations use a single access guard.
- Editor operations are explicitly defined before use.

---

## Master Acceptance Gates

The full refactor is accepted only when all gates below pass.

### Gate A: Automated Verification

Run from repository root:

```powershell
pytest -q
```

Expected:

```text
all tests pass
0 failed
```

Run from `frontend/`:

```powershell
npm run build
```

Expected:

```text
build succeeds
no application compile errors
no route import errors
```

Run Python import smoke test from repository root:

```powershell
python -c "from api.main import create_app; app = create_app(); print(len(app.routes))"
```

Expected:

```text
prints a positive route count
does not raise ImportError
does not connect to unavailable external services during import
```

### Gate B: API Contract

The backend must expose these route groups under `/api`:

- `/api/auth/*`
- `/api/knowledge_bases/*`
- `/api/documents/*`
- `/api/upload/*` or `/api/documents/upload/*`, with one canonical path documented.
- `/api/search/*`
- `/api/chat/*`
- `/api/ppt/*`
- `/api/health`

Acceptance check:

```powershell
python - <<'PY'
from api.main import create_app
app = create_app()
paths = sorted({route.path for route in app.routes})
required_prefixes = [
    "/api/auth",
    "/api/knowledge_bases",
    "/api/chat",
    "/api/ppt",
    "/api/health",
]
missing = [prefix for prefix in required_prefixes if not any(path.startswith(prefix) for path in paths)]
if missing:
    raise SystemExit(f"missing route prefixes: {missing}")
print("route prefixes ok")
PY
```

Expected:

```text
route prefixes ok
```

### Gate C: Security

The application must not start in production mode with default secrets.

Acceptance check:

```powershell
$env:APP_ENV="production"
$env:JWT_SECRET_KEY=""
python -c "from config.settings import settings; settings.validate_for_runtime()"
```

Expected:

```text
non-zero exit or raised configuration error explaining JWT_SECRET_KEY is required
```

Development mode may still start with `.env` values, but defaults must be clearly marked unsafe.

### Gate D: Authorization

The following scenarios must have API tests:

- Owner can create, view, share, upload to, and delete their own knowledge base.
- Non-owner cannot delete another user's knowledge base.
- Approved member can view and search a joined knowledge base.
- Pending member cannot search a knowledge base.
- Cross-tenant access returns 403 or 404 according to documented policy.
- Chat history cannot be read or renamed by a different user.

Expected:

```text
tests cover every scenario above and pass in pytest
```

### Gate E: Data Consistency

Deleting a knowledge base must delete or mark inactive all related records:

- Knowledge base row.
- Membership rows.
- Uploaded file rows.
- Document rows.
- Document chunk rows.
- Ingestion job rows.
- Qdrant vectors.
- Elasticsearch documents.
- Temporary uploaded files owned by that knowledge base, if still present.

If Qdrant or Elasticsearch cleanup fails, PostgreSQL must record an explicit cleanup failure or enqueue a retry task. Silent `except Exception: pass` is not accepted for this path.

Expected:

```text
delete endpoint returns success only when authoritative data is deleted and external-index cleanup is complete or explicitly queued for retry
```

### Gate F: Background Task Reliability

Document ingestion and PPT generation must expose observable states:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled` if cancellation is implemented

Failures must include a stable machine-readable code and a user-readable message.

Expected:

```text
frontend can refresh the page and still recover current task status from backend state
```

### Gate G: Frontend Behavior

Manual acceptance flow:

1. Register or log in.
2. Create a knowledge base.
3. Upload a small `.txt` document.
4. Wait for ingestion status to complete.
5. Enable RAG mode.
6. Ask a question that matches the uploaded text.
7. Confirm the answer includes content grounded in the uploaded document.
8. Open settings.
9. Delete the knowledge base as owner.
10. Confirm it disappears from the list.
11. Confirm RAG mode clears the deleted selected knowledge base.
12. Switch to PPT mode.
13. Send a simple PPT request.
14. Confirm the session reports either a follow-up question, waiting confirmation, or a running task state.

Expected:

```text
no blank page
no unhandled browser console errors from application code
no stale deleted knowledge base remains selected
```

---

## File Structure Plan

### Create

- `api/main.py`: FastAPI app factory and lifespan.
- `api/dependencies.py`: dependency providers and authorization helpers.
- `api/routers/__init__.py`: router package marker.
- `api/routers/auth.py`: moved authentication router.
- `api/routers/knowledge_bases.py`: knowledge-base router.
- `api/routers/documents.py`: document router.
- `api/routers/search.py`: search router.
- `api/routers/chat.py`: chat router.
- `api/routers/ppt.py`: PPT router.
- `services/__init__.py`: service package marker.
- `services/kb_service.py`: knowledge-base business behavior.
- `services/ingestion_service.py`: document ingestion behavior.
- `services/search_service.py`: hybrid retrieval behavior.
- `services/chat_service.py`: chat behavior.
- `services/ppt_service.py`: PPT task behavior.
- `tests/conftest.py`: shared test fixtures.
- `tests/api/test_app_routes.py`: app factory and route registration tests.
- `tests/api/test_knowledge_base_lifecycle.py`: knowledge-base lifecycle tests.
- `tests/api/test_authorization.py`: permission tests.
- `tests/api/test_chat_sessions.py`: chat ownership tests.
- `tests/services/test_kb_service.py`: deletion cascade unit tests.
- `tests/services/test_search_service.py`: hybrid search tests.
- `docs/architecture/backend-refactor.md`: updated backend architecture.
- `docs/architecture/api-contract.md`: stable API contract.
- `.env.example`: documented development configuration.

### Modify

- `api/ragControll.py`: convert to compatibility wrapper or keep temporary route forwarding.
- `api/auth.py`: move or re-export auth router.
- `api/ppt_agent_router.py`: move into router/service split and fix background reply handling.
- `config/settings.py`: use typed settings and runtime validation.
- `core/auth/jwt.py`: read secret and token TTL from settings.
- `storage/postgres.py`: add missing cascade repository methods and remove HTTP-specific assumptions.
- `storage/redis_client.py`: add ownership-aware chat session helpers.
- `storage/qdrant.py`: expose deletion by knowledge base.
- `storage/elasticsearch.py`: expose deletion by knowledge base.
- `core/retrieval/hybrid.py`: become canonical retrieval path or move into `services/search_service.py`.
- `frontend/vite.config.js`: simplify proxy to `/api`.
- `frontend/src/api/request.js`: centralize base URL and refresh behavior.
- `frontend/src/api/auth.js`: migrate to `/api/auth`.
- `frontend/src/api/document.js`: migrate to canonical `/api/documents` paths.
- `frontend/src/api/knowledgeBase.js`: migrate to `/api/knowledge_bases`.
- `frontend/src/stores/chat.js`: separate RAG/PPT task concerns.
- `frontend/src/stores/auth.js`: align token refresh and user state.
- `frontend/src/views/chat/SettingsDrawer.vue`: keep owner-only delete and use updated API paths.

---

## Task 1: Establish App Factory And Route Registration

**Files:**

- Create: `api/main.py`
- Create: `api/routers/__init__.py`
- Modify: `api/ragControll.py`
- Test: `tests/api/test_app_routes.py`

- [ ] **Step 1: Write failing route registration tests**

Create `tests/api/test_app_routes.py` with tests that import `create_app()` and assert all required router prefixes are present.

```python
from api.main import create_app


def test_create_app_registers_required_route_prefixes():
    app = create_app()
    paths = {route.path for route in app.routes}

    required_prefixes = [
        "/api/auth",
        "/api/knowledge_bases",
        "/api/chat",
        "/api/ppt",
        "/api/health",
    ]

    for prefix in required_prefixes:
        assert any(path.startswith(prefix) for path in paths), prefix


def test_create_app_does_not_require_running_external_services_on_import():
    app = create_app()
    assert app.title
    assert len(app.routes) > 0
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
pytest tests/api/test_app_routes.py -q
```

Expected before implementation:

```text
fails because api.main does not exist
```

- [ ] **Step 3: Create `api/main.py` app factory**

Implement `create_app()` so router registration is not hidden under `if __name__ == "__main__"`.

Required behavior:

- Creates a FastAPI app.
- Adds `RequestIDMiddleware`.
- Registers all routers under `/api`.
- Adds `/api/health`.
- Keeps database initialization in lifespan, not import time.

- [ ] **Step 4: Run route registration tests**

Run:

```powershell
pytest tests/api/test_app_routes.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run full tests**

Run:

```powershell
pytest -q
```

Expected:

```text
no new failures beyond existing known knowledge-base delete failures
```

- [ ] **Step 6: Commit**

```powershell
git add api/main.py api/routers/__init__.py api/ragControll.py tests/api/test_app_routes.py
git commit -m "refactor: add FastAPI app factory"
```

Acceptance:

- Importing `api.main:create_app` works.
- `uvicorn api.main:create_app --factory` can discover the app.
- Existing startup path remains documented until old path is removed.

---

## Task 2: Centralize Runtime Settings And Secret Validation

**Files:**

- Modify: `config/settings.py`
- Modify: `core/auth/jwt.py`
- Create: `.env.example`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_settings.py`:

```python
import pytest

from config.settings import Settings


def test_production_requires_jwt_secret_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings()

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings.validate_for_runtime()


def test_development_allows_local_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings()

    settings.validate_for_runtime()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
pytest tests/test_settings.py -q
```

Expected before implementation:

```text
fails because Settings.validate_for_runtime does not exist
```

- [ ] **Step 3: Implement runtime validation**

Add fields:

- `APP_ENV`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`

Add method:

```python
def validate_for_runtime(self) -> None:
    if self.APP_ENV.lower() == "production":
        missing = []
        if not self.JWT_SECRET_KEY:
            missing.append("JWT_SECRET_KEY")
        if self.PG_PASSWORD in ("", "678678") and not os.getenv("DATABASE_URL"):
            missing.append("PG_PASSWORD or DATABASE_URL")
        if self.ES_PASSWORD in ("", "changeme"):
            missing.append("ES_PASSWORD")
        if self.EMBEDDING_API_KEY in ("", "123123"):
            missing.append("EMBEDDING_API_KEY")
        if missing:
            raise ValueError("Missing production configuration: " + ", ".join(missing))
```

- [ ] **Step 4: Update JWT helper to read settings**

Replace hard-coded `_SECRET_KEY` in `core/auth/jwt.py` with `settings.JWT_SECRET_KEY`.

Acceptance:

- Development mode still works locally.
- Production mode fails fast with a clear error if required secrets are absent.

- [ ] **Step 5: Add `.env.example`**

Include safe example values and comments:

```text
APP_ENV=development
JWT_SECRET_KEY=replace-this-in-production
PG_HOST=127.0.0.1
PG_PORT=5432
PG_USER=workface
PG_PASSWORD=replace-this
PG_DATABASE=workface
QDRANT_URL=http://localhost:6333
ES_HOSTS=http://localhost:9200
ES_USER=elastic
ES_PASSWORD=replace-this
EMBEDDING_MODEL=bge-m3
EMBEDDING_BASE_URL=http://localhost:1233/v1
EMBEDDING_API_KEY=replace-this
REDIS_HOST=localhost
REDIS_PORT=6379
```

- [ ] **Step 6: Run tests**

Run:

```powershell
pytest tests/test_settings.py -q
pytest -q
```

Expected:

```text
settings tests pass
full test suite does not gain new failures
```

- [ ] **Step 7: Commit**

```powershell
git add config/settings.py core/auth/jwt.py .env.example tests/test_settings.py
git commit -m "chore: validate runtime secrets"
```

---

## Task 3: Implement Knowledge-Base Delete Lifecycle

**Files:**

- Modify: `api/routers/knowledge_bases.py` or `api/ragControll.py` during transition
- Modify: `storage/postgres.py`
- Modify: `storage/qdrant.py`
- Modify: `storage/elasticsearch.py`
- Test: `tests/test_backend_delete_knowledge_base.py`
- Test: `tests/api/test_knowledge_base_lifecycle.py`

- [ ] **Step 1: Preserve existing failing tests**

Run:

```powershell
pytest tests/test_backend_delete_knowledge_base.py -q
```

Expected before implementation:

```text
2 failed
```

- [ ] **Step 2: Add repository cascade methods**

Add methods:

- `DocumentChunkStore.delete_by_knowledge_base(db, kb_id) -> int`
- `IngestionJobStore.delete_by_knowledge_base(db, kb_id) -> int`
- `DocumentStore.delete_by_knowledge_base(db, kb_id) -> int`
- `UploadedFileStore.delete_by_knowledge_base(db, kb_id) -> int`
- `KbMemberStore.delete_by_knowledge_base(db, kb_id) -> int`
- `KnowledgeBaseStore.delete(db, kb_id) -> bool`

Acceptance:

- Methods return deleted row counts or boolean success.
- Methods do not commit directly; transaction stays controlled by `get_session()`.

- [ ] **Step 3: Add external index deletion by knowledge base**

Add:

- `QdrantService.delete_knowledge_base_vectors(tenant_id: str, knowledge_base_id: str) -> None`
- `ElasticsearchService.delete_knowledge_base_chunks(knowledge_base_id: str) -> Any`

Acceptance:

- Qdrant deletion filters by both tenant and knowledge base.
- Elasticsearch deletion filters by knowledge base.

- [ ] **Step 4: Implement delete endpoint**

Endpoint:

```text
DELETE /api/knowledge_bases/{kb_id}
```

Compatibility endpoint during migration:

```text
DELETE /knowledge_bases/{kb_id}
```

Required behavior:

- Requires authentication.
- Loads knowledge base.
- Returns not found if missing.
- Checks `str(kb.owner_id) == user["user_id"]`.
- Deletes related PostgreSQL rows in one transaction.
- Cleans Qdrant and Elasticsearch.
- Returns deleted counts.

Response shape:

```json
{
  "message": "knowledge_base_deleted",
  "knowledge_base_id": "uuid",
  "deleted": {
    "chunks": 3,
    "jobs": 1,
    "documents": 1,
    "files": 1,
    "members": 0,
    "knowledge_bases": 1
  }
}
```

- [ ] **Step 5: Add behavior tests**

Create `tests/api/test_knowledge_base_lifecycle.py` with API-level tests using dependency overrides or mocked current user/session.

Minimum tests:

- Owner can delete.
- Non-owner receives forbidden.
- Missing knowledge base returns not found.
- External index delete methods are called.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
pytest tests/test_backend_delete_knowledge_base.py tests/api/test_knowledge_base_lifecycle.py -q
```

Expected:

```text
all focused knowledge-base delete tests pass
```

- [ ] **Step 7: Run full tests**

Run:

```powershell
pytest -q
```

Expected:

```text
all tests pass or only unrelated pre-existing environment-dependent tests fail with documented reason
```

- [ ] **Step 8: Commit**

```powershell
git add api storage tests
git commit -m "feat: delete knowledge bases with cascade cleanup"
```

Acceptance:

- Existing frontend delete button calls a working backend endpoint.
- User cannot delete a knowledge base they do not own.
- There is no silent partial cleanup without recorded failure.

---

## Task 4: Centralize Knowledge-Base Authorization

**Files:**

- Create or modify: `api/dependencies.py`
- Modify: knowledge-base, upload, search, and document endpoints
- Modify: `storage/postgres.py`
- Test: `tests/api/test_authorization.py`

- [ ] **Step 1: Write authorization tests**

Create `tests/api/test_authorization.py` with real API-level scenarios. If test factories do not exist yet, create them in `tests/conftest.py` before writing these tests.

Required fixture behavior:

- `auth_headers(user)` returns `{"Authorization": "Bearer <access-token>"}` for the provided user.
- `create_user(username, tenant_id=None)` creates a persisted user.
- `create_knowledge_base(owner, tenant_id=None)` creates a persisted knowledge base owned by `owner`.
- `create_kb_member(user, kb, status)` creates a persisted membership row.
- External search dependencies are mocked so authorization tests do not require Qdrant or Elasticsearch.

Required test cases:

```python
def test_owner_can_access_own_knowledge_base(client, create_user, create_knowledge_base, auth_headers):
    owner = create_user("owner")
    kb = create_knowledge_base(owner)

    response = client.get(f"/api/knowledge_bases/{kb.id}", headers=auth_headers(owner))

    assert response.status_code == 200
    assert response.json()["id"] == str(kb.id)


def test_approved_member_can_search_joined_knowledge_base(
    client,
    create_user,
    create_knowledge_base,
    create_kb_member,
    auth_headers,
    mock_search_service,
):
    owner = create_user("owner")
    member = create_user("member", tenant_id=owner.tenant_id)
    kb = create_knowledge_base(owner)
    create_kb_member(member, kb, status="approved")
    mock_search_service.return_value = []

    response = client.get(
        f"/api/search/{kb.id}",
        params={"query": "hello", "limit": 5},
        headers=auth_headers(member),
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_pending_member_cannot_search_knowledge_base(
    client,
    create_user,
    create_knowledge_base,
    create_kb_member,
    auth_headers,
):
    owner = create_user("owner")
    pending = create_user("pending", tenant_id=owner.tenant_id)
    kb = create_knowledge_base(owner)
    create_kb_member(pending, kb, status="pending")

    response = client.get(
        f"/api/search/{kb.id}",
        params={"query": "hello", "limit": 5},
        headers=auth_headers(pending),
    )

    assert response.status_code == 403


def test_non_owner_cannot_delete_knowledge_base(client, create_user, create_knowledge_base, auth_headers):
    owner = create_user("owner")
    other = create_user("other", tenant_id=owner.tenant_id)
    kb = create_knowledge_base(owner)

    response = client.delete(f"/api/knowledge_bases/{kb.id}", headers=auth_headers(other))

    assert response.status_code == 403


def test_cross_tenant_access_is_rejected(client, create_user, create_knowledge_base, auth_headers):
    owner = create_user("owner", tenant_id="tenant_a")
    outsider = create_user("outsider", tenant_id="tenant_b")
    kb = create_knowledge_base(owner, tenant_id="tenant_a")

    response = client.get(f"/api/knowledge_bases/{kb.id}", headers=auth_headers(outsider))

    assert response.status_code in (403, 404)
```

- [ ] **Step 2: Implement permission helpers**

Required helpers:

- `require_kb_owner(db, kb_id, user)`.
- `require_kb_access(db, kb_id, user)`.
- `require_kb_editor_or_owner(db, kb_id, user)` if editor upload is supported.

Policy:

- Owner can do everything.
- Approved member can read/search.
- Pending member cannot read/search.
- Only owner can share, approve members, or delete.
- Upload is owner-only until editor role behavior is implemented and tested.

- [ ] **Step 3: Apply helpers to routes**

Use helpers in:

- Get knowledge-base detail.
- Share knowledge base.
- Join approval.
- List members.
- Upload.
- Search.
- Delete document.
- Delete knowledge base.

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/api/test_authorization.py -q
pytest -q
```

Expected:

```text
authorization tests pass
full suite passes
```

- [ ] **Step 5: Commit**

```powershell
git add api storage tests/api/test_authorization.py
git commit -m "fix: centralize knowledge-base authorization"
```

Acceptance:

- No route contains a one-off owner or tenant check when a helper should be used.
- Authorization failure messages are stable and do not leak unrelated tenant data.

---

## Task 5: Split Ingestion Into A Service Boundary

**Files:**

- Create: `services/ingestion_service.py`
- Modify: document upload router
- Modify: `api/ragControll.py` compatibility path if needed
- Test: `tests/services/test_ingestion_service.py`

- [ ] **Step 1: Write ingestion service tests**

Create tests for:

- Empty parsed document marks job failed.
- Parser error marks job failed.
- Successful parse creates chunks and calls Qdrant/ES.
- Qdrant failure records sync failure.
- ES failure records sync failure.

- [ ] **Step 2: Extract `process_uploaded_document`**

Move logic from route file into `services/ingestion_service.py`.

Required public interface:

```python
class IngestionService:
    def process_uploaded_document(self, job_id: str, file_id: str, request_id: str = "-") -> None:
        ...
```

Async implementation is acceptable if all callers use it consistently.

- [ ] **Step 3: Keep upload route thin**

Upload route responsibilities:

- Authenticate.
- Authorize knowledge base.
- Validate file.
- Store upload metadata.
- Submit ingestion task.
- Return job id.

Upload route must not parse, chunk, embed, or index.

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/services/test_ingestion_service.py -q
pytest -q
```

Expected:

```text
ingestion service tests pass
full suite passes
```

- [ ] **Step 5: Commit**

```powershell
git add services/ingestion_service.py api storage tests/services/test_ingestion_service.py
git commit -m "refactor: extract ingestion service"
```

Acceptance:

- Upload endpoint remains compatible.
- Ingestion can be tested without running FastAPI.
- Ingestion failures leave inspectable job state.

---

## Task 6: Make Hybrid Search The Canonical Search Path

**Files:**

- Create or modify: `services/search_service.py`
- Modify: `core/retrieval/hybrid.py`
- Modify: search router
- Test: `tests/services/test_search_service.py`

- [ ] **Step 1: Write search service tests**

Required scenarios:

- Empty query is rejected.
- Query uses both vector and BM25 retrievers.
- RRF-fused result contains full content when ES has it.
- Search respects tenant and knowledge-base filters.
- ES failure does not hide vector results unless the policy says search must fail.

- [ ] **Step 2: Define search result contract**

Canonical result fields:

```json
{
  "chunk_id": "string",
  "document_id": "string",
  "file_id": "string",
  "file_name": "string",
  "content": "string",
  "score": 0.0,
  "rrf_score": 0.0,
  "bm25_score": 0.0,
  "page_start": 1,
  "page_end": 1,
  "content_type": "text",
  "heading_path": "string",
  "keywords": [],
  "token_count": 0
}
```

- [ ] **Step 3: Replace route-level search logic**

Search route should:

- Authenticate.
- Authorize knowledge-base access.
- Call `SearchService.search(...)`.
- Return canonical result shape.

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/services/test_search_service.py -q
pytest -q
```

Expected:

```text
search service tests pass
full suite passes
```

- [ ] **Step 5: Commit**

```powershell
git add services/search_service.py core/retrieval/hybrid.py api tests/services/test_search_service.py
git commit -m "refactor: use hybrid retrieval for search"
```

Acceptance:

- Search endpoint no longer duplicates embedding/Qdrant/ES orchestration.
- Hybrid search behavior is unit-tested.

---

## Task 7: Stabilize PPT Agent Background Execution

**Files:**

- Modify: `api/ppt_agent_router.py` during transition
- Create: `services/ppt_service.py`
- Modify: `storage/ppt_state_store.py`
- Test: `tests/api/test_ppt_router.py`
- Test: `tests/services/test_ppt_service.py`

- [ ] **Step 1: Write regression test for background reply persistence**

Test must cover the current bug:

- Invoke background PPT graph path.
- Fake graph returns `assistant_reply`.
- Assert assistant reply is saved to chat history.
- Assert no `UnboundLocalError` is swallowed.

- [ ] **Step 2: Fix `reply` assignment order**

Required order:

```python
next_state = ppt_graph.invoke(state)
reply = next_state.get("assistant_reply", "")
status = next_state.get("status", "collecting")
save_ppt_state(session_id, next_state)
save_chat_message(session_id, "user", message)
if reply:
    save_chat_message(session_id, "assistant", reply)
```

- [ ] **Step 3: Extract PPT service**

Create `PptService` with:

- `start_or_continue_session(session_id, message)`.
- `run_background_generation(session_id, state, message)`.
- `get_status(session_id)`.
- `delete_session(session_id)`.
- `upload_material(session_id, file)`.

- [ ] **Step 4: Make failure states explicit**

Failures must return:

```json
{
  "status": "failed",
  "error_code": "ppt_generation_failed",
  "response": "PPT 生成失败，请稍后重试",
  "pptx_download_url": ""
}
```

Internal exception detail may be logged, but must not be exposed raw to normal users.

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/api/test_ppt_router.py tests/services/test_ppt_service.py -q
pytest -q
```

Expected:

```text
PPT tests pass
full suite passes
```

- [ ] **Step 6: Commit**

```powershell
git add api/ppt_agent_router.py services/ppt_service.py storage/ppt_state_store.py tests/api/test_ppt_router.py tests/services/test_ppt_service.py
git commit -m "fix: stabilize PPT background tasks"
```

Acceptance:

- Background generation does not lose assistant history.
- SSE and polling both read from the same durable task state.
- Raw local filesystem paths are not shown to frontend users.

---

## Task 8: Normalize Frontend API Paths And State Boundaries

**Files:**

- Modify: `frontend/vite.config.js`
- Modify: `frontend/src/api/request.js`
- Modify: `frontend/src/api/auth.js`
- Modify: `frontend/src/api/document.js`
- Modify: `frontend/src/api/knowledgeBase.js`
- Modify: `frontend/src/stores/chat.js`
- Create: `frontend/src/stores/pptTask.js` if PPT state remains complex
- Test: `tests/test_frontend_delete_knowledge_base.py`

- [ ] **Step 1: Update API path convention**

Canonical frontend paths:

- `/api/auth/send-code`
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/refresh`
- `/api/auth/me`
- `/api/auth/logout`
- `/api/knowledge_bases/`
- `/api/knowledge_bases/{id}`
- `/api/documents/{id}`
- `/api/upload/{knowledge_base_id}` or the canonical replacement from API contract
- `/api/search/{knowledge_base_id}`
- `/api/chat`
- `/api/chat/sessions`
- `/api/ppt/chat`

- [ ] **Step 2: Simplify Vite proxy**

`frontend/vite.config.js` should proxy `/api` to the backend and avoid route-by-route duplication.

Expected shape:

```js
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

- [ ] **Step 3: Remove ineffective dynamic import**

Because `frontend/src/api/document.js` is statically imported by `frontend/src/stores/chat.js`, do not dynamically import it in `SettingsDrawer.vue` for bundle splitting. Either import it statically once or move upload handling to a lazily loaded component that owns all document API imports.

- [ ] **Step 4: Preserve owner-only delete behavior**

Keep:

- Owner-only delete button.
- Revalidation through `getKnowledgeBase(kb.id)`.
- Clearing selected knowledge base after successful delete.

- [ ] **Step 5: Build frontend**

Run:

```powershell
npm run build
```

from `frontend/`.

Expected:

```text
build succeeds
no application compile errors
no ineffective dynamic import warning for src/api/document.js
```

- [ ] **Step 6: Run frontend source tests**

Run:

```powershell
pytest tests/test_frontend_delete_knowledge_base.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit**

```powershell
git add frontend tests/test_frontend_delete_knowledge_base.py
git commit -m "refactor: normalize frontend API paths"
```

Acceptance:

- All frontend API calls use `/api`.
- Vite proxy is simple enough to match production reverse proxy behavior.
- Existing delete knowledge base UI behavior remains intact.

---

## Task 9: Add Health Checks And Observability

**Files:**

- Create: `api/routers/health.py`
- Modify: `api/main.py`
- Modify: `core/logging.py`
- Test: `tests/api/test_health.py`

- [ ] **Step 1: Add health tests**

Create tests:

- `/api/health` returns `{"status": "ok"}` without external service checks.
- `/api/health/dependencies` reports PostgreSQL, Redis, Qdrant, and Elasticsearch statuses.

- [ ] **Step 2: Implement lightweight health endpoint**

`GET /api/health`:

```json
{
  "status": "ok",
  "service": "biggraph",
  "version": "1.0.0"
}
```

- [ ] **Step 3: Implement dependency health endpoint**

`GET /api/health/dependencies`:

```json
{
  "status": "degraded",
  "dependencies": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "unavailable",
    "elasticsearch": "ok"
  }
}
```

Policy:

- `ok` only when all dependencies are reachable.
- `degraded` when any optional dependency is unavailable.
- `failed` when PostgreSQL is unavailable.

- [ ] **Step 4: Confirm request id logging**

Every API response should include or log a request id. Errors must log `request_id`.

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/api/test_health.py -q
pytest -q
```

Expected:

```text
health tests pass
full suite passes
```

- [ ] **Step 6: Commit**

```powershell
git add api/routers/health.py api/main.py core/logging.py tests/api/test_health.py
git commit -m "feat: add health checks"
```

Acceptance:

- Health endpoint does not fail just because Qdrant/ES are offline.
- Dependency endpoint gives operators enough information to diagnose startup issues.

---

## Task 10: Documentation And Developer Workflow

**Files:**

- Create: `docs/architecture/backend-refactor.md`
- Create: `docs/architecture/api-contract.md`
- Modify: `docs/roadmap.md`
- Modify: `start_web.bat`
- Create or modify: `README.md` if absent

- [ ] **Step 1: Document backend architecture**

`docs/architecture/backend-refactor.md` must include:

- App factory.
- Router modules.
- Service modules.
- Storage modules.
- Background job boundary.
- Authorization model.
- Error response format.

- [ ] **Step 2: Document API contract**

`docs/architecture/api-contract.md` must list:

- Method.
- Path.
- Auth requirement.
- Request fields.
- Response fields.
- Error codes.

Minimum covered resources:

- Auth.
- Knowledge bases.
- Documents.
- Search.
- Chat.
- PPT.
- Health.

- [ ] **Step 3: Update startup instructions**

Document:

```powershell
python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Document frontend:

```powershell
cd frontend
npm run dev
```

- [ ] **Step 4: Add verification checklist**

Documentation must include:

```powershell
pytest -q
cd frontend
npm run build
```

- [ ] **Step 5: Run verification**

Run:

```powershell
pytest -q
```

Run from `frontend/`:

```powershell
npm run build
```

Expected:

```text
backend tests pass
frontend build succeeds
```

- [ ] **Step 6: Commit**

```powershell
git add docs README.md start_web.bat
git commit -m "docs: document refactored architecture and workflow"
```

Acceptance:

- A new engineer can start backend and frontend from documented commands.
- API paths in docs match frontend code.
- Docs use UTF-8 and render readable Chinese/English text.

---

## Final Full-System Acceptance Checklist

The refactor is complete only when every item below is checked.

- [ ] `pytest -q` passes from repository root.
- [ ] `npm run build` passes from `frontend/`.
- [ ] `python -c "from api.main import create_app; app = create_app(); print(len(app.routes))"` succeeds.
- [ ] Production settings validation rejects missing `JWT_SECRET_KEY`.
- [ ] All backend routes are registered outside `if __name__ == "__main__"`.
- [ ] Frontend API calls use `/api/...` consistently.
- [ ] Knowledge-base delete works from frontend and backend.
- [ ] Owner-only authorization is tested.
- [ ] Member read/search authorization is tested.
- [ ] Cross-tenant access rejection is tested.
- [ ] Chat session ownership is tested.
- [ ] Document upload rejects unsupported file types.
- [ ] Document upload has file size validation.
- [ ] Ingestion failures are visible through job status.
- [ ] Qdrant and ES cleanup failures are recorded or queued for retry.
- [ ] Hybrid retrieval is used by the canonical search endpoint.
- [ ] PPT background task saves assistant replies correctly.
- [ ] PPT status survives frontend refresh.
- [ ] Health endpoints exist and are documented.
- [ ] `.env.example` exists and contains no real secrets.
- [ ] Architecture and API contract docs are current.
- [ ] No new garbled Chinese text is introduced in touched UTF-8 files.
- [ ] Existing user changes are preserved unless explicitly superseded by this plan.

---

## Risk Register

| Risk | Impact | Mitigation | Acceptance Signal |
| --- | --- | --- | --- |
| Route migration breaks existing frontend calls | Users see 404s | Keep compatibility routes until frontend migration is complete | Old and new route tests pass during transition |
| External services are unavailable in local tests | Tests become flaky | Use dependency injection and mocks for unit/API tests | `pytest -q` does not require Qdrant/ES/Redis unless explicitly marked integration |
| Cascade delete removes too much data | Data loss | Require owner check before delete and unit-test repository filters | Non-owner/cross-tenant delete tests pass |
| PPT generation remains tied to in-process threads | Lost jobs on restart | Introduce task service interface first, then swap runner later | Status persists outside thread-local memory |
| Token storage remains XSS-sensitive | Account compromise after XSS | Document current risk and plan HttpOnly cookie migration separately | Security doc explicitly marks current localStorage model as accepted or replaced |
| Encoding cleanup touches too many files | Large noisy diff | Only normalize files touched by this refactor unless a dedicated encoding task is approved | No unrelated doc/source churn |

---

## Suggested Child Plans

This master plan should be executed through smaller child plans in this order:

1. `backend-app-factory-and-settings`
2. `knowledge-base-lifecycle-and-authorization`
3. `ingestion-service-and-job-status`
4. `hybrid-search-service`
5. `ppt-task-service`
6. `frontend-api-normalization`
7. `health-observability-and-docs`

Each child plan should be saved under `docs/superpowers/plans/` and should include the exact tests for that subsystem.

---

## Self-Review

Spec coverage:

- Backend composition is covered by Tasks 1, 9, and 10.
- Runtime security is covered by Task 2.
- Knowledge-base deletion and authorization are covered by Tasks 3 and 4.
- Ingestion and search are covered by Tasks 5 and 6.
- PPT reliability is covered by Task 7.
- Frontend API cleanup is covered by Task 8.
- Documentation and workflow are covered by Task 10.

Placeholder scan:

- The document contains no unfinished placeholder markers.
- The document contains no fake task steps that can be marked complete without real implementation.
- The only intentionally broad sections are marked as child plans and have concrete acceptance gates.

Type and naming consistency:

- Canonical app factory is `api.main:create_app`.
- Canonical API prefix is `/api`.
- Canonical knowledge-base path is `/api/knowledge_bases`.
- Canonical service names use `services/*_service.py`.
