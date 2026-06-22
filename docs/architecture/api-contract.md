# BigGraph API Contract

Base URL: `/api`

All protected endpoints require:

```http
Authorization: Bearer <access_token>
```

Errors use FastAPI `HTTPException.detail` and the HTTP status encoded by `storage.error_codes.ErrorCode`.

## Auth

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/send-code` | No | email payload | verification send result |
| POST | `/api/auth/register` | No | username, email, password, code | user and token data |
| POST | `/api/auth/login` | No | username/email and password | access token, refresh token, user |
| POST | `/api/auth/refresh` | No | refresh token | renewed access token |
| GET | `/api/auth/me` | Yes | none | current user |
| POST | `/api/auth/logout` | Yes | none | logout result |

Common errors: 400 validation failure, 401 invalid token, 409 duplicate user.

## Knowledge Bases

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/knowledge_bases/` | Yes | none | list of owned and approved joined knowledge bases |
| POST | `/api/knowledge_bases/` | Yes | `name`, optional `description` | created knowledge base |
| GET | `/api/knowledge_bases/{kb_id}` | Yes | path `kb_id` | knowledge base detail |
| POST | `/api/knowledge_bases/{kb_id}/share` | Owner | path `kb_id` | share code |
| POST | `/api/knowledge_bases/join/{share_code}` | Yes | path `share_code` | membership request status |
| POST | `/api/knowledge_bases/{kb_id}/members/{member_id}/approve` | Owner | path ids | approval result |
| GET | `/api/knowledge_bases/{kb_id}/members` | Owner | path `kb_id` | member list |
| DELETE | `/api/knowledge_bases/{kb_id}` | Owner | path `kb_id` | deleted counts and `cleanup_errors` |

Authorization:

- owner can read, share, upload, approve, search, delete.
- approved member can read and search.
- pending member cannot read or search.
- cross-tenant access is rejected.

## Documents And Uploads

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/upload/{knowledge_base_id}` | Owner | multipart `file` | `job_id`, `file_id`, `file_name`, `status` |
| GET | `/api/jobs/{job_id}` | Yes | path `job_id` | status, state, progress, error_code, error_message |
| GET | `/api/documents/{doc_id}` | Yes | path `doc_id` | document detail |
| DELETE | `/api/documents/{doc_id}` | Owner | path `doc_id` | deleted chunk count and `cleanup_errors` |

Upload validation:

- allowed suffixes: `.txt`, `.md`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.html`
- maximum size: `MAX_UPLOAD_BYTES` in `api/ragControll.py`

Job state contract:

- queued: internal status `pending`
- running: `parsing`, `cleaning`, `chunking`, `embedding`, `indexing`
- completed: internal status `completed`
- failed: internal status `failed`, with `error_code = ingestion_failed`
- cancelled: internal status `cancelled`

## Search

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/search/{knowledge_base_id}` | Owner or approved member | query params `query`, optional `limit` | `results`, `query`, `knowledge_base_id` |

`/api/search/{knowledge_base_id}` delegates to `services/search_service.py`.

Each result contains:

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

Common errors: 400 empty query, 403 forbidden, 404 knowledge base not found.

## Chat

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/chat` | Yes | `message`, optional `session_id`, optional `context` | assistant response |
| POST | `/api/chat/sessions` | Yes | none | created session |
| GET | `/api/chat/sessions` | Yes | none | sessions owned by user |
| PATCH | `/api/chat/sessions/{session_id}` | Owner | `title` | rename result |
| GET | `/api/chat/history/{session_id}` | Owner | path `session_id` | messages |
| DELETE | `/api/chat/history/{session_id}` | Owner | path `session_id` | delete result |

Session ownership is enforced by `require_chat_session_owner`.

## PPT Agent

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/ppt/chat` | Current implementation does not require JWT | PPT chat request | next agent response or task state |
| GET | `/api/ppt/status/{session_id}` | Current implementation does not require JWT | path `session_id` | durable PPT status, response, download URL, `error_code` |
| GET | `/api/ppt/stream/{session_id}` | Current implementation does not require JWT | path `session_id` | server-sent task events |
| POST | `/api/ppt/upload` | Current implementation does not require JWT | multipart `file`, `session_id` | material upload result |

PPT background execution stores state outside the in-memory request path so the frontend can refresh and recover status. Failed PPT tasks use `error_code = ppt_generation_failed`.

## Health

| Method | Path | Auth | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | No | none | `{"status":"ok","service":"biggraph","version":"1.0.0"}` |
| GET | `/api/health/dependencies` | No | none | aggregate status for PostgreSQL, Redis, Qdrant, Elasticsearch |

Dependency status policy:

- `ok`: all dependencies are reachable.
- `degraded`: optional dependency unavailable.
- `failed`: PostgreSQL unavailable.
