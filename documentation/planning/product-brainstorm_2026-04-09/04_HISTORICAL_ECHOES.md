# 04: Historical Echoes

**Feature**: When a new post is analyzed, find the 3-5 most semantically similar past posts and attach their actual market outcomes.

**Status**: Planning
**Date**: 2026-04-09
**Estimated Effort**: Large (3-4 sessions)

---

## Overview

Shitpost Alpha has 1,000+ analyzed posts with complete outcome tracking (T+1/T+3/T+7/T+30 returns, accuracy, P&L) -- but this historical data is never used to inform new analyses. When Trump posts about tariffs, the system doesn't know that his last 5 tariff posts averaged +2.3% on XLE within 7 days.

This feature adds a **semantic similarity pipeline**: embed all post texts using OpenAI's `text-embedding-3-small`, store embeddings in a new `post_embeddings` table, and on each new prediction, find the 3-5 most similar historical posts with their realized outcomes. The aggregated "echo" data surfaces in three places:

1. **Telegram alerts**: "Similar past posts averaged +1.8% over 7 days (3/5 correct)"
2. **Frontend feed**: Echo cards showing matched posts and their outcomes
3. **LLM prompt enrichment** (future): Feed echo outcomes back into the analysis prompt

This closes the missing feedback loop: the system finally learns from its own history.

---

## Motivation: The Missing Feedback Loop

### What We Have

```
Post → LLM Analysis → Prediction → Outcomes (tracked)
                                         │
                                         └── Data just sits in the DB
```

### What We Want

```
Post → LLM Analysis → Prediction → Outcomes (tracked)
  ↑                                      │
  │                                      ▼
  └──── Echo Lookup ◄──── Similarity Search ◄──── Embeddings
```

### Concrete Value

**Without echoes** (today):
```
🟢 SHITPOST ALPHA ALERT
Sentiment: BULLISH (82% confidence)
Assets: XLE, OXY
Thesis: Positive energy policy implications
```

**With echoes** (proposed):
```
🟢 SHITPOST ALPHA ALERT
Sentiment: BULLISH (82% confidence)
Assets: XLE, OXY
Thesis: Positive energy policy implications

📊 Historical Echoes (3 similar past posts):
• Avg T+7 return: +1.8%
• Win rate: 2/3 correct (67%)
• Avg P&L ($1k): +$18
• Best match: "Drill baby drill!" (2025-11-15) → XLE +3.2% in 7d
```

The user now has empirical evidence to calibrate their trust in the signal.

---

## Architecture

### Embedding Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    Embedding Pipeline                        │
│                                                              │
│  1. Backfill (one-time):                                    │
│     All existing posts → embed → store in post_embeddings    │
│                                                              │
│  2. Inline (ongoing):                                       │
│     New prediction created → embed post text → store         │
│     → similarity search → aggregate echoes                   │
│     → attach to prediction + alert                           │
│                                                              │
│  3. Similarity Search:                                      │
│     New embedding → cosine similarity against all stored     │
│     → top 5 matches → join with prediction_outcomes          │
│     → compute aggregate stats                                │
└──────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Analyzer    │────►│ EchoService  │────►│ EmbeddingClient  │
│ (after LLM)  │     │              │     │ (OpenAI API)     │
└──────────────┘     │  embed()     │     └──────────────────┘
                     │  search()    │
                     │  aggregate() │     ┌──────────────────┐
                     │              │────►│ post_embeddings  │
                     └──────┬───────┘     │ (PostgreSQL)     │
                            │             └──────────────────┘
                            │
                     ┌──────▼──────┐     ┌──────────────────┐
                     │ Echo Result │────►│ Alert Formatting  │
                     │ (aggregated)│     │ Frontend API      │
                     └─────────────┘     └──────────────────┘
```

---

## Embedding Strategy

### Model Choice

| Model | Dimensions | Cost per 1M tokens | Quality | Speed |
|-------|-----------|--------------------|---------| ------|
| `text-embedding-3-small` | 1536 | $0.02 | Good | Fast |
| `text-embedding-3-large` | 3072 | $0.13 | Better | Fast |
| `text-embedding-ada-002` | 1536 | $0.10 | Good | Fast |

**Recommendation**: `text-embedding-3-small` (1536 dimensions). It's the cheapest, fastest, and quality is sufficient for semantic similarity of short social media posts. The posts are typically 50-280 characters, so token counts are tiny.

### Cost Analysis

**Backfill (one-time)**:
- ~1,000 existing analyzed posts
- Average post length: ~50 tokens
- Total: ~50,000 tokens
- Cost: 50,000 / 1,000,000 * $0.02 = **$0.001** (negligible)

**Ongoing**:
- ~5-15 new predictions per day
- Each needs: 1 embedding (post text) + 1 search (same embedding reused)
- Cost per day: ~750 tokens * $0.02/1M = **$0.000015/day** (negligible)

Total embedding costs are under $1/year. This is not a cost concern.

### What Gets Embedded

The **plain text** of the post (`Signal.text` or `TruthSocialShitpost.text`), not the enhanced content. Rationale:

1. The enhanced content includes metadata (author, engagement, timestamps) that would pollute semantic similarity. Two posts about tariffs should match regardless of their engagement counts.
2. Post text is what carries the semantic meaning.
3. Post text is short (50-280 chars typically), keeping embedding costs minimal.

### Embedding Function

```python
# New file: shit/llm/embeddings.py

from typing import Optional
from openai import OpenAI
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("embeddings")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingClient:
    """Client for generating text embeddings via OpenAI API."""

    def __init__(self, model: str = EMBEDDING_MODEL):
        self.model = model
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats (1536 dimensions).
        """
        # Truncate very long texts (unlikely for social media posts)
        text = text[:8000]  # ~2000 tokens, well within model limits

        response = self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed (max 2048 per API call).

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # OpenAI supports batch embedding (up to 2048 inputs)
        truncated = [t[:8000] for t in texts]
        response = self._client.embeddings.create(
            model=self.model,
            input=truncated,
        )
        return [item.embedding for item in response.data]
```

---

## Storage: pgvector vs In-Memory FAISS

### Option A: pgvector on Neon (Recommended)

Neon PostgreSQL supports the `pgvector` extension natively. This means vector similarity search runs inside the database alongside all our other data.

**Pros**:
- No separate infrastructure to manage.
- Joins directly with `predictions`, `prediction_outcomes`, `ticker_registry`.
- Neon supports `pgvector` out of the box (just `CREATE EXTENSION vector`).
- Transactional consistency with the rest of the data.
- Works across service restarts (persistent).
- Supports exact and approximate nearest neighbor (IVFFlat, HNSW indexes).

**Cons**:
- Neon's free/starter tier may have performance limits for large vector sets.
- At 1,000-10,000 vectors with 1536 dimensions, exact cosine similarity is fast enough without an index. Performance concern is premature.

### Option B: In-Memory FAISS

**Pros**:
- Extremely fast similarity search (sub-millisecond).
- No database dependency for search.

**Cons**:
- Must load all vectors into memory on each service start (~23MB for 10,000 x 1536).
- Not persistent -- need to rebuild from DB on restart.
- Cannot join directly with prediction_outcomes (requires separate DB query).
- Another dependency to install and manage.
- Overkill for <10,000 vectors.

### Decision: pgvector

For our scale (1,000-10,000 posts), pgvector is the clear winner. Exact cosine similarity over 10,000 vectors with 1536 dimensions takes ~10-50ms in PostgreSQL -- well within our latency budget. If we ever reach 100,000+ posts, we can add an HNSW index without changing the application code.

### Schema: `post_embeddings` Table

```sql
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE post_embeddings (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    shitpost_id VARCHAR(255),
    signal_id VARCHAR(255),
    text_hash VARCHAR(64) NOT NULL,       -- SHA-256 of the embedded text (dedup)
    embedding vector(1536) NOT NULL,       -- pgvector column
    model VARCHAR(50) NOT NULL DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_post_embeddings_prediction UNIQUE (prediction_id)
);

-- Index for cosine similarity search
CREATE INDEX idx_post_embeddings_cosine ON post_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
-- Note: IVFFlat requires at least 10*lists rows to build. For <100 rows,
-- use exact search (no index needed). Add HNSW index at 10,000+ rows.

-- Index for joining
CREATE INDEX idx_post_embeddings_prediction_id ON post_embeddings(prediction_id);
```

### SQLAlchemy Model

```python
# New file or addition to shitvault/shitpost_models.py

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from shit.db.data_models import Base, IDMixin, TimestampMixin


class PostEmbedding(Base, IDMixin, TimestampMixin):
    """Stores text embeddings for semantic similarity search."""

    __tablename__ = "post_embeddings"

    prediction_id = Column(
        Integer, ForeignKey("predictions.id"),
        nullable=False, unique=True, index=True,
    )
    shitpost_id = Column(String(255), nullable=True)
    signal_id = Column(String(255), nullable=True)
    text_hash = Column(String(64), nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    model = Column(String(50), nullable=False, default="text-embedding-3-small")

    def __repr__(self):
        src = self.shitpost_id or self.signal_id or "?"
        return f"<PostEmbedding(prediction_id={self.prediction_id}, source={src})>"
```

**Dependency**: Add `pgvector` to `requirements.txt`:
```
pgvector>=0.3.0
```

---

## Similarity Matching

### Cosine Similarity Search

```python
def find_similar_posts(
    self,
    embedding: list[float],
    limit: int = 5,
    min_similarity: float = 0.60,
    exclude_prediction_id: int | None = None,
) -> list[dict]:
    """Find the most similar historical posts by embedding cosine similarity.

    Args:
        embedding: The query embedding vector.
        limit: Maximum number of matches to return.
        min_similarity: Minimum cosine similarity threshold (0-1).
        exclude_prediction_id: Exclude this prediction from results
            (to avoid matching the post against itself).

    Returns:
        List of dicts with prediction_id, similarity, text preview, etc.
    """
    from sqlalchemy import text as sql_text

    with get_session() as session:
        # pgvector cosine distance: 1 - cosine_similarity
        # Lower distance = more similar
        # We want similarity >= min_similarity, so distance <= 1 - min_similarity
        max_distance = 1.0 - min_similarity

        query = sql_text("""
            SELECT
                pe.prediction_id,
                pe.shitpost_id,
                pe.signal_id,
                1 - (pe.embedding <=> :query_vec) AS similarity,
                p.assets,
                p.market_impact,
                p.confidence,
                p.thesis,
                p.post_timestamp
            FROM post_embeddings pe
            JOIN predictions p ON p.id = pe.prediction_id
            WHERE pe.prediction_id != COALESCE(:exclude_id, -1)
                AND p.analysis_status = 'completed'
                AND (pe.embedding <=> :query_vec) <= :max_dist
            ORDER BY pe.embedding <=> :query_vec
            LIMIT :lim
        """)

        result = session.execute(query, {
            "query_vec": str(embedding),  # pgvector accepts string repr
            "exclude_id": exclude_prediction_id,
            "max_dist": max_distance,
            "lim": limit,
        })

        matches = []
        for row in result.fetchall():
            matches.append({
                "prediction_id": row[0],
                "shitpost_id": row[1],
                "signal_id": row[2],
                "similarity": round(float(row[3]), 4),
                "assets": row[4],
                "market_impact": row[5],
                "confidence": row[6],
                "thesis": row[7],
                "post_timestamp": row[8],
            })

        return matches
```

### Threshold Tuning

The `min_similarity` parameter controls how similar a post must be to qualify as an "echo." Based on text-embedding-3-small behavior:

| Similarity | Meaning | Example |
|-----------|---------|---------|
| 0.95+ | Near-duplicate | Same topic, nearly identical wording |
| 0.85-0.95 | Very similar | Same topic, different wording |
| 0.70-0.85 | Related topic | Same sector/company, different angle |
| 0.60-0.70 | Loosely related | Shared themes but different focus |
| <0.60 | Not meaningfully similar | Noise |

**Recommended threshold**: `0.65` -- captures topically related posts without too much noise. This should be configurable and can be tuned after observing real matches.

### Recency Weighting (Optional, Deferred)

Recent posts may be more predictive than old ones. A future enhancement could apply a time-decay weight:

```python
# Future: weighted_similarity = similarity * recency_factor
# recency_factor = exp(-days_old / 180)  # Half-life of 180 days
```

For v1, we use pure cosine similarity without recency weighting. The `post_timestamp` is returned so consumers can apply their own recency logic if desired.

---

## Echo Aggregation

### How to Summarize 3-5 Matches

Given the matched posts and their prediction_outcomes, compute aggregate statistics:

```python
def aggregate_echoes(
    self,
    matches: list[dict],
    timeframe: str = "t7",
) -> dict:
    """Aggregate outcomes from similar historical posts.

    Args:
        matches: List of match dicts from find_similar_posts().
        timeframe: Which timeframe to aggregate ("t1", "t3", "t7", "t30").

    Returns:
        Aggregated echo statistics dict.
    """
    if not matches:
        return {"count": 0}

    prediction_ids = [m["prediction_id"] for m in matches]

    from shit.db.sync_session import get_session
    from shit.market_data.models import PredictionOutcome

    with get_session() as session:
        outcomes = session.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id.in_(prediction_ids),
        ).all()

    # Group outcomes by prediction_id
    outcomes_by_pred = {}
    for o in outcomes:
        outcomes_by_pred.setdefault(o.prediction_id, []).append(o)

    # Compute per-match statistics
    returns = []
    correct_count = 0
    incorrect_count = 0
    pnl_values = []
    match_details = []

    for match in matches:
        pred_outcomes = outcomes_by_pred.get(match["prediction_id"], [])
        for o in pred_outcomes:
            ret = getattr(o, f"return_{timeframe}", None)
            corr = getattr(o, f"correct_{timeframe}", None)
            pnl = getattr(o, f"pnl_{timeframe}", None)

            if ret is not None:
                returns.append(ret)
            if corr is True:
                correct_count += 1
            elif corr is False:
                incorrect_count += 1
            if pnl is not None:
                pnl_values.append(pnl)

        match_details.append({
            "prediction_id": match["prediction_id"],
            "similarity": match["similarity"],
            "assets": match.get("assets", []),
            "thesis": (match.get("thesis") or "")[:100],
            "post_timestamp": match.get("post_timestamp"),
            "outcomes": [
                {
                    "symbol": o.symbol,
                    f"return_{timeframe}": getattr(o, f"return_{timeframe}", None),
                    f"correct_{timeframe}": getattr(o, f"correct_{timeframe}", None),
                }
                for o in pred_outcomes
            ],
        })

    evaluated = correct_count + incorrect_count
    return {
        "count": len(matches),
        "timeframe": timeframe,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else None,
        "median_return": round(sorted(returns)[len(returns) // 2], 4) if returns else None,
        "win_rate": round(correct_count / evaluated, 4) if evaluated > 0 else None,
        "correct": correct_count,
        "incorrect": incorrect_count,
        "pending": len(matches) - evaluated,
        "avg_pnl": round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "matches": match_details,
    }
```

### Example Aggregation Output

```python
{
    "count": 4,
    "timeframe": "t7",
    "avg_return": 1.82,     # Average T+7 return across all matched outcomes
    "median_return": 1.45,
    "win_rate": 0.6667,     # 2 out of 3 evaluated were correct
    "correct": 2,
    "incorrect": 1,
    "pending": 1,           # 1 match doesn't have T+7 outcome yet
    "avg_pnl": 18.20,       # Average P&L on $1000 position
    "matches": [
        {
            "prediction_id": 234,
            "similarity": 0.89,
            "assets": ["XLE", "OXY"],
            "thesis": "Drill baby drill — bullish energy sector",
            "post_timestamp": "2025-11-15T14:30:00",
            "outcomes": [
                {"symbol": "XLE", "return_t7": 3.2, "correct_t7": true},
                {"symbol": "OXY", "return_t7": 2.1, "correct_t7": true},
            ],
        },
        # ... more matches
    ],
}
```

---

## Integration Points

### 1. Analyzer Integration (Embedding on Analysis)

After a prediction is created and stored, embed the post text and store it:

**File**: `shitpost_ai/shitpost_analyzer.py`, in `_analyze_shitpost()` after `store_analysis()`:

```python
# After successful prediction storage:
if analysis_id and not dry_run:
    # Generate and store embedding for similarity search
    try:
        from shit.echoes.echo_service import EchoService
        echo_service = EchoService()
        echo_service.embed_and_store(
            prediction_id=int(analysis_id),
            text=shitpost.get("text", ""),
            shitpost_id=shitpost_id,
        )
    except Exception as e:
        logger.warning(f"Failed to generate embedding: {e}")
```

### 2. Alert Formatting (Telegram)

Modify the alert engine to include echo data when available:

**File**: `notifications/telegram_sender.py`, in `format_telegram_alert()`:

```python
def format_telegram_alert(alert: dict) -> str:
    # ... existing alert formatting ...

    # Append echo summary if available
    echoes = alert.get("echoes")
    if echoes and echoes.get("count", 0) > 0:
        msg += "\n\\U0001f4ca *Historical Echoes*"
        msg += f" \\({echoes['count']} similar past posts\\):\n"
        if echoes.get("avg_return") is not None:
            msg += f"\\u2022 Avg T\\+7 return: {echoes['avg_return']:+.1f}%\n"
        if echoes.get("win_rate") is not None:
            wr = echoes["win_rate"] * 100
            msg += f"\\u2022 Win rate: {echoes['correct']}/{echoes['correct'] + echoes['incorrect']} \\({wr:.0f}%\\)\n"
        if echoes.get("avg_pnl") is not None:
            msg += f"\\u2022 Avg P&L \\($1k\\): ${echoes['avg_pnl']:+.0f}\n"

    return msg
```

### 3. Frontend API

**New endpoint**: `GET /api/posts/{prediction_id}/echoes`

```python
# File: api/routers/echoes.py

from fastapi import APIRouter, HTTPException
from api.schemas.echoes import EchoResponse

router = APIRouter()

@router.get("/posts/{prediction_id}/echoes", response_model=EchoResponse)
def get_echoes(prediction_id: int):
    """Get historical echo matches for a prediction."""
    from shit.echoes.echo_service import EchoService

    service = EchoService()
    embedding = service.get_embedding(prediction_id)
    if embedding is None:
        raise HTTPException(404, "No embedding found for this prediction")

    matches = service.find_similar_posts(
        embedding=embedding,
        limit=5,
        exclude_prediction_id=prediction_id,
    )
    echoes = service.aggregate_echoes(matches, timeframe="t7")
    return echoes
```

**Response schema**:

```python
# File: api/schemas/echoes.py

from pydantic import BaseModel
from typing import Optional

class EchoOutcome(BaseModel):
    symbol: str
    return_t7: Optional[float] = None
    correct_t7: Optional[bool] = None

class EchoMatch(BaseModel):
    prediction_id: int
    similarity: float
    assets: list[str]
    thesis: str
    post_timestamp: Optional[str] = None
    outcomes: list[EchoOutcome]

class EchoResponse(BaseModel):
    count: int
    timeframe: str
    avg_return: Optional[float] = None
    median_return: Optional[float] = None
    win_rate: Optional[float] = None
    correct: int = 0
    incorrect: int = 0
    pending: int = 0
    avg_pnl: Optional[float] = None
    matches: list[EchoMatch]
```

### 4. Feed Response Enhancement

Add echoes to the existing `FeedResponse` so the frontend can display them inline:

```python
# In api/services/feed_service.py, add echo lookup to get_feed_response():
def get_feed_response(self, offset: int) -> Optional[dict]:
    # ... existing code ...

    # Fetch echoes for this prediction
    try:
        from shit.echoes.echo_service import EchoService
        service = EchoService()
        embedding = service.get_embedding(prediction_id)
        if embedding:
            matches = service.find_similar_posts(
                embedding, limit=3, exclude_prediction_id=prediction_id,
            )
            echoes = service.aggregate_echoes(matches)
        else:
            echoes = None
    except Exception:
        echoes = None

    response["echoes"] = echoes
    return response
```

### 5. LLM Prompt Enrichment (Future, Not in v1)

In a future iteration, echo outcomes could be injected into the analysis prompt (similar to fundamentals enrichment in Doc 02):

```
HISTORICAL ECHOES:
Similar past posts about energy policy averaged +1.8% on XLE over 7 days (3/5 correct).
Consider this track record when calibrating your confidence.
```

This creates a feedback loop where the LLM benefits from the system's own prediction history. Deferred to avoid circular dependencies in v1 (embedding happens after analysis, but prompt enrichment happens before).

---

## Alert Format: How Echoes Appear in Telegram

### Compact Format (Default)

```
🟢 SHITPOST ALPHA ALERT

Sentiment: BULLISH (82% confidence)
Assets: XLE, OXY
Thesis: Pro-energy policy signals bullish for fossil fuel sector

📊 Historical Echoes (4 similar posts):
• Avg T+7 return: +1.8%
• Win rate: 2/3 (67%)
• Avg P&L ($1k): +$18

⚠️ This is NOT financial advice.
```

### When No Echoes Exist

If the post is too unique (no matches above threshold), the echo section is omitted entirely. The alert looks exactly like today's alerts.

### When Echoes Have No Outcomes Yet

If matches exist but their outcomes haven't matured:

```
📊 Historical Echoes (3 similar posts):
• Outcomes: 3 pending (too recent to evaluate)
```

---

## Backfill Plan

### Phase 1: Enable pgvector Extension

```sql
-- Run once on Neon production database
CREATE EXTENSION IF NOT EXISTS vector;
```

Neon supports pgvector natively. No special setup required.

### Phase 2: Create Table

```sql
CREATE TABLE post_embeddings (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    shitpost_id VARCHAR(255),
    signal_id VARCHAR(255),
    text_hash VARCHAR(64) NOT NULL,
    embedding vector(1536) NOT NULL,
    model VARCHAR(50) NOT NULL DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_post_embeddings_prediction UNIQUE (prediction_id)
);

CREATE INDEX idx_post_embeddings_prediction_id ON post_embeddings(prediction_id);
-- Skip vector index for now (exact search is fast enough for <10k rows)
```

### Phase 3: Backfill Existing Posts

```python
# CLI: python -m shit.echoes.backfill

async def backfill_embeddings(batch_size: int = 100):
    """Embed all existing analyzed posts that don't have embeddings yet."""
    from shit.db.sync_session import get_session
    from shitvault.shitpost_models import Prediction
    from shit.echoes.echo_service import EchoService

    service = EchoService()

    with get_session() as session:
        # Find predictions without embeddings
        predictions = session.execute(text("""
            SELECT p.id, p.shitpost_id, p.signal_id,
                   COALESCE(s.text, ts.text) as post_text
            FROM predictions p
            LEFT JOIN signals s ON s.signal_id = p.signal_id
            LEFT JOIN truth_social_shitposts ts ON ts.shitpost_id = p.shitpost_id
            LEFT JOIN post_embeddings pe ON pe.prediction_id = p.id
            WHERE p.analysis_status = 'completed'
                AND pe.id IS NULL
                AND COALESCE(s.text, ts.text) IS NOT NULL
            ORDER BY p.id
        """)).fetchall()

    total = len(predictions)
    logger.info(f"Backfilling embeddings for {total} predictions")

    # Batch embed for efficiency
    for i in range(0, total, batch_size):
        batch = predictions[i:i + batch_size]
        texts = [row[3] for row in batch]

        embeddings = service.embedding_client.embed_batch(texts)

        with get_session() as session:
            for j, (pred_id, shitpost_id, signal_id, text) in enumerate(batch):
                service._store_embedding(
                    session,
                    prediction_id=pred_id,
                    shitpost_id=shitpost_id,
                    signal_id=signal_id,
                    text=text,
                    embedding=embeddings[j],
                )
            session.commit()

        logger.info(f"Backfilled {min(i + batch_size, total)}/{total} embeddings")

    logger.info(f"Backfill complete: {total} embeddings generated")
```

**Estimated backfill time**: ~1,000 posts / 100 per batch = 10 API calls. At ~1 second each, total time: ~10 seconds. Cost: $0.001.

### Phase 4: Add Vector Index (When Scale Demands)

At 10,000+ rows, add an HNSW index for approximate nearest neighbor search:

```sql
CREATE INDEX idx_post_embeddings_hnsw ON post_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

This changes exact cosine search to approximate, trading ~2% recall for 10-100x speed. Not needed until 10,000+ posts.

---

## EchoService: Central Service Class

```python
# New file: shit/echoes/echo_service.py

import hashlib
from typing import Optional

from shit.db.sync_session import get_session
from shit.llm.embeddings import EmbeddingClient
from shit.logging import get_service_logger

logger = get_service_logger("echo_service")

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_SIMILARITY_THRESHOLD = 0.65
DEFAULT_MATCH_LIMIT = 5


class EchoService:
    """Manages post embeddings and historical similarity search.

    Usage:
        service = EchoService()
        service.embed_and_store(prediction_id=123, text="...", shitpost_id="abc")
        matches = service.find_similar_posts(embedding, limit=5)
        echoes = service.aggregate_echoes(matches, timeframe="t7")
    """

    def __init__(self):
        self.embedding_client = EmbeddingClient(model=EMBEDDING_MODEL)

    def embed_and_store(
        self,
        prediction_id: int,
        text: str,
        shitpost_id: str | None = None,
        signal_id: str | None = None,
    ) -> bool:
        """Generate embedding for a post and store it.

        Args:
            prediction_id: The prediction ID to associate with.
            text: Post text to embed.
            shitpost_id: Optional shitpost ID.
            signal_id: Optional signal ID.

        Returns:
            True if stored, False if error or already exists.
        """
        if not text or not text.strip():
            logger.debug(f"Skipping empty text for prediction {prediction_id}")
            return False

        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Check if already embedded
        with get_session() as session:
            from shit.echoes.models import PostEmbedding
            existing = session.query(PostEmbedding).filter(
                PostEmbedding.prediction_id == prediction_id,
            ).first()
            if existing:
                logger.debug(f"Embedding already exists for prediction {prediction_id}")
                return False

        # Generate embedding
        embedding = self.embedding_client.embed(text)

        # Store
        with get_session() as session:
            self._store_embedding(
                session, prediction_id, shitpost_id, signal_id, text, embedding,
            )
            session.commit()

        logger.info(f"Stored embedding for prediction {prediction_id}")
        return True

    def _store_embedding(
        self, session, prediction_id, shitpost_id, signal_id, text, embedding,
    ):
        """Store an embedding in the database."""
        from shit.echoes.models import PostEmbedding
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        record = PostEmbedding(
            prediction_id=prediction_id,
            shitpost_id=shitpost_id,
            signal_id=signal_id,
            text_hash=text_hash,
            embedding=embedding,
            model=EMBEDDING_MODEL,
        )
        session.add(record)

    def get_embedding(self, prediction_id: int) -> Optional[list[float]]:
        """Retrieve the stored embedding for a prediction."""
        with get_session() as session:
            from shit.echoes.models import PostEmbedding
            record = session.query(PostEmbedding).filter(
                PostEmbedding.prediction_id == prediction_id,
            ).first()
            if record:
                return list(record.embedding)
        return None

    def find_similar_posts(
        self,
        embedding: list[float],
        limit: int = DEFAULT_MATCH_LIMIT,
        min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD,
        exclude_prediction_id: int | None = None,
    ) -> list[dict]:
        """Find similar posts by cosine similarity. See docstring above."""
        # ... (implementation shown in Similarity Matching section)

    def aggregate_echoes(
        self,
        matches: list[dict],
        timeframe: str = "t7",
    ) -> dict:
        """Aggregate outcomes from similar posts. See docstring above."""
        # ... (implementation shown in Echo Aggregation section)
```

---

## New Package Structure

```
shit/
└── echoes/
    ├── __init__.py
    ├── echo_service.py     # Main service (embed, search, aggregate)
    ├── models.py           # PostEmbedding SQLAlchemy model
    └── backfill.py         # CLI for batch embedding existing posts

shit/llm/
└── embeddings.py           # EmbeddingClient (OpenAI embedding API)
```

---

## Testing Strategy

### Unit Tests

**File**: `shit_tests/echoes/test_echo_service.py`

1. **`test_embed_and_store`**: Mock OpenAI API, verify embedding stored in DB.
2. **`test_embed_and_store_duplicate`**: Call twice, verify second call returns False.
3. **`test_embed_and_store_empty_text`**: Empty text, verify returns False.
4. **`test_get_embedding`**: Store then retrieve, verify vector matches.
5. **`test_get_embedding_not_found`**: Unknown prediction_id, verify returns None.

**File**: `shit_tests/echoes/test_similarity.py`

6. **`test_find_similar_posts`**: Store 10 embeddings, search with a query vector, verify top matches returned in descending similarity order.
7. **`test_find_similar_posts_exclude_self`**: Verify the `exclude_prediction_id` parameter works.
8. **`test_find_similar_posts_min_threshold`**: With high threshold, verify low-similarity posts are excluded.
9. **`test_find_similar_posts_empty_db`**: No embeddings in DB, verify empty list returned.

**File**: `shit_tests/echoes/test_aggregation.py`

10. **`test_aggregate_echoes_with_outcomes`**: 3 matches with T+7 outcomes, verify avg_return, win_rate, avg_pnl.
11. **`test_aggregate_echoes_no_outcomes`**: Matches exist but no prediction_outcomes, verify graceful handling.
12. **`test_aggregate_echoes_partial_outcomes`**: Some matches have outcomes, some pending. Verify correct/pending counts.
13. **`test_aggregate_echoes_empty_matches`**: Empty matches list, verify `{"count": 0}`.

**File**: `shit_tests/llm/test_embeddings.py`

14. **`test_embed_single`**: Mock OpenAI, verify correct API call and return value.
15. **`test_embed_batch`**: Mock OpenAI batch API, verify multiple embeddings returned.
16. **`test_embed_truncation`**: Very long text (>8000 chars), verify truncation.

### Integration Tests

17. **`test_end_to_end_echo_flow`**: Create a prediction, embed it, create 5 historical predictions with known embeddings and outcomes, search for echoes, verify aggregation.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `shit/echoes/__init__.py` | Create | Package init |
| `shit/echoes/echo_service.py` | Create | Main service class |
| `shit/echoes/models.py` | Create | PostEmbedding SQLAlchemy model |
| `shit/echoes/backfill.py` | Create | CLI for batch embedding existing posts |
| `shit/llm/embeddings.py` | Create | EmbeddingClient for OpenAI embeddings API |
| `api/routers/echoes.py` | Create | API endpoint for echoes |
| `api/schemas/echoes.py` | Create | Pydantic response models |
| `api/main.py` | Modify | Register echoes router |
| `shitpost_ai/shitpost_analyzer.py` | Modify | Call embed_and_store after prediction creation |
| `notifications/telegram_sender.py` | Modify | Include echo summary in alert format |
| `notifications/event_consumer.py` | Modify | Look up echoes when dispatching alerts |
| `api/services/feed_service.py` | Modify | Include echoes in feed response |
| `requirements.txt` | Modify | Add `pgvector>=0.3.0` |
| `shit_tests/echoes/test_echo_service.py` | Create | Unit tests for echo service |
| `shit_tests/echoes/test_similarity.py` | Create | Unit tests for similarity search |
| `shit_tests/echoes/test_aggregation.py` | Create | Unit tests for aggregation |
| `shit_tests/llm/test_embeddings.py` | Create | Unit tests for embedding client |

---

## Open Questions

1. **pgvector on Neon**: Verify `CREATE EXTENSION vector` works on our Neon tier. Neon's documentation says pgvector is supported on all plans, but we should confirm before implementation.

2. **Embedding model lock-in**: If we switch from `text-embedding-3-small` to a different model later, all existing embeddings become incompatible. The `model` column on `post_embeddings` tracks this, but a model change would require re-embedding everything. This is cheap (~$0.001) but the migration needs to be planned.

3. **Similarity threshold**: 0.65 is a starting point. We should analyze actual similarity distributions after backfill to tune this. A histogram of all-pairs similarity scores would help.

4. **Embedding scope**: Should we embed the post text only, or include the LLM thesis? The thesis captures the LLM's interpretation, which might be more useful for similarity. But it also means the embedding depends on LLM behavior, which may change. Start with post text only for simplicity.

5. **Real-time vs batch echoes**: The current design computes echoes synchronously when an alert is dispatched or the API is called. At scale, this could add latency. A future optimization could pre-compute echoes asynchronously after embedding storage, caching the results in a `prediction_echoes` table.

6. **Frontend design**: How should echoes appear in the React feed? Options: (a) collapsible section below the prediction card, (b) separate tab/view, (c) inline summary with expandable details. This is a frontend design decision that doesn't affect the backend.

7. **Echo staleness**: As new posts are added and embedded, the echo matches for an old prediction change (new similar posts appear). Should we cache echo results or always compute fresh? For v1, always compute fresh -- the query is fast with pgvector.

8. **Notification worker enrichment**: The `NotificationsWorker` event consumer has a minimal event payload (no thesis, no text). To include echoes in event-driven alerts, the worker needs to (a) query the prediction for its embedding, then (b) run the echo search. This adds ~50-100ms per alert. Worth it for the user value.
