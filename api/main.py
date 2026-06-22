from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from api.auth import router as auth_router
from api.ppt_agent_router import router as ppt_agent_router
from api.ragControll import app as rag_app
from core.logging import RequestIDMiddleware
from storage.elasticsearch import ElasticsearchService
from storage.postgres import engine, init_db
from storage.qdrant import QdrantService
from storage.redis_client import get_redis


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def _copy_api_routes(target: FastAPI, source_routes, prefix: str = "") -> None:
    for route in source_routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == "/{full_path:path}":
            continue
        target.add_api_route(
            f"{prefix}{route.path}",
            route.endpoint,
            methods=list(route.methods or []),
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            name=route.name,
            include_in_schema=route.include_in_schema,
            response_class=route.response_class,
        )


def _check_postgres() -> str:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return "ok"
    except Exception:
        return "unavailable"


def _check_redis() -> str:
    try:
        get_redis().ping()
        return "ok"
    except Exception:
        return "unavailable"


def _check_qdrant() -> str:
    try:
        QdrantService().client.get_collections()
        return "ok"
    except Exception:
        return "unavailable"


def _check_elasticsearch() -> str:
    try:
        return "ok" if ElasticsearchService().ping() else "unavailable"
    except Exception:
        return "unavailable"


def create_app() -> FastAPI:
    app = FastAPI(title="BigGraph API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "biggraph", "version": "1.0.0"}

    @app.get("/api/health/dependencies")
    async def dependency_health() -> dict[str, object]:
        dependencies = {
            "postgres": _check_postgres(),
            "redis": _check_redis(),
            "qdrant": _check_qdrant(),
            "elasticsearch": _check_elasticsearch(),
        }
        if dependencies["postgres"] != "ok":
            status = "failed"
        elif any(value != "ok" for value in dependencies.values()):
            status = "degraded"
        else:
            status = "ok"
        return {"status": status, "dependencies": dependencies}

    _copy_api_routes(app, rag_app.routes, prefix="/api")
    _copy_api_routes(app, auth_router.routes, prefix="/api")
    _copy_api_routes(app, ppt_agent_router.routes)
    return app


app = create_app()
