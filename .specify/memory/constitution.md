<!--
  Sync Impact Report
  Version: (none) → 1.0.0
  Change: Initial ratification of Polis Duplicate Detection Service Constitution.
  Principles: Full replacement of generic 5-principle template with 9 project-specific principles.
  Added sections: Technology & Architecture Requirements, Development Workflow, Non-Goals, Governing Maxim.
  Removed sections: Generic placeholders (PRINCIPLE_1–5, SECTION_2, SECTION_3, GOVERNANCE_RULES).
  Templates: plan-template.md ✅ (Constitution Check remains generic); spec-template.md ✅ (no change);
  tasks-template.md ✅ (aligned test task note with constitution); checklist-template.md ✅ (no change).
  Follow-up TODOs: None.
-->

# Polis Duplicate Detection Service Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

All features MUST be implemented using test-first development.

The required cycle is: Write tests → Observe failure → Implement → Tests pass → Refactor.

**Requirements:**

- Unit tests and integration tests are mandatory.
- All similarity logic must be test-covered with real text examples.
- Threshold logic must be tested explicitly.
- New code must not reduce overall coverage.

Tests define correctness. Implementation serves tests.

### II. Deterministic & Reproducible Behavior

The service must behave deterministically for the same inputs.

- Identical inputs must produce identical similarity outputs.
- Model versions must be pinned.
- Thresholds must be explicit and configurable.
- No hidden randomness in similarity scoring.

Behavior must be reproducible across environments.

### III. Clean, Readable, Explainable Code

All code must be written for long-term maintainability. Code must be clean and easy to read;
focus on simplicity and comment regularly.

**Requirements:**

- Functions must be small and single-purpose.
- All public methods must have docstrings.
- All similarity adjustments must be commented with rationale.
- No “magic numbers” (all thresholds must be named constants).
- Control flow must be obvious without reading tests.
- If a rule affects semantic meaning, it must be explained in comments.

### IV. Opinion-Aware Similarity as a First-Class Concept

Similarity logic must be implemented as a composable pipeline, not a single score.

Implementation must support:

- base embedding similarity
- opinion-aware adjustments (negation, scope, conditionality, time)
- tiered classification (block / warn / related / different)

These steps must be: isolated into separate functions, independently testable, individually documented.
No single function may both compute embeddings and classify policy behavior.

### V. Strict API Contract

The service must expose a small, stable API surface.

**Requirements:**

- JSON-only request/response format.
- Explicit schemas for all endpoints.
- Consistent error structure.
- No silent shape changes.
- Backward-compatible evolution only.

The API contract must be documented and versioned.

### VI. Fail-Open and Defensive Programming

The service must never block participation due to internal failure.

**Implementation rules:**

- All external calls must have timeouts.
- All failures must default to “allow”.
- No uncaught exceptions may propagate to callers.
- Invalid input must return structured errors.

Defensive behavior is required at all integration boundaries.

### VII. Conversation-Scoped Data Model

All storage and retrieval must be scoped to a single conversation.

**Implementation rules:**

- No cross-conversation similarity checks.
- No global embedding reuse.
- All queries must require conversation ID.
- Indexing must assume per-conversation isolation.

Conversation boundaries are a hard architectural constraint.

### VIII. Performance as a Design Constraint

The service is designed for synchronous use.

**Requirements:**

- Similarity checks must complete within target latency.
- Vector search must be indexed.
- No blocking I/O in request paths.
- Models must be CPU-friendly.

Performance must be measured, not assumed.

### IX. No Hidden Product Logic

This service must not embed product or policy decisions.

It must not: decide what should be blocked, change user text, merge comments, infer intent, rank opinions.
It returns structured similarity results only. Interpretation belongs to Polis.

## Technology & Architecture Requirements

- Implemented as an independent microservice.
- Vector similarity must use a real vector index.
- Model choice must be documented.
- Thresholds must be externally configurable.
- Must run without GPU or proprietary APIs.

## Development Workflow

### Code Standards

- PEP 8–compliant formatting.
- Type hints required for all public functions.
- No unused imports or dead code.
- Logging must be structured and meaningful.
- No inline configuration (use env or config files).

### Documentation Requirements

- Inline docstrings for all public functions.
- Documentation is part of the deliverable.

### Change Control

Any change that affects: similarity thresholds, classification logic, model choice, or API shape
requires: new tests, updated documentation, and explicit justification in commit message.

## Non-Goals

This service will not: moderate content, perform clustering, summarize opinions, evaluate truth,
rank or score arguments, or make product decisions. It provides similarity signals only.

## Governing Maxim

Correctness, clarity, and reproducibility matter more than cleverness.

## Governance

- **Amendment procedure**: Changes to principles or mandatory sections require documentation,
  approval, and update to this constitution; version and Last Amended date must be updated.
- **Versioning policy**: Semantic versioning (MAJOR.MINOR.PATCH). MAJOR for backward-incompatible
  principle removals or redefinitions; MINOR for new principles or materially expanded guidance;
  PATCH for clarifications and non-semantic refinements.
- **Compliance review**: All PRs and reviews must verify compliance with these principles.
  Complexity or exceptions must be justified; constitution supersedes conflicting local practices.

**Version**: 1.0.0 | **Ratified**: 2026-02-04 | **Last Amended**: 2026-02-04
