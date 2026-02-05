# Data Model: Duplicate Detection Microservice

**Branch**: 001-duplicate-detection  
**Date**: 2026-02-04  
**Input**: spec.md, plan.md, research.md

## Scope

All data is scoped to a single conversation (zid). No cross-conversation queries or global embedding reuse (constitution VII).

## Entities

### Conversation (logical)

- **Identity**: `zid` (integer, conversation id from Polis).
- **Role**: Scoping boundary; every check and storage operation is for one conversation.
- **No local table**: The microservice does not own the conversation; it only uses `zid` to filter embeddings and similar comments.

### Comment (logical, input/output)

- **Identity**: Within a conversation, `tid` (integer, comment id from Polis).
- **Attributes**: `zid`, `tid`, `txt` (comment text, max length per Polis: 1000 chars).
- **Role**: Input to duplicate-check and to store-embedding; output as similar comment (identifier + text + similarity/tier).
- **No local comments table**: The microservice stores only what it needs for similarity (embeddings + text for similar-comment responses).

### Comment embedding (persistent)

Stored in PostgreSQL table `comment_embeddings`.

| Field      | Type         | Constraints | Description |
|-----------|--------------|-------------|-------------|
| zid       | INTEGER      | NOT NULL, PK | Conversation id |
| tid       | INTEGER      | NOT NULL, PK | Comment id within conversation |
| txt       | VARCHAR(1000)| NOT NULL     | Comment text (for similar-comment responses) |
| embedding | vector(384)  | NOT NULL     | pgvector; normalized embedding from all-MiniLM-L6-v2 |
| created   | BIGINT       | DEFAULT now_as_millis() | Creation time (optional) |

- **Primary key**: (zid, tid).
- **Uniqueness**: One row per (zid, tid); store is idempotent (upsert on same key).
- **Index**: HNSW on `embedding` with `vector_cosine_ops` for similarity search.
- **Validation**: `txt` length ≤ 1000; embedding dimension 384.

### Similarity result (in-memory / API response)

- **Attributes**:
  - `tier`: one of `block` | `warn` | `related` | `allow`.
  - `similar_comments`: list of { `tid`, `txt`, `similarity` (float), `tier` }.
- **Derivation**: From embedding similarity vs thresholds; tier = block if similarity ≥ block threshold, warn if ≥ warn threshold, etc.
- **No persistence**: Returned only in check response.

## State transitions

- **Store embedding**: Caller provides (zid, tid, txt). Service computes embedding, then upserts row (zid, tid, txt, embedding). Idempotent for same (zid, tid).
- **Check duplicate**: Caller provides (zid, txt). Service computes embedding for txt, queries `comment_embeddings` for same zid by cosine similarity, classifies each match into tier, returns tier and similar_comments. No state change.

## Validation rules (from spec)

- Comment text: non-empty; max length 1000 (align with Polis).
- Conversation id (zid): required; integer.
- Comment id (tid) for store: required; integer.
- Invalid or missing required fields → structured 4xx error (FR-009).

## Relationships

- `comment_embeddings.zid` scopes all rows to one conversation.
- Similar comments returned in check are only from the same `zid`.
- No foreign key to Polis `comments` table in this service (microservice may use its own DB or shared DB; schema is compatible with Polis comments (zid, tid) for future integration).
