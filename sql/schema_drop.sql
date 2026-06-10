-- ============================================================================
-- PostgreSQL 删表脚本 — 用于开发环境重建
-- 使用方式: psql -U rag -d rag -f postgre_schema_drop.sql
-- ============================================================================

-- 删除触发器
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY[
            'knowledge_bases', 'uploaded_files', 'documents',
            'document_chunks', 'ingestion_jobs'
        ])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s;', tbl, tbl);
    END LOOP;
END;
$$;

-- 删除函数
DROP FUNCTION IF EXISTS update_updated_at_column();

-- 删除索引
DROP INDEX IF EXISTS idx_knowledge_bases_tenant;
DROP INDEX IF EXISTS idx_uploaded_files_tenant;
DROP INDEX IF EXISTS idx_uploaded_files_hash;
DROP INDEX IF EXISTS idx_uploaded_files_kb;
DROP INDEX IF EXISTS idx_documents_tenant;
DROP INDEX IF EXISTS idx_documents_kb;
DROP INDEX IF EXISTS idx_documents_status;
DROP INDEX IF EXISTS idx_documents_file;
DROP INDEX IF EXISTS idx_chunks_document;
DROP INDEX IF EXISTS idx_chunks_tenant;
DROP INDEX IF EXISTS idx_chunks_qdrant_point;
DROP INDEX IF EXISTS idx_chunks_es_doc;
DROP INDEX IF EXISTS idx_chunks_sync_status;
DROP INDEX IF EXISTS idx_chunks_kb;
DROP INDEX IF EXISTS idx_chunks_file;
DROP INDEX IF EXISTS idx_jobs_tenant;
DROP INDEX IF EXISTS idx_jobs_status;
DROP INDEX IF EXISTS idx_jobs_kb;
DROP INDEX IF EXISTS idx_jobs_file;
DROP INDEX IF EXISTS idx_jobs_doc;
DROP INDEX IF EXISTS uq_chunks_doc_index;

-- 删除表（按依赖顺序倒序）
DROP TABLE IF EXISTS ingestion_jobs;
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS uploaded_files;
DROP TABLE IF EXISTS knowledge_bases;

-- 删除类型
DROP TYPE IF EXISTS vector_sync_status;
DROP TYPE IF EXISTS ingestion_job_status;
DROP TYPE IF EXISTS document_status;
