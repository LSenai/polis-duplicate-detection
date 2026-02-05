# Research: Duplicate Detection Microservice

**Branch**: 001-duplicate-detection  
**Date**: 2026-02-04  
**Input**: Technical context from plan.md; polis_duplicate_detection_feasibility.md

## 1. Embedding model

**Decision**: Use `sentence-transformers/all-MiniLM-L6-v2` for comment embeddings.

**Rationale**:
- Already used in Polis embedding infrastructure (Delphi/EVōC); validated for this domain.
- Fast inference (~100 ms for small batches), small footprint (~80 MB), 384 dimensions.
- Multilingual support; Apache 2.0 license; runs on CPU.
- Constitution requires pinned model and CPU-friendly choice.

**Alternatives considered**:
- Larger sentence-transformers models: Better quality but higher latency and memory; rejected for <200 ms target.
- OpenAI/Cohere embeddings: Requires proprietary API and network; constitution requires no proprietary APIs.
- Custom fine-tuned model: Out of scope for initial microservice; can be revisited later.

---

## 2. Similarity thresholds

**Decision**: Configurable thresholds with default values: block ≥0.93, warn 0.88–0.93, related 0.75–0.88, below 0.75 = different. Exact values MUST be validated and tested (constitution + spec).

**Rationale**:
- Polis is opinion-based; precision over recall to avoid blocking distinct opinions.
- Feasibility and spec: conservative block threshold (0.93) so only true paraphrases are blocked.
- Thresholds must be explicit, configurable (e.g. env or config file), and covered by tests.

**Alternatives considered**:
- Lower block threshold (e.g. 0.90): Higher recall but more false positives; rejected per spec (distinct opinions must not be blocked).
- Fixed thresholds in code: Rejected; constitution requires externally configurable thresholds.

---

## 3. Vector storage and search

**Decision**: PostgreSQL with pgvector extension; table `comment_embeddings` with HNSW index on embedding (cosine); similarity via `1 - (embedding <=> $1)`; queries scoped by conversation id (zid).

**Rationale**:
- Spec and feasibility: single-conversation scale; pgvector allows indexed vector search in same DB as Polis.
- HNSW (vector_cosine_ops) gives sublinear search; sufficient for tens of thousands of comments per conversation.
- No new infrastructure; aligns with “real vector index” (constitution).

**Alternatives considered**:
- FAISS: Faster at very large scale but adds another component; pgvector keeps one DB and matches Polis stack.
- DynamoDB (existing Polis embeddings): No native vector search; scan not suitable for real-time check; rejected.
- Redis/RediSearch: Extra infra; deferred unless latency demands it.

---

## 4. API framework and shape

**Decision**: FastAPI; JSON-only; two main endpoints: (1) POST check (conversation id + comment text → similarity result with tier and similar comments), (2) POST store (conversation id + comment id + text → store embedding). Health/readiness endpoint; documented recommended timeout (e.g. 2 s) for check.

**Rationale**:
- Spec: stable JSON API, explicit schemas, consistent error structure, health/readiness (FR-010).
- FastAPI provides OpenAPI schemas, validation, and async support; fits Python microservice.
- Polis integration (comments.ts) will call check before insert and store after insert; API shape supports that flow.

**Alternatives considered**:
- Flask: Viable but FastAPI gives schemas and async out of the box.
- GraphQL: Spec and Polis call pattern are request/response; REST/JSON is sufficient.

---

## 5. Fail-open and defensive behavior

**Decision**: All internal failures, timeouts, and unhandled errors result in a response that allows the caller to treat the outcome as “allow” (no block). Invalid input returns structured 4xx with consistent error body. No uncaught exceptions to caller. External calls (e.g. DB) use timeouts.

**Rationale**:
- Spec FR-007, FR-009: fail-open; structured errors for invalid input.
- Constitution VI: failures default to allow; timeouts; structured errors; no uncaught exceptions.

**Alternatives considered**:
- Returning 5xx on internal errors: Caller could interpret as “block”; rejected; fail-open only.
- No timeouts: Rejected; constitution requires timeouts on external calls.

---

## 6. Scale assumption (single-conversation)

**Decision**: Design and validate for single-conversation scale: order of magnitude up to tens of thousands of comments per conversation (e.g. 10k–50k). Document in plan; no cross-conversation or global-scale requirement in this phase.

**Rationale**:
- Spec clarification: single-conversation scale only; plan documents order of magnitude.
- pgvector HNSW and <200 ms target are feasible at this scale with indexed search and CPU model.

**Alternatives considered**:
- Global cross-conversation index: Out of scope; constitution requires conversation-scoped data only.
- Hard numeric cap in spec: Avoided; order-of-magnitude in plan is sufficient for design.

---

## 7. Integration with Polis (later phase)

**Decision**: Integration points (server/src/routes/comments.ts handle_POST_comments, DB schema in Polis DB, client 409 handling) are out of scope for this plan. Microservice is built to be called by Polis server: check before insert, store after insert; API contract and error shape designed so Polis can implement fail-open and timeout on its side.

**Rationale**:
- Spec: integration addressed in integration/planning.
- Plan focuses on microservice implementation; Polis-side changes are a separate step.

**Alternatives considered**:
- In-process Polis plugin: Rejected for this plan; microservice is the chosen architecture (spec + feasibility).
