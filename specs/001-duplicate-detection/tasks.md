# Tasks: Duplicate Detection Microservice

**Input**: Design documents from `specs/001-duplicate-detection/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Constitution mandates test-first development; tests are required for each user story. Write tests first, observe failure, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/` at repository root (per plan.md)
- Source: `src/api/`, `src/services/`, `src/config/`, `src/models/` (if needed)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per plan.md: directories src/api, src/services, src/config, src/models, tests/unit, tests/integration, tests/contract
- [x] T002 Add requirements.txt or pyproject.toml with Python 3.11+, FastAPI, sentence-transformers, pgvector driver (e.g. asyncpg with pgvector), uvicorn, pytest, pydantic
- [x] T003 [P] Configure linting and formatting (e.g. ruff, black) in pyproject.toml or config at repo root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story. No user story work can begin until this phase is complete.

- [x] T004 Create database schema for comment_embeddings (zid, tid, txt, embedding vector(384), created) and HNSW index per data-model.md; add migration script or SQL file in repo (e.g. migrations/ or docs/)
- [x] T005 [P] Add config module: load THRESHOLD_BLOCK, THRESHOLD_WARN, THRESHOLD_RELATED and DATABASE_URL from env; no inline config; in src/config/settings.py
- [x] T006 [P] Implement DB connection with timeout (e.g. asyncpg + pgvector) in src/services/db.py or src/api/deps.py
- [x] T007 Load sentence-transformers model all-MiniLM-L6-v2 once (singleton or app state) in src/services/embedding.py
- [x] T008 Add structured error response schema (error, detail) and exception handlers for 4xx in src/api/errors.py and wire in FastAPI app
- [x] T009 Add structured logging (JSON or key-value) in src/api/main.py or middleware
- [x] T010 Implement GET /health (readiness) in src/api/routes.py and wire in FastAPI app in src/api/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Check Comment for Semantic Duplicates (Priority: P1) MVP

**Goal**: Caller can POST /check with zid and txt; service returns tier (block/warn/related/allow) and similar_comments. Precision over recall; conversation-scoped only.

**Independent Test**: Call POST /check with a new comment and existing conversation; verify response includes correct tier and similar comments when applicable.

### Tests for User Story 1 (test-first: write these first, observe failure)

- [x] T011 [P] [US1] Unit tests for similarity tier classification (block/warn/related/allow) with real text examples and threshold boundaries in tests/unit/test_similarity.py
- [x] T012 [P] [US1] Unit tests for threshold config (named constants, no magic numbers) in tests/unit/test_thresholds.py
- [x] T013 [P] [US1] Unit tests for embedding generation (output shape 384, deterministic for same input) in tests/unit/test_embedding.py
- [x] T014 [US1] Integration test for POST /check: no similar comments returns allow; with similar returns tier and similar_comments; conversation-scoped in tests/integration/test_check.py

### Implementation for User Story 1

- [x] T015 [P] [US1] Add Pydantic schemas CheckRequest, CheckResponse, SimilarComment per contracts/openapi.yaml in src/api/schemas.py
- [x] T016 [US1] Implement embedding service: generate_embedding(text) returns normalized 384-dim vector in src/services/embedding.py using all-MiniLM-L6-v2
- [x] T017 [US1] Implement similarity/tier classification: score to tier (block/warn/related/allow) using config thresholds; single-purpose, documented in src/services/similarity.py
- [x] T018 [US1] Implement storage layer: query similar comments by zid and embedding (pgvector cosine similarity, limit) in src/services/storage.py
- [x] T019 [US1] Implement check flow: embed text, query similar, classify each match, determine overall tier, build CheckResponse in src/services/check_service.py
- [x] T020 [US1] Implement POST /check route with validation (zid required, txt length 1-1000); return 4xx for invalid input in src/api/routes.py
- [x] T021 [US1] Wire check route; on internal exception return allow-shaped response (tier=allow, similar_comments=[]) so caller never blocks on service failure in src/api/

**Checkpoint**: User Story 1 fully functional and testable independently

---

## Phase 4: User Story 2 - Store Embedding After Comment Is Accepted (Priority: P2)

**Goal**: Caller can POST /store with zid, tid, txt; service stores embedding; idempotent for same (zid, tid). Future /check in that conversation includes stored comment.

**Independent Test**: POST /store for (zid, tid, txt); then POST /check with paraphrase of txt; verify similar_comments contains stored comment.

### Tests for User Story 2 (test-first)

- [x] T022 [P] [US2] Integration test for POST /store then POST /check finds similar comment in tests/integration/test_store.py
- [x] T023 [P] [US2] Integration test for POST /store idempotent: same zid,tid twice yields single representation in tests/integration/test_store.py

### Implementation for User Story 2

- [x] T024 [US2] Add Pydantic schemas StoreRequest, StoreResponse per contracts/openapi.yaml in src/api/schemas.py
- [x] T025 [US2] Implement upsert (zid, tid, txt, embedding) in storage layer; one row per (zid, tid) in src/services/storage.py
- [x] T026 [US2] Implement store flow: embed txt, upsert row in src/services/store_service.py
- [x] T027 [US2] Implement POST /store route with validation (zid, tid, txt 1-1000); return 4xx for invalid input in src/api/routes.py
- [x] T028 [US2] Wire store route; on internal error return structured error or allow-shaped response per fail-open (store does not block participation) in src/api/

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - Fail-Open and Structured Errors (Priority: P1)

**Goal**: Invalid input returns 4xx with consistent error body; timeouts/errors never cause caller to block comments; no uncaught exceptions to caller.

**Independent Test**: Simulate invalid POST /check and POST /store; simulate DB down or timeout; verify 4xx body shape and allow-shaped response for check.

### Tests for User Story 3 (test-first)

- [x] T029 [P] [US3] Integration test for POST /check with missing zid or txt returns 4xx with consistent error body in tests/integration/test_errors.py
- [x] T030 [P] [US3] Integration test for POST /store with missing zid, tid, or txt returns 4xx in tests/integration/test_errors.py
- [x] T031 [US3] Integration test for DB unavailable or timeout: POST /check returns allow-shaped response (tier=allow, similar_comments=[]) in tests/integration/test_errors.py

### Implementation for User Story 3

- [x] T032 [US3] Ensure all uncaught exceptions in /check path result in allow-shaped response (no 5xx that caller could interpret as block) in src/api/
- [x] T033 [US3] Document recommended timeout for POST /check (e.g. 2s) in OpenAPI description or README per spec Assumptions

**Checkpoint**: Fail-open and structured errors validated

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T034 [P] Add README with env vars, run, and test commands from specs/001-duplicate-detection/quickstart.md at repo root
- [x] T035 Run quickstart validation: start app, curl /health, POST /check, POST /store, verify behavior
- [x] T036 [P] Add type hints and docstrings to all public functions in src/; remove unused imports and dead code per constitution

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3–5)**: All depend on Foundational
  - US1 (Phase 3) can start after Phase 2 - no dependency on US2/US3
  - US2 (Phase 4) can start after Phase 2 - uses storage/embedding from US1
  - US3 (Phase 5) can start after Phase 2 - overlaps error handling with Phase 2 and US1
- **Polish (Phase 6)**: After desired user stories are complete

### Within Each User Story

- Tests MUST be written and MUST fail before implementation (test-first)
- Implementation order: schemas → services (embedding, similarity, storage) → routes → fail-open wiring

### Parallel Opportunities

- Phase 1: T003 [P]
- Phase 2: T005 [P], T006 [P]
- Phase 3: T011 [P], T012 [P], T013 [P]; T015 [P]
- Phase 4: T022 [P], T023 [P]; T024 [P]
- Phase 5: T029 [P], T030 [P]
- Phase 6: T034 [P], T036 [P]

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational  
3. Complete Phase 3: User Story 1 (tests first, then implementation)  
4. **STOP and VALIDATE**: Test US1 independently (POST /check, tier, similar_comments)  
5. Deploy/demo if ready  

### Incremental Delivery

1. Setup + Foundational → foundation ready  
2. Add User Story 1 → test independently → MVP  
3. Add User Story 2 → test independently (store + check)  
4. Add User Story 3 → test independently (errors, fail-open)  
5. Polish → quickstart and docs  

---

## Notes

- [P] = parallelizable; [US1/US2/US3] = user story for traceability  
- Each story is independently testable; commit after each task or logical group  
- Constitution: test-first, small single-purpose functions, named thresholds, structured logging, fail-open
