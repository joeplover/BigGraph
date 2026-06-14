# =============================================================================
# Embedding 服务 Dockerfile — llama.cpp + bge-m3 GGUF
# 多阶段构建：Stage 1 编译 llama.cpp → Stage 2 运行
# =============================================================================

# ---- Stage 1: 编译 llama.cpp ----
FROM ubuntu:22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global http.sslverify false && \
    git clone --depth 1 https://github.com/ggerganov/llama.cpp.git /llama
WORKDIR /llama
RUN mkdir build && cd build && cmake .. -DBUILD_SHARED_LIBS=OFF && make llama-server -j$(nproc)

# ---- Stage 2: 运行（最小化镜像） ----
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /llama/build/bin/llama-server /usr/local/bin/llama-server

EXPOSE 1233

# 模型文件通过 docker-compose volume 挂载到 /model/ 目录
CMD ["llama-server", "-m", "/model/bge-m3-Q4_K_M.gguf", "--host", "0.0.0.0", "--port", "1233", "--embedding", "--ctx-size", "8192", "--ubatch-size", "1024"]