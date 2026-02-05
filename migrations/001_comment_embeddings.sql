-- Duplicate Detection: comment_embeddings table and HNSW index
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;
-- Per data-model.md: zid (conversation), tid (comment), txt, embedding vector(384), created

CREATE TABLE IF NOT EXISTS comment_embeddings (
    zid INTEGER NOT NULL,
    tid INTEGER NOT NULL,
    txt VARCHAR(1000) NOT NULL,
    embedding vector(384) NOT NULL,
    created BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    PRIMARY KEY (zid, tid)
);

-- HNSW index for fast cosine similarity search (per-conversation queries use zid filter)
CREATE INDEX IF NOT EXISTS comment_embeddings_vector_idx
ON comment_embeddings
USING hnsw (embedding vector_cosine_ops);
