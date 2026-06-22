# Main Sync Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the in-progress merge by integrating `codex/full-refactor` with the latest `origin/main` without losing either the latest main member-management features or the refactor acceptance gates.

**Architecture:** Keep `origin/main` as the authoritative base, then manually merge the refactor branch into the six conflicting files. Backend route conflicts must preserve latest main behavior and route additions while delegating authorization/search/deletion cleanup to the refactor service layer. Storage conflicts must keep the clearer `*_knowledge_base*` methods and add old-name aliases for compatibility with latest main callers.

**Tech Stack:** FastAPI, SQLAlchemy/Postgres, Qdrant, Elasticsearch, Vue 3, Vite, Element Plus, pytest, npm build.

---

## Evidence

- Current branch: `main`
- Current HEAD: `e685a2fcbb1202264f4e44063d5ae36de614eb0c`
- Current `origin/main`: `e685a2fcbb1202264f4e44063d5ae36de614eb0c`
- Refactor branch: `codex/full-refactor`
- Refactor commit: `5308303 refactor: harden BigGraph architecture and acceptance gates`
- Merge base between refactor and latest main: `2bb924137898ec643e430032f7864ca434cf65d4`
- Diagnosis: the refactor commit was based on stale main; latest main contains later commits from `2bb9241..e685a2f`.

## Files To Resolve

- Modify: `api/ragControll.py`
  - Preserve latest main startup index initialization, member reject/remove routes, member display names, and access-aware search permission.
  - Preserve refactor service-layer authorization, upload validation, search delegation, deletion response contract, and chat session ownership.
- Modify: `frontend/src/api/knowledgeBase.js`
  - Preserve latest main `rejectMember` and `removeMember`.
  - Preserve refactor `/api/...` route prefix for every exported function.
- Modify: `frontend/src/views/chat/SettingsDrawer.vue`
  - Preserve latest main `成员审核` navigation.
  - Preserve refactor delete icon/loading state and owner revalidation before deletion.
- Modify: `storage/postgres.py`
  - Preserve latest main `delete_member`.
  - Preserve/refactor `user_can_access`.
  - Keep `delete_by_knowledge_base(...)` methods and add `delete_by_kb(...)` aliases.
- Modify: `storage/qdrant.py`
  - Keep `delete_knowledge_base_vectors(...)` and add `delete_kb_vectors(...)` alias.
- Modify: `storage/elasticsearch.py`
  - Keep `delete_knowledge_base_chunks(...)` and add `delete_kb_chunks(...)` alias.
- Modify: `start_web.bat`
  - Keep the one-click launcher and fix nested quoting in `start` commands.

## Task 1: Resolve Backend Route Conflict

**Files:**
- Modify: `api/ragControll.py`
- Test: `tests/api/test_search_route.py`
- Test: `tests/api/test_authorization.py`
- Test: `tests/api/test_upload_validation.py`
- Test: `tests/api/test_document_delete.py`
- Test: `tests/test_backend_delete_knowledge_base.py`

- [ ] **Step 1: Preserve latest main imports and refactor service imports**

Ensure the imports include all of these names:

```python
from storage.postgres import (
    DocumentChunkStore,
    DocumentStore,
    IngestionJobStore,
    KbMemberStore,
    KnowledgeBaseStore,
    UploadedFileStore,
    UserStore,
    get_session,
)
from services.chat_service import require_chat_session_owner
from services.kb_service import require_kb_access, require_kb_editor_or_owner, require_kb_owner
from services.search_service import SearchService
```

- [ ] **Step 2: Preserve startup initialization**

Keep the latest main lifespan behavior:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    try:
        _es.ensure_index()
    except Exception:
        logger.warning("Elasticsearch 索引初始化失败（可稍后自动创建）")
    try:
        _qdrant.ensure_collection()
    except Exception:
        logger.warning("Qdrant 集合初始化失败（可稍后自动创建）")
    logger.info("数据库表已就绪")
    yield
```

- [ ] **Step 3: Merge member-management routes with centralized owner checks**

The approve, reject, remove, and list routes must call `require_kb_owner(db, kb_id, user)` before touching member records. The reject and remove endpoints must remain:

```python
@app.post("/knowledge_bases/{kb_id}/members/{member_id}/reject")
async def reject_kb_member(kb_id: str, member_id: str, user: dict = Depends(get_current_user)):
    with get_session() as db:
        require_kb_owner(db, kb_id, user)
        member = KbMemberStore.get(db, member_id)
        if not member or str(member.knowledge_base_id) != kb_id:
            raise ErrorCode.NOT_FOUND.exception(detail="成员申请不存在")
        if member.status != KbMemberStatus.pending:
            raise ErrorCode.CONFLICT.exception(detail=f"该申请已被{member.status.value}")
        KbMemberStore.update_status(db, member_id, KbMemberStatus.rejected)
        return {"message": "已拒绝加入", "member_id": member_id, "status": "rejected"}


@app.delete("/knowledge_bases/{kb_id}/members/{member_id}")
async def remove_kb_member(kb_id: str, member_id: str, user: dict = Depends(get_current_user)):
    with get_session() as db:
        require_kb_owner(db, kb_id, user)
        member = KbMemberStore.get(db, member_id)
        if not member or str(member.knowledge_base_id) != kb_id:
            raise ErrorCode.NOT_FOUND.exception(detail="成员记录不存在")
        KbMemberStore.delete_member(db, member_id)
        return {"message": "已移除成员", "member_id": member_id}
```

- [ ] **Step 4: Keep display names in member list**

The list route must still enrich members with `UserStore.get(...)`:

```python
member_user = UserStore.get(db, str(m.user_id))
display_name = member_user.display_name if member_user else str(m.user_id)[:8]
```

- [ ] **Step 5: Resolve search route in favor of service delegation**

Replace the conflict block with:

```python
with get_session() as db:
    kb = require_kb_access(db, knowledge_base_id, user)
    tenant_id = kb.tenant_id

results = _search_service.search(
    query=query,
    tenant_id=tenant_id,
    knowledge_base_id=knowledge_base_id,
    limit=limit,
)
```

Run:

```powershell
pytest tests/api/test_search_route.py -q
```

Expected: search route tests pass.

- [ ] **Step 6: Resolve knowledge-base delete route in favor of explicit cleanup contract**

Keep the refactor response shape:

```python
{
    "message": "知识库已删除",
    "deleted": {
        "chunks": deleted_chunks,
        "jobs": deleted_jobs,
        "documents": deleted_documents,
        "files": deleted_files,
        "members": deleted_members,
        "knowledge_bases": deleted_kb,
    },
    "cleanup_errors": cleanup_errors,
}
```

Use the new method names in this route:

```python
DocumentChunkStore.delete_by_knowledge_base(db, kb_id)
IngestionJobStore.delete_by_knowledge_base(db, kb_id)
DocumentStore.delete_by_knowledge_base(db, kb_id)
UploadedFileStore.delete_by_knowledge_base(db, kb_id)
KbMemberStore.delete_by_knowledge_base(db, kb_id)
_qdrant.delete_knowledge_base_vectors(tenant_id=tenant_id, knowledge_base_id=kb_id)
_es.delete_knowledge_base_chunks(knowledge_base_id=kb_id)
```

Run:

```powershell
pytest tests/test_backend_delete_knowledge_base.py tests/api/test_document_delete.py -q
```

Expected: deletion tests pass.

## Task 2: Resolve Storage Compatibility Conflicts

**Files:**
- Modify: `storage/postgres.py`
- Modify: `storage/qdrant.py`
- Modify: `storage/elasticsearch.py`
- Test: `tests/test_backend_delete_knowledge_base.py`

- [ ] **Step 1: Keep both Postgres deletion method names**

`UploadedFileStore` must include:

```python
@staticmethod
def delete_by_knowledge_base(db: Session, knowledge_base_id: str) -> int:
    count = db.query(UploadedFile).filter(
        UploadedFile.knowledge_base_id == knowledge_base_id,
    ).delete(synchronize_session="fetch")
    db.flush()
    return count

@staticmethod
def delete_by_kb(db: Session, kb_id: str) -> int:
    return UploadedFileStore.delete_by_knowledge_base(db, kb_id)
```

`DocumentStore` must include:

```python
@staticmethod
def delete_by_knowledge_base(db: Session, knowledge_base_id: str) -> int:
    count = db.query(Document).filter(
        Document.knowledge_base_id == knowledge_base_id,
    ).delete(synchronize_session="fetch")
    db.flush()
    return count

@staticmethod
def delete_by_kb(db: Session, kb_id: str) -> int:
    return DocumentStore.delete_by_knowledge_base(db, kb_id)
```

`DocumentChunkStore` must include:

```python
@staticmethod
def delete_by_knowledge_base(db: Session, knowledge_base_id: str) -> int:
    count = db.query(DocumentChunk).filter(
        DocumentChunk.knowledge_base_id == knowledge_base_id,
    ).delete(synchronize_session="fetch")
    db.flush()
    return count

@staticmethod
def delete_by_kb(db: Session, kb_id: str) -> int:
    return DocumentChunkStore.delete_by_knowledge_base(db, kb_id)
```

`IngestionJobStore` must include:

```python
@staticmethod
def delete_by_knowledge_base(db: Session, knowledge_base_id: str) -> int:
    count = db.query(IngestionJob).filter(
        IngestionJob.knowledge_base_id == knowledge_base_id,
    ).delete(synchronize_session="fetch")
    db.flush()
    return count

@staticmethod
def delete_by_kb(db: Session, kb_id: str) -> int:
    return IngestionJobStore.delete_by_knowledge_base(db, kb_id)
```

`KbMemberStore` must include:

```python
@staticmethod
def delete_by_knowledge_base(db: Session, knowledge_base_id: str) -> int:
    count = db.query(KbMember).filter(
        KbMember.knowledge_base_id == knowledge_base_id,
    ).delete(synchronize_session="fetch")
    db.flush()
    return count

@staticmethod
def delete_by_kb(db: Session, kb_id: str) -> int:
    return KbMemberStore.delete_by_knowledge_base(db, kb_id)
```

- [ ] **Step 2: Keep latest main member deletion helper**

`KbMemberStore` must include:

```python
@staticmethod
def delete_member(db: Session, member_id: str) -> bool:
    member = db.get(KbMember, member_id)
    if not member:
        return False
    db.delete(member)
    db.flush()
    return True
```

- [ ] **Step 3: Keep Qdrant method and alias**

`storage/qdrant.py` must include:

```python
def delete_knowledge_base_vectors(self, tenant_id: str, knowledge_base_id: str) -> None:
    self.client.delete(
        collection_name=self.collection,
        points_selector=Filter(must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="knowledge_base_id", match=MatchValue(value=knowledge_base_id)),
        ]),
    )

def delete_kb_vectors(self, tenant_id: str, knowledge_base_id: str) -> None:
    return self.delete_knowledge_base_vectors(tenant_id, knowledge_base_id)
```

- [ ] **Step 4: Keep Elasticsearch method and alias**

`storage/elasticsearch.py` must include:

```python
def delete_knowledge_base_chunks(self, knowledge_base_id: str) -> Any:
    return self.client.delete_by_query(
        index=self.index,
        body={"query": {"term": {"knowledge_base_id": knowledge_base_id}}},
        refresh=True,
    )

def delete_kb_chunks(self, knowledge_base_id: str) -> Any:
    return self.delete_knowledge_base_chunks(knowledge_base_id)
```

- [ ] **Step 5: Run storage/deletion tests**

Run:

```powershell
pytest tests/test_backend_delete_knowledge_base.py tests/api/test_document_delete.py -q
```

Expected: tests pass.

## Task 3: Resolve Frontend API And Drawer Conflicts

**Files:**
- Modify: `frontend/src/api/knowledgeBase.js`
- Modify: `frontend/src/views/chat/SettingsDrawer.vue`
- Test: `tests/test_frontend_delete_knowledge_base.py`
- Test: `frontend` build

- [ ] **Step 1: Normalize every knowledge-base API route to `/api/...`**

`frontend/src/api/knowledgeBase.js` must export all of these functions:

```javascript
export function getMyKnowledgeBases() {
  return request.get('/api/knowledge_bases/')
}

export function createKnowledgeBase(name, description = '') {
  return request.post('/api/knowledge_bases/', null, {
    params: { name, description },
  })
}

export function getKnowledgeBase(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}`)
}

export function shareKnowledgeBase(kbId) {
  return request.post(`/api/knowledge_bases/${kbId}/share`)
}

export function joinKnowledgeBase(shareCode) {
  return request.post(`/api/knowledge_bases/join/${shareCode}`)
}

export function approveMember(kbId, memberId) {
  return request.post(`/api/knowledge_bases/${kbId}/members/${memberId}/approve`)
}

export function rejectMember(kbId, memberId) {
  return request.post(`/api/knowledge_bases/${kbId}/members/${memberId}/reject`)
}

export function removeMember(kbId, memberId) {
  return request.delete(`/api/knowledge_bases/${kbId}/members/${memberId}`)
}

export function getMembers(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}/members`)
}

export function deleteKnowledgeBase(kbId) {
  return request.delete(`/api/knowledge_bases/${kbId}`)
}
```

- [ ] **Step 2: Preserve SettingsDrawer member audit navigation**

The management section must keep:

```vue
<el-button size="small" class="action-btn" @click="goToMembers">
  成员审核
</el-button>
```

The script must keep:

```javascript
function goToMembers() {
  router.push('/kb-members')
}
```

- [ ] **Step 3: Preserve refactor delete UX and authorization revalidation**

The delete button must use `Delete` and loading state:

```vue
<el-button
  v-if="kb.is_owner"
  text
  size="small"
  type="danger"
  :icon="Delete"
  :loading="deletingKbId === kb.id"
  @click="handleDeleteKb(kb)"
>
  删除
</el-button>
```

The imports must include:

```javascript
import { Delete, Upload } from '@element-plus/icons-vue'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBase,
  joinKnowledgeBase,
  shareKnowledgeBase,
} from '@/api/knowledgeBase'
import { getJobStatus, uploadFile } from '@/api/document'
```

- [ ] **Step 4: Run frontend contract tests and build**

Run:

```powershell
pytest tests/test_frontend_delete_knowledge_base.py -q
```

Expected: frontend static contract test passes.

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: build exits with code 0. Known VueUse annotation warnings and chunk-size warnings are acceptable.

## Task 4: Fix One-Click Windows Launcher Quoting

**Files:**
- Modify: `start_web.bat`

- [ ] **Step 1: Fix nested quoting in backend start command**

Use:

```bat
start "BigGraph Backend API" cmd /k "cd /d ""%ROOT%"" && python -m uvicorn api.main:create_app --factory --host %BACKEND_HOST% --port %BACKEND_PORT%"
```

- [ ] **Step 2: Fix nested quoting in frontend start command**

Use:

```bat
start "BigGraph Frontend" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev -- --host %FRONTEND_HOST% --port %FRONTEND_PORT%"
```

- [ ] **Step 3: Validate script syntax by inspection**

Run:

```powershell
cmd /c start_web.bat
```

Expected: it opens backend and frontend terminal windows and opens `http://127.0.0.1:3002`. Close the two spawned terminal windows after smoke testing.

## Task 5: Final Merge Verification

**Files:**
- Modify/stage only resolved source files and docs.
- Do not stage: `logs/biggraph.log`
- Do not stage: `logs/biggraph.log.2026-06-12`
- Do not stage: `emb/`

- [ ] **Step 1: Confirm no conflict markers remain**

Run:

```powershell
git diff --check
```

Expected: no `leftover conflict marker` output.

- [ ] **Step 2: Confirm unresolved-file list is empty**

Run:

```powershell
git diff --name-only --diff-filter=U
```

Expected: no file paths printed.

- [ ] **Step 3: Run full backend test suite**

Run:

```powershell
pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Run frontend production build**

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: build exits with code 0.

- [ ] **Step 5: Run app factory smoke test**

Run:

```powershell
python -c "from api.main import create_app; app = create_app(); print(len(app.routes))"
```

Expected: prints a route count and exits with code 0.

- [ ] **Step 6: Stage only intended files**

Run:

```powershell
git add .env.example README.md api/main.py api/ppt_agent_router.py api/ragControll.py config/settings.py core/auth/jwt.py docs/architecture/api-contract.md docs/architecture/backend-refactor.md docs/superpowers/plans/2026-06-22-biggraph-full-refactor-acceptance-plan.md docs/superpowers/plans/2026-06-22-main-sync-recovery-plan.md frontend/src/api/auth.js frontend/src/api/document.js frontend/src/api/knowledgeBase.js frontend/src/api/request.js frontend/src/views/chat/SettingsDrawer.vue frontend/vite.config.js pytest.ini services/__init__.py services/chat_service.py services/kb_service.py services/search_service.py start_web.bat storage/elasticsearch.py storage/postgres.py storage/ppt_state_store.py storage/qdrant.py storage/redis_client.py tests/api/test_app_routes.py tests/api/test_authorization.py tests/api/test_chat_authorization.py tests/api/test_document_delete.py tests/api/test_health.py tests/api/test_job_status.py tests/api/test_ppt_router.py tests/api/test_ppt_status.py tests/api/test_search_route.py tests/api/test_upload_validation.py tests/services/test_search_service.py tests/test_backend_delete_knowledge_base.py tests/test_documentation_acceptance.py tests/test_frontend_delete_knowledge_base.py tests/test_settings.py
```

Expected: `git status --short --branch` shows no `UU` entries and does not stage `emb/` or log files.

- [ ] **Step 7: Commit the merge**

Run:

```powershell
git commit -m "merge: integrate full refactor with latest main"
```

Expected: merge commit succeeds.

## Acceptance Criteria

- `main` remains based on latest `origin/main` commit `e685a2fcbb1202264f4e44063d5ae36de614eb0c`.
- No latest main member-management feature is lost:
  - `/knowledge_bases/{kb_id}/members/{member_id}/reject`
  - `DELETE /knowledge_bases/{kb_id}/members/{member_id}`
  - `/kb-members` frontend route
  - `KbMembers.vue` calls `rejectMember` and `removeMember`
  - member list includes `display_name`
- No refactor acceptance gate is lost:
  - `api.main:create_app`
  - centralized KB authorization
  - chat session ownership checks
  - upload type/size validation
  - search route delegates to `SearchService`
  - document and knowledge-base deletion report `cleanup_errors`
  - frontend KB API paths use `/api/...`
- `git diff --check` has no conflict markers.
- `git diff --name-only --diff-filter=U` is empty.
- `pytest -q` exits with code 0.
- `npm run build` exits with code 0.
- App factory smoke test exits with code 0.
- `emb/`, `logs/biggraph.log`, and `logs/biggraph.log.2026-06-12` are not staged.
