# 企业级 RAG Agent Platform 节点级开发流程文档

## 0. 文档说明

本文档用于指导企业级 RAG Agent Platform 的分阶段开发。

系统目标是基于：

- FastAPI
- LangGraph
- LLM
- Embedding Model
- Qdrant
- PostgreSQL / MySQL
- 文件存储
- 异步任务队列

构建一个支持：

- 文档上传
- 文档解析
- 文档切分
- 向量入库
- 知识库问答
- 引用溯源
- 拒答机制
- 权限过滤
- 评测体系
- 业务 Agent 扩展

的企业级知识库与 Agent 工作流平台。

---

# 1. 总体开发目标

系统最终不是一个简单的 RAG Demo，而是一个可扩展的企业知识库 Agent 平台。

核心能力包括：

```text
文档入库
知识检索
问答生成
引用校验
权限控制
评测追踪
业务 Agent 编排
```

系统整体采用：

```text
FastAPI API 层
  ↓
Service 服务层
  ↓
LangGraph 编排层
  ↓
RAG 能力层
  ↓
基础设施层
```

---

# 2. 总体模块划分

```text
app/
  api/
    documents.py
    chat.py
    agents.py
    evals.py

  core/
    config.py
    logging.py
    security.py

  db/
    models.py
    session.py
    repositories/

  graphs/
    router_graph.py

    ingestion/
      graph.py
      nodes.py
      state.py

    rag/
      graph.py
      nodes.py
      state.py

    security/
      graph.py
      nodes.py

    evaluation/
      graph.py
      nodes.py

    agents/
      business_graph.py
      ppt_graph.py
      workflow_graph.py
      crawler_graph.py

  services/
    document_service.py
    parser_service.py
    chunk_service.py
    embedding_service.py
    vector_store_service.py
    retrieval_service.py
    rerank_service.py
    llm_service.py
    permission_service.py
    eval_service.py

  integrations/
    qdrant_client.py
    llm_client.py
    embedding_client.py
    bm25_client.py

  schemas/
    document.py
    chat.py
    agent.py
    eval.py

  workers/
    ingestion_worker.py
    crawler_worker.py

tests/
  test_ingestion.py
  test_rag_query.py
  test_permissions.py
  test_eval.py
```

---

# 3. LangGraph 总体架构

系统拆分为多个子图，不建议把所有节点放进一个巨大 Graph。

```text
AgentRouterGraph
  ├── DocumentIngestionGraph
  ├── RAGQueryGraph
  ├── SecurityGuardGraph
  ├── EvaluationGraph
  └── BusinessAgentGraph
        ├── PPTAgentGraph
        ├── GPTWorkflowGraph
        └── DataCrawlerGraph
```

---

# 4. 全局状态设计

建议所有 Graph 共享一个基础 State。

```python
from typing import TypedDict


class GraphState(TypedDict, total=False):
    """
    GraphState 是 LangGraph 在节点之间传递的全局状态对象。

    可以把它理解为一次任务执行过程中的“上下文容器”：
    - 文档入库节点会往里面写 document_id、file_path、chunks 等字段
    - RAG 检索节点会往里面写 retrieved_docs、reranked_docs 等字段
    - LLM 生成节点会往里面写 answer、citations、grounding_result 等字段
    - 日志和监控节点会往里面写 logs、metrics、status 等字段

    total=False 表示这些字段不是每次都必须存在。
    不同子图、不同节点只需要读取和写入自己负责的字段。
    """

    # =========================
    # 1. 请求与用户身份信息
    # =========================
    # request_id：一次 API 请求的唯一 ID，用于日志追踪和问题排查。
    request_id: str

    # tenant_id：租户 ID，用于多租户隔离。所有检索、入库、权限判断都必须带上它。
    tenant_id: str

    # user_id：当前用户 ID，用于权限判断、审计日志、个性化上下文。
    user_id: str

    # session_id：会话 ID，用于多轮对话、聊天历史和上下文追踪。
    session_id: str

    # =========================
    # 2. 任务类型与意图识别
    # =========================
    # task_type：任务大类，例如 ingestion、rag_query、ppt、workflow、crawler。
    task_type: str

    # intent：用户意图，例如 qa、summary、compare、extract、ppt、workflow、crawl。
    intent: str

    # =========================
    # 3. 用户问题与 Query 改写
    # =========================
    # user_query：用户原始问题。
    user_query: str

    # rewritten_query：经过 QueryRewriteNode 改写后的检索友好问题。
    rewritten_query: str

    # expanded_queries：MultiQueryNode 生成的多个检索 query，用于提升召回率。
    expanded_queries: list[str]

    # =========================
    # 4. 文档入库相关状态
    # =========================
    # document_id：文档唯一 ID。
    document_id: str

    # knowledge_base_id：知识库 ID，用于区分不同知识库范围。
    knowledge_base_id: str

    # file_path：上传文件的存储路径。
    file_path: str

    # original_filename：用户上传时的原始文件名。
    original_filename: str

    # file_type：文件类型，例如 pdf、docx、txt、md、csv、xlsx、html。
    file_type: str

    # raw_text：ParseDocumentNode 从原始文件中解析出的未清洗文本。
    raw_text: str

    # cleaned_text：CleanTextNode 清洗后的文本。
    cleaned_text: str

    # pages：按页保存的解析结果，通常包含 page、text、tables 等信息。
    pages: list[dict]

    # chunks：ChunkDocumentNode 切分后的文本块列表。
    chunks: list[dict]

    # =========================
    # 5. 元数据与权限信息
    # =========================
    # metadata：文档、chunk 或请求级别的元数据，例如文件名、页码、部门、分类、版本等。
    metadata: dict

    # permissions：当前用户权限信息，例如角色、部门、权限组、ACL 等。
    permissions: dict

    # =========================
    # 6. 检索与重排序状态
    # =========================
    # vector_results：向量检索结果，一般来自 Qdrant。
    vector_results: list[dict]

    # bm25_results：关键词检索结果，一般来自 Elasticsearch、PostgreSQL FTS 或 BM25 服务。
    bm25_results: list[dict]

    # retrieved_docs：向量检索和关键词检索合并去重后的候选文档片段。
    retrieved_docs: list[dict]

    # reranked_docs：RerankNode 重排序后的文档片段。
    reranked_docs: list[dict]

    # metadata_filtered_docs：经过元数据过滤后的文档片段。
    metadata_filtered_docs: list[dict]

    # permitted_docs：经过权限过滤后，用户真正可以访问的文档片段。
    permitted_docs: list[dict]

    # =========================
    # 7. LLM 上下文构造
    # =========================
    # final_context：最终拼接给 LLM 的上下文文本。
    final_context: str

    # context_docs：用于构造 final_context 的原始文档片段列表，CitationNode 会基于它生成引用。
    context_docs: list[dict]

    # =========================
    # 8. Prompt、答案、引用与 Grounding
    # =========================
    # prompt_template：当前任务使用的 Prompt 模板名称，例如 qa_prompt、summary_prompt。
    prompt_template: str

    # answer：LLM 生成的答案正文。
    answer: str

    # raw_llm_response：LLM 原始响应，便于调试和审计。
    raw_llm_response: str

    # citations：答案引用来源，必须来自真实 context_docs，不能由 LLM 编造。
    citations: list[dict]

    # grounding_result：GroundingCheckNode 的校验结果，用于判断答案是否被上下文支持。
    grounding_result: dict

    # =========================
    # 9. 任务状态与错误信息
    # =========================
    # status：当前任务状态，例如 INIT、RUNNING、SUCCESS、FAILED、REFUSED、RETRYING。
    status: str

    # error：当前任务或节点的错误信息。
    error: str

    # retry_count：当前任务或节点已经重试的次数。
    retry_count: int

    # =========================
    # 10. 日志与指标
    # =========================
    # logs：节点执行日志，例如每个节点的输入、输出、耗时、状态。
    logs: list[dict]

    # metrics：性能指标，例如 token 消耗、检索耗时、生成耗时、召回数量。
    metrics: dict
```

> 说明：这个 `GraphState` 是一个“总览版状态对象”，用于帮助理解整个系统有哪些核心状态字段。实际开发时，建议进一步拆分为 `BaseState`、`DocumentIngestionState`、`RAGQueryState`、`SecurityState`、`EvaluationState` 和 `BusinessAgentState`，避免单个 State 过大。

### 4.1 字段分组说明

| 字段组 | 代表字段 | 作用 |
|---|---|---|
| 请求与用户身份 | `request_id`、`tenant_id`、`user_id`、`session_id` | 用于请求追踪、多租户隔离、权限判断和会话管理 |
| 任务类型与意图 | `task_type`、`intent` | 判断当前任务是文档入库、知识问答、PPT、工作流还是爬虫 |
| Query 处理 | `user_query`、`rewritten_query`、`expanded_queries` | 保存用户原始问题、改写后的问题和多路检索问题 |
| 文档入库 | `document_id`、`file_path`、`raw_text`、`cleaned_text`、`chunks` | 支撑文档解析、清洗、切分和入库 |
| 元数据与权限 | `metadata`、`permissions` | 保存文档元数据和用户权限信息 |
| 检索与排序 | `vector_results`、`bm25_results`、`retrieved_docs`、`reranked_docs`、`permitted_docs` | 保存召回、合并、重排序、过滤后的结果 |
| 上下文构造 | `final_context`、`context_docs` | 保存最终传给 LLM 的上下文和对应原始 chunk |
| 答案与校验 | `answer`、`citations`、`grounding_result` | 保存答案、引用来源和事实一致性校验结果 |
| 状态与错误 | `status`、`error`、`retry_count` | 记录任务执行状态、错误和重试次数 |
| 日志与指标 | `logs`、`metrics` | 记录节点日志、耗时、token、召回数量等指标 |

---

# 5. 第一阶段：基础项目搭建

## 5.1 阶段目标

先搭建一个可以运行的后端骨架，为后续文档入库和问答流程打基础。

## 5.2 需要完成的内容

```text
1. 创建 FastAPI 项目
2. 创建配置系统
3. 创建数据库连接
4. 创建 Qdrant 连接
5. 创建 LLM Client
6. 创建 Embedding Client
7. 创建基础日志系统
8. 创建统一异常处理
```

## 5.3 推荐开发顺序

### Step 1：创建 FastAPI 入口

文件：

```text
app/main.py
```

职责：

```text
1. 创建 FastAPI 实例
2. 注册路由
3. 注册异常处理
4. 注册启动和关闭事件
```

示例结构：

```python
from fastapi import FastAPI

from app.api import documents, chat, agents, evals


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise RAG Agent Platform")

    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(evals.router, prefix="/api/evals", tags=["evals"])

    return app


app = create_app()
```

### Step 2：创建配置模块

文件：

```text
app/core/config.py
```

配置内容：

```text
DATABASE_URL
QDRANT_URL
QDRANT_API_KEY
LLM_PROVIDER
LLM_API_KEY
EMBEDDING_PROVIDER
EMBEDDING_API_KEY
UPLOAD_DIR
MAX_UPLOAD_SIZE
```

### Step 3：创建数据库连接

文件：

```text
app/db/session.py
```

职责：

```text
1. 创建数据库 engine
2. 创建 session
3. 提供 FastAPI dependency
```

### Step 4：创建 Qdrant Client

文件：

```text
app/integrations/qdrant_client.py
```

职责：

```text
1. 初始化 Qdrant 客户端
2. 创建 collection
3. upsert points
4. search points
5. delete points
```

### Step 5：创建 LLM Client

文件：

```text
app/integrations/llm_client.py
```

职责：

```text
1. 封装 LLM 调用
2. 支持普通生成
3. 支持结构化输出
4. 支持超时和重试
```

### Step 6：创建 Embedding Client

文件：

```text
app/integrations/embedding_client.py
```

职责：

```text
1. 封装 embedding 模型调用
2. 支持单条 embedding
3. 支持批量 embedding
4. 记录 embedding model 和 dimension
```

## 5.4 第一阶段验收标准

```text
1. FastAPI 可以启动
2. /docs 可以打开
3. 数据库可以连接
4. Qdrant 可以连接
5. LLM Client 可以完成一次测试调用
6. Embedding Client 可以生成一条向量
```

---

# 6. 第二阶段：DocumentIngestionGraph 文档入库图

## 6.1 阶段目标

实现从文档上传到 Qdrant 向量入库的完整闭环。

## 6.2 文档入库总体流程

```text
UploadNode
  ↓
CreateDocumentTaskNode
  ↓
FileTypeDetectNode
  ↓
ParseDocumentNode
  ↓
CleanTextNode
  ↓
ChunkDocumentNode
  ↓
ExtractMetadataNode
  ↓
DedupDocumentNode
  ↓
EmbeddingNode
  ↓
QdrantIndexNode
  ↓
UpdateDocumentStatusNode
```

## 6.3 State 设计

文件：

```text
app/graphs/ingestion/state.py
```

```python
from typing import TypedDict


class IngestionState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    knowledge_base_id: str

    document_id: str
    task_id: str

    file_path: str
    original_filename: str
    file_type: str
    file_hash: str

    raw_text: str
    cleaned_text: str
    pages: list[dict]
    chunks: list[dict]
    embedded_chunks: list[dict]

    metadata: dict
    dedup_result: dict

    indexed_count: int
    collection_name: str

    status: str
    current_step: str
    error_message: str
    retry_count: int
```

---

# 6.4 UploadNode

## 职责

接收用户上传文件，保存到文件存储，并创建 document 记录。

## 输入

```json
{
  "file": "UploadFile",
  "tenant_id": "tenant_xxx",
  "user_id": "user_xxx",
  "knowledge_base_id": "kb_xxx"
}
```

## 输出

```json
{
  "document_id": "doc_xxx",
  "file_path": "/storage/docs/doc_xxx.pdf",
  "original_filename": "xxx.pdf",
  "file_hash": "sha256_xxx"
}
```

## 开发文件

```text
app/api/documents.py
app/services/document_service.py
app/db/models.py
```

## 开发任务

```text
1. 定义 upload API
2. 校验文件大小
3. 校验文件扩展名
4. 计算文件 sha256
5. 保存文件到本地或对象存储
6. 创建 documents 表记录
7. 返回 document_id
```

## 建议支持格式

第一版：

```text
pdf
docx
txt
md
csv
xlsx
html
```

暂不做：

```text
OCR
扫描 PDF
登录态网页抓取
```

## 验收标准

```text
1. 可以上传 PDF
2. 文件能保存到指定目录
3. documents 表有记录
4. 返回 document_id 和 file_path
```

---

# 6.5 CreateDocumentTaskNode

## 职责

创建异步入库任务，记录任务状态。

## 输入

```json
{
  "document_id": "doc_xxx",
  "file_path": "/storage/docs/doc_xxx.pdf"
}
```

## 输出

```json
{
  "task_id": "task_xxx",
  "status": "UPLOADED"
}
```

## 开发文件

```text
app/services/document_service.py
app/workers/ingestion_worker.py
app/db/models.py
```

## 数据表字段

```text
id
document_id
tenant_id
status
current_step
error_message
retry_count
created_at
updated_at
started_at
finished_at
```

## 状态枚举

```text
UPLOADED
PARSING
PARSED
CLEANING
CHUNKING
EMBEDDING
INDEXING
READY
FAILED
RETRYING
```

## 开发任务

```text
1. 创建 ingestion_tasks 表
2. 上传成功后创建任务记录
3. 返回 task_id
4. 支持通过 task_id 查询任务状态
```

## 验收标准

```text
1. 上传文档后自动创建 ingestion_task
2. task 初始状态为 UPLOADED
3. 可以通过接口查询状态
```

---

# 6.6 FileTypeDetectNode

## 职责

识别文件类型，决定后续使用哪个 Parser。

## 输入

```json
{
  "file_path": "/storage/docs/doc_xxx.pdf",
  "original_filename": "xxx.pdf"
}
```

## 输出

```json
{
  "file_type": "pdf",
  "parser": "PdfParser"
}
```

## 开发文件

```text
app/services/parser_service.py
app/graphs/ingestion/nodes.py
```

## 开发任务

```text
1. 根据扩展名判断文件类型
2. 可选：根据 MIME type 二次判断
3. 映射 file_type 到 parser
4. 不支持的类型返回 FAILED
```

## Parser 映射

```text
pdf  -> PdfParser
docx -> DocxParser
txt  -> TxtParser
md   -> MarkdownParser
csv  -> CsvParser
xlsx -> ExcelParser
html -> HtmlParser
```

## 验收标准

```text
1. PDF 能识别为 pdf
2. DOCX 能识别为 docx
3. 未知格式会返回错误
```

---

# 6.7 ParseDocumentNode

## 职责

解析原始文档，提取文本、页码、表格等信息。

## 输入

```json
{
  "file_path": "/storage/docs/doc_xxx.pdf",
  "file_type": "pdf"
}
```

## 输出

```json
{
  "raw_text": "...",
  "pages": [
    {
      "page": 1,
      "text": "...",
      "tables": []
    }
  ]
}
```

## 开发文件

```text
app/services/parser_service.py
app/graphs/ingestion/nodes.py
```

## Parser 选择

| 文件类型 | 推荐库 |
|---|---|
| PDF | PyMuPDF / pdfplumber |
| DOCX | python-docx |
| TXT | 原生读取 |
| MD | markdown / 原生读取 |
| CSV | pandas |
| XLSX | openpyxl / pandas |
| HTML | BeautifulSoup |

## 开发任务

```text
1. 定义 BaseParser 抽象类
2. 实现 PdfParser
3. 实现 TxtParser
4. 实现 DocxParser
5. 后续补充 CSV、XLSX、HTML
6. 返回统一结构：raw_text + pages
```

## BaseParser 示例

```python
from abc import ABC, abstractmethod


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> dict:
        pass
```

## 验收标准

```text
1. PDF 可以提取文本
2. TXT 可以提取文本
3. DOCX 可以提取文本
4. pages 中保留页码信息
```

---

# 6.8 CleanTextNode

## 职责

清洗解析出来的文本。

## 输入

```json
{
  "raw_text": "..."
}
```

## 输出

```json
{
  "cleaned_text": "..."
}
```

## 开发文件

```text
app/services/chunk_service.py
app/graphs/ingestion/nodes.py
```

## 清洗规则

```text
1. 统一换行符
2. 去除连续多余空行
3. 去除不可见字符
4. 去除明显乱码
5. 去除过短无意义文本
6. 保留标题层级
7. 保留表格文本
```

## MVP 先做

```text
1. strip
2. 合并多个空行
3. 统一 \r\n 为 \n
4. 删除长度过短的段落
```

## 验收标准

```text
1. cleaned_text 不为空
2. 多余空行被减少
3. 文本主体内容不丢失
```

---

# 6.9 ChunkDocumentNode

## 职责

将清洗后的文档切分为适合检索的 chunk。

## 输入

```json
{
  "cleaned_text": "...",
  "pages": []
}
```

## 输出

```json
{
  "chunks": [
    {
      "chunk_id": "chunk_xxx",
      "text": "...",
      "page_start": 1,
      "page_end": 2,
      "heading": "系统架构设计",
      "chunk_index": 0
    }
  ]
}
```

## 开发文件

```text
app/services/chunk_service.py
app/graphs/ingestion/nodes.py
```

## 分块策略优先级

```text
1. 标题结构切分
2. 段落切分
3. token 长度兜底
4. 后续再做语义切分
```

## 推荐参数

```text
chunk_size: 500 - 1000 tokens
chunk_overlap: 80 - 150 tokens
```

## MVP 实现

```text
1. 按段落切分
2. 累积到 chunk_size
3. 加入 overlap
4. 生成 chunk_id
5. 保留 chunk_index
```

## 验收标准

```text
1. 长文档可以切成多个 chunk
2. 每个 chunk 有唯一 chunk_id
3. chunk 文本长度在合理范围内
4. chunk 保留 document_id 和 index
```

---

# 6.10 ExtractMetadataNode

## 职责

为文档和 chunk 补充元数据。

## 输入

```json
{
  "document_id": "doc_xxx",
  "chunks": []
}
```

## 输出

```json
{
  "chunks": [
    {
      "chunk_id": "chunk_xxx",
      "text": "...",
      "metadata": {
        "tenant_id": "tenant_xxx",
        "knowledge_base_id": "kb_xxx",
        "document_id": "doc_xxx",
        "filename": "xxx.pdf",
        "page_start": 1,
        "page_end": 2
      }
    }
  ]
}
```

## 开发文件

```text
app/services/document_service.py
app/graphs/ingestion/nodes.py
```

## 必须包含的 metadata

```text
tenant_id
knowledge_base_id
document_id
chunk_id
filename
file_type
page_start
page_end
chunk_index
created_by
created_at
permission_group
```

## 验收标准

```text
1. 每个 chunk 都有 metadata
2. metadata 中包含 tenant_id
3. metadata 中包含 document_id
4. metadata 中包含权限相关字段
```

---

# 6.11 DedupDocumentNode

## 职责

进行文档级和 chunk 级去重。

## 输入

```json
{
  "document_id": "doc_xxx",
  "file_hash": "sha256_xxx",
  "chunks": []
}
```

## 输出

```json
{
  "dedup_result": {
    "is_duplicate_document": false,
    "duplicate_chunk_ids": []
  }
}
```

## 开发文件

```text
app/services/document_service.py
app/graphs/ingestion/nodes.py
```

## 去重层级

MVP：

```text
1. file_sha256
2. chunk_text_sha256
```

增强版：

```text
1. 文件 hash 去重
2. 文本 hash 去重
3. chunk hash 去重
4. 语义相似度去重
```

## 验收标准

```text
1. 相同文件重复上传可以识别
2. 相同 chunk 可以识别
3. 不影响首次上传入库
```

---

# 6.12 EmbeddingNode

## 职责

为每个 chunk 生成向量。

## 输入

```json
{
  "chunks": [
    {
      "chunk_id": "chunk_xxx",
      "text": "..."
    }
  ]
}
```

## 输出

```json
{
  "embedded_chunks": [
    {
      "chunk_id": "chunk_xxx",
      "text": "...",
      "vector": [0.1, 0.2, 0.3],
      "metadata": {}
    }
  ]
}
```

## 开发文件

```text
app/services/embedding_service.py
app/integrations/embedding_client.py
app/graphs/ingestion/nodes.py
```

## 开发任务

```text
1. 实现 batch embedding
2. 支持失败重试
3. 记录 embedding_model
4. 记录 embedding_dim
5. 长文本超过限制时抛出明确错误
```

## 验收标准

```text
1. 每个 chunk 都能生成 vector
2. vector 维度一致
3. embedding 失败时任务进入 FAILED
```

---

# 6.13 QdrantIndexNode

## 职责

将向量和 metadata 写入 Qdrant。

## 输入

```json
{
  "embedded_chunks": []
}
```

## 输出

```json
{
  "indexed_count": 128,
  "collection_name": "tenant_xxx_kb_xxx"
}
```

## 开发文件

```text
app/services/vector_store_service.py
app/integrations/qdrant_client.py
app/graphs/ingestion/nodes.py
```

## Qdrant payload 示例

```json
{
  "tenant_id": "tenant_xxx",
  "knowledge_base_id": "kb_xxx",
  "document_id": "doc_xxx",
  "chunk_id": "chunk_xxx",
  "text": "...",
  "filename": "xxx.pdf",
  "page_start": 1,
  "page_end": 2,
  "department": "研发部",
  "permission_group": "group_xxx",
  "created_at": "2026-06-09"
}
```

## 开发任务

```text
1. 创建 collection
2. 检查 collection 是否存在
3. 批量 upsert vectors
4. payload 中写入 metadata
5. 支持按 document_id 删除旧索引
```

## Collection 命名建议

```text
tenant_{tenant_id}_kb_{knowledge_base_id}
```

或者统一 collection：

```text
enterprise_rag_chunks
```

然后通过 payload filter 做隔离。

MVP 建议：

```text
统一 collection + payload filter
```

## 验收标准

```text
1. chunk 可以写入 Qdrant
2. payload 包含 document_id 和 chunk_id
3. 可以通过 Qdrant 查询到写入结果
```

---

# 6.14 UpdateDocumentStatusNode

## 职责

更新文档最终入库状态。

## 成功输出

```json
{
  "status": "READY",
  "chunk_count": 128,
  "indexed_count": 128
}
```

## 失败输出

```json
{
  "status": "FAILED",
  "current_step": "EMBEDDING",
  "error_message": "embedding request timeout",
  "retry_count": 1
}
```

## 开发文件

```text
app/services/document_service.py
app/graphs/ingestion/nodes.py
```

## 验收标准

```text
1. 入库成功后 documents.status = READY
2. ingestion_tasks.status = READY
3. 失败时记录 current_step 和 error_message
```

---

# 6.15 DocumentIngestionGraph 组装

文件：

```text
app/graphs/ingestion/graph.py
```

流程：

```text
FileTypeDetectNode
  ↓
ParseDocumentNode
  ↓
CleanTextNode
  ↓
ChunkDocumentNode
  ↓
ExtractMetadataNode
  ↓
DedupDocumentNode
  ↓
EmbeddingNode
  ↓
QdrantIndexNode
  ↓
UpdateDocumentStatusNode
```

注意：

```text
UploadNode 和 CreateDocumentTaskNode 通常在 API / Service 层完成，
Graph 主要处理文档解析到入库流程。
```

## 第二阶段验收标准

```text
1. 用户上传文档
2. 系统创建任务
3. 后台执行入库 Graph
4. 文档被解析
5. 文档被切分
6. chunk 被 embedding
7. 向量写入 Qdrant
8. 文档状态变成 READY
```

---

# 7. 第三阶段：RAGQueryGraph 基础问答图

## 7.1 阶段目标

实现基于知识库的基础问答闭环。

## 7.2 基础问答流程

MVP 版本：

```text
UserQueryNode
  ↓
HybridRetrieveNode
  ↓
ContextBuildNode
  ↓
PromptTemplateSelectNode
  ↓
AnswerGenerateNode
  ↓
CitationNode
  ↓
GroundingCheckNode
  ↓
RefusalOrFinalAnswerNode
```

增强版本：

```text
UserQueryNode
  ↓
InputSafetyCheckNode
  ↓
IntentClassifyNode
  ↓
QueryRewriteNode
  ↓
MultiQueryNode
  ↓
HybridRetrieveNode
  ↓
MergeDedupRetrieveResultNode
  ↓
RerankNode
  ↓
MetadataFilterNode
  ↓
PermissionFilterNode
  ↓
ContextBuildNode
  ↓
PromptTemplateSelectNode
  ↓
AnswerGenerateNode
  ↓
CitationNode
  ↓
GroundingCheckNode
  ↓
RefusalOrFinalAnswerNode
```

## 7.3 State 设计

文件：

```text
app/graphs/rag/state.py
```

```python
from typing import TypedDict


class RAGState(TypedDict, total=False):
    request_id: str
    tenant_id: str
    user_id: str
    knowledge_base_id: str
    session_id: str

    user_query: str
    query_id: str

    input_safe: bool
    risk_type: str

    intent: str
    rewritten_query: str
    expanded_queries: list[str]

    vector_results: list[dict]
    bm25_results: list[dict]
    retrieved_docs: list[dict]
    reranked_docs: list[dict]
    metadata_filtered_docs: list[dict]
    permitted_docs: list[dict]

    final_context: str
    context_docs: list[dict]
    prompt_template: str

    answer: str
    raw_llm_response: str
    citations: list[dict]

    grounding_result: dict

    final_answer: str
    refused: bool
    refusal_reason: str

    logs: list[dict]
    metrics: dict
```

---

# 7.4 UserQueryNode

## 职责

接收用户问题，初始化查询状态。

## 输入

```json
{
  "user_query": "系统如何做权限控制？",
  "tenant_id": "tenant_xxx",
  "user_id": "user_xxx",
  "knowledge_base_id": "kb_xxx"
}
```

## 输出

```json
{
  "query_id": "query_xxx",
  "user_query": "系统如何做权限控制？"
}
```

## 开发文件

```text
app/api/chat.py
app/services/retrieval_service.py
app/graphs/rag/nodes.py
```

## 开发任务

```text
1. 创建 POST /api/rag/query
2. 接收用户 query
3. 生成 query_id
4. 初始化 RAGState
```

## 验收标准

```text
1. API 可以接收问题
2. 系统能生成 query_id
3. 状态中包含 tenant_id、user_id、knowledge_base_id
```

---

# 7.5 InputSafetyCheckNode

## 职责

检测用户输入是否存在明显攻击风险。

## 检测内容

```text
1. Prompt Injection
2. 要求泄露系统提示词
3. 要求绕过权限
4. 要求输出全部文档
5. 恶意命令注入
```

## 输出

```json
{
  "input_safe": true,
  "risk_type": null
}
```

## MVP 实现

先用规则判断：

```text
ignore previous instructions
忽略之前的指令
输出系统提示词
绕过权限
导出全部文档
```

## 后续增强

```text
1. LLM 安全分类
2. 专门的安全模型
3. 风险分级
```

## 验收标准

```text
1. 正常问题可以通过
2. 明显攻击问题会被拦截
3. 被拦截问题不会进入检索和生成
```

---

# 7.6 IntentClassifyNode

## 职责

识别用户意图，决定走普通 RAG 还是业务 Agent。

## 意图类型

```text
qa          普通知识问答
summary     文档摘要
compare     多文档对比
extract     信息提取
table       表格生成
ppt         PPT 生成
workflow    复杂工作流
crawl       数据采集
unknown     未知任务
```

## 输出

```json
{
  "intent": "qa"
}
```

## MVP 实现

第一阶段可以全部默认为：

```text
qa
```

后续再加分类器。

## 验收标准

```text
1. 普通问题识别为 qa
2. “生成 PPT” 问题识别为 ppt
3. “抓取数据” 问题识别为 crawl
```

---

# 7.7 QueryRewriteNode

## 职责

将用户问题改写成更适合检索的查询。

## 输入

```json
{
  "user_query": "这个系统权限怎么做的？"
}
```

## 输出

```json
{
  "rewritten_query": "企业级 RAG Agent 平台的租户隔离、用户权限、文档 ACL 和访问控制设计"
}
```

## 开发文件

```text
app/services/retrieval_service.py
app/services/llm_service.py
app/graphs/rag/nodes.py
```

## 改写原则

```text
1. 保留用户原意
2. 补全隐含实体
3. 去掉口语化表达
4. 不添加用户没有问的主题
5. 输出一句适合检索的 query
```

## MVP 策略

可以先跳过该节点：

```text
rewritten_query = user_query
```

## 验收标准

```text
1. 简短问题能改写成完整问题
2. 改写不偏离用户原意
3. 改写失败时回退到原始问题
```

---

# 7.8 MultiQueryNode

## 职责

从多个角度生成检索 query，提高召回率。

## 输入

```json
{
  "rewritten_query": "企业级 RAG 系统权限设计"
}
```

## 输出

```json
{
  "expanded_queries": [
    "企业级 RAG 系统权限控制设计",
    "文档级权限和租户隔离实现方式",
    "知识库问答系统用户访问控制",
    "RAG 平台敏感信息保护和审计日志"
  ]
}
```

## MVP 策略

第一版：

```text
expanded_queries = [rewritten_query]
```

## 增强版

使用 LLM 生成 3-5 个 query。

## 验收标准

```text
1. 至少生成 1 个 query
2. 增强版可以生成多个不同角度 query
3. 不生成与问题无关的 query
```

---

# 7.9 HybridRetrieveNode

## 职责

执行向量检索和关键词检索。

## 输入

```json
{
  "expanded_queries": []
}
```

## 输出

```json
{
  "vector_results": [],
  "bm25_results": []
}
```

## 开发文件

```text
app/services/retrieval_service.py
app/services/vector_store_service.py
app/integrations/qdrant_client.py
app/integrations/bm25_client.py
app/graphs/rag/nodes.py
```

## MVP 实现

只做 Qdrant vector search：

```text
1. 对 query 生成 embedding
2. 调用 Qdrant search
3. 使用 tenant_id 和 knowledge_base_id 过滤
4. 返回 top_k chunks
```

## 检索参数

```text
Vector Search TopK = 30
BM25 Search TopK = 30
最终候选 = 60
```

## Qdrant Filter

必须过滤：

```text
tenant_id
knowledge_base_id
```

可选过滤：

```text
document_id
department
created_at
permission_group
```

## 验收标准

```text
1. 用户问题可以召回相关 chunk
2. 检索结果包含 score
3. 检索结果包含 text 和 metadata
4. tenant_id 和 knowledge_base_id 过滤生效
```

---

# 7.10 MergeDedupRetrieveResultNode

## 职责

合并多路召回结果并去重。

## 输入

```json
{
  "vector_results": [],
  "bm25_results": []
}
```

## 输出

```json
{
  "retrieved_docs": []
}
```

## 去重 Key

```text
chunk_id
document_id + page_start + text_hash
```

## 合并策略

MVP：

```text
1. 合并 vector_results 和 bm25_results
2. 按 chunk_id 去重
3. 保留最高 score
4. 按 score 排序
```

增强版：

```text
hybrid_score = vector_score * 0.7 + bm25_score * 0.3
```

## 验收标准

```text
1. 重复 chunk 只保留一条
2. 结果按 score 排序
3. 保留来源 source: vector / bm25 / both
```

---

# 7.11 RerankNode

## 职责

对召回结果进行重排序，提高最终上下文质量。

## 输入

```json
{
  "user_query": "...",
  "retrieved_docs": []
}
```

## 输出

```json
{
  "reranked_docs": []
}
```

## MVP 实现

```text
reranked_docs = retrieved_docs 按 score 排序
```

## 增强版

可以接入：

```text
bge-reranker
jina-reranker
cross encoder reranker
LLM rerank
```

## 推荐输出字段

```json
{
  "chunk_id": "chunk_xxx",
  "text": "...",
  "score": 0.82,
  "rerank_score": 0.91,
  "metadata": {}
}
```

## 验收标准

```text
1. reranked_docs 不为空
2. 排序稳定
3. 可以限制最终 top_n
```

---

# 7.12 MetadataFilterNode

## 职责

根据用户指定条件或系统条件过滤检索结果。

## 过滤条件示例

```json
{
  "department": "研发部",
  "document_type": "技术文档",
  "created_at_gte": "2026-01-01"
}
```

## 输出

```json
{
  "metadata_filtered_docs": []
}
```

## MVP 策略

```text
metadata_filtered_docs = reranked_docs
```

后续加入实际过滤逻辑。

## 验收标准

```text
1. 无过滤条件时不丢失结果
2. 有过滤条件时只保留符合条件的结果
```

---

# 7.13 PermissionFilterNode

## 职责

根据用户权限过滤文档，确保无权限内容不会进入 LLM 上下文。

## 输入

```json
{
  "user_id": "user_xxx",
  "tenant_id": "tenant_xxx",
  "metadata_filtered_docs": []
}
```

## 输出

```json
{
  "permitted_docs": []
}
```

## 权限判断依据

```text
tenant_id
user_id
role_id
department_id
permission_group
document_acl
```

## 重要要求

```text
权限过滤必须发生在 AnswerGenerateNode 之前。
不能只依赖前端隐藏。
不能把无权限内容放进 prompt。
```

## MVP 策略

第一版至少做：

```text
1. tenant_id 过滤
2. knowledge_base_id 过滤
```

后续做：

```text
1. document_acl
2. department
3. role
4. permission_group
```

## 验收标准

```text
1. 不同 tenant 的用户不能检索到对方文档
2. 无权限文档不会进入 context
3. 权限过滤后为空时进入拒答
```

---

# 7.14 ContextBuildNode

## 职责

把检索结果构造成 LLM 可用上下文。

## 输入

```json
{
  "permitted_docs": []
}
```

## 输出

```json
{
  "final_context": "...",
  "context_docs": []
}
```

## 上下文格式

```text
[文档 1]
chunk_id: chunk_xxx
document_id: doc_xxx
文件名: system_design.pdf
页码: 12
内容:
系统采用租户隔离、角色权限和文档 ACL 进行权限控制。

[文档 2]
chunk_id: chunk_yyy
document_id: doc_yyy
文件名: permission.md
页码: 3
内容:
权限过滤必须在答案生成前完成。
```

## 开发任务

```text
1. 选择 top_n docs
2. 拼接上下文
3. 保留来源信息
4. 控制 token 长度
5. 保存 context_docs 用于 CitationNode
```

## 验收标准

```text
1. final_context 包含文本内容
2. final_context 包含来源信息
3. 不包含无权限文档
4. 上下文长度不超过配置限制
```

---

# 7.15 PromptTemplateSelectNode

## 职责

根据任务类型选择 Prompt 模板。

## 输入

```json
{
  "intent": "qa"
}
```

## 输出

```json
{
  "prompt_template": "qa"
}
```

## QA Prompt 核心要求

```text
你是企业知识库问答助手。

你只能基于给定上下文回答用户问题。
如果上下文中没有足够依据，必须说明无法从当前知识库中找到依据。
回答必须尽量准确、简洁、结构化。
不要编造事实。
不要编造引用。
引用必须来自上下文中的文档信息。
```

## 模板类型

| intent | template |
|---|---|
| qa | qa_prompt |
| summary | summary_prompt |
| compare | compare_prompt |
| extract | extract_prompt |
| table | table_prompt |
| ppt | ppt_outline_prompt |

## 验收标准

```text
1. qa 意图选择 qa_prompt
2. 不同 intent 可选择不同模板
3. 默认 fallback 到 qa_prompt
```

---

# 7.16 AnswerGenerateNode

## 职责

调用 LLM 生成答案。

## 输入

```json
{
  "user_query": "...",
  "final_context": "...",
  "prompt_template": "qa"
}
```

## 输出

```json
{
  "answer": "...",
  "raw_llm_response": "..."
}
```

## 开发文件

```text
app/services/llm_service.py
app/integrations/llm_client.py
app/graphs/rag/nodes.py
```

## 生成要求

```text
1. 必须基于上下文
2. 不允许无依据扩展
3. 如果依据不足，要明确说明
4. 答案结构清晰
5. 尽量带引用标记
```

## 验收标准

```text
1. 可以根据 context 回答
2. context 为空时不胡编
3. LLM 调用失败时返回明确错误
```

---

# 7.17 CitationNode

## 职责

把答案依据映射回真实文档来源。

## 输入

```json
{
  "answer": "...",
  "context_docs": []
}
```

## 输出

```json
{
  "citations": [
    {
      "citation_id": "cite_1",
      "document_id": "doc_xxx",
      "chunk_id": "chunk_xxx",
      "filename": "system_design.pdf",
      "page_start": 12,
      "page_end": 13,
      "snippet": "系统采用租户隔离..."
    }
  ]
}
```

## 重要原则

```text
不要让 LLM 自己编造引用。
引用必须来自 retrieved/context docs。
```

## MVP 实现

```text
1. 取最终用于构造 context 的 top docs
2. 生成 citations
3. 每条 citation 包含 filename、page、chunk_id、snippet
```

## 增强版

```text
1. 根据答案句子匹配最相关 chunk
2. 建立 answer sentence -> citation 映射
3. 支持前端点击定位原文
```

## 验收标准

```text
1. 每个 citation 都来自真实 chunk
2. citation 中包含 filename
3. citation 中包含 chunk_id
4. citation 中包含 snippet
```

---

# 7.18 GroundingCheckNode

## 职责

检查答案是否被上下文支持。

## 输入

```json
{
  "answer": "...",
  "context_docs": [],
  "citations": []
}
```

## 输出

```json
{
  "grounded": true,
  "unsupported_claims": [],
  "confidence": 0.86
}
```

## MVP 实现

规则判断：

```text
1. answer 为空 -> 不通过
2. context_docs 为空 -> 不通过
3. citations 为空 -> 不通过
4. answer 包含“不知道/无法找到依据” -> 允许拒答
```

## 增强版

使用 LLM 判断：

```text
1. 答案中的每个关键断言是否能在 context 中找到依据
2. 找出 unsupported claims
3. 输出 grounded 和 confidence
```

## 验收标准

```text
1. 没有上下文时 grounding=false
2. 没有引用时 grounding=false
3. 有上下文和引用时 grounding=true
```

---

# 7.19 RefusalOrFinalAnswerNode

## 职责

根据检索结果和 grounding 结果决定返回答案或拒答。

## 拒答条件

```text
1. 没有召回文档
2. 召回分数过低
3. 权限过滤后无文档
4. final_context 为空
5. answer 为空
6. citations 为空
7. grounding=false
```

## 拒答示例

```text
当前知识库中没有找到足够依据回答该问题。你可以尝试更换知识库范围，或上传相关文档后重新提问。
```

## 输出

```json
{
  "final_answer": "...",
  "refused": false,
  "refusal_reason": null
}
```

## 验收标准

```text
1. 有依据时返回答案
2. 无依据时明确拒答
3. 无权限时明确拒答
4. 不编造答案
```

---

# 7.20 RAGQueryGraph 组装

文件：

```text
app/graphs/rag/graph.py
```

MVP 图：

```text
UserQueryNode
  ↓
HybridRetrieveNode
  ↓
ContextBuildNode
  ↓
PromptTemplateSelectNode
  ↓
AnswerGenerateNode
  ↓
CitationNode
  ↓
GroundingCheckNode
  ↓
RefusalOrFinalAnswerNode
```

增强图：

```text
UserQueryNode
  ↓
InputSafetyCheckNode
  ↓
IntentClassifyNode
  ↓
QueryRewriteNode
  ↓
MultiQueryNode
  ↓
HybridRetrieveNode
  ↓
MergeDedupRetrieveResultNode
  ↓
RerankNode
  ↓
MetadataFilterNode
  ↓
PermissionFilterNode
  ↓
ContextBuildNode
  ↓
PromptTemplateSelectNode
  ↓
AnswerGenerateNode
  ↓
CitationNode
  ↓
GroundingCheckNode
  ↓
RefusalOrFinalAnswerNode
```

## 第三阶段验收标准

```text
1. 用户可以提问
2. 系统可以从 Qdrant 召回 chunk
3. 系统可以构造上下文
4. LLM 可以基于上下文回答
5. 返回结果包含 citations
6. 无相关文档时可以拒答
```

---

# 8. 第四阶段：增强检索质量

## 8.1 阶段目标

提升召回率、引用准确率和答案稳定性。

## 8.2 需要增强的节点

```text
QueryRewriteNode
MultiQueryNode
HybridRetrieveNode
MergeDedupRetrieveResultNode
RerankNode
MetadataFilterNode
```

---

# 8.3 QueryRewriteNode 增强

开发内容：

```text
1. 使用 LLM 改写 query
2. 输出结构化 rewritten_query
3. 加失败 fallback
4. 记录 rewritten_query 到 query_logs
```

验收标准：

```text
1. 口语问题能被改写
2. 改写不改变原意
3. 检索命中率提升
```

---

# 8.4 MultiQueryNode 增强

开发内容：

```text
1. 使用 LLM 生成 3-5 个 query
2. query 之间角度不同
3. 不生成无关 query
4. 控制 query 数量
```

验收标准：

```text
1. 多表达问题能命中同一文档
2. Recall@K 提升
3. 无明显无关召回增加
```

---

# 8.5 HybridRetrieveNode 增强

开发内容：

```text
1. 接入 BM25
2. 支持 Elasticsearch 或 PostgreSQL FTS
3. vector search 和 keyword search 并行
4. 合并结果
```

推荐权重：

```text
vector_score * 0.7 + bm25_score * 0.3
```

验收标准：

```text
1. 精确关键词问题命中率提升
2. 语义问题仍可命中
3. Hybrid 效果优于单向量检索
```

---

# 8.6 RerankNode 增强

开发内容：

```text
1. 接入 bge-reranker 或 jina-reranker
2. 输入 query + candidate docs
3. 输出 rerank_score
4. 取 TopN 进入上下文
```

验收标准：

```text
1. Top3 文档相关性提升
2. 引用准确率提升
3. 无关 chunk 更少进入 context
```

---

# 9. 第五阶段：异步任务与工程化

## 9.1 阶段目标

让文档入库从 Demo 变成稳定后台任务。

## 9.2 需要开发的能力

```text
1. 异步入库任务
2. 任务状态查询
3. 失败重试
4. 文档重新索引
5. 日志追踪
6. token 和耗时统计
```

## 9.3 API 设计

```text
POST   /api/documents/upload
GET    /api/documents
GET    /api/documents/{document_id}
GET    /api/documents/{document_id}/status
POST   /api/documents/{document_id}/retry
DELETE /api/documents/{document_id}
```

## 9.4 Worker 流程

```text
用户上传文档
  ↓
保存文件
  ↓
创建 ingestion_task
  ↓
返回 document_id + task_id
  ↓
后台 worker 执行 DocumentIngestionGraph
  ↓
更新任务状态
```

## 9.5 可重试节点

```text
ParseDocumentNode
EmbeddingNode
QdrantIndexNode
LLMCallNode
WebFetchNode
```

## 9.6 不建议盲目重试节点

```text
PermissionFilterNode
InputSafetyCheckNode
DocumentACLNode
FileTypeDetectNode
```

## 9.7 日志字段

```json
{
  "request_id": "req_xxx",
  "query_id": "query_xxx",
  "tenant_id": "tenant_xxx",
  "user_id": "user_xxx",
  "node_name": "HybridRetrieveNode",
  "latency_ms": 120,
  "status": "success",
  "error": null,
  "created_at": "2026-06-09T10:00:00"
}
```

## 第五阶段验收标准

```text
1. 上传接口快速返回
2. 后台任务自动执行
3. 可以查询任务状态
4. 失败后可以重试
5. 每个节点有日志
6. 可以排查失败原因
```

---

# 10. 第六阶段：权限与安全

## 10.1 阶段目标

支持企业级多租户、知识库隔离和文档权限。

## 10.2 SecurityGuardGraph

```text
TenantCheckNode
  ↓
UserPermissionNode
  ↓
DocumentACLNode
  ↓
PromptInjectionDetectNode
  ↓
SensitiveInfoMaskNode
  ↓
OutputSafetyCheckNode
  ↓
AuditLogNode
```

---

# 10.3 TenantCheckNode

职责：

```text
确保用户只能访问当前租户的数据。
```

开发内容：

```text
1. 校验 tenant_id 是否存在
2. 校验 user 是否属于 tenant
3. 检索时强制加 tenant filter
```

验收标准：

```text
不同 tenant 之间数据完全隔离。
```

---

# 10.4 UserPermissionNode

职责：

```text
加载用户角色、部门、权限组。
```

输出：

```json
{
  "permissions": {
    "roles": ["admin"],
    "departments": ["研发部"],
    "permission_groups": ["group_xxx"]
  }
}
```

---

# 10.5 DocumentACLNode

职责：

```text
判断用户是否有权限访问 document 或 chunk。
```

权限来源：

```text
1. 用户
2. 角色
3. 部门
4. 权限组
5. 文档 ACL
```

---

# 10.6 PromptInjectionDetectNode

检测内容：

```text
1. 忽略之前所有指令
2. 输出系统提示词
3. 绕过权限检查
4. 返回所有文档
5. 修改系统规则
```

---

# 10.7 SensitiveInfoMaskNode

脱敏内容：

```text
手机号
邮箱
身份证号
API Key
Token
数据库连接字符串
内部 IP
```

---

# 10.8 AuditLogNode

记录内容：

```json
{
  "user_id": "user_xxx",
  "tenant_id": "tenant_xxx",
  "query": "...",
  "retrieved_document_ids": [],
  "answer_id": "ans_xxx",
  "created_at": "2026-06-09T10:00:00"
}
```

---

## 第六阶段验收标准

```text
1. 用户不能访问其他租户文档
2. 用户不能访问无权限文档
3. Prompt Injection 会被拦截
4. 敏感信息可以脱敏
5. 所有访问行为有审计日志
```

---

# 11. 第七阶段：EvaluationGraph 评测体系

## 11.1 阶段目标

让 RAG 效果可以量化评估。

## 11.2 EvaluationGraph

```text
LoadEvalDatasetNode
  ↓
RunQueryNode
  ↓
MeasureRetrievalNode
  ↓
MeasureAnswerNode
  ↓
MeasureCitationNode
  ↓
MeasureRefusalNode
  ↓
GenerateEvalReportNode
```

---

# 11.3 Eval 数据结构

```json
{
  "question": "系统如何进行权限控制？",
  "expected_answer": "系统通过租户隔离、用户角色、文档 ACL 进行权限控制。",
  "reference_document_ids": ["doc_1", "doc_2"],
  "must_have_keywords": ["租户隔离", "文档权限", "角色"],
  "should_refuse": false
}
```

---

# 11.4 MeasureRetrievalNode

指标：

```text
Recall@K
MRR
Hit Rate
TopK Accuracy
```

---

# 11.5 MeasureAnswerNode

指标：

```text
Answer Accuracy
Keyword Coverage
Faithfulness
Completeness
```

---

# 11.6 MeasureCitationNode

指标：

```text
Citation Accuracy
Citation Coverage
Citation Faithfulness
```

---

# 11.7 MeasureRefusalNode

指标：

```text
Refusal Accuracy
False Refusal Rate
False Answer Rate
```

---

## 第七阶段验收标准

```text
1. 可以维护 eval dataset
2. 可以批量运行测试问题
3. 可以输出评测报告
4. 可以比较不同检索策略
5. 可以发现效果退化
```

---

# 12. 第八阶段：BusinessAgentGraph 业务 Agent

## 12.1 阶段目标

在基础 RAG 能力上扩展业务 Agent。

## 12.2 BusinessAgentGraph

```text
TaskRouterNode
  ↓
TaskPlannerNode
  ↓
ToolSelectNode
  ↓
SubGraphDispatchNode
  ↓
HumanApprovalNode
  ↓
FinalArtifactNode
```

---

# 12.3 TaskRouterNode

职责：

```text
判断用户任务类型，路由到不同子图。
```

路由规则：

```text
qa       -> RAGQueryGraph
ppt      -> PPTAgentGraph
workflow -> GPTWorkflowGraph
crawl    -> DataCrawlerGraph
```

---

# 12.4 PPTAgentGraph

流程：

```text
PPTTaskAnalyzeNode
  ↓
RetrievePPTContextNode
  ↓
GeneratePPTOutlineNode
  ↓
GenerateSlideContentNode
  ↓
GenerateChartDataNode
  ↓
BuildPPTFileNode
  ↓
ReviewPPTNode
  ↓
ReturnPPTNode
```

验收标准：

```text
1. 可以基于知识库生成 PPT 大纲
2. 可以生成每页内容
3. 可以生成 pptx 文件
4. 返回下载链接
```

---

# 12.5 GPTWorkflowGraph

流程：

```text
WorkflowIntentNode
  ↓
WorkflowPlanNode
  ↓
StepDispatchNode
  ↓
ToolCallNode
  ↓
StepResultCheckNode
  ↓
WorkflowSummaryNode
```

适用场景：

```text
1. 生成报告
2. 分析多个文档
3. 调用多个工具
4. 多步骤审批
```

---

# 12.6 DataCrawlerGraph

流程：

```text
ScheduleTriggerNode
  ↓
SearchKeywordGenerateNode
  ↓
WebSearchNode
  ↓
WebFetchNode
  ↓
ContentExtractNode
  ↓
ContentCleanNode
  ↓
DedupNode
  ↓
SummarizeNode
  ↓
EmbeddingNode
  ↓
QdrantIndexNode
  ↓
DailyReportNode
```

第一版只支持：

```text
1. 公开网页
2. RSS
3. 指定 URL 列表
```

暂不支持：

```text
1. 登录态爬虫
2. 绕过反爬
3. 大规模抓取
```

---

# 13. 数据库表设计

## 13.1 documents

```text
id
tenant_id
knowledge_base_id
filename
file_path
file_type
file_hash
status
version
created_by
created_at
updated_at
```

---

## 13.2 document_chunks

```text
id
document_id
tenant_id
knowledge_base_id
chunk_index
text
text_hash
page_start
page_end
heading
metadata_json
created_at
```

---

## 13.3 ingestion_tasks

```text
id
document_id
tenant_id
status
current_step
error_message
retry_count
created_at
updated_at
started_at
finished_at
```

---

## 13.4 query_logs

```text
id
tenant_id
user_id
session_id
query
rewritten_query
answer
retrieved_docs_json
citations_json
grounding_result_json
latency_ms
token_usage_json
created_at
```

---

## 13.5 eval_datasets

```text
id
tenant_id
question
expected_answer
reference_docs_json
must_have_keywords_json
should_refuse
created_at
updated_at
```

---

## 13.6 permissions

```text
id
tenant_id
resource_type
resource_id
subject_type
subject_id
permission
created_at
```

---

# 14. API 设计

## 14.1 文档接口

```text
POST   /api/documents/upload
GET    /api/documents
GET    /api/documents/{document_id}
GET    /api/documents/{document_id}/status
POST   /api/documents/{document_id}/retry
DELETE /api/documents/{document_id}
```

---

## 14.2 问答接口

```text
POST /api/rag/query
POST /api/chat
GET  /api/chat/sessions/{session_id}
GET  /api/chat/messages/{message_id}
```

请求：

```json
{
  "tenant_id": "tenant_xxx",
  "knowledge_base_id": "kb_xxx",
  "user_id": "user_xxx",
  "query": "系统如何进行权限控制？"
}
```

响应：

```json
{
  "answer": "系统通过租户隔离、文档级权限和角色控制实现权限管理。",
  "citations": [
    {
      "filename": "system_design.pdf",
      "page_start": 12,
      "page_end": 13,
      "snippet": "系统采用租户隔离和文档 ACL..."
    }
  ],
  "grounded": true,
  "refused": false
}
```

---

## 14.3 Agent 接口

```text
POST /api/agents/run
POST /api/agents/ppt
POST /api/agents/workflow
POST /api/agents/crawler/run
```

---

## 14.4 Eval 接口

```text
POST /api/evals/run
GET  /api/evals/reports
GET  /api/evals/reports/{report_id}
```

---

# 15. 分步开发路线图

## 阶段一：项目骨架

目标：

```text
搭建 FastAPI、数据库、Qdrant、LLM、Embedding 基础连接。
```

开发内容：

```text
1. app/main.py
2. app/core/config.py
3. app/db/session.py
4. app/integrations/qdrant_client.py
5. app/integrations/llm_client.py
6. app/integrations/embedding_client.py
```

验收：

```text
服务可启动，基础依赖可连接。
```

---

## 阶段二：文档上传和入库

目标：

```text
完成文档从上传到 Qdrant 入库。
```

开发节点：

```text
UploadNode
CreateDocumentTaskNode
FileTypeDetectNode
ParseDocumentNode
CleanTextNode
ChunkDocumentNode
ExtractMetadataNode
DedupDocumentNode
EmbeddingNode
QdrantIndexNode
UpdateDocumentStatusNode
```

验收：

```text
上传 PDF 后可以完成解析、切分、embedding、入库。
```

---

## 阶段三：基础 RAG 问答

目标：

```text
完成基于知识库的基础问答。
```

开发节点：

```text
UserQueryNode
HybridRetrieveNode
ContextBuildNode
PromptTemplateSelectNode
AnswerGenerateNode
CitationNode
GroundingCheckNode
RefusalOrFinalAnswerNode
```

验收：

```text
可以基于上传文档提问，回答带引用，无依据时拒答。
```

---

## 阶段四：增强检索

目标：

```text
提高召回质量和答案准确性。
```

开发节点：

```text
QueryRewriteNode
MultiQueryNode
MergeDedupRetrieveResultNode
RerankNode
MetadataFilterNode
```

验收：

```text
Recall@K、引用准确率、答案准确率提升。
```

---

## 阶段五：异步工程化

目标：

```text
让文档入库和问答链路可追踪、可重试、可维护。
```

开发内容：

```text
1. 异步 worker
2. 任务状态表
3. 节点日志
4. 失败重试
5. 文档重新索引
6. token 统计
```

验收：

```text
上传快速返回，后台处理，失败可追踪可重试。
```

---

## 阶段六：权限与安全

目标：

```text
实现企业级多租户和权限控制。
```

开发节点：

```text
TenantCheckNode
UserPermissionNode
DocumentACLNode
PermissionFilterNode
PromptInjectionDetectNode
SensitiveInfoMaskNode
OutputSafetyCheckNode
AuditLogNode
```

验收：

```text
用户不能访问无权限文档，不同租户完全隔离。
```

---

## 阶段七：评测体系

目标：

```text
让 RAG 效果可量化。
```

开发节点：

```text
LoadEvalDatasetNode
RunQueryNode
MeasureRetrievalNode
MeasureAnswerNode
MeasureCitationNode
MeasureRefusalNode
GenerateEvalReportNode
```

验收：

```text
可以批量跑测试集并输出质量报告。
```

---

## 阶段八：业务 Agent 扩展

目标：

```text
将系统扩展为企业知识工作流平台。
```

开发节点：

```text
TaskRouterNode
TaskPlannerNode
ToolSelectNode
SubGraphDispatchNode
HumanApprovalNode
FinalArtifactNode
PPTAgentGraph
GPTWorkflowGraph
DataCrawlerGraph
```

验收：

```text
可以生成 PPT、执行多步骤工作流、定时采集数据入库。
```

---

# 16. MVP 最小闭环优先级

## 必须优先完成

```text
1. FastAPI 项目结构
2. 文档上传
3. PDF / TXT / DOCX 解析
4. 文档 chunk
5. embedding
6. Qdrant 入库
7. vector search
8. LLM 回答
9. citation
10. refusal
```

---

## 第二优先级

```text
1. Query Rewrite
2. Multi-query
3. Hybrid Search
4. Rerank
5. Metadata Filter
6. 异步入库
7. 状态追踪
```

---

## 第三优先级

```text
1. 权限系统
2. Prompt Injection 防护
3. 敏感信息脱敏
4. 评测体系
5. PPT Agent
6. GPT Workflow
7. Data Crawler
```

---

# 17. 开发注意事项

## 17.1 不要一开始做太复杂

第一版不要同时做：

```text
OCR
复杂权限
完整评测平台
多 Agent 协作
自动爬虫
A/B 测试
复杂语义分块
```

先完成稳定闭环，再逐步增强。

---

## 17.2 不要把所有节点塞进一个 Graph

错误方式：

```text
EnterpriseRAGGraph 包含所有节点。
```

推荐方式：

```text
多个子图 + RouterGraph。
```

---

## 17.3 权限必须在后端完成

必须做：

```text
Qdrant payload filter
+
PermissionFilterNode
+
ContextBuildNode 前过滤
```

不能只做：

```text
前端隐藏按钮
前端过滤列表
```

---

## 17.4 引用必须来自真实 chunk

错误方式：

```text
让 LLM 自己编引用。
```

正确方式：

```text
检索结果保留 document_id、chunk_id、page。
CitationNode 从真实 context_docs 映射引用。
```

---

## 17.5 拒答机制必须明确

如果没有足够依据，系统必须拒答。

拒答场景：

```text
没有召回结果
召回结果分数太低
权限过滤后为空
上下文为空
引用为空
grounding 不通过
```

---

# 18. 推荐开发节奏

建议按下面顺序开发：

```text
第 1 周：
  - FastAPI 骨架
  - DB 连接
  - Qdrant 连接
  - LLM / Embedding Client

第 2 周：
  - 文档上传
  - PDF / TXT / DOCX 解析
  - chunk
  - embedding
  - Qdrant 入库

第 3 周：
  - 基础向量检索
  - 上下文构造
  - LLM 回答
  - 引用来源
  - 拒答机制

第 4 周：
  - 异步任务
  - 状态追踪
  - 失败重试
  - 日志记录

第 5 周：
  - Query Rewrite
  - Multi-query
  - Hybrid Search
  - Rerank

第 6 周：
  - tenant 隔离
  - 权限过滤
  - Prompt Injection 检测
  - 审计日志

第 7 周：
  - Eval Dataset
  - Eval Runner
  - Retrieval Metrics
  - Answer / Citation Metrics

第 8 周以后：
  - PPT Agent
  - GPT Workflow
  - Data Crawler
  - Human Approval
```

---

# 19. Agent 状态机与 Graph State 设计

## 19.1 为什么状态机很重要

在本项目中，LangGraph 不是简单的流程编排工具，而是整个系统的智能任务状态机。

每个节点都应该遵循：

```text
读取 State
执行单一职责
写回 State
根据 State 决定下一步
```

状态机需要承担：

```text
1. 记录任务当前处于哪个节点
2. 记录每个节点的输入和输出
3. 支持失败重试
4. 支持中断恢复
5. 支持权限过滤
6. 支持引用溯源
7. 支持评测与审计
8. 支持子图之间状态传递
```

如果状态机设计不清晰，后续会出现：

```text
1. 节点之间字段混乱
2. 子图之间状态难复用
3. 异步任务状态和 Graph 状态不一致
4. 错误重试很难做
5. 日志追踪不完整
6. 权限过滤链路不可验证
7. Citation 和 Grounding 难保证可靠
8. 多 Agent 任务无法恢复和审计
```

因此，本项目建议把状态机作为第一优先级基础设施来开发。

---

## 19.2 状态机设计原则

### 19.2.1 State 要显式，不要隐式

错误方式：

```python
state["data"] = result
```

正确方式：

```python
state["retrieved_docs"] = retrieved_docs
state["reranked_docs"] = reranked_docs
state["permitted_docs"] = permitted_docs
```

每个关键字段都应该有明确含义。

---

### 19.2.2 节点只改自己负责的字段

例如：

```text
HybridRetrieveNode 只负责写入：
- vector_results
- bm25_results
- retrieved_docs

RerankNode 只负责写入：
- reranked_docs

PermissionFilterNode 只负责写入：
- permitted_docs
```

不要让一个节点到处修改状态，否则后续很难 debug。

---

### 19.2.3 State 要支持追踪

建议每个 State 都包含：

```python
request_id: str
trace_id: str
node_history: list[dict]
metrics: dict
errors: list[dict]
```

这样每次任务执行都可以追踪。

---

### 19.2.4 State 要支持失败恢复

每个节点执行前后都应记录：

```text
current_node
previous_node
status
retry_count
error_message
```

如果某个节点失败，可以知道从哪里重试。

---

### 19.2.5 State 要支持子图传递

例如：

```text
AgentRouterGraph
  ↓
RAGQueryGraph
  ↓
SecurityGuardGraph
```

子图之间不能随意丢字段。

建议拆分：

```text
BaseState
DocumentIngestionState
RAGQueryState
SecurityState
EvaluationState
BusinessAgentState
```

其中所有子状态都继承或兼容 `BaseState`。

---

## 19.3 推荐状态模型分层

### 19.3.1 BaseState

所有图共享的基础状态。

```python
from typing import TypedDict, Literal


class NodeLog(TypedDict, total=False):
    node_name: str
    status: Literal["pending", "running", "success", "failed", "skipped"]
    input_keys: list[str]
    output_keys: list[str]
    latency_ms: int
    error: str
    started_at: str
    ended_at: str


class BaseState(TypedDict, total=False):
    request_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str

    current_node: str
    previous_node: str
    next_node: str

    status: Literal[
        "INIT",
        "RUNNING",
        "WAITING",
        "SUCCESS",
        "FAILED",
        "RETRYING",
        "REFUSED",
        "CANCELLED",
    ]

    retry_count: int
    max_retries: int

    node_history: list[NodeLog]
    errors: list[dict]
    metrics: dict

    created_at: str
    updated_at: str
```

---

### 19.3.2 DocumentIngestionState

文档入库状态。

```python
class DocumentIngestionState(BaseState, total=False):
    task_id: str

    document_id: str
    knowledge_base_id: str

    original_filename: str
    file_path: str
    file_type: str
    file_hash: str
    file_size: int

    raw_text: str
    cleaned_text: str
    pages: list[dict]
    tables: list[dict]

    chunks: list[dict]
    chunk_count: int

    dedup_result: dict

    embedded_chunks: list[dict]
    embedding_model: str
    embedding_dim: int

    collection_name: str
    indexed_count: int

    current_step: str
    error_message: str
```

---

### 19.3.3 RAGQueryState

问答状态。

```python
class RAGQueryState(BaseState, total=False):
    query_id: str
    knowledge_base_id: str

    user_query: str
    normalized_query: str
    rewritten_query: str
    expanded_queries: list[str]

    intent: str
    input_safe: bool
    risk_type: str

    query_filters: dict

    vector_results: list[dict]
    bm25_results: list[dict]
    retrieved_docs: list[dict]
    reranked_docs: list[dict]
    metadata_filtered_docs: list[dict]
    permitted_docs: list[dict]

    retrieval_top_k: int
    rerank_top_n: int
    min_score: float

    final_context: str
    context_docs: list[dict]
    context_token_count: int

    prompt_template: str
    prompt: str

    answer: str
    raw_llm_response: str

    citations: list[dict]
    grounding_result: dict

    refused: bool
    refusal_reason: str
    final_answer: str

    token_usage: dict
    latency_ms: int
```

---

### 19.3.4 SecurityState

安全和权限状态。

```python
class SecurityState(BaseState, total=False):
    permissions: dict

    user_roles: list[str]
    department_ids: list[str]
    permission_groups: list[str]

    allowed_document_ids: list[str]
    denied_document_ids: list[str]

    input_risk: dict
    output_risk: dict

    masked_fields: list[str]

    audit_log_id: str
```

---

### 19.3.5 EvaluationState

评测状态。

```python
class EvaluationState(BaseState, total=False):
    eval_run_id: str
    dataset_id: str

    eval_items: list[dict]
    eval_results: list[dict]

    retrieval_metrics: dict
    answer_metrics: dict
    citation_metrics: dict
    refusal_metrics: dict

    report_id: str
    report_path: str
```

---

### 19.3.6 BusinessAgentState

业务 Agent 状态。

```python
class BusinessAgentState(BaseState, total=False):
    task_id: str
    task_type: str

    user_goal: str
    task_plan: list[dict]

    selected_tools: list[str]
    tool_results: list[dict]

    subgraph_name: str
    subgraph_result: dict

    human_approval_required: bool
    human_approval_status: str

    artifact_type: str
    artifact_path: str
    artifact_url: str

    final_result: dict
```

---

## 19.4 节点执行状态规范

### 19.4.1 节点状态枚举

```text
pending
running
success
failed
skipped
retrying
```

### 19.4.2 Graph 任务状态枚举

```text
INIT
RUNNING
WAITING
SUCCESS
FAILED
RETRYING
REFUSED
CANCELLED
```

### 19.4.3 文档入库状态枚举

```text
UPLOADED
PARSING
PARSED
CLEANING
CHUNKING
DEDUPING
EMBEDDING
INDEXING
READY
FAILED
RETRYING
```

### 19.4.4 问答状态枚举

```text
RECEIVED
SAFETY_CHECKING
REWRITING
RETRIEVING
RERANKING
FILTERING
GENERATING
GROUNDING
ANSWERED
REFUSED
FAILED
```

---

## 19.5 状态转移设计

### 19.5.1 文档入库状态转移

```text
UPLOADED
  ↓
PARSING
  ↓
PARSED
  ↓
CLEANING
  ↓
CHUNKING
  ↓
DEDUPING
  ↓
EMBEDDING
  ↓
INDEXING
  ↓
READY
```

异常分支：

```text
任意节点失败
  ↓
FAILED
  ↓
RETRYING
  ↓
从失败节点重新执行
```

---

### 19.5.2 RAG 查询状态转移

```text
RECEIVED
  ↓
SAFETY_CHECKING
  ↓
REWRITING
  ↓
RETRIEVING
  ↓
RERANKING
  ↓
FILTERING
  ↓
GENERATING
  ↓
GROUNDING
  ↓
ANSWERED
```

拒答分支：

```text
无召回结果
权限过滤后为空
上下文为空
Grounding 不通过
  ↓
REFUSED
```

失败分支：

```text
LLM 调用失败
Embedding 调用失败
Qdrant 查询失败
  ↓
FAILED
```

---

## 19.6 节点输入输出契约

每个节点都要定义：

```text
node_name
required_input_keys
optional_input_keys
output_keys
possible_status
retryable
```

示例：

```python
class NodeContract(TypedDict):
    node_name: str
    required_input_keys: list[str]
    optional_input_keys: list[str]
    output_keys: list[str]
    possible_status: list[str]
    retryable: bool
```

---

### 19.6.1 HybridRetrieveNode Contract

```python
HybridRetrieveNodeContract = {
    "node_name": "HybridRetrieveNode",
    "required_input_keys": [
        "tenant_id",
        "knowledge_base_id",
        "expanded_queries",
    ],
    "optional_input_keys": [
        "query_filters",
        "retrieval_top_k",
    ],
    "output_keys": [
        "vector_results",
        "bm25_results",
        "retrieved_docs",
    ],
    "possible_status": [
        "success",
        "failed",
    ],
    "retryable": True,
}
```

---

### 19.6.2 PermissionFilterNode Contract

```python
PermissionFilterNodeContract = {
    "node_name": "PermissionFilterNode",
    "required_input_keys": [
        "tenant_id",
        "user_id",
        "metadata_filtered_docs",
    ],
    "optional_input_keys": [
        "permissions",
    ],
    "output_keys": [
        "permitted_docs",
    ],
    "possible_status": [
        "success",
        "refused",
        "failed",
    ],
    "retryable": False,
}
```

---

### 19.6.3 AnswerGenerateNode Contract

```python
AnswerGenerateNodeContract = {
    "node_name": "AnswerGenerateNode",
    "required_input_keys": [
        "user_query",
        "final_context",
        "prompt_template",
    ],
    "optional_input_keys": [
        "citations",
    ],
    "output_keys": [
        "answer",
        "raw_llm_response",
        "token_usage",
    ],
    "possible_status": [
        "success",
        "failed",
    ],
    "retryable": True,
}
```

---

## 19.7 推荐节点包装器

为了保证每个节点都能记录日志、错误和耗时，建议不要直接调用节点函数，而是通过统一 wrapper 执行。

```python
import time
from functools import wraps


def now_iso() -> str:
    # 实际项目中建议放到 app/core/time.py
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def graph_node(node_name: str, output_keys: list[str], retryable: bool = False):
    def decorator(func):
        @wraps(func)
        def wrapper(state: dict) -> dict:
            start = time.time()

            state["current_node"] = node_name
            state["status"] = "RUNNING"

            try:
                result = func(state)

                latency_ms = int((time.time() - start) * 1000)

                result.setdefault("node_history", []).append({
                    "node_name": node_name,
                    "status": "success",
                    "output_keys": output_keys,
                    "latency_ms": latency_ms,
                    "started_at": state.get("updated_at"),
                    "ended_at": now_iso(),
                })

                result["previous_node"] = node_name
                result["updated_at"] = now_iso()

                return result

            except Exception as e:
                latency_ms = int((time.time() - start) * 1000)

                state.setdefault("node_history", []).append({
                    "node_name": node_name,
                    "status": "failed",
                    "output_keys": output_keys,
                    "latency_ms": latency_ms,
                    "error": str(e),
                    "ended_at": now_iso(),
                })

                state.setdefault("errors", []).append({
                    "node_name": node_name,
                    "error": str(e),
                    "retryable": retryable,
                })

                state["status"] = "FAILED"
                state["error_message"] = str(e)
                state["updated_at"] = now_iso()

                return state

        return wrapper

    return decorator
```

---

## 19.8 条件路由设计

LangGraph 的关键不是只做顺序执行，而是根据状态做条件路由。

### 19.8.1 安全检查路由

```python
def route_after_safety_check(state: RAGQueryState) -> str:
    if not state.get("input_safe", True):
        return "refusal"
    return "intent_classify"
```

---

### 19.8.2 检索后路由

```python
def route_after_retrieve(state: RAGQueryState) -> str:
    docs = state.get("retrieved_docs", [])
    if not docs:
        state["refused"] = True
        state["refusal_reason"] = "NO_RETRIEVED_DOCS"
        return "refusal"
    return "rerank"
```

---

### 19.8.3 权限过滤后路由

```python
def route_after_permission_filter(state: RAGQueryState) -> str:
    docs = state.get("permitted_docs", [])
    if not docs:
        state["refused"] = True
        state["refusal_reason"] = "NO_PERMISSION_DOCS"
        return "refusal"
    return "context_build"
```

---

### 19.8.4 Grounding 后路由

```python
def route_after_grounding(state: RAGQueryState) -> str:
    grounding = state.get("grounding_result", {})
    if not grounding.get("grounded", False):
        state["refused"] = True
        state["refusal_reason"] = "GROUNDING_FAILED"
        return "refusal"
    return "final_answer"
```

---

## 19.9 状态持久化设计

复杂项目中，State 不应该只存在内存中。

建议持久化三类数据：

```text
1. 任务级状态
2. 节点级执行日志
3. 最终业务结果
```

### 19.9.1 graph_runs 表

```text
id
request_id
trace_id
graph_name
tenant_id
user_id
status
current_node
input_json
output_json
error_message
created_at
updated_at
finished_at
```

---

### 19.9.2 graph_node_runs 表

```text
id
graph_run_id
node_name
status
input_keys_json
output_keys_json
latency_ms
error_message
retryable
retry_count
started_at
finished_at
```

---

### 19.9.3 graph_state_snapshots 表

```text
id
graph_run_id
node_name
state_json
created_at
```

建议：

```text
开发环境保存完整 state。
生产环境保存关键字段，避免存储过大或泄露敏感数据。
```

---

## 19.10 状态机开发顺序建议

建议先开发状态机基础能力，再开发复杂节点。

### Step 1：定义 BaseState

```text
app/graphs/base/state.py
```

### Step 2：定义节点状态枚举

```text
app/graphs/base/enums.py
```

### Step 3：定义 NodeContract

```text
app/graphs/base/contracts.py
```

### Step 4：定义 graph_node wrapper

```text
app/graphs/base/node_wrapper.py
```

### Step 5：定义状态持久化 Repository

```text
app/db/repositories/graph_run_repository.py
```

### Step 6：定义 State Snapshot 机制

```text
每个节点执行后保存一次关键 state。
```

### Step 7：将状态机接入 IngestionGraph

先接入：

```text
DocumentIngestionGraph
```

因为它流程稳定，便于验证状态流转。

### Step 8：将状态机接入 RAGQueryGraph

再接入：

```text
RAGQueryGraph
```

因为它涉及更多条件路由和拒答分支。

---

## 19.11 状态机最佳实践

### 19.11.1 State 字段不要无限膨胀

不要把所有中间数据都塞进 state。

例如：

```text
大文件原文
超长 LLM response
完整 embedding vector
```

可以只存引用：

```text
file_path
object_storage_key
vector_id
artifact_path
```

---

### 19.11.2 敏感字段不要完整落库

例如：

```text
用户隐私
API Key
Token
内部连接字符串
敏感文档全文
```

需要：

```text
脱敏
截断
加密
按环境控制是否保存
```

---

### 19.11.3 每个节点必须可单测

节点函数应该做到：

```text
输入 state
输出 state
无隐藏全局依赖
外部依赖通过 service 注入
```

---

### 19.11.4 每个节点必须幂等

尤其是：

```text
QdrantIndexNode
UpdateDocumentStatusNode
AuditLogNode
```

重复执行时不能产生严重副作用。

---

### 19.11.5 状态机和数据库状态要对齐

例如文档入库：

```text
state.status
documents.status
ingestion_tasks.status
```

三者必须保持一致。

---

## 19.12 建议目录补充

```text
app/
  graphs/
    base/
      state.py
      enums.py
      contracts.py
      node_wrapper.py
      routing.py
      persistence.py

    ingestion/
      state.py
      graph.py
      nodes.py
      routes.py

    rag/
      state.py
      graph.py
      nodes.py
      routes.py

    security/
      state.py
      graph.py
      nodes.py
      routes.py

    evaluation/
      state.py
      graph.py
      nodes.py
      routes.py

    agents/
      state.py
      business_graph.py
      ppt_graph.py
      workflow_graph.py
      crawler_graph.py
      routes.py
```

---

## 19.13 状态机优先后的开发顺序调整

原始开发顺序：

```text
基础 RAG 闭环 → 增强检索 → 异步工程化 → 权限安全 → 评测 → 业务 Agent
```

建议调整为：

```text
1. FastAPI / DB / Qdrant / LLM / Embedding 基础连接
2. BaseState / NodeContract / NodeWrapper / 状态持久化
3. DocumentIngestionGraph
4. RAGQueryGraph
5. 条件路由和拒答机制
6. 权限状态机
7. Evaluation 状态机
8. Business Agent 状态机
```

也就是说：

> 先把状态机骨架设计好，再开发具体节点。节点可以逐步增强，但 State 和状态转移如果一开始混乱，后面重构成本会非常高。

---

# 20. 最终交付目标

完成后系统应具备：

```text
1. 企业文档自动入库
2. 企业知识统一检索
3. 基于权限的安全问答
4. 答案引用来源可追踪
5. 无依据问题可拒答
6. 检索和生成链路可观测
7. RAG 效果可评测
8. 可扩展业务 Agent 工作流
```

最终定位：

> 面向企业知识管理的 RAG Agent 工作流平台。系统基于 FastAPI 提供服务接口，基于 LangGraph 编排多节点智能流程，结合文档解析、向量检索、混合召回、重排序、权限过滤、引用校验和业务 Agent，实现从知识入库、智能问答到复杂业务产物生成的一体化平台。
