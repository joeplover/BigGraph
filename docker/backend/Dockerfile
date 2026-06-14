# =============================================================================
# Backend Dockerfile — BigGraph FastAPI 后端
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# ---- 系统依赖（编译 psycopg、lxml 等原生扩展需要） ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- Python 依赖（排除 Windows 专用包 pywin32） ----
COPY docker/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 项目代码（按模块拷贝，排除无关目录） ----
COPY main.py .
COPY api/ api/
COPY config/ config/
COPY core/ core/
COPY graphs/ graphs/
COPY ppt_agent/ ppt_agent/
COPY ppt_creator/ ppt_creator/
COPY storage/ storage/
COPY scripts/ scripts/
COPY sql/ sql/
COPY tests/ tests/

# ---- 运行时动态目录（由 volume 挂载） ----
RUN mkdir -p /app/uploads /app/logs

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]