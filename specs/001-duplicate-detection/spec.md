# Feature Specification: Duplicate Detection Microservice

**Feature Branch**: `001-duplicate-detection`  
**Created**: 2026-02-04  
**Status**: Draft  
**Input**: Duplicate detection microservice for Polis comments; semantic paraphrase detection, block/warn/related tiers, JSON API, fail-open. Ref: polis_duplicate_detection_feasibility.md

## Clarifications

### Session 2026-02-04

- Q: Should the duplicate-detection API be restricted (e.g. authentication or network boundary), or is it acceptable to assume it is only ever called by the Polis server on a trusted network with no auth in scope for this spec? → A: Internal/trusted network only; no authentication requirement in this spec.
- Q: Should the service be required to expose structured logging, metrics (e.g. latency, error rate, duplicate-check outcomes), or a health endpoint, or is that left entirely to the implementation plan? → A: Structured logging and a health/readiness endpoint only; no explicit metrics requirement in spec.
- Q: Should the spec define a maximum recommended or required timeout (in seconds) that the caller uses when calling the duplicate-check endpoint, after which the caller MUST treat the result as "allow"? → A: Service advertises a recommended timeout (e.g. in docs); spec does not require a specific caller value.
- Q: Should the spec state an assumption or target for scale (e.g. max comments per conversation, or "single-conversation scale only"), or leave all scale assumptions to the implementation plan? → A: Assume single-conversation scale only (e.g. up to tens of thousands of comments per conversation); document order of magnitude in plan.
- Q: Should the service enforce rate limiting (e.g. max requests per minute per caller or per conversation), or is limiting entirely the responsibility of the Polis server? → A: No rate limiting in the service for this spec; caller (Polis server) is responsible for throttling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check Comment for Semantic Duplicates (Priority: P1)

When a participant submits a comment in a Polis conversation, the system (Polis server) calls the duplicate-detection service to see if the comment is a semantic paraphrase of an existing comment in that conversation. The service returns a classification (block / warn / related) and, when relevant, a list of similar comments so the caller can block true paraphrases, show warnings for very similar text, or surface related comments—without blocking distinct opinions.

**Why this priority**: Core value of the microservice; without it there is no feature.

**Independent Test**: Call the service with a new comment and existing conversation; verify response includes correct tier and similar comments when applicable. Can be tested with a single conversation and a small set of comments.

**Acceptance Scenarios**:

1. **Given** a conversation with existing comments, **When** the caller submits a comment that is a true paraphrase of an existing one, **Then** the service returns a block-tier result and the similar comment(s) so the caller can reject or suggest upvote.
2. **Given** a conversation with existing comments, **When** the caller submits a comment that is very similar but not a paraphrase, **Then** the service returns a warn-tier result so the caller can show a warning but allow override.
3. **Given** a conversation with existing comments, **When** the caller submits a comment that is topically related but a distinct opinion (e.g. "Ban AI in schools" vs "Ban screens in schools"), **Then** the service returns related or allow—never block—so distinct opinions are not blocked.
4. **Given** a conversation with existing comments, **When** the caller submits a comment with no similar comments, **Then** the service returns an allow result with no similar comments to block or warn.

---

### User Story 2 - Store Embedding After Comment Is Accepted (Priority: P2)

After the Polis server accepts and persists a new comment, it notifies the duplicate-detection service so the service can store an embedding for that comment, scoped to the conversation. Future duplicate checks in that conversation use this stored data.

**Why this priority**: Required for duplicate checks to work over time; depends on P1 contract.

**Independent Test**: Store an embedding for a (conversation, comment) pair, then run a duplicate check for a paraphrase of that comment; verify the new comment is detected as similar.

**Acceptance Scenarios**:

1. **Given** a conversation and a newly accepted comment, **When** the caller requests storage of the comment for that conversation, **Then** the service stores it and future checks in that conversation consider it.
2. **Given** storage requested for the same conversation and comment id, **Then** the service idempotently updates or retains a single representation (no duplicate entries for the same comment).

---

### User Story 3 - Fail-Open and Structured Errors (Priority: P1)

When the duplicate-detection service is unavailable, slow, or returns an error, the caller (Polis server) must still allow the comment to be submitted. The service must not cause participation to be blocked by its own failure. Invalid or malformed requests must result in a structured error response, not an unhandled failure.

**Why this priority**: Preserves participation and avoids blocking users due to an optional check.

**Independent Test**: Simulate timeouts, service down, or invalid input; verify caller receives a clear outcome (allow comment) or structured error, and that no uncaught exception propagates to the caller.

**Acceptance Scenarios**:

1. **Given** the duplicate-detection service is unreachable or times out, **When** the caller performs a duplicate check, **Then** the caller receives a response that means "allow" (e.g. no block, no similar comments) so the comment can proceed.
2. **Given** the duplicate-detection service returns an internal error, **When** the caller performs a duplicate check, **Then** the caller receives a response that means "allow" (fail-open).
3. **Given** the caller sends an invalid or malformed request (e.g. missing required fields), **When** the caller performs a duplicate check, **Then** the service returns a structured error (e.g. HTTP 4xx with a consistent error shape), not a crash.

---

### Edge Cases

- What happens when the conversation has no comments yet? Service returns allow with no similar comments.
- What happens when the same text is submitted twice in quick succession? First submission stores embedding; second submission is detected as duplicate (exact or near-exact match) and returns block.
- What happens when comment text is empty or exceeds maximum length? Service returns structured validation error; caller can reject before calling duplicate check.
- What happens when the conversation id does not exist or is invalid? Service returns structured error; caller decides whether to allow or reject.
- What happens when two comments are topically similar but express different positions (e.g. "Ban AI in schools" vs "Ban screens in schools")? Service must NOT classify as block; at most warn or related, with precision over recall so distinct opinions are never blocked.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST accept a request containing at least conversation identifier and comment text, and return a structured result indicating whether the comment is a semantic duplicate or similar to existing comments in that conversation.
- **FR-002**: The service MUST classify similarity into at least three tiers: block (true paraphrase), warn (very similar, allow with warning), and related or below (allow without blocking). Thresholds are configurable; exact values must be validated and tested.
- **FR-003**: The service MUST return a list of similar comments (e.g. identifier and text) with their similarity tier and score when applicable, so the caller can block, warn, or show related comments.
- **FR-004**: The service MUST scope all similarity checks to a single conversation; it MUST NOT use or return similar comments from other conversations.
- **FR-005**: The service MUST prioritize precision over recall: it MUST NOT block comments that express distinct opinions, even if topically similar. Better to miss some duplicates than to block valid distinct opinions.
- **FR-006**: The service MUST support storing an embedding (or equivalent) for a comment in a conversation after the comment is accepted, so future duplicate checks in that conversation include it.
- **FR-007**: On any internal failure, timeout, or inability to respond, the service MUST allow the caller to treat the outcome as "allow" (fail-open). It MUST NOT require the caller to block comments when the service is down or errors.
- **FR-008**: The service MUST use a stable, documented request/response format (e.g. JSON) and consistent error structure for all endpoints.
- **FR-009**: Invalid or malformed input MUST result in a structured error response (e.g. 4xx with a defined body), not an unhandled exception or 5xx that could be interpreted as "block".
- **FR-010**: The service MUST support structured logging and MUST expose a health or readiness endpoint; metrics are not required by this spec.

### Key Entities

- **Conversation**: A single Polis discussion (e.g. identified by conversation id). All duplicate checks and stored embeddings are scoped to one conversation.
- **Comment**: A participant-submitted text in a conversation, with an identifier and the text. Input to duplicate check and to storage.
- **Similarity result**: The outcome of a duplicate check: tier (block / warn / related or allow), optional list of similar comments (identifier, text, similarity score/tier), and metadata needed by the caller to enforce block/warn/allow and to show suggestions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Comment submission flow (including the duplicate check) adds under 200 ms latency in normal conditions, so participants are not noticeably delayed.
- **SC-002**: Fewer than 5% of comments that express distinct opinions are incorrectly blocked (false positive rate for blocking).
- **SC-003**: At least 95% of comments that are true paraphrases of an existing comment in the same conversation are correctly classified as block-tier (precision in paraphrase detection).
- **SC-004**: When the duplicate-detection service is unavailable or errors, 100% of comment submissions that would otherwise be allowed are still allowed (fail-open); no participant is blocked solely due to service failure.
- **SC-005**: Users can complete submitting a comment (including duplicate check and optional warning/override) without encountering unhandled errors or unclear failure modes.

## Integration with Polis

This service is intended to work with Polis as follows (see also the main repo [README](../../README.md) and [repomix-polis-info.xml](../../repomix-polis-info.xml) for Polis codebase context):

- The **Polis server** calls `POST /check` before inserting a comment; this service returns tier and similar comments. The Polis server (or client) enforces block/warn/allow—this service does not block or reject.
- After the comment is accepted and stored in Polis, the Polis server calls `POST /store` so this service can store an embedding. This service does not read the Polis database; it is populated only via the API.
- Identifiers `zid` (conversation id) and `tid` (comment id) align with Polis's conversation and comment model.

## Assumptions

- The microservice will be called by the Polis server (e.g. from comment submission flow); it does not replace the server’s exact-duplicate check.
- The duplicate-detection API is assumed to be reachable only by the Polis server on a trusted network; authentication and authorization of callers are out of scope for this spec.
- Thresholds (e.g. block ≥0.93, warn 0.88–0.93, allow &lt;0.88) are examples and MUST be validated and tested; they may be tuned for precision and to avoid blocking distinct opinions.
- Request/response format will be JSON; schemas and error shape will be documented and versioned. The API documentation MUST advertise a recommended timeout for the duplicate-check endpoint; the caller is not required by this spec to use a specific value.
- Integration points (e.g. Polis `handle_POST_comments`, database, client handling of 409/similar suggestions) are out of scope for this spec and will be addressed in integration/planning.
- Technical choices (language, framework, model, database) are assumed for planning but are not part of this specification’s requirements; the spec focuses on behavior and outcomes.
- Scale is assumed to be single-conversation only (e.g. up to tens of thousands of comments per conversation); the implementation plan MUST document the order of magnitude used for design and validation.
- Rate limiting is out of scope for the duplicate-detection service; the caller (Polis server) is responsible for throttling.
