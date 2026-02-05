# Quickstart: Duplicate Detection Microservice

**Branch**: 001-duplicate-detection  
**Date**: 2026-02-04

## Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- (Optional) Docker for local Postgres + pgvector

## Environment

Create a `.env` (or export) with:

```bash
# Database (microservice-owned or shared)
DATABASE_URL=postgresql://user:pass@localhost:5432/duplicate_detection

# Thresholds (configurable; defaults below)
THRESHOLD_BLOCK=0.93
THRESHOLD_WARN=0.88
THRESHOLD_RELATED=0.75

# Optional: recommended timeout to advertise for /check (seconds)
CHECK_TIMEOUT_RECOMMENDED=2
```

Do not commit secrets; use env or a secure config source.

## Database setup

1. Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Run migrations (or apply schema from data-model.md):

```sql
CREATE TABLE comment_embeddings (
    zid INTEGER NOT NULL,
    tid INTEGER NOT NULL,
    txt VARCHAR(1000) NOT NULL,
    embedding vector(384) NOT NULL,
    created BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    PRIMARY KEY (zid, tid)
);

CREATE INDEX comment_embeddings_vector_idx
ON comment_embeddings
USING hnsw (embedding vector_cosine_ops);
```

## Install and run

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

(Adjust module path if app lives at `main:app` at repo root.)

## Verify

- Health: `curl http://localhost:8000/health`
- Check (no similar comments):  
  `curl -X POST http://localhost:8000/check -H "Content-Type: application/json" -d '{"zid": 1, "txt": "Hello world"}'`
- Store:  
  `curl -X POST http://localhost:8000/store -H "Content-Type: application/json" -d '{"zid": 1, "tid": 1, "txt": "Hello world"}'`
- Check again (paraphrase):  
  `curl -X POST http://localhost:8000/check -H "Content-Type: application/json" -d '{"zid": 1, "txt": "Hi world"}'`  
  Expect tier and similar_comments as per thresholds.

## Tests

```bash
# Unit tests (similarity, thresholds, embedding)
pytest tests/unit -v

# Integration tests (API + DB)
pytest tests/integration -v

# All
pytest -v
```

Constitution: test-first; unit and integration tests mandatory; threshold and similarity logic covered with real text examples.

## API contract

See `specs/001-duplicate-detection/contracts/openapi.yaml`. Recommended timeout for `/check`: 2 s (caller may treat no response within that time as "allow").

## Integration with Polis

See the main repo [README](../../README.md) ("How this service works with Polis") and [repomix-polis-info.xml](../../repomix-polis-info.xml) for Polis codebase context. In short: Polis server calls `POST /check` before comment insert and `POST /store` after insert; use recommended timeout; on timeout or 5xx, treat as allow (fail-open). Client: handle 409 (or equivalent) from Polis server with similar comment suggestions when tier is block or warn.
