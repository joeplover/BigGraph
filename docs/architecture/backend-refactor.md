# BigGraph 后端重构架构说明

## 入口与应用组合

当前后端标准入口是 `api.main:create_app`，本地启动命令如下：

```powershell
python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
```

`api/main.py` 负责创建 FastAPI 应用、注册 `RequestIDMiddleware`、挂载健康检查，并把迁移期仍在 `api/ragControll.py`、`api/auth.py`、`api/ppt_agent_router.py` 中的路由统一暴露到 `/api` 前缀下。`api/ragControll.py` 仍保留兼容路由与静态兜底，但新的运行入口不再依赖 `if __name__ == "__main__"`。

## 分层边界

后端按以下边界演进：

- API 层：解析 HTTP 请求、调用认证依赖、执行轻量参数校验、调用服务层。
- Service 层：承载业务规则和跨存储编排。
- Storage 层：只处理 PostgreSQL、Redis、Qdrant、Elasticsearch 的读写原语。
- Core 层：承载解析、切片、embedding、混合检索等算法能力。

当前已落地的服务模块：

- `services/kb_service.py`：知识库存在性、租户隔离、owner 权限、成员访问权限。核心守卫包括 `require_kb_owner`、`require_kb_access`、`require_kb_editor_or_owner`。
- `services/chat_service.py`：聊天会话归属校验，核心守卫为 `require_chat_session_owner`。
- `services/search_service.py`：统一检索入口，封装 `core.retrieval.hybrid.HybridRetrievalService`，返回 API 使用的稳定结果结构。

## 权限模型

知识库权限遵循以下规则：

- owner 可以查看、分享、审批成员、上传、搜索和删除自己的知识库。
- approved member 可以查看和搜索已加入的知识库。
- pending member 不能查看和搜索。
- 跨租户访问返回 403 或 404，当前统一由 `ErrorCode.TENANT_MISMATCH` 返回 403。
- 上传和删除文档暂时为 owner-only，后续如启用 editor 角色，必须先扩展 `require_kb_editor_or_owner` 的测试。

聊天会话权限遵循以下规则：

- 会话元数据保存在 Redis，包含 `user_id`。
- 读取历史、重命名、删除、继续向某个 session 写入消息前，必须调用 `require_chat_session_owner`。
- 非 owner 访问返回 403。

## 数据生命周期

知识库删除流程：

1. `require_kb_owner` 校验 owner 与租户。
2. PostgreSQL 删除分片、导入任务、文档、上传文件、成员、知识库记录。
3. Qdrant 按 `tenant_id + knowledge_base_id` 删除向量。
4. Elasticsearch 按 `knowledge_base_id` 删除全文索引。
5. 外部清理失败会写入 `cleanup_errors` 并记录日志，不再静默吞掉。

文档删除流程：

1. 加载文档。
2. 使用文档的 `knowledge_base_id` 调用 `require_kb_editor_or_owner`。
3. PostgreSQL 标记文档 deleted，并删除文档分片。
4. Qdrant 和 Elasticsearch 清理失败会进入 `cleanup_errors`。

## 导入任务状态

上传接口 `POST /api/upload/{knowledge_base_id}` 只负责鉴权、格式/大小校验、保存上传文件、创建导入任务并提交后台处理。任务状态通过 `GET /api/jobs/{job_id}` 查询。

内部阶段 `status` 保留详细进度：

- `pending`
- `parsing`
- `cleaning`
- `chunking`
- `embedding`
- `indexing`
- `completed`
- `failed`
- `cancelled`

API 额外返回前端稳定状态 `state`：

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

失败响应包含稳定 `error_code`，当前导入失败为 `ingestion_failed`，并返回 `error_message` 给前端展示。

## 检索架构

`services/search_service.py` 是 API 的唯一检索入口。路由 `/api/search/{knowledge_base_id}` 只做认证、知识库访问授权，然后调用 `SearchService.search(...)`。

`SearchService` 使用 `HybridRetrievalService` 执行：

- query embedding
- Qdrant dense retrieval
- Elasticsearch BM25 retrieval
- reciprocal rank fusion
- Elasticsearch full content 补全

API 返回稳定字段：`chunk_id`、`document_id`、`file_id`、`file_name`、`content`、`score`、`rrf_score`、`bm25_score`、`page_start`、`page_end`、`content_type`、`heading_path`、`keywords`、`token_count`。

## 错误响应

业务错误统一通过 `storage/error_codes.py` 中的 `ErrorCode` 构造 `HTTPException`。全局异常处理器将未捕获异常转为标准 500 响应。请求日志由 `RequestIDMiddleware` 记录 request id、方法、路径和状态码。

## 验证命令

```powershell
pytest -q
cd frontend
npm run build
cd ..
python -c "from api.main import create_app; app = create_app(); print(len(app.routes))"
```
