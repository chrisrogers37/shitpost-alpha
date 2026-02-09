# Architecture Evaluation Addendum: Kafka & Event-Driven Communication for Multi-Source Expansion

**Date**: 2026-02-09
**Parent Document**: [ARCHITECTURE_EVALUATION.md](./ARCHITECTURE_EVALUATION.md)
**Scope**: Re-evaluation of communication pattern decision (D2) given planned multi-source expansion
**Status**: Evaluation complete. Amends D2 recommendation.

---

## Table of Contents

1. [Context & Motivation](#1-context--motivation)
2. [Re-evaluation of D2: Database Polling vs. Event-Driven](#2-re-evaluation-of-d2-database-polling-vs-event-driven)
3. [Kafka Topic Topology Design](#3-kafka-topic-topology-design)
4. [Technology Comparison: Kafka vs. Alternatives](#4-technology-comparison-kafka-vs-alternatives)
5. [Architectural Impact on Existing Service Boundaries](#5-architectural-impact-on-existing-service-boundaries)
6. [Updated Migration Plan](#6-updated-migration-plan)
7. [Cost Analysis](#7-cost-analysis)
8. [Recommendation](#8-recommendation)
9. [Amended Decision Log](#9-amended-decision-log)

---

## 1. Context & Motivation

### 1.1 What Changed

The original evaluation (Section 4.1) recommended database polling based on a single-source system:

> ~28,000 posts over ~13 months = ~70 posts/day = ~3 posts/hour

This was the correct call for that context. Section 10.1 explicitly called message queues an anti-pattern:

> At ~70 posts/day and ~$15/month infrastructure budget, adding Kafka, RabbitMQ, or even Redis pub/sub is over-engineering for the volume.

**The premise has changed.** The planned expansion includes:

| Source | Type | Estimated Volume | Frequency |
|--------|------|-----------------|-----------|
| Truth Social | Social media | ~70 posts/day | Real-time (5-min poll) |
| Twitter/X | Social media | ~500-5,000 posts/day (filtered) | Real-time (streaming API or poll) |
| Reddit | Social media | ~200-1,000 posts/day (filtered) | Near-real-time (poll) |
| Congressional trading disclosures | Financial filings | ~5-20/day (bursty) | Batch (daily) |
| SEC filings | Regulatory | ~10-50/day (filtered) | Batch (daily, bursty around deadlines) |
| Fed announcements | Monetary policy | ~1-5/day | Scheduled (known calendar) |
| Earnings calendars | Corporate events | ~20-100/day (seasonal) | Batch (quarterly heavy) |

**Aggregate volume**: ~800-6,000+ events/day across 5-10 sources, up from ~70/day from 1 source.

### 1.2 The Fundamental Question

The original evaluation's polling pattern (Section 4.3) relies on each service asking "Is there work for me to do?" against the database. This works when there's one table (`truth_social_shitposts`) with one writer (ETL) and one consumer (Analyzer).

With N sources, the question becomes: **does each new source get its own table, its own ETL, its own polling query — or is there a shared event backbone that decouples producers from consumers?**

This addendum evaluates whether that backbone should be Kafka, a lighter alternative, or whether the database-as-queue pattern can stretch to cover multi-source ingestion.

---

## 2. Re-evaluation of D2: Database Polling vs. Event-Driven

### 2.1 Where Database Polling Breaks Down

The original evaluation's polling pattern (Section 3.3) defines precondition checks per service:

| Service | Original Precondition |
|---------|----------------------|
| ETL | "Are there S3 files I haven't processed?" |
| Analyzer | "Are there posts where analyzed=False?" |
| Market Data | "Are there completed predictions with missing price data?" |

With multiple sources, this pattern hits three concrete problems:

**Problem 1: Polling query proliferation.** The Analyzer currently runs one query:

```sql
SELECT * FROM truth_social_shitposts
WHERE shitpost_id NOT IN (SELECT shitpost_id FROM predictions)
LIMIT 5;
```

With 7 sources, this becomes 7 queries against 7 tables (or one polymorphic table with complex filtering). Each new source requires modifying the Analyzer's polling logic — the Analyzer must *know about every source type*. This violates the decoupling that Section 3.3 was designed to achieve.

**Problem 2: Fan-in is awkward with polling.** The desired pattern is many-producers-to-shared-consumers. With polling, the consumer must enumerate all possible producers. Adding a new source means touching downstream services. With an event backbone, adding a new source means "publish to the topic" — downstream services are unchanged.

**Problem 3: Heterogeneous frequencies.** Twitter might produce events every second. SEC filings arrive in quarterly bursts. Congressional disclosures trickle in daily. A single 5-minute cron poll (Section 4.2) is either too slow for Twitter or wastefully frequent for SEC filings. Event-driven naturally handles mixed cadences — events arrive when they arrive.

### 2.2 Where Database Polling Still Holds

Not everything needs to change. The original evaluation is correct that:

- **Market Data Service polling** (Section 4.3) remains valid. It polls for "predictions with missing price data" — this is downstream of the source-ingestion problem and source-agnostic by design.
- **Outcome calculation polling** remains valid. It checks for incomplete outcomes by elapsed time, not by source.
- **Alert Service polling** (Section 4.3) remains valid. It checks for new predictions regardless of source.

The event-driven need is specifically at the **ingestion and normalization layer** — getting heterogeneous source data into a common format and notifying the analysis pipeline.

### 2.3 The Key Architectural Insight

The multi-source expansion doesn't require making *everything* event-driven. It requires an event backbone at the **fan-in point**: where N harvesters produce normalized content events that a single analysis pipeline consumes.

```
                    ┌─── Truth Social Harvester ──┐
                    │                              │
                    ├─── Twitter/X Harvester ──────┤
                    │                              │
                    ├─── Reddit Harvester ─────────┤     ┌── Analyzer
                    │                              ├────>│
                    ├─── SEC Filing Harvester ─────┤     ├── Market Data
                    │                              │     │
                    ├─── Congressional Harvester ──┤     └── Alerts
                    │                              │
                    └─── Fed Announcement Scraper ─┘
                              │
                        EVENT BACKBONE
                     (the question: what is this?)
```

**Amended position on D2**: Database polling remains correct for service-to-service communication *downstream* of ingestion (Analyzer → Market Data → Outcomes → Alerts). But the fan-in point — N harvesters feeding shared consumers — benefits from an event-driven pattern. The question is which technology implements that pattern.

---

## 3. Kafka Topic Topology Design

This section designs the Kafka architecture *as if we adopt it*, to evaluate its fitness. Section 4 compares alternatives.

### 3.1 Topic Design

Three topics, organized by stage in the pipeline:

```
shitpost.raw-content          # All harvested content, all sources
shitpost.normalized-content   # Cleaned, schema-validated, ready for analysis
shitpost.predictions          # Completed analysis results
```

**Why three topics instead of one?**

- `raw-content` is the firehose — every source dumps here in its native format. Consumers that need source-specific processing subscribe here.
- `normalized-content` is the fan-in point — a normalizer service transforms source-specific data into a common schema. The Analyzer subscribes here and doesn't know or care about the source.
- `predictions` enables downstream services (Market Data, Alerts) to react to new predictions without polling. This is optional — polling still works here — but it's natural to add once the backbone exists.

### 3.2 Event Schemas

**Topic: `shitpost.raw-content`**

```json
{
  "event_id": "uuid-v4",
  "event_type": "raw_content_harvested",
  "timestamp": "2026-02-09T14:30:00Z",
  "source": "truth_social",
  "source_id": "114130750873498871",
  "s3_key": "truth-social/raw/2026/02/09/114130750873498871.json",
  "metadata": {
    "harvester_version": "1.0",
    "harvest_mode": "incremental"
  }
}
```

Key design choices:
- The event carries a **reference to S3**, not the full payload. S3 remains the source of truth for raw data (preserving the pattern Section 7.5 correctly identified as well-designed).
- `source` field enables topic-level filtering without separate topics per source.
- `source_id` is the native ID from the origin platform.

**Topic: `shitpost.normalized-content`**

```json
{
  "event_id": "uuid-v4",
  "event_type": "content_normalized",
  "timestamp": "2026-02-09T14:30:05Z",
  "source": "truth_social",
  "source_id": "114130750873498871",
  "db_id": 1548,
  "content": {
    "text": "Post content here...",
    "author": "realDonaldTrump",
    "author_verified": true,
    "posted_at": "2026-02-09T14:25:00Z",
    "content_type": "original",
    "engagement": {
      "replies": 450,
      "shares": 1200,
      "likes": 8500
    },
    "media_attached": false,
    "tags": [],
    "mentions": []
  },
  "analysis_hint": {
    "is_repost": false,
    "has_financial_keywords": true,
    "priority": "normal"
  }
}
```

Key design choices:
- This is the **common schema** all sources normalize into. A Reddit post and a Truth Social post look the same at this layer.
- `content_type` distinguishes originals from reposts/retweets/retruths — the bypass logic (Section 3.1, Analyzer) works generically.
- `analysis_hint` lets the normalizer pre-filter content the Analyzer would skip, reducing unnecessary LLM calls.
- `db_id` references the database row, since the ETL has already stored the post by this point.

**Topic: `shitpost.predictions`**

```json
{
  "event_id": "uuid-v4",
  "event_type": "prediction_created",
  "timestamp": "2026-02-09T14:30:30Z",
  "prediction_id": "uuid-v4",
  "source": "truth_social",
  "source_id": "114130750873498871",
  "shitpost_id": "114130750873498871",
  "analysis_status": "completed",
  "assets": ["TSLA", "DJT"],
  "sentiment": "bullish",
  "confidence": "high"
}
```

Key design choices:
- This topic is consumed by Market Data (to trigger price backfill) and Alerts (to trigger notifications).
- Carries only the fields downstream services need — the full prediction is in PostgreSQL.
- `analysis_status` lets consumers filter for completed vs. bypassed predictions without a DB round-trip.

### 3.3 Partition Strategy

| Topic | Partition Key | Partitions | Rationale |
|-------|--------------|------------|-----------|
| `raw-content` | `source` | 4-8 | Keeps per-source ordering; allows parallel consumption by source |
| `normalized-content` | `source_id` | 4 | Even distribution; ordering within a source entity is preserved |
| `predictions` | `shitpost_id` | 2 | Low volume; mainly for fan-out to Market Data + Alerts |

At 5-10 sources and <10K events/day, partition counts are modest. Start with fewer and increase only if consumer lag grows.

### 3.4 Consumer Group Design

```
Consumer Group: normalizer-group
  └── Subscribes to: shitpost.raw-content
  └── Instances: 1 (scales to N for parallel source processing)

Consumer Group: analyzer-group
  └── Subscribes to: shitpost.normalized-content
  └── Instances: 1 (rate-limited by LLM API anyway)

Consumer Group: market-data-group
  └── Subscribes to: shitpost.predictions
  └── Instances: 1

Consumer Group: alert-group
  └── Subscribes to: shitpost.predictions
  └── Instances: 1

Consumer Group: etl-group
  └── Subscribes to: shitpost.raw-content
  └── Instances: 1 (writes to PostgreSQL)
```

### 3.5 How Existing Services Become Consumers

| Current Service | Current Pattern | Kafka Pattern |
|----------------|----------------|---------------|
| Harvester | Cron → API → S3 | Cron → API → S3 → **produce to `raw-content`** |
| ETL | Cron → poll S3 → write DB | **Consume `raw-content`** → read S3 → write DB → **produce to `normalized-content`** |
| Analyzer | Cron → poll DB (analyzed=False) → LLM → write DB | **Consume `normalized-content`** → LLM → write DB → **produce to `predictions`** |
| Market Data | Cron → poll DB (missing prices) → yfinance → write DB | **Consume `predictions`** → yfinance → write DB (cron retained for refresh) |
| Alert Service | Cron → poll DB (new predictions) → send notifications | **Consume `predictions`** → send notifications |

---

## 4. Technology Comparison: Kafka vs. Alternatives

### 4.1 Evaluation Criteria

Weighted for a solo Python developer on Railway with a ~$15/month budget expanding to 5-10 data sources:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Fan-in pattern support | High | N producers → shared consumers without consumer changes |
| Operational complexity | High | Setup, monitoring, debugging burden for a solo dev |
| Python ecosystem | High | Quality of client libraries, async support, community |
| Railway deployability | Medium | Can it run on Railway, or does it require a platform move? |
| Cost | High | Monthly spend for the expected volume |
| Durability & replay | Medium | Can you replay events? How long are they retained? |
| Scaling headroom | Low | Matters only if volume 10x-100x exceeds projections |

### 4.2 Option A: Apache Kafka / Redpanda (Managed)

**Managed providers**: Confluent Cloud, Upstash Kafka, Redpanda Serverless, AWS MSK Serverless.

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Fan-in support | Excellent | Purpose-built for this. Topic-based pub/sub with consumer groups is exactly the pattern. |
| Operational complexity | **High (self-hosted) / Medium (managed)** | Self-hosted Kafka on Railway is impractical (JVM, ZooKeeper/KRaft, memory-hungry). Managed services abstract this away but add vendor lock-in. |
| Python ecosystem | Good | `confluent-kafka` (C-backed, fast), `aiokafka` (pure Python, async). Both mature. |
| Railway deployability | Poor (self-hosted) / Good (managed external) | Kafka doesn't run on Railway. You'd use a managed provider (Confluent, Upstash) as an external service, similar to how Neon PostgreSQL is external. |
| Cost | **$0-20/month (managed serverless)** | Upstash Kafka: Free tier covers 10K messages/day. Confluent Cloud basic: ~$0 at low volume (pay-per-use). Redpanda Serverless: Free tier covers most hobby usage. |
| Durability & replay | Excellent | Configurable retention (days to infinite). Full event replay. Log compaction for state reconstruction. |
| Scaling headroom | Excellent | Kafka handles millions of events/second. Absurd overkill for this volume, but it means you never hit a ceiling. |

**Upstash Kafka pricing (most relevant for this project)**:
- Free tier: 10,000 messages/day, 256 partitions, 1 day retention
- Pay-as-you-go: $0.60/100K messages after free tier
- At ~6,000 events/day: **free or <$1/month**

**Verdict**: Managed Kafka is surprisingly affordable at this volume. The cost objection from Section 10.1 assumed self-hosted or enterprise-tier managed. Serverless Kafka pricing has changed the calculus.

### 4.3 Option B: Redis Streams

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Fan-in support | Good | Consumer groups, stream-per-topic, `XREADGROUP` provides Kafka-like semantics. |
| Operational complexity | Medium | Simpler than Kafka. Single binary. But: persistence config matters, memory management, no built-in schema registry. |
| Python ecosystem | Excellent | `redis-py` has native Streams support. `aioredis` for async. Very well-documented. |
| Railway deployability | Good | Railway has a Redis plugin ($5/month) or use Upstash Redis (free tier: 10K commands/day). |
| Cost | **$0-5/month** | Upstash Redis free tier may suffice. Railway Redis: $5/month. |
| Durability & replay | Moderate | Streams are persistent and replayable, but limited by memory. No log compaction. Retention requires manual `XTRIM`. |
| Scaling headroom | Good | Handles 100K+ messages/second. More than sufficient. |

**Key limitation**: Redis Streams lack native topic-level partitioning. You simulate it with multiple streams, but consumer group assignment is per-stream, not per-partition. For a simple fan-in pattern with <10K events/day, this doesn't matter. For complex routing, it gets awkward.

**Verdict**: Strong option. Lower learning curve than Kafka, cheaper, runs on Railway natively. But weaker replay/retention semantics and less natural multi-topic routing.

### 4.4 Option C: PostgreSQL LISTEN/NOTIFY + Outbox Table

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Fan-in support | Moderate | LISTEN/NOTIFY is fire-and-forget (no persistence). Outbox table pattern adds persistence but requires polling the outbox — you're back to database-as-queue with extra steps. |
| Operational complexity | **Low** | No new infrastructure. Uses existing Neon PostgreSQL. |
| Python ecosystem | Good | `psycopg2`/`psycopg` support LISTEN/NOTIFY natively. `asyncpg` has excellent async support. |
| Railway deployability | Excellent | Already deployed. No changes needed. |
| Cost | **$0** | Uses existing database. |
| Durability & replay | **Poor (NOTIFY) / Moderate (outbox)** | NOTIFY messages are lost if no listener is connected. Outbox table persists but requires separate polling. |
| Scaling headroom | Low | NOTIFY doesn't scale past a few hundred messages/second on Neon's serverless tier. Connection limits are tight. |

**Critical problem for this use case**: Neon's serverless PostgreSQL uses connection pooling and auto-suspend. LISTEN/NOTIFY requires persistent connections — it is fundamentally incompatible with Neon's architecture. The original evaluation (Section 4.1) correctly identified this:

> Requires persistent connections (not great with Neon serverless)

The outbox pattern (insert events into a table, poll that table) works but provides no advantage over the current database-as-queue approach. It adds a table and a polling mechanism to achieve what the existing `analyzed=False` pattern already does.

**Verdict**: Not viable with Neon. Would work with a traditional always-on PostgreSQL instance, but switching databases to enable messaging is backwards. Ruled out.

### 4.5 Option D: AWS SQS/SNS

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Fan-in support | Excellent | SNS fan-out to multiple SQS queues is a native pattern. Dead letter queues built in. |
| Operational complexity | Low-Medium | Managed by AWS. No servers. But: IAM policies, queue configuration, DLQ setup. AWS console is complex for a newcomer. |
| Python ecosystem | Excellent | `boto3` is already in the project (used for S3). Zero new libraries. |
| Railway deployability | Good | External service, connects via HTTPS. Works from anywhere. |
| Cost | **$0-1/month** | SQS: $0.40/million requests. SNS: $0.50/million publishes. At 6K events/day = 180K/month. Well within free tier (1M SQS requests/month free). |
| Durability & replay | **Poor** | SQS messages are consumed and deleted. No replay. No event log. No retention beyond 14 days. To get replay, you'd need to combine with Kinesis or S3, which adds complexity. |
| Scaling headroom | Excellent | Effectively unlimited. |

**Key limitation**: SQS is a queue, not a log. Messages are consumed once and deleted. You can't replay events, reprocess from a point in time, or add a new consumer that reads historical events. For a data pipeline where you might want to reprocess data after fixing a bug or adding a new analysis dimension, this is a real limitation.

**Also**: SQS ordering guarantees are per-message-group (FIFO queues) or none (standard queues). Standard queues can deliver messages out of order and sometimes duplicate. FIFO queues are limited to 300 messages/second per message group.

**Verdict**: Cheapest option after PostgreSQL. The lack of replay is the dealbreaker — in a data pipeline, the ability to reprocess events is valuable. If you don't need replay, SQS+SNS is extremely practical.

### 4.6 Option E: NATS

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Fan-in support | Excellent | Subject-based pub/sub with queue groups. JetStream adds persistence and replay. |
| Operational complexity | **Low** | Single ~20MB binary. No JVM, no ZooKeeper. Starts in milliseconds. Minimal configuration. |
| Python ecosystem | Good | `nats-py` is the official async client. Well-maintained but smaller community than Kafka or Redis. |
| Railway deployability | **Good** | Runs as a lightweight Docker container on Railway. ~50MB memory footprint. Can co-locate with a service. |
| Cost | **$0-3/month** | Self-hosted on Railway: minimal resource usage. Synadia Cloud (managed NATS): free tier covers small workloads. |
| Durability & replay | Good (with JetStream) | JetStream provides persistent streams with replay, consumer acknowledgment, and retention policies. Not as mature as Kafka's log but covers the use case. |
| Scaling headroom | Excellent | NATS handles millions of messages/second. JetStream handles persistent workloads at scale. |

**Key strength**: NATS is the lightest-weight option that provides real event-driven semantics with durability. It's the "right-sized Kafka" for small-to-medium workloads. The Go binary is trivial to deploy and has near-zero operational overhead.

**Key limitation**: Smaller ecosystem than Kafka or Redis. Fewer tutorials, fewer Stack Overflow answers, fewer Python examples. JetStream is newer than Kafka Streams and less battle-tested for complex stream processing.

**Verdict**: The best fit if you want event-driven architecture without Kafka's conceptual and operational weight. Underrated option.

### 4.7 Comparison Matrix

| Criterion | Kafka (managed) | Redis Streams | PG LISTEN/NOTIFY | SQS/SNS | NATS |
|-----------|-----------------|---------------|-------------------|---------|------|
| Fan-in (N→1) | ★★★★★ | ★★★★ | ★★★ | ★★★★★ | ★★★★★ |
| Solo-dev ops burden | ★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★★ |
| Python ecosystem | ★★★★ | ★★★★★ | ★★★★ | ★★★★★ | ★★★ |
| Railway deploy | ★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★ |
| Cost (<10K events/day) | ★★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| Durability & replay | ★★★★★ | ★★★ | ★★ | ★★ | ★★★★ |
| Scaling headroom | ★★★★★ | ★★★★ | ★★ | ★★★★★ | ★★★★★ |
| **Weighted score** | **4.0** | **3.9** | **3.3** | **3.8** | **4.2** |

*(Weighted: Fan-in 20%, Ops burden 25%, Python 15%, Railway 10%, Cost 15%, Durability 10%, Scaling 5%)*

---

## 5. Architectural Impact on Existing Service Boundaries

### 5.1 Impact Summary

If an event backbone is adopted, the original evaluation's 7 services (Section 3.1) change as follows:

| Service | Original Role | Impact | Change Required |
|---------|--------------|--------|-----------------|
| **Harvester** | API → S3 | **Minor**: adds event publish after S3 write | Append 5 lines of producer code |
| **ETL** | S3 → PostgreSQL | **Moderate**: triggered by event instead of cron poll | Switch from cron-poll to consumer loop |
| **Analyzer** | Poll DB → LLM → DB | **Moderate**: triggered by event instead of polling `analyzed=False` | Switch from cron-poll to consumer loop |
| **Market Data** | Poll DB → yfinance → DB | **Minor**: optionally triggered by prediction events; cron retained for price refresh | Add optional consumer, keep cron |
| **Alert Service** | Poll DB → notifications | **Minor**: optionally triggered by prediction events | Add optional consumer |
| **Dashboard** | Read-only web UI | **None** | No change |
| **NEW: Normalizer** | Transform source-specific → common schema | **New service** | Consumes `raw-content`, produces `normalized-content` |

### 5.2 The Normalizer: A New Service

The multi-source expansion introduces a service that doesn't exist in the original evaluation: a **Normalizer** that transforms heterogeneous source data into the common schema the Analyzer expects.

Currently, the Analyzer reads `truth_social_shitposts` directly and understands Truth Social's data format (content field, retruth detection, engagement metrics). With multiple sources, either:

**(a)** The Analyzer grows source-specific logic for each new source (violates single responsibility, becomes a hairball), or

**(b)** A Normalizer sits between ETL and Analyzer, producing a common content format regardless of source.

Option (b) is correct. The Normalizer:

- Consumes raw-content events (or polls a staging table)
- Reads the source-specific data from S3 or the database
- Maps it to the common `NormalizedContent` schema
- Publishes to the normalized-content topic (or writes to a `normalized_content` table)
- Handles source-specific bypass logic (e.g., retweets from Twitter, retruth from Truth Social)

This service is needed **regardless of whether you adopt Kafka**. Even with database polling, you need a normalization step. The event backbone just makes the trigger mechanism cleaner.

### 5.3 Does S3 Remain the Source of Truth?

**Yes. Unambiguously.**

The original evaluation (Section 7.5) correctly identified S3 as the immutable source of truth:

> S3 is correctly positioned as the immutable source of truth for raw post data. The database is a derived, queryable view.

Adding an event backbone does not change this. The event (in any technology) carries a **reference** to the S3 object, not the payload itself. The flow is:

```
Harvester → S3 (store raw data) → Event backbone (notify: "new data at s3://...")
                                           ↓
                                    ETL reads from S3 using the reference
```

Kafka's log is **not** the source of truth. It's a notification mechanism. Events can expire from Kafka/Redis/NATS after days or weeks, but S3 retains everything forever. If you need to reprocess, you reprocess from S3, not from the event log.

This is an important distinction: some architectures use Kafka's log as the primary data store (event sourcing). That would be over-engineering here. S3 is cheaper, simpler, and already works.

### 5.4 What Happens to the ETL Service?

The ETL service's role changes subtly but importantly:

**Before (single source)**: Cron → scan S3 for new files → load into `truth_social_shitposts`

**After (multi source)**: Receive event → read S3 object by key → load into source-specific or polymorphic table

The key difference: **the ETL no longer needs to scan S3**. Currently, the `S3Processor` uses `paginator.paginate()` to list S3 objects and find new ones. This is slow (S3 LIST is expensive at scale) and brittle (relies on key naming conventions). With events, the ETL receives the exact S3 key to process. No scanning needed.

The ETL also needs to handle multiple source schemas. Two approaches:

1. **Polymorphic table**: A single `content` table with a `source` column and a JSON `raw_data` column. Simpler but loses type safety.
2. **Per-source tables**: `truth_social_posts`, `twitter_posts`, `reddit_posts`, etc. More tables but stronger schemas.

**Recommendation**: Start with per-source tables (each harvester owns its table schema), normalize into a common view or table via the Normalizer. This keeps the clean write-ownership pattern from Section 7.2.

### 5.5 Updated Service Decomposition Diagram

```
                    ┌───────────────────────────────────────────────┐
                    │              EXTERNAL SOURCES                  │
                    │  Truth Social  Twitter  Reddit  SEC  Congress  │
                    └──┬──────────┬───────┬──────┬────────┬────────┘
                       │          │       │      │        │
                  ┌────▼──┐  ┌───▼──┐ ┌──▼──┐ ┌─▼──┐ ┌──▼──┐
                  │Harvest│  │Harv. │ │Harv.│ │Harv│ │Harv.│
                  │Truth  │  │Twit. │ │Redd.│ │SEC │ │Cong.│
                  └───┬───┘  └──┬───┘ └──┬──┘ └─┬──┘ └──┬──┘
                      │         │        │      │       │
                      ▼         ▼        ▼      ▼       ▼
                  ┌──────────────────────────────────────────┐
                  │            S3 Data Lake                   │
                  │  s3://bucket/{source}/raw/YYYY/MM/DD/    │
                  └─────────────────┬────────────────────────┘
                                    │
                      ┌─────────────▼──────────────┐
                      │     EVENT BACKBONE          │
                      │  Topic: raw-content         │
                      │  (notification + S3 ref)    │
                      └──────┬──────────────────────┘
                             │
                     ┌───────▼────────┐
                     │   ETL Service  │
                     │  (per-source   │
                     │   loaders)     │
                     └───────┬────────┘
                             │ WRITES: per-source tables
                             │
                      ┌──────▼──────────────┐
                      │  EVENT BACKBONE      │
                      │  Topic: normalized   │
                      └──────┬──────────────┘
                             │
                     ┌───────▼────────┐
                     │   Normalizer   │
                     │ (source→common │
                     │   schema)      │
                     └───────┬────────┘
                             │
                     ┌───────▼────────┐
                     │  LLM Analyzer  │
                     │  (unchanged    │
                     │   analysis     │
                     │   logic)       │
                     └───────┬────────┘
                             │ WRITES: predictions
                             │
                      ┌──────▼──────────────┐
                      │  EVENT BACKBONE      │
                      │  Topic: predictions  │
                      └──┬──────────────┬───┘
                         │              │
                  ┌──────▼──────┐ ┌─────▼───────┐
                  │ Market Data │ │   Alerts    │
                  │ (cron+event)│ │ (event)     │
                  └──────┬──────┘ └─────────────┘
                         │
                  ┌──────▼────────────────────────────────────┐
                  │            Neon PostgreSQL                  │
                  │                                            │
                  │  truth_social_posts │ twitter_posts        │
                  │  reddit_posts       │ sec_filings          │
                  │  normalized_content │ predictions          │
                  │  market_prices      │ prediction_outcomes  │
                  └────────────────────┬──────────────────────┘
                                       │
                                ┌──────▼──────┐
                                │  Dashboard  │
                                │  (read-only)│
                                └─────────────┘
```

---

## 6. Updated Migration Plan

The original evaluation defines a 5-phase plan (Section 8). The event backbone slots in as a new Phase 3, shifting the original Phases 3-5 forward.

### 6.1 Amended Phase Sequence

| Phase | Original Plan | Amended Plan | Timing |
|-------|---------------|-------------|--------|
| 0 | Wire Market Data Service | **Unchanged** | Week 1 |
| 1 | Decouple Orchestrator (independent crons) | **Unchanged** | Week 2 |
| 2 | Split Requirements and Settings | **Unchanged** | Week 3 |
| **3** | **Clean Up Dead Code/Tables** | **Event backbone introduction** | Week 4-5 |
| 4 | ~~Extract Alert Service~~ | Clean Up Dead Code/Tables (was Phase 3) | Week 6 |
| 5 | ~~Dashboard Refactoring~~ | Second source onboarding + Normalizer | Week 7-8 |
| 6 | (new) | Extract Alert Service (was Phase 4) | When needed |
| 7 | (new) | Dashboard Refactoring (was Phase 5) | When needed |

**Critical point**: Phases 0-2 are unchanged and should proceed immediately. They have value independent of whether you adopt an event backbone. The event backbone is Phase 3 — it builds on the foundation of independent services established in Phases 0-2.

### 6.2 Phase 3 (New): Event Backbone Introduction

**Risk**: Medium
**Value**: High — enables multi-source expansion without downstream service changes
**Effort**: Medium (1-2 weeks)

#### Step 1: Deploy the backbone (Day 1-2)

- Provision the chosen messaging service (see Section 8 for recommendation)
- Create the three topics/streams: `raw-content`, `normalized-content`, `predictions`
- Add connection credentials to `.env` and per-service settings
- Write a thin Python wrapper: `shit/messaging/producer.py` and `shit/messaging/consumer.py`

#### Step 2: Add event publishing to the existing Harvester (Day 3)

- After the existing S3 write in `truth_social_s3_harvester.py`, publish a `raw_content_harvested` event
- The event contains the S3 key and source metadata — **not** the payload
- The harvester continues to work exactly as before; the event is an additive side effect
- If the event publish fails, log and continue — S3 is the source of truth, not the event

```python
# In truth_social_s3_harvester.py, after s3_data_lake.store_raw_data():
await event_producer.publish("raw-content", {
    "event_type": "raw_content_harvested",
    "source": "truth_social",
    "source_id": shitpost.id,
    "s3_key": s3_key,
    "timestamp": datetime.utcnow().isoformat()
})
```

#### Step 3: Migrate ETL from cron-poll to event-driven (Day 4-5)

- Add a consumer that listens to `raw-content` and calls the existing `S3Processor._process_single_s3_data()`
- **Keep the cron job as a fallback** — it catches anything the event consumer missed
- The cron job's S3 scan becomes a consistency check, not the primary trigger
- This is the "dual-write/dual-read" migration pattern: both mechanisms run simultaneously until trust is established

#### Step 4: Add event publishing after ETL writes (Day 5)

- After the ETL writes a row to the database, publish to `normalized-content`
- The Analyzer can optionally consume this instead of polling `analyzed=False`
- Again, keep the polling cron as a fallback during migration

#### Step 5: Add event publishing after Analyzer writes (Day 6)

- After storing a prediction, publish to `predictions`
- Market Data and Alerts can optionally consume this instead of polling

#### Step 6: Validate and cut over (Day 7-10)

- Run both mechanisms (cron polling + event consumption) for 1 week
- Compare: are events delivering work faster? Are any events being missed?
- Once confident, reduce cron frequency (from 5-min to 30-min or hourly) — the cron becomes a safety net, not the primary trigger
- Do **not** remove crons entirely. They remain as consistency checks.

### 6.3 Phase 5 (New): Second Source Onboarding

**Risk**: Medium
**Value**: High — validates the multi-source architecture
**Effort**: Medium (1-2 weeks)

This is where the event backbone pays off. Adding a second source (e.g., Twitter/X or congressional trading disclosures) should require:

1. A new harvester module (e.g., `twitter_harvester/`) that writes to S3 and publishes to `raw-content`
2. A new table (e.g., `twitter_posts`) with source-specific schema
3. A normalizer handler for the new source type
4. **Zero changes** to the Analyzer, Market Data, or Alert services

If adding the second source requires changes to downstream services, the architecture is wrong. This phase is the validation test.

### 6.4 Incremental Adoption: One Source at a Time

**The event backbone can be adopted incrementally.** This is critical — it is not all-or-nothing.

The migration path is:

1. **Phase 3, Step 2**: Truth Social harvester publishes events. ETL consumes events *and* continues cron polling. The system works identically to before, with events as an additive layer.
2. **Phase 5**: Second source publishes events. Its ETL handler is event-driven from day one (no legacy cron to migrate).
3. **Phase 5+N**: Each additional source is event-driven natively. No cron needed for new sources.
4. **Eventually**: Truth Social's cron fallback can be removed once the event path is proven reliable.

This means you **never have a big-bang migration**. The existing system continues working throughout. Events are additive, not replacement.

---

## 7. Cost Analysis

### 7.1 Current Baseline

From the original evaluation (Appendix B):

| Item | Cost |
|------|------|
| Railway services (pipeline + dashboard) | ~$8-10/month |
| Neon PostgreSQL (free tier) | $0 |
| S3 storage | ~$1-2/month |
| OpenAI API (GPT-4, ~70 analyses/day) | ~$3-5/month |
| **Total** | **~$12-17/month** |

### 7.2 Cost of Adding an Event Backbone

#### Option A: Upstash Kafka (Managed Serverless)

| Item | Cost |
|------|------|
| Free tier: 10,000 messages/day | $0 |
| At 6,000 events/day (5-10 sources): within free tier | $0 |
| At 20,000 events/day (growth scenario): ~$0.60/month | ~$1/month |
| **Event backbone total** | **$0-1/month** |

#### Option B: Redis Streams via Upstash

| Item | Cost |
|------|------|
| Upstash Redis free tier: 10,000 commands/day | $0 |
| At 6,000 events/day with 3 commands/event: 18,000/day | ~$1/month (pay-as-you-go) |
| Railway Redis plugin (alternative) | $5/month |
| **Event backbone total** | **$1-5/month** |

#### Option C: NATS on Railway

| Item | Cost |
|------|------|
| NATS container (~50MB RAM, minimal CPU) | ~$2-3/month |
| Or Synadia Cloud free tier | $0 |
| **Event backbone total** | **$0-3/month** |

#### Option D: AWS SQS/SNS

| Item | Cost |
|------|------|
| SQS free tier: 1M requests/month | $0 |
| SNS free tier: 1M publishes/month | $0 |
| At 6,000 events/day = ~180K/month: within free tier | $0 |
| **Event backbone total** | **$0** |

### 7.3 Cost of Multi-Source Expansion (Regardless of Event Backbone)

Adding 5-10 sources increases costs independently of the communication pattern:

| Item | Current | With 5-10 Sources |
|------|---------|-------------------|
| Railway services (more harvesters) | ~$8-10/month | ~$12-18/month |
| S3 storage (more raw data) | ~$1-2/month | ~$3-5/month |
| OpenAI API (more analyses) | ~$3-5/month | ~$15-40/month |
| Neon PostgreSQL (may exceed free tier) | $0 | $0-19/month |
| Event backbone | $0 | $0-5/month |
| **Total** | **~$12-17/month** | **~$30-87/month** |

**Key insight**: The event backbone is one of the cheapest components of the multi-source expansion. The dominant cost increase comes from LLM API calls (scaling linearly with analyzed content) and potentially outgrowing Neon's free tier. The communication infrastructure is a rounding error in the budget.

### 7.4 Cost-Benefit Summary

The event backbone adds $0-5/month and provides:

- Zero-touch downstream services when adding new sources
- Elimination of S3 polling scans (which get slower with more data)
- Natural handling of heterogeneous source frequencies
- Event replay capability for reprocessing

The cost of *not* having it is measured in developer time: each new source requires modifying downstream services, writing new polling queries, and managing more cron coordination.

---

## 8. Recommendation

### 8.1 Amended Decision on D2

**Original D2 (Section 9)**: Database polling. Each service checks for work on its cron schedule.

**Amended D2**: **Hybrid approach — event-driven fan-in for source ingestion, database polling retained for downstream services.**

Specifically:

- **Event-driven**: Harvesters → ETL → Normalizer → Analyzer (the multi-source fan-in path)
- **Database polling retained**: Market Data Service (poll for missing prices on cron), Outcome Calculator (poll for incomplete outcomes on cron), Alert Service (poll or event — either works)

This is not a wholesale rejection of the original recommendation. It's a scoped amendment: the fan-in point needs event-driven communication; everything else is fine with polling.

### 8.2 Recommended Technology: Redis Streams (Near-Term) or Upstash Kafka (If Growth Materializes)

**For the immediate 2-4 source expansion: Redis Streams via Upstash.**

Rationale:

1. **Lowest operational burden.** Redis is a known quantity with excellent Python support. `redis-py` is already a near-zero-learning-curve library. Upstash Redis is serverless — no container to manage.
2. **Sufficient semantics.** Consumer groups, persistent streams, and acknowledgment cover the fan-in pattern. The limitations (no partition-level parallelism, manual XTRIM for retention) don't matter at <10K events/day.
3. **Cheapest viable option with durability.** Free or ~$1/month. SQS is also free but lacks replay. PostgreSQL LISTEN/NOTIFY is free but incompatible with Neon.
4. **Railway-friendly.** Upstash is a Railway integration. No platform move required.
5. **Migration path to Kafka exists.** If you outgrow Redis Streams (>10 sources, >50K events/day, need log compaction or complex consumer groups), the abstraction layer (`shit/messaging/`) swaps the backend. The producer/consumer interfaces are the same shape.

**If volume exceeds 50K events/day or you need >7 days of replay: migrate to Upstash Kafka.**

Upstash Kafka is equally cheap at low volume, has superior replay/retention, and handles partition-level parallelism natively. The reason to start with Redis Streams instead of jumping directly to Kafka: Redis Streams has a simpler mental model and the `redis-py` library is more Pythonic than `confluent-kafka`. For a solo developer, the learning curve matters.

**Why not NATS?** NATS scored highest in the weighted comparison (Section 4.7) on paper, but the Python ecosystem is thinner. `nats-py` has ~1,200 GitHub stars vs. `redis-py` at ~12,000+. For a solo Python developer, community support and documentation quality tip the scale. NATS is the right answer for a Go shop; Redis Streams is the right answer for a Python shop.

### 8.3 Agreement and Disagreement with Original Evaluation

| Original Position | This Addendum | Verdict |
|-------------------|---------------|---------|
| Section 4.1: "Use the PostgreSQL database itself as the integration point between services" | **Partially disagree** for multi-source. Agree for downstream services. Disagree for the N-source fan-in point. | Amend |
| Section 4.2: "~3 posts/hour doesn't justify event infrastructure" | **Agree for single source. Disagree given multi-source.** Volume increases 10-100x with new sources, and the issue isn't just volume — it's the coupling of N producers to shared consumers. | Amend |
| Section 4.4: "Upgrade to event-driven only if post volume exceeds ~500/day" | **Agree on the threshold, disagree on the trigger.** Even at <500/day, 5+ heterogeneous sources with different frequencies and schemas benefit from a shared event backbone. Volume isn't the only reason — fan-in topology is. | Amend |
| Section 7.5: "S3 is correctly positioned as the immutable source of truth" | **Strongly agree.** Events carry S3 references, not payloads. S3 remains canonical. | Reinforce |
| Section 10.1: "Don't introduce a message queue" | **Disagree given multi-source context.** The original rationale was correct for a single source. With N sources, the event backbone is the cheapest, simplest way to decouple producers from consumers. The cost objection ($5-15/month for Redis) is outdated — serverless options are $0-1/month. | Amend |
| Section 3.3: "Each pipeline stage checks its own preconditions" | **Agree — and the event backbone preserves this.** Services still check preconditions; they just get notified faster about when to check. Crons remain as fallback consistency checks. | Reinforce |
| Section 8: Phased migration plan | **Agree on Phases 0-2. Amend Phase 3+ to include event backbone.** | Amend |
| Section 5.5: "The shit/ package stays as a shared library" | **Agree, and extend it.** Add `shit/messaging/` as the shared event producer/consumer abstraction. | Extend |

### 8.4 What to Do Right Now

1. **Execute Phases 0-2 of the original evaluation immediately.** They are prerequisite to any event backbone work and have standalone value.
2. **During Phase 2, add `shit/messaging/` as a thin abstraction layer** with `publish(topic, event)` and `consume(topic, group, handler)` interfaces. Implement the Redis Streams backend.
3. **In Phase 3, wire the event backbone into the Truth Social harvester** as an additive side effect. Keep cron polling as fallback.
4. **When you're ready to add source #2**, build it event-native from day one. This is the validation that the architecture works.

Do not build the event backbone before the independent services exist. The original evaluation's Phase 0-2 sequence is correct — decouple first, then add the communication layer.

---

## 9. Amended Decision Log

### D2 (Amended): Database Polling vs. Event-Driven

**Original Decision**: Database polling for all service communication.

**Amended Decision**: Hybrid — event-driven for source ingestion fan-in (Harvesters → ETL → Normalizer → Analyzer), database polling retained for downstream services (Market Data, Outcomes, Alerts).

**Rationale**: Multi-source expansion (5-10 sources) changes the topology from 1-producer-to-1-consumer to N-producers-to-shared-consumers. Database polling requires every consumer to know about every producer (query N tables or build polymorphic queries). An event backbone decouples this — new sources publish events; consumers are unchanged.

**Technology**: Redis Streams via Upstash (near-term), with migration path to Upstash Kafka if volume or replay needs grow.

**Cost impact**: $0-1/month (serverless Redis Streams at <10K events/day).

**Tradeoff**: One new infrastructure dependency (managed, serverless). Mitigated by keeping cron polling as a fallback during and after migration.

**Revisit when**: Volume exceeds 50K events/day, need >7 days of event replay, or need partition-level consumer parallelism → migrate to Upstash Kafka.

### D9 (New): S3 vs. Event Log as Source of Truth

**Decision**: S3 remains the immutable source of truth. The event backbone is a notification mechanism, not a data store.

**Rationale**: S3 is cheaper, simpler, and already works. Events carry references to S3 objects. Event retention is short (hours to days). S3 retention is permanent. Reprocessing rebuilds from S3, not from the event log.

**Tradeoff**: Events must include the S3 key so consumers can fetch the full payload. Slightly more latency than carrying the payload in the event. Acceptable at this scale.

### D10 (New): Per-Source Tables vs. Polymorphic Table

**Decision**: Per-source tables with a shared Normalizer that produces a common `normalized_content` view.

**Rationale**: Each source has a different raw schema (Truth Social's engagement metrics differ from SEC filing fields). Per-source tables preserve type safety and source-specific queries. The Normalizer maps to a common schema for the Analyzer.

**Tradeoff**: More tables. Mitigated by the Normalizer providing a single entry point for downstream services.

### D11 (New): Event Backbone Technology

**Decision**: Redis Streams via Upstash (near-term). Upstash Kafka as growth option.

**Rationale**: Lowest learning curve for a solo Python developer. Best Python ecosystem support. Cheapest option with durability and replay. Railway-native via Upstash integration. Migration path to Kafka exists via the `shit/messaging/` abstraction layer.

**Tradeoff**: Redis Streams lacks native partitioning and log compaction. These features aren't needed at <10K events/day with <10 sources. If they become needed, the Kafka migration path is proven.

---

*This addendum is based on the original Architecture Evaluation dated 2026-02-09 and reflects planned expansion to 5-10 data sources. All section references (e.g., "Section 4.1") refer to the parent document unless otherwise noted.*
