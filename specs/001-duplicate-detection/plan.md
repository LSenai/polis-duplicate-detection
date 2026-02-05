# Implementation Plan: Duplicate Detection Microservice

**Branch**: `001-duplicate-detection` | **Date**: 2026-02-04 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/001-duplicate-detection/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.

## Summary

Build a Python microservice that detects semantic paraphrases among Polis comments using embeddings (sentence-transformers all-MiniLM-L6-v2), classifies similarity into block / warn / related tiers with conservative thresholds (block ≥0.93), and returns structured JSON results. The service stores embeddings in PostgreSQL with pgvector, exposes a stable JSON API, and fails open on errors. Polis server integration (handle_POST_comments, client 409 handling) is deferred to a later phase.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, sentence-transformers (all-MiniLM-L6-v2), PostgreSQL with pgvector (e.g. psycopg2 or asyncpg + pgvector), uvicorn  
**Storage**: PostgreSQL with pgvector extension; table `comment_embeddings` (zid, tid, txt, embedding vector(384), created) with HNSW index for cosine similarity  
**Testing**: pytest; unit tests for embedding/similarity/threshold logic; integration tests for API and DB  
**Target Platform**: Linux server (local first, then deployable as microservice)  
**Project Type**: Single project (microservice)  
**Performance Goals**: Duplicate-check latency <200 ms end-to-end; indexed vector search; single-conversation scale (e.g. up to tens of thousands of comments per conversation)  
**Constraints**: <200 ms added to comment submission path; CPU-only (no GPU); fail-open on errors; thresholds configurable (block ≥0.93, warn 0.88–0.93, related 0.75–0.88)  
**Scale/Scope**: Single-conversation scale; order of magnitude documented in research (tens of thousands of comments per conversation for design/validation)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | Pass | Plan mandates unit + integration tests; threshold and similarity logic test-covered with real text examples. |
| II. Deterministic & Reproducible | Pass | Pinned model (all-MiniLM-L6-v2); explicit configurable thresholds; no randomness in scoring. |
| III. Clean, Readable, Explainable Code | Pass | Small single-purpose functions; docstrings; thresholds as named constants; rationale in comments. |
| IV. Opinion-Aware Similarity | Pass | Composable pipeline: embedding → similarity → tiered classification (block/warn/related); isolated, testable, documented. |
| V. Strict API Contract | Pass | JSON-only; explicit schemas; consistent error structure; documented and versioned. |
| VI. Fail-Open & Defensive | Pass | Timeouts on external calls; failures default to allow; structured errors for invalid input. |
| VII. Conversation-Scoped Data | Pass | All queries scoped by conversation id; no cross-conversation use; per-conversation indexing. |
| VIII. Performance as Design Constraint | Pass | <200 ms target; vector search indexed (HNSW); CPU-friendly model. |
| IX. No Hidden Product Logic | Pass | Service returns similarity results only; no blocking/merging/intent/ranking decisions. |

No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-duplicate-detection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md             # Created by /speckit.tasks
```

### Source Code (repository root)

```text
src/
├── api/                 # FastAPI app, routes, schemas
├── services/            # Embedding, similarity, storage
├── models/              # Domain / DB models (if any beyond schemas)
└── config/              # Thresholds, env (no inline config)

tests/
├── unit/                # Similarity, thresholds, embedding
├── integration/         # API + DB
└── contract/            # Optional API contract tests

# Optional: app entry at repo root
main.py or src/main.py
```

**Structure Decision**: Single Python project at repo root. FastAPI app in `src/api`, embedding and similarity logic in `src/services`, config (thresholds, env) in `src/config`. Tests mirror src layout. Aligns with constitution (small API surface, composable similarity pipeline, test-first).

## Complexity Tracking

> No constitution violations; table not used.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |
