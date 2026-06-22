#!/usr/bin/env sh
set -eu

python - <<'PY'
import base64
import os
import socket
import sys
import time
from urllib import error, parse, request


def wait_tcp(name: str, host: str, port: int, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                print(f"[entrypoint] {name} is reachable at {host}:{port}", flush=True)
                return
        except OSError as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"{name} is not reachable at {host}:{port}: {last_error}")


def wait_http(
    name: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            req = request.Request(url, headers=headers or {})
            with request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 500:
                    print(f"[entrypoint] {name} is reachable at {url}", flush=True)
                    return
        except (OSError, error.URLError, error.HTTPError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"{name} is not reachable at {url}: {last_error}")


def int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


try:
    wait_tcp("PostgreSQL", os.getenv("PG_HOST", "127.0.0.1"), int_env("PG_PORT", 5432))
    wait_tcp("Redis", os.getenv("REDIS_HOST", "localhost"), int_env("REDIS_PORT", 6379))

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/") + "/collections"
    qdrant_headers = {}
    if os.getenv("QDRANT_API_KEY"):
        qdrant_headers["api-key"] = os.environ["QDRANT_API_KEY"]
    wait_http("Qdrant", qdrant_url, qdrant_headers)

    es_url = os.getenv("ES_HOSTS", "http://localhost:9200").split(",", 1)[0].rstrip("/") + "/"
    es_headers = {}
    if os.getenv("ES_USER") or os.getenv("ES_PASSWORD"):
        token = f"{os.getenv('ES_USER', '')}:{os.getenv('ES_PASSWORD', '')}".encode()
        es_headers["Authorization"] = "Basic " + base64.b64encode(token).decode()
    wait_http("Elasticsearch", es_url, es_headers)

    embedding_base = os.getenv("EMBEDDING_BASE_URL", "http://localhost:1233/v1")
    parsed = parse.urlparse(embedding_base)
    embedding_health = parse.urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))
    wait_http("Embedding", embedding_health)
except Exception as exc:
    print(f"[entrypoint] dependency check failed: {exc}", file=sys.stderr, flush=True)
    raise
PY

exec "$@"

