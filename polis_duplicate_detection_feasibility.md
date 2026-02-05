# Technical Feasibility Assessment: Paraphrase & Duplicate Detection for Polis

## Executive Summary

**✅ HIGHLY FEASIBLE** - Implementing paraphrase and duplicate detection for Polis is technically viable and represents an excellent first extension project. The codebase has existing infrastructure that makes this straightforward to implement as a modular, optional feature.

**Key Finding:** Polis already has embedding infrastructure in place (via the Delphi/EVōC Lambda service), which can be leveraged or used as a reference for building a lightweight duplicate detection service.

### 🎯 Critical Design Insight for Polis

**Polis is designed for opinion clustering, not just topic clustering.** This fundamentally shapes the implementation:

- **Conservative threshold (0.93):** Only block true paraphrases, never related-but-distinct positions
- **Precision over recall:** Better to miss some duplicates than block valid distinct opinions
- **Tiered response:** Block obvious paraphrases / Warn on very similar / Show related comments
- **User agency:** Always allow override for warnings

**Example - These should NOT be blocked:**
```
Comment A: "AI tools should be banned from all school computers"
Comment B: "We should not allow any screens in school at all"
```
These have high topical similarity (~0.78) but represent different policy positions. In Polis, users must be able to vote on both separately because they test different dimensions of opinion.

---

## 1. Current Architecture Analysis

### 1.1 Comment Submission Flow

**Location:** `server/src/routes/comments.ts` (line ~494400)

The comment submission follows this sequence:

```
Client POST → handle_POST_comments() → Input validation → Duplicate check → 
Conversation validation → Moderation → Language detection → DB insertion → 
Auto-vote (optional) → Notifications → Response
```

**Key Integration Point:**
```typescript
// Current simple duplicate check (line ~494469)
const exists = await commentExists(zid, txt);
if (exists) {
  failJson(res, 409, "polis_err_post_comment_duplicate");
  return;
}
```

This is currently an **exact text match** only. Perfect place to add semantic similarity.

### 1.2 Database Schema

**Comments Table** (from schema):
```sql
CREATE TABLE comments(
    tid INTEGER NOT NULL,        -- Comment ID (auto-generated)
    zid INTEGER NOT NULL,        -- Conversation ID
    pid INTEGER NOT NULL,        -- Participant ID
    txt VARCHAR(1000) NOT NULL,  -- Comment text (our input)
    created BIGINT DEFAULT now_as_millis(),
    lang VARCHAR(10),            -- Language detection exists!
    -- ... other fields
    UNIQUE(zid, txt)            -- Enforces exact duplicate prevention
);
```

**Observations:**
- Maximum comment length: 1000 characters
- Already has language detection (`lang` field)
- Unique constraint on `(zid, txt)` enforces exact duplicates
- No existing embedding or similarity fields (clean slate)

### 1.3 Existing Embedding Infrastructure

**Location:** `delphi/umap_narrative/polismath_commentgraph/`

Polis already has:
- **SentenceTransformer embeddings** (384-dimensional using `all-MiniLM-L6-v2`)
- **DynamoDB storage** for embeddings (`CommentEmbeddings` table)
- **Lambda service** that processes conversations asynchronously

**Schema from existing system:**
```python
class CommentEmbedding(BaseModel):
    conversation_id: int
    comment_id: int
    embedding: List[float]  # 384-dimensional
    umap_coordinates: Coordinates  # 2D projection
```

**This is excellent news** because:
1. Pattern already exists for embedding generation
2. Model choice validated (`all-MiniLM-L6-v2` is perfect for this)
3. Storage strategy proven
4. Can reference implementation details

---

## 2. Proposed Implementation Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│  Client submits comment                                      │
└────────────┬────────────────────────────────────────────────┘
             │
             v
┌─────────────────────────────────────────────────────────────┐
│  POST /api/v3/comments handler                               │
│  (server/src/routes/comments.ts)                            │
└────────────┬────────────────────────────────────────────────┘
             │
             v
┌─────────────────────────────────────────────────────────────┐
│  NEW: Check for semantic duplicates                          │
│  ┌──────────────────────────────────────────────┐           │
│  │ 1. Generate embedding for new comment        │           │
│  │ 2. Search existing embeddings for similarity │           │
│  │ 3. If match found above threshold:           │           │
│  │    - Return similar comments to client       │           │
│  │ 4. Otherwise: continue with insertion        │           │
│  └──────────────────────────────────────────────┘           │
└────────────┬────────────────────────────────────────────────┘
             │
             v (no duplicates found)
┌─────────────────────────────────────────────────────────────┐
│  Existing comment insertion flow continues                   │
│  - Moderation check                                          │
│  - Language detection                                        │
│  - DB insert                                                 │
│  - Store embedding for future comparisons                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Component Architecture

#### Option A: Microservice (Recommended)

**Separate Node.js/Python service:**

```
┌──────────────────────────────────────────────────┐
│  Duplicate Detection Service                     │
│  ┌────────────────────────────────────────────┐ │
│  │ POST /check-duplicate                      │ │
│  │ Input: {zid, txt, lang}                   │ │
│  │ Output: {is_duplicate, similar_comments}  │ │
│  └────────────────────────────────────────────┘ │
│                                                   │
│  ┌────────────────────────────────────────────┐ │
│  │ POST /store-embedding                      │ │
│  │ Input: {zid, tid, txt}                    │ │
│  │ Output: {success}                         │ │
│  └────────────────────────────────────────────┘ │
│                                                   │
│  Components:                                     │
│  - SentenceTransformer model                     │
│  - FAISS vector index (or PostgreSQL pgvector)   │
│  - Cache layer (Redis optional)                  │
└──────────────────────────────────────────────────┘
```

**Pros:**
- Language agnostic (can use Python for ML)
- Independent scaling
- Easy to disable/enable
- No impact on main server if down

**Cons:**
- Extra deployment complexity
- Network latency

#### Option B: Integrated Service

**Add to existing Node.js server with Python bridge:**

```typescript
// In comments.ts
import { checkDuplicate, storeEmbedding } from '../utils/duplicateDetection';

// Inside handle_POST_comments, before commentExists check:
const similarComments = await checkDuplicate(zid, txt, lang);
if (similarComments.length > 0) {
  return res.status(409).json({
    error: 'polis_err_post_comment_similar',
    similar_comments: similarComments
  });
}
```

**Pros:**
- Simpler deployment
- Lower latency
- Easier development setup

**Cons:**
- Node.js + Python bridge complexity
- Harder to scale independently

### 2.3 Storage Options

#### Option 1: PostgreSQL with pgvector (Recommended)

```sql
-- New table for embeddings
CREATE TABLE comment_embeddings (
    zid INTEGER NOT NULL,
    tid INTEGER NOT NULL,
    embedding vector(384),  -- pgvector extension
    created BIGINT DEFAULT now_as_millis(),
    PRIMARY KEY (zid, tid),
    FOREIGN KEY (zid, tid) REFERENCES comments (zid, tid)
);

-- Create HNSW index for fast similarity search
CREATE INDEX comment_embeddings_vector_idx 
ON comment_embeddings 
USING hnsw (embedding vector_cosine_ops);
```

**Query for similar comments:**
```sql
-- Find truly similar comments (paraphrases only)
SELECT 
    tid, 
    txt, 
    1 - (embedding <=> $1) as similarity
FROM comment_embeddings e
JOIN comments c USING (zid, tid)
WHERE zid = $2
  AND 1 - (embedding <=> $1) > 0.93  -- Conservative threshold
ORDER BY embedding <=> $1
LIMIT 5;

-- For tiered warnings, use multiple queries or CASE:
SELECT 
    tid,
    txt,
    1 - (embedding <=> $1) as similarity,
    CASE 
        WHEN 1 - (embedding <=> $1) >= 0.93 THEN 'block'
        WHEN 1 - (embedding <=> $1) >= 0.88 THEN 'warn'
        WHEN 1 - (embedding <=> $1) >= 0.75 THEN 'related'
        ELSE 'different'
    END as similarity_level
FROM comment_embeddings e
JOIN comments c USING (zid, tid)
WHERE zid = $2
  AND 1 - (embedding <=> $1) > 0.75  -- Fetch all potentially related
ORDER BY embedding <=> $1
LIMIT 10;
```

**Pros:**
- Same database as everything else
- No new infrastructure
- Built-in ACID properties
- Fast with HNSW index

**Cons:**
- Requires pgvector extension
- Slightly slower than FAISS for very large datasets

#### Option 2: DynamoDB (leverage existing)

Use existing `CommentEmbeddings` table pattern:

**Pros:**
- Already deployed
- Proven pattern

**Cons:**
- No native vector search (need to scan)
- More expensive for similarity search
- Not ideal for real-time checks

#### Option 3: Redis with RediSearch

**Pros:**
- Extremely fast
- Vector similarity built-in

**Cons:**
- New infrastructure
- Cost
- Data persistence concerns

**RECOMMENDATION: Start with PostgreSQL + pgvector**

---

## 3. Implementation Details

### 3.1 Embedding Generation

**Model Choice:** `sentence-transformers/all-MiniLM-L6-v2`

This is already used in Polis's existing embedding system. It's perfect because:
- Fast inference (~100ms for batch of 10)
- Small model size (~80MB)
- 384 dimensions (good balance)
- Multilingual support
- Apache 2.0 license

**Python code (for microservice):**

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class DuplicateDetector:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # Conservative thresholds for Polis opinion-based context
        self.thresholds = {
            'block': 0.93,      # Only block true paraphrases
            'warn': 0.88,       # Show warning but allow submission
            'related': 0.75     # Show as related (informational)
        }
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate 384-dim embedding for text"""
        return self.model.encode([text], normalize_embeddings=True)[0]
    
    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two embeddings"""
        return np.dot(emb1, emb2)  # Already normalized
    
    def classify_similarity(self, similarity: float) -> str:
        """Classify similarity level for appropriate UX response"""
        if similarity >= self.thresholds['block']:
            return 'block'
        elif similarity >= self.thresholds['warn']:
            return 'warn'
        elif similarity >= self.thresholds['related']:
            return 'related'
        else:
            return 'different'
```

### 3.2 Similarity Threshold Tuning

**Critical Design Consideration for Polis:**

Polis is designed for **opinion clustering**, not just topic clustering. Users must be able to submit comments that express related but distinct positions. For example:

- **Comment A**: "AI tools should be banned from all school computers"
- **Comment B**: "We should not allow any screens in school at all, except for very specific skill-building tasks"

These comments have high topical similarity (~0.78) but represent **fundamentally different policy positions**:
- A = narrow ban on AI specifically  
- B = broad ban on all screens (much more restrictive)

In Polis, these should NOT be treated as duplicates because voting patterns would differ significantly. The distinction is politically meaningful.

**Therefore, we use CONSERVATIVE thresholds optimized for precision (avoiding false positives):**

| Similarity | Interpretation | Action | Example |
|------------|----------------|--------|---------|
| 0.93-1.0   | True paraphrase | **Block** + suggest upvote | "Teachers need better pay" vs "Teachers should be paid more" |
| 0.88-0.93  | Very similar | **Warn** but allow override | "Schools should ban AI" vs "We should prohibit AI in classrooms" |
| 0.75-0.88  | Related topic | **Show** as related (info only) | "Ban AI from schools" vs "Ban screens from schools" |
| < 0.75     | Different | **Allow** without notice | Different topics entirely |

**Production threshold: 0.93** for blocking (only catch true paraphrases)

This prioritizes **user agency** and **nuanced opinion expression** over aggressive deduplication.

### 3.3 Integration Point in Server

**File:** `server/src/routes/comments.ts`

```typescript
// Add new function before handle_POST_comments
interface SimilarComment {
  tid: number;
  txt: string;
  similarity: number;
  level: 'block' | 'warn' | 'related';
}

async function checkSemanticDuplicate(
  zid: number, 
  txt: string,
  lang: string
): Promise<{
  shouldBlock: boolean;
  shouldWarn: boolean;
  similar: SimilarComment[];
}> {
  
  // Feature flag check
  const conversation = await getConversationInfo(zid);
  if (!conversation.enable_duplicate_detection) {
    return {shouldBlock: false, shouldWarn: false, similar: []};
  }
  
  try {
    // Call microservice or use integrated function
    const response = await fetch(`${DUPLICATE_DETECTION_SERVICE}/check`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({zid, txt, lang}),
      timeout: 2000  // 2s timeout, fail open
    });
    
    const result = await response.json();
    
    // Classify responses by similarity level
    const blockLevel = result.similar.filter(c => c.level === 'block');
    const warnLevel = result.similar.filter(c => c.level === 'warn');
    const relatedLevel = result.similar.filter(c => c.level === 'related');
    
    return {
      shouldBlock: blockLevel.length > 0,
      shouldWarn: warnLevel.length > 0,
      similar: [...blockLevel, ...warnLevel, ...relatedLevel]
    };
    
  } catch (error) {
    logger.error('Duplicate detection service error:', error);
    // Fail open - allow comment if service is down
    return {shouldBlock: false, shouldWarn: false, similar: []};
  }
}

// Modify handle_POST_comments
async function handle_POST_comments(req: RequestWithP, res: any) {
  const { zid, uid, txt, vote, is_seed } = req.p;
  let { force_submit } = req.p;  // Allow user override
  
  // ... existing validation ...
  
  // Check exact duplicates (keep existing)
  const exists = await commentExists(zid, txt);
  if (exists) {
    failJson(res, 409, "polis_err_post_comment_duplicate");
    return;
  }
  
  // NEW: Check semantic duplicates (unless user forces submission)
  if (!force_submit) {
    const dupCheck = await checkSemanticDuplicate(zid, txt, lang);
    
    // Block only true paraphrases (>0.93 similarity)
    if (dupCheck.shouldBlock) {
      return res.status(409).json({
        error: 'polis_err_post_comment_paraphrase',
        message: 'This comment is very similar to an existing one',
        action: 'block',
        similar_comments: dupCheck.similar.filter(c => c.level === 'block'),
        can_override: false  // True paraphrases cannot be overridden
      });
    }
    
    // Warn about very similar comments (0.88-0.93 similarity)
    if (dupCheck.shouldWarn) {
      return res.status(409).json({
        error: 'polis_err_post_comment_similar',
        message: 'Similar comments exist. You can vote on them or submit anyway.',
        action: 'warn',
        similar_comments: dupCheck.similar.filter(c => 
          c.level === 'warn' || c.level === 'block'
        ),
        can_override: true  // User can choose to submit anyway
      });
    }
    
    // Optionally show related comments (0.75-0.88 similarity) as context
    // This would be returned in the success response to show in UI
    req.p.related_comments = dupCheck.similar.filter(c => c.level === 'related');
  }
  
  // ... continue with existing flow ...
}
```

### 3.4 Client-Side Handling

**Update client submission to handle tiered similarity responses:**

```javascript
// client-participation/src/api/comments.ts

async function submitComment(conversationId, text, forceSubmit = false) {
  try {
    const response = await fetch('/api/v3/comments', {
      method: 'POST',
      body: JSON.stringify({
        conversation_id: conversationId,
        txt: text,
        force_submit: forceSubmit  // User override for warnings
      })
    });
    
    if (response.status === 409) {
      const data = await response.json();
      
      // Handle different similarity levels
      if (data.action === 'block') {
        // True paraphrase - cannot override
        return {
          success: false,
          blocked: true,
          message: 'This comment is a paraphrase of an existing one',
          similar: data.similar_comments,
          canOverride: false
        };
      }
      
      if (data.action === 'warn') {
        // Very similar - user can override
        return {
          success: false,
          warning: true,
          message: 'Similar comments exist',
          similar: data.similar_comments,
          canOverride: true
        };
      }
    }
    
    // Success - may include related comments as context
    const result = await response.json();
    return {
      success: true,
      tid: result.tid,
      related: result.related_comments || []
    };
    
  } catch (error) {
    console.error('Comment submission failed:', error);
    throw error;
  }
}

// UI Component example
function CommentSubmitModal({ similarComments, action, onSubmitAnyway, onVoteInstead }) {
  if (action === 'block') {
    return (
      <Modal>
        <h3>This comment is too similar to an existing one</h3>
        <p>Please vote on the existing comment instead:</p>
        {similarComments.map(c => (
          <CommentCard 
            key={c.tid} 
            text={c.txt} 
            similarity={c.similarity}
            onVote={() => onVoteInstead(c.tid)}
          />
        ))}
        <Button onClick={onClose}>Got it</Button>
      </Modal>
    );
  }
  
  if (action === 'warn') {
    return (
      <Modal>
        <h3>Similar comments already exist</h3>
        <p>Would you like to vote on these instead, or submit your comment anyway?</p>
        {similarComments.map(c => (
          <CommentCard 
            key={c.tid} 
            text={c.txt} 
            similarity={c.similarity}
            onVote={() => onVoteInstead(c.tid)}
          />
        ))}
        <div>
          <Button variant="secondary" onClick={onSubmitAnyway}>
            Submit my comment anyway
          </Button>
          <Button variant="primary" onClick={onClose}>
            I'll vote on these instead
          </Button>
        </div>
      </Modal>
    );
  }
}
```

---

## 4. Minimal Viable Product (MVP) Scope

### Phase 1: Core Functionality (2-3 weeks)

**Week 1: Service Setup**
- [ ] Set up Python microservice with FastAPI
- [ ] Implement embedding generation endpoint
- [ ] Implement similarity search endpoint
- [ ] Add PostgreSQL + pgvector setup
- [ ] Docker containerization

**Week 2: Integration**
- [ ] Add database migration for `comment_embeddings` table
- [ ] Integrate service call in `handle_POST_comments`
- [ ] Add feature flag to conversation settings
- [ ] Error handling and fail-open logic
- [ ] Basic logging and metrics

**Week 3: Client & Testing**
- [ ] Update client to handle similar comment response
- [ ] Create simple UI for "similar comments found" modal
- [ ] Write integration tests
- [ ] Performance testing
- [ ] Documentation

### Phase 2: Enhancements (1-2 weeks)

- [ ] Batch embedding generation for existing comments
- [ ] Admin dashboard for duplicate detection stats
- [ ] Configurable similarity threshold per conversation
- [ ] Language-specific handling improvements
- [ ] Advanced caching layer

---

## 5. Technical Challenges & Solutions

### Edge Cases Specific to Opinion-Based Discussions

**Edge Case 1: Negations**
```
Comment A: "We should ban single-use plastics"
Comment B: "We should NOT ban single-use plastics"

Problem: High textual similarity (~0.92) but OPPOSITE positions
Solution: 
- Add negation detection (NOT, don't, never, shouldn't)
- If negation differs, reduce similarity score by 0.15
- Ensures these are never blocked despite high text similarity
```

**Edge Case 2: Scope Differences**
```
Comment A: "AI should be regulated in healthcare"
Comment B: "AI should be regulated in all industries"

Problem: Different scopes (specific vs. broad)
Solution:
- Extract scope keywords (healthcare vs. all industries)
- If scope differs significantly, treat as distinct
- Use named entity recognition (NER) for domains
```

**Edge Case 3: Conditional vs. Absolute Statements**
```
Comment A: "We need bike lanes"
Comment B: "We need bike lanes if the city funds them"

Problem: Similar topic but different commitment levels
Solution:
- Detect conditional words (if, unless, when, provided)
- Conditionals are always treated as distinct positions
- These represent different policy stances
```

**Edge Case 4: Time-Bound Statements**
```
Comment A: "We should implement this immediately"
Comment B: "We should implement this in 5 years"

Problem: Same action, very different timelines
Solution:
- Detect temporal expressions (now, later, by 2025)
- Significant timeline differences = distinct positions
- Timeline is often the core debate point
```

**Implementation Example:**
```python
class PolisAwareDuplicateDetector(DuplicateDetector):
    """Enhanced detector that understands opinion nuances"""
    
    def check_for_duplicate(
        self, 
        text1: str, 
        text2: str
    ) -> tuple[float, str]:
        """
        Returns (adjusted_similarity, classification)
        Classification: 'block', 'warn', 'related', 'different'
        """
        # Generate base similarity from embeddings
        emb1 = self.generate_embedding(text1)
        emb2 = self.generate_embedding(text2)
        base_similarity = self.compute_similarity(emb1, emb2)
        
        # Adjust for opinion-specific features
        adjusted_similarity = self.adjust_similarity_for_opinion_context(
            text1, text2, base_similarity
        )
        
        # Classify
        classification = self.classify_similarity(adjusted_similarity)
        return adjusted_similarity, classification
    
    def adjust_similarity_for_opinion_context(
        self, 
        text1: str, 
        text2: str, 
        base_similarity: float
    ) -> float:
        """Adjust similarity score based on opinion-specific features"""
        
        # Check for negation differences
        if self._has_negation_conflict(text1, text2):
            base_similarity -= 0.15  # Significant penalty
        
        # Check for scope differences  
        if self._has_scope_conflict(text1, text2):
            base_similarity -= 0.10
        
        # Check for conditional vs absolute
        if self._has_conditionality_conflict(text1, text2):
            base_similarity -= 0.08
        
        # Check for time-bound conflicts
        if self._has_timeline_conflict(text1, text2):
            base_similarity -= 0.08
        
        return max(0.0, base_similarity)  # Don't go negative
    
    def _has_negation_conflict(self, text1: str, text2: str) -> bool:
        """Detect if one negates what the other affirms"""
        negation_words = {'not', 'no', 'never', "don't", "shouldn't", 
                         "wouldn't", "can't", "won't", 'without', 'against'}
        
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        
        neg1 = bool(tokens1 & negation_words)
        neg2 = bool(tokens2 & negation_words)
        
        # One has negation, other doesn't = opposite positions
        return neg1 != neg2
```

### Challenge 1: Performance

**Issue:** Embedding generation + similarity search adds latency to comment submission

**Solutions:**
1. **Async processing:** Generate embedding after comment accepted, check on next submission
   - Pros: No latency impact
   - Cons: First duplicate won't be caught
   
2. **Fast model:** Use DistilBERT or MiniLM (both ~100ms)
   - Pros: Real-time feasible
   - Cons: Still adds latency

3. **Caching:** Cache embeddings for common phrases
   - Pros: Much faster for popular topics
   - Cons: Cache invalidation complexity

**RECOMMENDATION:** Start with #2 (fast model), add #3 if needed

### Challenge 2: Multilingual Comments

**Issue:** Polis supports multiple languages

**Solutions:**
1. Use multilingual model: `paraphrase-multilingual-MiniLM-L12-v2`
   - 384 dimensions, supports 50+ languages
   - Slightly slower but more accurate

2. Language-specific models (current approach uses language detection)
   - Higher accuracy per language
   - More complex infrastructure

**RECOMMENDATION:** Start with multilingual model, same as existing Polis embedding system

### Challenge 3: Cold Start

**Issue:** First conversation has no embeddings to compare against

**Solutions:**
1. **Simple:** First comment always succeeds (no comparison data)
2. **Better:** Backfill embeddings for existing comments
3. **Best:** Generate embeddings for seed comments proactively

**RECOMMENDATION:** #1 for MVP, #3 for production

### Challenge 4: Vector Index Size

**Issue:** Large conversations (10,000+ comments) need efficient search

**Solutions:**
1. **HNSW index** (Hierarchical Navigable Small World)
   - ~10ms search time for 100k vectors
   - Available in pgvector
   
2. **Partitioning:** Separate index per conversation
   - Automatic with `WHERE zid = X`
   
3. **Pruning:** Only index active, non-moderated comments
   - Reduces index size by ~30%

**RECOMMENDATION:** HNSW with per-conversation partitioning

---

## 6. Infrastructure Requirements

### Development Environment

```yaml
# docker-compose.yml addition
services:
  duplicate-detector:
    build: ./duplicate-detection-service
    ports:
      - "8001:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - MODEL_NAME=all-MiniLM-L6-v2
      - SIMILARITY_THRESHOLD=0.85
    volumes:
      - ./models:/models  # Cache for ML model
```

### Production Requirements

**Compute:**
- 1 CPU, 2GB RAM (microservice)
- GPU not required (inference is fast enough on CPU)

**Storage:**
- ~1.5KB per comment (384 floats * 4 bytes)
- 100,000 comments = ~150MB
- Negligible compared to text storage

**Database:**
- PostgreSQL 15+ with pgvector extension
- Existing Polis database can be used
- Index size: ~2x embedding size

---

## 7. Testing Strategy

### Threshold Validation Strategy

**Critical:** Before deployment, validate the 0.93 threshold with real Polis data:

1. **Collect Sample Data:**
   - Export 500-1000 comment pairs from existing Polis conversations
   - Manually label as: "duplicate", "similar but distinct", or "unrelated"
   - Focus on policy/opinion domains (e.g., urban planning, education, healthcare)

2. **Measure Precision/Recall:**
   ```python
   # Goal: Maximize precision (avoid false positives)
   # Acceptable: Lower recall (some duplicates slip through)
   
   thresholds_to_test = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95]
   
   for threshold in thresholds_to_test:
       precision, recall, f1 = evaluate_threshold(
           labeled_pairs, 
           threshold,
           target_metric='precision'  # Prioritize avoiding false blocks
       )
       
       print(f"Threshold {threshold}:")
       print(f"  Precision: {precision:.2%}")  # Want >95%
       print(f"  Recall: {recall:.2%}")        # Accept 60-80%
       print(f"  False positive rate: {1-precision:.2%}")  # Want <5%
   ```

3. **Target Metrics:**
   - **Precision >95%**: Less than 5% of blocked comments are actually distinct
   - **False Positive Rate <5%**: Avoid blocking valid distinct opinions
   - **Recall 60-80%**: Catch most true paraphrases (some slipping through is OK)

4. **Example Calibration:**
   ```
   Test with these Polis-style examples:
   
   SHOULD BLOCK (paraphrases):
   ✓ "Increase teacher salaries" / "Pay teachers more"
   ✓ "We need bike lanes" / "More bike lanes are needed"
   ✓ "Ban plastic bags" / "Plastic bags should be banned"
   
   SHOULD NOT BLOCK (distinct positions):
   ✓ "Ban AI in schools" / "Ban screens in schools"
   ✓ "Increase teacher pay" / "Reduce class sizes"
   ✓ "More bike lanes" / "Ban cars from downtown"
   ```

### Unit Tests

```python
def test_embedding_generation():
    detector = DuplicateDetector()
    text = "I like pizza"
    embedding = detector.generate_embedding(text)
    assert embedding.shape == (384,)
    assert -1 <= embedding.min() <= 1
    assert -1 <= embedding.max() <= 1

def test_true_paraphrase_detection():
    """Test that true paraphrases are detected (>0.93 similarity)"""
    detector = DuplicateDetector()
    text1 = "Teachers need better pay"
    text2 = "Teachers should be paid more"
    
    emb1 = detector.generate_embedding(text1)
    emb2 = detector.generate_embedding(text2)
    sim = detector.compute_similarity(emb1, emb2)
    
    assert sim > 0.93  # Should be flagged as paraphrase
    assert detector.classify_similarity(sim) == 'block'

def test_related_but_distinct_not_blocked():
    """Test that related but distinct positions are NOT blocked"""
    detector = DuplicateDetector()
    text1 = "AI tools should be banned from all school computers"
    text2 = "We should not allow any screens in school at all"
    
    emb1 = detector.generate_embedding(text1)
    emb2 = detector.generate_embedding(text2)
    sim = detector.compute_similarity(emb1, emb2)
    
    # Should be related but NOT blocked
    assert sim < 0.93  # Not similar enough to block
    assert detector.classify_similarity(sim) in ['related', 'different']
    
def test_very_similar_gets_warning():
    """Test that very similar comments get warning but not block"""
    detector = DuplicateDetector()
    text1 = "Schools should ban AI"
    text2 = "We should prohibit AI in classrooms"
    
    emb1 = detector.generate_embedding(text1)
    emb2 = detector.generate_embedding(text2)
    sim = detector.compute_similarity(emb1, emb2)
    
    # Should warn but not block (0.88-0.93 range)
    assert 0.88 <= sim < 0.93
    assert detector.classify_similarity(sim) == 'warn'

def test_threshold_calibration_with_polis_examples():
    """Test with real Polis-style policy comments"""
    detector = DuplicateDetector()
    
    # Example 1: Same position, different wording (should block)
    pairs_should_block = [
        ("We need universal healthcare", "Everyone should have healthcare"),
        ("Raise the minimum wage", "Minimum wage should be higher"),
        ("Ban assault weapons", "Assault weapons should be banned"),
    ]
    
    for text1, text2 in pairs_should_block:
        emb1 = detector.generate_embedding(text1)
        emb2 = detector.generate_embedding(text2)
        sim = detector.compute_similarity(emb1, emb2)
        assert sim >= 0.93, f"Failed to block paraphrase: '{text1}' vs '{text2}' (sim={sim})"
    
    # Example 2: Related but distinct positions (should NOT block)
    pairs_should_not_block = [
        ("Ban AI in schools", "Ban all screens in schools"),
        ("We need more bike lanes", "We need to ban cars in the city"),
        ("Increase teacher salaries", "Reduce class sizes"),
    ]
    
    for text1, text2 in pairs_should_not_block:
        emb1 = detector.generate_embedding(text1)
        emb2 = detector.generate_embedding(text2)
        sim = detector.compute_similarity(emb1, emb2)
        assert sim < 0.93, f"Incorrectly blocked distinct positions: '{text1}' vs '{text2}' (sim={sim})"
```

### Integration Tests

```typescript
describe('Duplicate Detection', () => {
  it('should block exact duplicates', async () => {
    const agent = await initializeParticipant(conversationId);
    
    await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'I like pizza'
    }).expect(200);
    
    // Try to submit exact duplicate
    const res = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'I like pizza'
    }).expect(409);
    
    expect(res.body.error).toBe('polis_err_post_comment_duplicate');
  });
  
  it('should block true paraphrases (>0.93 similarity)', async () => {
    const agent = await initializeParticipant(conversationId);
    
    await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'Teachers need better pay'
    }).expect(200);
    
    const res = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'Teachers should be paid more'
    }).expect(409);
    
    expect(res.body.error).toBe('polis_err_post_comment_paraphrase');
    expect(res.body.action).toBe('block');
    expect(res.body.can_override).toBe(false);
    expect(res.body.similar_comments).toHaveLength(1);
  });
  
  it('should warn but allow override for very similar comments (0.88-0.93)', async () => {
    const agent = await initializeParticipant(conversationId);
    
    await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'Schools should ban AI'
    }).expect(200);
    
    // First attempt without override - should warn
    const res1 = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'We should prohibit AI in classrooms'
    }).expect(409);
    
    expect(res1.body.error).toBe('polis_err_post_comment_similar');
    expect(res1.body.action).toBe('warn');
    expect(res1.body.can_override).toBe(true);
    
    // Second attempt with override - should succeed
    const res2 = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'We should prohibit AI in classrooms',
      force_submit: true
    }).expect(200);
    
    expect(res2.body.tid).toBeDefined();
  });
  
  it('should NOT block related but distinct positions', async () => {
    const agent = await initializeParticipant(conversationId);
    
    await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'AI tools should be banned from all school computers'
    }).expect(200);
    
    // This is a different position (broader scope) - should be allowed
    const res = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'We should not allow any screens in school at all'
    }).expect(200);
    
    expect(res.body.tid).toBeDefined();
    
    // May optionally include related comments in response
    if (res.body.related_comments) {
      expect(res.body.related_comments.length).toBeGreaterThan(0);
    }
  });
  
  it('should handle feature flag - disabled means no checking', async () => {
    // Disable duplicate detection for this conversation
    await db.query(
      'UPDATE conversations SET enable_duplicate_detection = false WHERE zid = $1',
      [conversationId]
    );
    
    const agent = await initializeParticipant(conversationId);
    
    await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'Teachers need better pay'
    }).expect(200);
    
    // Should allow even exact paraphrase when disabled
    const res = await agent.post('/api/v3/comments').send({
      conversation_id: conversationId,
      txt: 'Teachers should be paid more'
    }).expect(200);
    
    expect(res.body.tid).toBeDefined();
  });
});
```

### Performance Tests

```bash
# Load test with ab (Apache Bench)
ab -n 1000 -c 10 -p comment.json \
   -T application/json \
   http://localhost:8001/check-duplicate

# Measure p95 latency (should be < 200ms)
```

---

## 8. Deployment Strategy

### Staged Rollout

**Stage 1: Threshold Calibration (Week 1)**
- Run offline analysis on existing conversations
- Manually review 100+ comment pairs at different similarity levels
- Identify optimal threshold that avoids blocking distinct opinions
- Document edge cases (multilingual, domain-specific terminology)

**Stage 2: Shadow Mode (Week 2)**
- Deploy service but don't block comments
- Log what WOULD be blocked at different thresholds
- Collect metrics:
  - Distribution of similarity scores in real traffic
  - Examples of comments in 0.88-0.93 range (warn zone)
  - Examples of comments in >0.93 range (block zone)
- Have moderators manually review flagged pairs

**Stage 3: Opt-in Beta (Week 3-4)**
- Enable for 3-5 friendly test conversations
- Collect user feedback:
  - "Did you feel unfairly blocked?"
  - "Were the suggested similar comments actually similar?"
  - "Did you use the override feature?"
- Monitor override rate (high rate = threshold too aggressive)

**Stage 4: Controlled Rollout (Week 5+)**
- A/B test: 20% of new conversations get duplicate detection
- Compare metrics between groups:
  - Total comments submitted
  - Unique opinions expressed
  - User frustration signals (abandonment, overrides)
  - Conversation quality (moderator assessment)

**Stage 5: Default On (Week 8+)**
- Enable by default for new conversations
- Existing conversations keep current setting
- Provide admin controls: adjust thresholds per conversation
- Continue monitoring and iterating

### Monitoring & Metrics

**Key Metrics:**
```
Performance:
- duplicate_check_latency_ms (p50, p95, p99)
- embedding_generation_time_ms
- similarity_search_time_ms
- service_availability (uptime %)

Accuracy:
- similarity_score_distribution (histogram)
- block_rate (% submissions blocked)
- warn_rate (% submissions warned)
- override_rate (% users click "submit anyway")
- false_positive_reports (user feedback)

Impact:
- comments_per_conversation (before/after)
- unique_opinions_expressed (estimate via clustering)
- user_satisfaction_score (survey)
- moderator_workload (duplicate reports)
```

**Alerts:**
```
CRITICAL (page on-call):
- Latency > 500ms for 5 minutes
- Service down > 1 minute
- Error rate > 10%

WARNING (notify team):
- Override rate > 30% (threshold too aggressive)
- Block rate > 20% (may be overfitting)
- Latency > 300ms for 10 minutes
```

**Dashboard Views:**
```
Real-time:
- Requests per second
- Latency percentiles
- Error rate
- Service health

Daily Summary:
- Comments checked
- Blocks / Warnings / Allowed
- Top similar comment pairs
- User override patterns

Weekly Review:
- Threshold effectiveness
- Example pairs for manual review
- User feedback summary
```

---

## 9. Estimated Effort

### Development Time

| Phase | Task | Effort |
|-------|------|--------|
| **Backend** |
| | Microservice setup | 2 days |
| | Embedding generation | 1 day |
| | Similarity search | 2 days |
| | Database integration | 1 day |
| | Server integration | 2 days |
| | Error handling | 1 day |
| **Frontend** |
| | Similar comments UI | 2 days |
| | API integration | 1 day |
| **Testing** |
| | Unit tests | 2 days |
| | Integration tests | 2 days |
| | Performance testing | 1 day |
| **DevOps** |
| | Docker setup | 1 day |
| | Deployment scripts | 1 day |
| | Monitoring | 1 day |
| **Documentation** |
| | API docs | 1 day |
| | User guide | 1 day |
| **Total** | | **22 days (~4-5 weeks)** |

### Resource Requirements

- 1 Full-stack developer (primary)
- 1 DevOps engineer (part-time, deployment support)
- 1 UX designer (part-time, UI mockups)

---

## 10. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Service downtime affects comments | High | Low | Fail-open design - allow comments if service down |
| False positives annoy users | Medium | Medium | Tunable threshold + user override option |
| Performance degrades at scale | Medium | Low | Async processing + caching |
| Model drift over time | Low | Low | Regular evaluation, model versioning |
| Multi-language accuracy issues | Medium | Medium | Use proven multilingual model |

---

## 11. Success Metrics

### Technical Metrics
- **Latency:** p95 < 200ms added to comment submission
- **Precision:** >95% (less than 5% false positives - blocking distinct opinions)
- **Recall:** 60-80% (catching most paraphrases, some slipping through is acceptable)
- **Availability:** 99.9% uptime
- **Override Rate:** <15% (users forcing submission despite warning)

### Product Metrics
- **Duplicate reduction:** 15-25% reduction in near-duplicate comments
- **User satisfaction:** <10% of blocked users report frustration (via survey)
- **Opinion diversity:** No decrease in unique opinion clusters per conversation
- **Engagement:** No significant drop in comment submission rates
- **Moderator feedback:** Positive assessment of conversation quality improvement

### Key Success Criterion
**The system should NEVER block genuinely distinct positions, even if they're topically related.** 

Priority hierarchy:
1. Avoid false positives (blocking distinct opinions) ← MOST CRITICAL
2. Improve conversation quality (reduce noise)
3. Catch true paraphrases (maximize recall)

This prioritization reflects Polis's core mission: enabling nuanced opinion expression.

---

## 12. Alternative Approaches Considered

### Approach A: Client-side checking only
**Pros:** No server load
**Cons:** Can't check against other users' comments, easy to bypass
**Verdict:** ❌ Insufficient

### Approach B: Simple keyword matching
**Pros:** Very fast
**Cons:** Misses paraphrases, high false negative rate
**Verdict:** ❌ Doesn't solve the problem

### Approach C: Use existing Lambda service
**Pros:** Reuses infrastructure
**Cons:** Designed for batch processing, not real-time
**Verdict:** ❌ Not suitable for synchronous API

### Approach D: LLM-based comparison (GPT-4, Claude)
**Pros:** Very accurate
**Cons:** Too slow (500ms+), expensive, requires API key
**Verdict:** ❌ Overkill for this use case

---

## 13. Future Enhancements

Once MVP is successful, consider:

1. **Smart suggestions:** "Instead of submitting this, consider voting on these similar comments"
2. **Auto-merge:** Automatically combine very similar comments (with user consent)
3. **Cluster visualization:** Show users where their comment would fit in the conversation map
4. **Cross-conversation detection:** Find similar discussions across multiple conversations
5. **Trend detection:** Alert moderators when many people try to submit similar comments

---

## Conclusion

**Paraphrase & duplicate detection is HIGHLY FEASIBLE for Polis.**

### Why this is a great first project:

✅ **Clear integration point:** One function call in the comment submission handler
✅ **Existing infrastructure:** Can leverage existing embedding patterns
✅ **Modular design:** Can be built and deployed independently
✅ **Fail-safe:** Degrades gracefully if service is unavailable
✅ **Measurable impact:** Clear metrics for success
✅ **Reasonable scope:** 4-5 weeks for MVP
✅ **Low risk:** Doesn't modify core functionality
✅ **High value:** Reduces noise while preserving nuanced opinion expression

### Critical Design Principles for Polis:

**1. Conservative Threshold (0.93):** Only block true paraphrases, never distinct positions
**2. Tiered Response:** Block / Warn / Show Related based on similarity level  
**3. User Override:** Always allow "submit anyway" for warnings
**4. Opinion-Aware:** Adjust for negations, scope, conditionals, and timelines
**5. Fail-Open:** If service is down, allow all comments through
**6. Precision over Recall:** Avoid false positives even if some duplicates slip through

### Recommended approach:

1. Start with **PostgreSQL + pgvector** for storage
2. Build **Python microservice** for embedding generation
3. Use **all-MiniLM-L6-v2** model (proven in Polis)
4. Implement **PolisAwareDuplicateDetector** with opinion context adjustments
5. **Conservative threshold (0.93)** for blocking
6. Deploy as **opt-in feature** initially
7. **Validate threshold** with real Polis data before full rollout
8. Monitor **override rate** and **user feedback** closely

### Example behavior:

```
✅ BLOCK (>0.93 similarity):
"Teachers need better pay" → "Teachers should be paid more"

⚠️ WARN (0.88-0.93 similarity):  
"Schools should ban AI" → "We should prohibit AI in classrooms"
(User can override)

ℹ️ SHOW RELATED (0.75-0.88 similarity):
"Ban AI in schools" → "Ban screens in schools"
(Informational only, both allowed)

✅ ALLOW (<0.75 OR negation/scope conflicts):
"AI tools should be banned" → "We should NOT ban AI tools"
(Opposite positions, both critical for Polis)
```

### Success will be measured by:

- **<5% false positive rate** (blocking distinct opinions)
- **>60% recall** on true paraphrases
- **<15% override rate** (users bypassing warnings)
- **No decrease** in opinion diversity per conversation
- **Positive moderator feedback** on quality improvement

### Next steps:

1. Set up development environment with pgvector
2. Create proof-of-concept microservice with tiered thresholds
3. **Test with sample Polis comments** from real conversations
4. **Manually validate threshold** using labeled pairs
5. Benchmark performance on realistic data (target <200ms)
6. Design UI mockups for block/warn/related responses
7. Begin implementation of MVP

**The conservative threshold approach ensures we never sacrifice Polis's core value: enabling nuanced opinion expression and meaningful democratic deliberation.**

Ready to proceed when you are!
