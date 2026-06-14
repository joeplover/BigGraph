# =============================================================================
# Frontend Dockerfile — BigGraph Vue3 前端
# 多阶段构建：Stage 1 编译 → Stage 2 Nginx 运行
# =============================================================================

# ---- Stage 1: 构建 ----
FROM node:20-alpine AS builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Nginx 运行 ----
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

# 自定义 Nginx 配置（含 SPA 路由回退 + API 代理）
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]