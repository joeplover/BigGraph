-- ============================================================================
-- PostgreSQL 建表脚本 — 企业级 RAG 知识库平台
-- 对应 Python 模型: postgre_model.py
-- 开发文档 16.3 节: PostgreSQL 作为元数据中心 & 持久化层
--
-- 使用方式:
--   psql -U rag -d rag -f postgre_schema.sql
-- 或:
--   pgAdmin → Query Tool → 粘贴执行
-- ============================================================================

-- 如果数据库不存在，先手动创建:
-- CREATE DATABASE rag WITH ENCODING 'UTF8' LC_COLLATE='zh_CN.UTF-8' LC_CTYPE='zh_CN.UTF-8';


-- ============================================================================
-- 1. 枚举类型
-- ============================================================================

-- 文档生命周期状态
--   pending  : 初始状态，文档刚创建但还没处理完
--   active   : 文档已全部处理完成（含向量索引），可被检索
--   archived : 已归档，不再参与检索但保留数据
--   deleted  : 软删除标记
--   failed   : 解析/处理流程中出错
DO $$ BEGIN
    CREATE TYPE document_status AS ENUM (
        'pending', 'active', 'archived', 'deleted', 'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 导入任务阶段状态
--   pending   : 任务刚创建，等待处理
--   parsing   : 正在解析文件（PDF/DOCX/TXT 等）
--   cleaning  : 正在文本清洗（去除零宽字符、合并断行等）
--   chunking  : 正在将清洗后文本切片成 chunk
--   embedding : 正在调用 embedding 模型生成向量
--   indexing  : 正在写入 Qdrant + ES
--   completed : 全部处理完成，文档可被检索
--   failed    : 处理过程中出现不可恢复的错误
--   cancelled : 被用户手动取消
DO $$ BEGIN
    CREATE TYPE ingestion_job_status AS ENUM (
        'pending', 'parsing', 'cleaning', 'chunking',
        'embedding', 'indexing', 'completed', 'failed', 'cancelled'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 单一路径（Qdrant 或 ES）的同步状态
--   pending : 等待写入，还没开始处理
--   indexed : 写入成功，数据已可用
--   partial : 写入部分成功（如批量写入时部分失败），需重试
--   failed  : 写入彻底失败（如连接异常），需人工介入
DO $$ BEGIN
    CREATE TYPE vector_sync_status AS ENUM (
        'pending', 'indexed', 'partial', 'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 知识库成员角色
DO $$ BEGIN
    CREATE TYPE kb_member_role AS ENUM ('viewer', 'editor');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 知识库成员状态
DO $$ BEGIN
    CREATE TYPE kb_member_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================================
-- 1.5 用户表
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(50) NOT NULL,               -- 登录用户名
    password_hash   VARCHAR(255) NOT NULL,              -- bcrypt 哈希
    display_name    VARCHAR(100),                       -- 显示名称
    email           VARCHAR(100),                       -- 邮箱
    is_verified     BOOLEAN DEFAULT false,              -- 邮箱是否已验证
    tenant_id       VARCHAR(64) NOT NULL,               -- 绑定的默认租户
    is_active       BOOLEAN DEFAULT true,               -- 账户是否激活
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);


-- ============================================================================
-- 2. 知识库表（修改版 — 增加 owner_id 和 share_code）
-- ============================================================================
-- 用途: 租户下的知识库分组，一个知识库包含多篇文档
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   VARCHAR(64) NOT NULL,          -- 租户 ID（隔离键）
    name        VARCHAR(255) NOT NULL,          -- 知识库名称
    description TEXT,                           -- 知识库描述
    owner_id    UUID REFERENCES users(id),      -- 知识库创建者
    share_code  VARCHAR(64) UNIQUE,             -- 分享码，用于通过链接加入
    metadata    JSONB DEFAULT '{}'::jsonb,      -- 扩展元数据
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引: 按租户查询知识库列表
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_tenant ON knowledge_bases(tenant_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_owner ON knowledge_bases(owner_id);


-- ============================================================================
-- 3. 上传文件记录表
-- ============================================================================
-- 用途: 记录每次文件上传的信息，一个文件对应一篇文档
CREATE TABLE IF NOT EXISTS uploaded_files (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         VARCHAR(64) NOT NULL,     -- 租户 ID
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
    original_name     VARCHAR(512) NOT NULL,    -- 原始文件名（含后缀）
    storage_path      VARCHAR(1024) NOT NULL,   -- 服务器上的存储路径
    content_type      VARCHAR(255),             -- MIME 类型
    size_bytes        INTEGER DEFAULT 0,        -- 文件大小（字节）
    file_hash         VARCHAR(64),              -- SHA256 哈希，用于文件去重
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_tenant ON uploaded_files(tenant_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_hash ON uploaded_files(file_hash);


-- ============================================================================
-- 4. 文档表
-- ============================================================================
-- 用途: 解析后的文档记录。一个上传文件（uploaded_file）解析后生成一篇文档（document）。
--       文档下包含多个 chunk（document_chunks）。
CREATE TABLE IF NOT EXISTS documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         VARCHAR(64) NOT NULL,                    -- 租户 ID
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
    file_id           UUID NOT NULL REFERENCES uploaded_files(id),
    title             VARCHAR(512) NOT NULL,                   -- 文档标题
    source_type       VARCHAR(64) DEFAULT 'upload',            -- 来源类型: upload / api / crawl
    source_uri        VARCHAR(1024),                           -- 来源路径/URL
    status            document_status DEFAULT 'pending',       -- 文档状态
    version           INTEGER DEFAULT 1,                       -- 版本号（覆盖上传时递增）
    parser_name       VARCHAR(128),                            -- 解析器名称: pdf_parser / docx_parser 等
    parser_version    VARCHAR(64),                             -- 解析器版本
    metadata          JSONB DEFAULT '{}'::jsonb,               -- 扩展元数据（如页数、作者等）
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_kb ON documents(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);


-- ============================================================================
-- 5. 文档块表（核心关联表）
-- ============================================================================
-- 用途: 连接 Qdrant 和 ES 的桥梁。一份文档被切成多个 chunk，
--       每个 chunk 在 Qdrant 中有一个 point，在 ES 中有一个 document。
--       PostgreSQL 是记录系统（source of truth）。
CREATE TABLE IF NOT EXISTS document_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         VARCHAR(64) NOT NULL,                    -- 租户 ID
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
    document_id       UUID NOT NULL REFERENCES documents(id),
    file_id           UUID NOT NULL REFERENCES uploaded_files(id),

    -- --- chunk 内容 ---
    chunk_index       INTEGER NOT NULL,                        -- 在文档中的序号（从 0 开始）
    content           TEXT NOT NULL,                           -- 清洗后的完整文本
    content_type      VARCHAR(64) DEFAULT 'text',              -- 内容类型: text / table / image
    heading_path      VARCHAR(1024),                           -- 标题路径，如 "员工手册 / 考勤制度 / 请假流程"
    page_start        INTEGER,                                 -- 起始页码
    page_end          INTEGER,                                 -- 结束页码
    token_count       INTEGER DEFAULT 0,                       -- 字符数 / token 数

    -- --- 外部系统关联 ---
    qdrant_point_id   VARCHAR(128),                            -- Qdrant 中的 point UUID
    es_doc_id         VARCHAR(128),                            -- ES 中的文档 _id

    -- --- 同步状态 ---
    qdrant_sync       vector_sync_status DEFAULT 'pending',    -- 写入 Qdrant 的状态
    es_sync           vector_sync_status DEFAULT 'pending',    -- 写入 ES 的状态
    vector_status     VARCHAR(64) DEFAULT 'pending',           -- 整体索引状态（pending / indexed / partial）

    -- --- 元数据 ---
    keywords          JSONB DEFAULT '[]'::jsonb,               -- 关键词列表
    metadata          JSONB DEFAULT '{}'::jsonb,               -- 扩展元数据

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引: 按文档查所有 chunk
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
-- 索引: 按租户过滤
CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON document_chunks(tenant_id);
-- 索引: 通过 Qdrant point_id 反查 chunk
CREATE INDEX IF NOT EXISTS idx_chunks_qdrant_point ON document_chunks(qdrant_point_id);
-- 索引: 通过 ES doc_id 反查 chunk
CREATE INDEX IF NOT EXISTS idx_chunks_es_doc ON document_chunks(es_doc_id);
-- 索引: 查询未同步的 chunk（用于补偿任务）
CREATE INDEX IF NOT EXISTS idx_chunks_sync_status ON document_chunks(vector_status);


-- ============================================================================
-- 6. 导入任务表
-- ============================================================================
-- 用途: 追踪文档从上传到索引完成的整个过程
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         VARCHAR(64) NOT NULL,                    -- 租户 ID
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
    file_id           UUID NOT NULL REFERENCES uploaded_files(id),
    document_id       UUID REFERENCES documents(id),           -- 处理完成后关联的文档

    status            ingestion_job_status DEFAULT 'pending',  -- 任务状态
    error_message     TEXT,                                    -- 失败时的错误信息
    progress          INTEGER DEFAULT 0,                       -- 进度百分比 0-100
    retry_count       INTEGER DEFAULT 0,                       -- 已重试次数

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON ingestion_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_kb ON ingestion_jobs(knowledge_base_id);


-- ============================================================================
-- 7. 知识库成员表
-- ============================================================================
-- 用途: 记录知识库的成员和加入状态
CREATE TABLE IF NOT EXISTS kb_members (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
    user_id           UUID NOT NULL REFERENCES users(id),
    role              kb_member_role DEFAULT 'viewer',
    status            kb_member_status DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_members_kb ON kb_members(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_kb_members_user ON kb_members(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_members ON kb_members(knowledge_base_id, user_id);


-- ============================================================================
-- 8. 更新时间触发器（自动更新 updated_at）
-- ============================================================================
-- 作用: 在 UPDATE 时自动将 updated_at 设为当前时间，不需要应用层手动维护
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为每张表注册触发器
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY[
            'knowledge_bases', 'uploaded_files', 'documents',
            'document_chunks', 'ingestion_jobs', 'users', 'kb_members'
        ])
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s;', tbl, tbl
        );
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at
             BEFORE UPDATE ON %s
             FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();',
            tbl, tbl
        );
    END LOOP;
END;
$$;


-- ============================================================================
-- 8. 外键索引补充（确保 JOIN 性能）
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_uploaded_files_kb ON uploaded_files(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_file ON documents(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON document_chunks(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON document_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_jobs_file ON ingestion_jobs(file_id);
CREATE INDEX IF NOT EXISTS idx_jobs_doc ON ingestion_jobs(document_id);


-- ============================================================================
-- 9. 完整性约束
-- ============================================================================
-- 确保同一个文档内 chunk_index 不重复
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_doc_index
    ON document_chunks(document_id, chunk_index);

-- 确保同一知识库下知识库名称不重复（可选，按需启用）
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_name_tenant
--     ON knowledge_bases(tenant_id, name);
