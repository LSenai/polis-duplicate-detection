# polis-duplicate-detection

Microservice for semantic duplicate/paraphrase detection of Polis comments. All operations are scoped to a single conversation (zid). Fail-open: internal errors must not cause callers to block comments.

Development follows the project constitution in [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## How this service works with Polis

This service is a **separate microservice**: it does not read or manage the Polis database. The Polis server (or your backend) calls this service over HTTP; this service only stores what it needs for duplicate detection.

- **Identifiers**: `zid` is the Polis conversation id; `tid` is the comment/statement id within that conversation. These align with Polis’s conversation and comment model (see [repomix-polis-info.xml](repomix-polis-info.xml) for Polis codebase context).
- **Data flow**: When a participant submits a comment in Polis, the **Polis server** should call `POST /check` *before* inserting the comment. This service returns a tier (block / warn / related / allow) and a list of similar comments. The **Polis server** (or client) decides whether to block, show a warning, or allow—this service only returns the signal. After the comment is accepted and stored in Polis, the Polis server must call `POST /store` with the same (zid, tid, txt) so this service can store an embedding for future checks.
- **No Polis DB access**: This service maintains its own table of (zid, tid, txt, embedding). It is populated only via `POST /store`. For existing/historical comments, a one-time backfill (something with access to Polis comment data calling `POST /store` for each comment) is required.
- **Fail-open**: On timeout, 5xx, or unreachable service, the caller should treat the outcome as allow so participation is never blocked by this service.

## Prerequisites

- Python 3.11+
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension (or Docker for local DB)

## Local DB with Docker (recommended for testing)

From the repo root:

```bash
docker compose up -d
./scripts/db-setup.sh
```

Then set (or export) the DB URL used by the app and tests:

```bash
export DATABASE_URL="postgresql://polis_dup:polis_dup_dev@localhost:5432/duplicate_detection"
```

Stop the DB when done: `docker compose down`.

## Environment

Create a `.env` (or export) with:

```bash
# Database (microservice-owned or shared); for Docker local DB use:
# DATABASE_URL=postgresql://polis_dup:polis_dup_dev@localhost:5432/duplicate_detection
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
2. Run the migration:

```bash
psql -f migrations/001_comment_embeddings.sql $DATABASE_URL
```

Or apply the schema manually (see `migrations/001_comment_embeddings.sql` or `specs/001-duplicate-detection/data-model.md`).

## Install and run

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify

- **Health**: `curl http://localhost:8000/health`
- **Check** (no similar comments):  
  `curl -X POST http://localhost:8000/check -H "Content-Type: application/json" -d '{"zid": 1, "txt": "Hello world"}'`
- **Store**:  
  `curl -X POST http://localhost:8000/store -H "Content-Type: application/json" -d '{"zid": 1, "tid": 1, "txt": "Hello world"}'`
- **Check again** (paraphrase):  
  `curl -X POST http://localhost:8000/check -H "Content-Type: application/json" -d '{"zid": 1, "txt": "Hi world"}'`  
  Expect `tier` and `similar_comments` as per thresholds.

Recommended client timeout for `POST /check`: **2 seconds**; treat no response within that time as allow (fail-open). See `specs/001-duplicate-detection/contracts/openapi.yaml` for the API contract.

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

See `specs/001-duplicate-detection/contracts/openapi.yaml`.

## Integration (Polis server)

See [How this service works with Polis](#how-this-service-works-with-polis) above. In short:

- Call `POST /check` before comment insert; call `POST /store` after insert.
- Use recommended timeout (2 s); on timeout or 5xx, treat as allow (fail-open).
- Client: handle 409 (or equivalent) from the Polis server with similar comment suggestions when tier is block or warn.
- For Polis codebase context (conversations, comments, submission flow), see [repomix-polis-info.xml](repomix-polis-info.xml).
