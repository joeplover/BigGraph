# BigGraph

BigGraph is a FastAPI + Vue application for knowledge-base RAG, document ingestion, chat sessions, and PPT agent workflows.

## Runtime

- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Qdrant
- Elasticsearch
- Vue 3 + Vite

## Backend

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the refactored API entrypoint:

```powershell
python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Health checks:

```powershell
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/health/dependencies
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend calls backend APIs through the canonical `/api/...` prefix. In development, Vite proxies `/api` to `http://localhost:8000`.

## Configuration

Copy `.env.example` and fill local values. Production mode requires real secrets:

- `JWT_SECRET_KEY`
- PostgreSQL password or `DATABASE_URL`
- Elasticsearch password
- embedding API key

Runtime validation is available through:

```powershell
python -c "from config.settings import settings; settings.validate_for_runtime()"
```

## Verification

Run backend tests from repository root:

```powershell
pytest -q
```

Run frontend build:

```powershell
cd frontend
npm run build
cd ..
```

Run API import smoke test:

```powershell
python -c "from api.main import create_app; app = create_app(); print(len(app.routes))"
```

## Architecture Documents

- `docs/architecture/backend-refactor.md`
- `docs/architecture/api-contract.md`
- `docs/superpowers/plans/2026-06-22-biggraph-full-refactor-acceptance-plan.md`

## Current Canonical APIs

- `/api/auth/*`
- `/api/knowledge_bases/*`
- `/api/upload/{knowledge_base_id}`
- `/api/jobs/{job_id}`
- `/api/documents/{doc_id}`
- `/api/search/{knowledge_base_id}`
- `/api/chat/*`
- `/api/ppt/*`
- `/api/health`
