# 05: Multi-LLM Ensemble Analysis

**Feature**: Run each post through GPT-4, Claude, and Grok in parallel. Compare outputs, surface consensus and disagreements, use consensus for higher confidence.

**Status**: COMPLETE  
**Started**: 2026-04-11  
**Completed**: 2026-04-12  
**PR**: #138  
**Priority**: High  
**Estimated Effort**: 3-4 sessions (actual: 1 session)

### Challenge Round Decisions (2026-04-11)

1. **Extend ProviderComparator** — Add `ConsensusBuilder` to `compare_providers.py` rather than creating a new `EnsembleAnalyzer` class. One parallel-execution path.
2. **Full scope** — Backend + alerts + frontend display (all 4 phases).
3. **Raw mean confidence** — No agreement bonus/penalty. Store raw mean of provider confidences. Agreement metrics in `ensemble_metadata` for display only. Calibration (Feature 06) refits naturally.
4. **Both alert paths** — `alert_engine.py` and `event_consumer.py` both pass `ensemble_metadata` to `format_telegram_alert()`.  

---

## Overview

Today, every post is analyzed by a single LLM provider (configured via `LLM_PROVIDER` in settings). This creates single-model risk: one provider's hallucinations, biases, or outages directly become our prediction quality. The ensemble feature runs the same post through 2-3 providers simultaneously, merges their outputs into a consensus prediction, and stores both the individual model responses and the merged result.

The infrastructure is already partially in place:
- `shit/llm/provider_config.py` defines all three providers with model configs and cost metadata.
- `shit/llm/compare_providers.py` has `ProviderComparator` with parallel execution via `asyncio.gather` and Jaccard agreement metrics.
- `shit/llm/llm_client.py` supports OpenAI, Anthropic, and Grok (OpenAI-compatible SDK) via a unified `LLMClient` interface.

What's missing: integrating the comparator into the production analysis pipeline, building a consensus merge function that produces a single canonical prediction, storing individual model outputs, and making ensemble mode configurable.

---

## Motivation

1. **Single-model risk**: GPT-4 has known biases around certain topics. Claude and Grok have different strengths (Claude for structured analysis, Grok for social media context). One model's blind spot is another's strength.
2. **Confidence calibration**: When 3/3 models agree on "bearish TSLA at 0.85 confidence," that signal is qualitatively different from a single model's 0.85. Consensus gives us a natural confidence multiplier.
3. **Provider outage resilience**: If one API is down or slow, the other two still produce a result. The system degrades gracefully rather than failing.
4. **A/B testing foundation**: Storing per-model outputs creates a dataset to evaluate which provider is most accurate over time, enabling informed model selection.

---

## Architecture

### Execution Flow

```
Post arrives for analysis
    |
    v
BypassService.should_bypass_post()  (unchanged)
    |
    v (not bypassed)
EnsembleAnalyzer.analyze(enhanced_content)
    |
    +---> asyncio.gather(
    |       LLMClient("openai", "gpt-4o").analyze(content),
    |       LLMClient("anthropic", "claude-sonnet-4-20250514").analyze(content),
    |       LLMClient("grok", "grok-2").analyze(content),
    |       return_exceptions=True
    |     )
    |
    v
Individual results (0-3 successful)
    |
    v
ConsensusBuilder.merge(results) -> ConsensusResult
    |
    v
Store prediction (consensus fields) + ensemble_results (individual outputs)
    |
    v
Emit PREDICTION_CREATED event (unchanged downstream)
```

### Timeout and Partial Results

Each provider call gets a 30-second timeout (already configured in `LLMClient._call_llm`). If a provider times out or errors:

- The failed result is recorded with `success=False` and the error message.
- Consensus is built from the remaining successful results.
- Minimum 1 successful result required to produce a prediction. With 0 successes, the post is marked `analysis_status='error'`.

```python
# In EnsembleAnalyzer
async def analyze_ensemble(self, enhanced_content: str) -> EnsembleResult:
    """Run content through all configured providers in parallel."""
    tasks = []
    for provider_id, client in self.clients.items():
        tasks.append(self._analyze_with_timeout(provider_id, client, enhanced_content))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = []
    failed = []
    for result in results:
        if isinstance(result, Exception):
            failed.append(ProviderResult(success=False, error=str(result)))
        elif result.success:
            successful.append(result)
        else:
            failed.append(result)

    if not successful:
        raise EnsembleError("All providers failed", failed_results=failed)

    consensus = self.consensus_builder.merge(successful)
    return EnsembleResult(
        consensus=consensus,
        individual_results=successful + failed,
        providers_queried=len(tasks),
        providers_succeeded=len(successful),
    )
```

### Provider Initialization

Reuse the existing `ProviderComparator.initialize()` pattern from `shit/llm/compare_providers.py`. It iterates providers, checks for API keys, and initializes only those with valid credentials.

```python
class EnsembleAnalyzer:
    """Production ensemble analyzer integrated with ShitpostAnalyzer."""

    def __init__(self, provider_ids: list[str] | None = None):
        self.provider_ids = provider_ids or settings.ENSEMBLE_PROVIDERS.split(",")
        self.clients: dict[str, LLMClient] = {}
        self.consensus_builder = ConsensusBuilder()

    async def initialize(self) -> list[str]:
        """Initialize LLM clients. Returns list of successfully initialized provider IDs."""
        initialized = []
        for provider_id in self.provider_ids:
            try:
                provider_config = get_provider(provider_id)
                api_key = getattr(settings, provider_config.api_key_env_var, None)
                if not api_key:
                    logger.warning(f"Skipping {provider_id}: no API key")
                    continue

                model_config = get_recommended_model(provider_id)
                client = LLMClient(
                    provider=provider_id,
                    model=model_config.model_id,
                    api_key=api_key,
                    base_url=provider_config.base_url,
                )
                # Skip connection test for speed -- first real call will validate
                self.clients[provider_id] = client
                initialized.append(provider_id)
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_id}: {e}")

        if not initialized:
            raise RuntimeError("No LLM providers available for ensemble")
        return initialized
```

---

## Consensus Algorithm

### Input Normalization

Each provider returns a dict with `assets`, `market_impact`, `confidence`, `thesis`. Before merging, normalize:

1. **Asset normalization**: Uppercase all tickers, run through `TickerValidator.validate_symbols()` to resolve aliases (META not FACEBOOK, etc.).
2. **Sentiment normalization**: Map to canonical set: `"bullish"`, `"bearish"`, `"neutral"`. Strip any provider-specific labels.
3. **Confidence clamping**: Clamp to [0.0, 1.0].

### Voting Scheme

```python
@dataclass
class ConsensusResult:
    """Merged consensus from multiple provider analyses."""
    assets: list[str]                    # Union of all detected assets
    market_impact: dict[str, str]        # Consensus sentiment per asset
    confidence: float                    # Aggregated confidence
    thesis: str                          # Best thesis (highest individual confidence)
    agreement_level: str                 # "unanimous", "majority", "split", "single"
    asset_agreement: float               # Jaccard similarity of asset sets
    sentiment_agreement: float           # Fraction of asset-sentiments that agree
    confidence_spread: float             # max - min individual confidence
    dissenting_views: list[dict]         # Where models disagreed
```

**Asset voting**: Union of all detected assets. An asset appears in the consensus if detected by >= 1 provider. The confidence for that asset is weighted by how many providers detected it.

**Sentiment voting (per asset)**:

```python
def _vote_sentiment(self, asset: str, results: list[ProviderResult]) -> str:
    """Majority vote on sentiment for a single asset."""
    votes = []
    for result in results:
        if asset in result.market_impact:
            votes.append(result.market_impact[asset])

    if not votes:
        return "neutral"

    # Count votes
    from collections import Counter
    counts = Counter(votes)
    winner, winner_count = counts.most_common(1)[0]

    # Majority = more than half
    if winner_count > len(votes) / 2:
        return winner
    # Tie between bullish/bearish = neutral (conservative)
    return "neutral"
```

**Confidence aggregation**:

```python
def _aggregate_confidence(self, results: list[ProviderResult]) -> float:
    """Weighted confidence based on agreement level."""
    confidences = [r.confidence for r in results if r.success]
    base_confidence = sum(confidences) / len(confidences)  # Mean

    # Agreement bonus/penalty
    n_providers = len(confidences)
    if n_providers >= 3:
        spread = max(confidences) - min(confidences)
        if spread < 0.1:  # Strong agreement
            return min(base_confidence * 1.1, 1.0)
        elif spread > 0.3:  # Strong disagreement
            return base_confidence * 0.85
    return base_confidence
```

**Agreement level classification**:

| Condition | Level | Description |
|-----------|-------|-------------|
| All providers agree on all asset sentiments | `"unanimous"` | 3/3 agree: bearish on SPY |
| > 50% agree on all assets | `"majority"` | 2/3 agree: bullish, 1 neutral |
| No majority on any asset | `"split"` | GPT-4 bearish, Claude neutral, Grok bullish |
| Only 1 provider succeeded | `"single"` | Fallback to single-model behavior |

### Disagreement Handling

When models disagree, capture the dissent explicitly:

```python
dissenting_views = []
for asset in consensus_assets:
    sentiments_by_provider = {}
    for result in successful_results:
        if asset in result.market_impact:
            sentiments_by_provider[result.provider] = result.market_impact[asset]
    if len(set(sentiments_by_provider.values())) > 1:
        dissenting_views.append({
            "asset": asset,
            "sentiments": sentiments_by_provider,
            "consensus": consensus_market_impact[asset],
        })
```

---

## Storage Schema

### Option A: JSON Column on Predictions (Recommended)

Add two columns to the existing `predictions` table:

```python
# In shitvault/shitpost_models.py - Prediction class
ensemble_results = Column(JSON, nullable=True)  # Individual model outputs
ensemble_metadata = Column(JSON, nullable=True)  # Agreement metrics
```

**`ensemble_results`** stores the per-model outputs:

```json
{
  "providers_queried": 3,
  "providers_succeeded": 3,
  "results": [
    {
      "provider": "openai",
      "model": "gpt-4o",
      "assets": ["TSLA", "F"],
      "market_impact": {"TSLA": "bearish", "F": "neutral"},
      "confidence": 0.85,
      "thesis": "Direct negative mention of Tesla...",
      "latency_ms": 2340,
      "success": true
    },
    {
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "assets": ["TSLA"],
      "market_impact": {"TSLA": "bearish"},
      "confidence": 0.78,
      "thesis": "Post signals negative sentiment toward EV market...",
      "latency_ms": 1890,
      "success": true
    },
    {
      "provider": "grok",
      "model": "grok-2",
      "assets": ["TSLA", "F", "GM"],
      "market_impact": {"TSLA": "bearish", "F": "bearish", "GM": "bearish"},
      "confidence": 0.92,
      "thesis": "Strong anti-EV rhetoric will pressure all auto stocks...",
      "latency_ms": 3100,
      "success": true
    }
  ]
}
```

**`ensemble_metadata`** stores agreement metrics:

```json
{
  "agreement_level": "majority",
  "asset_agreement": 0.33,
  "sentiment_agreement": 0.83,
  "confidence_spread": 0.14,
  "dissenting_views": [
    {
      "asset": "F",
      "sentiments": {"openai": "neutral", "grok": "bearish"},
      "consensus": "neutral"
    }
  ]
}
```

The top-level `predictions` fields (`assets`, `market_impact`, `confidence`, `thesis`) are set from the consensus result, so all existing downstream consumers (notifications, outcomes, frontend) work unchanged.

### Migration SQL

```sql
ALTER TABLE predictions ADD COLUMN ensemble_results JSONB;
ALTER TABLE predictions ADD COLUMN ensemble_metadata JSONB;

COMMENT ON COLUMN predictions.ensemble_results IS 'Per-model outputs from ensemble analysis (null for single-model)';
COMMENT ON COLUMN predictions.ensemble_metadata IS 'Agreement metrics from ensemble analysis (null for single-model)';
```

### Why Not a Separate Table?

A separate `ensemble_model_results` table would be more normalized but adds complexity for a feature where:
- Results are always read together (never queried individually by model).
- Volume is bounded (max 3 rows per prediction).
- JSON storage in PostgreSQL is well-indexed and queryable.

If per-model accuracy analysis later needs heavy querying, we can extract into a materialized view.

---

## Cost Analysis

### Per-Post Cost (Estimated)

Using recommended models from `provider_config.py`:

| Provider | Model | Input (1M tok) | Output (1M tok) | Est. per post |
|----------|-------|----------------|------------------|---------------|
| OpenAI | gpt-4o | $2.50 | $10.00 | ~$0.004 |
| Anthropic | claude-sonnet-4-20250514 | $3.00 | $15.00 | ~$0.006 |
| xAI | grok-2 | $2.00 | $10.00 | ~$0.004 |
| **Total** | | | | **~$0.014** |

Estimated per-post: ~500 input tokens, ~300 output tokens per provider.

### Monthly Cost Projection

| Scenario | Posts/day | Ensemble cost/month |
|----------|-----------|---------------------|
| Current volume | ~15 analyzed/day | ~$6.30/month |
| High volume | ~50 analyzed/day | ~$21.00/month |
| Spike event | 200 in one day | ~$2.80 one-time |

### Cost Controls

**When to ensemble vs. single-model:**

```python
# In settings
ENSEMBLE_ENABLED: bool = Field(default=True)
ENSEMBLE_PROVIDERS: str = Field(default="openai,anthropic,grok")
ENSEMBLE_MIN_PROVIDERS: int = Field(default=2)  # Minimum for valid ensemble
ENSEMBLE_CONFIDENCE_THRESHOLD: float = Field(default=0.0)  # Ensemble all posts by default

# Future: selective ensemble
# Only ensemble posts with high engagement or specific keywords
ENSEMBLE_ENGAGEMENT_THRESHOLD: int = Field(default=0)  # 0 = ensemble everything
```

**Budget circuit breaker**: Track daily LLM spend. If spend exceeds threshold, fall back to single-model (cheapest available). This is a future enhancement, not part of initial implementation.

---

## Integration with ShitpostAnalyzer

### Modified Analysis Flow

The key integration point is `ShitpostAnalyzer._analyze_shitpost()` in `shitpost_ai/shitpost_analyzer.py`. The change is minimal:

```python
# Before (single model):
analysis = await self.llm_client.analyze(enhanced_content)

# After (ensemble):
if self.ensemble_enabled:
    ensemble_result = await self.ensemble_analyzer.analyze_ensemble(enhanced_content)
    analysis = ensemble_result.consensus.to_analysis_dict()
    analysis["ensemble_results"] = ensemble_result.to_storage_dict()
    analysis["ensemble_metadata"] = ensemble_result.to_metadata_dict()
else:
    analysis = await self.llm_client.analyze(enhanced_content)
```

The `ShitpostAnalyzer.__init__` gains an `EnsembleAnalyzer` instance (initialized alongside `LLMClient`). The `initialize()` method initializes ensemble providers in parallel.

### Backward Compatibility

- When ensemble is disabled (`ENSEMBLE_ENABLED=False`), behavior is identical to today.
- `ensemble_results` and `ensemble_metadata` columns are nullable -- existing predictions have `NULL`.
- All downstream consumers (notifications, market data, outcomes) use the consensus values stored in the existing top-level prediction fields. No changes needed.

---

## Provider Normalization

### Response Format Differences

Each provider may return slightly different JSON structures. The existing `LLMClient.analyze()` already normalizes to a common schema:

```python
{
    "assets": list[str],
    "market_impact": dict[str, str],
    "confidence": float,
    "thesis": str,
    "meets_threshold": bool,
    "analysis_quality": str,
    "llm_provider": str,
    "llm_model": str,
}
```

This normalization happens inside `LLMClient._parse_analysis_response()` and `LLMClient.analyze()` -- the ensemble layer receives already-normalized dicts.

### Edge Cases

- **Grok returns extra assets**: Grok (trained on X/Truth Social data) may detect more assets. The union approach captures these.
- **Claude returns structured but conservative**: Claude tends to return fewer assets with higher confidence. The consensus algorithm accounts for this.
- **Provider returns invalid JSON**: `LLMClient._parse_manual_response()` is the fallback. Ensemble treats manual-parsed results the same as JSON-parsed results, but the low confidence (0.5 default) naturally down-weights them in consensus.

---

## Alert Format

### Telegram Message with Consensus

Current format (from `notifications/telegram_sender.py`):

```
[emoji] SHITPOST ALPHA ALERT
Sentiment: BEARISH (85% confidence)
Assets: TSLA, F, GM
```

**Enhanced with ensemble data:**

```
[emoji] SHITPOST ALPHA ALERT

Sentiment: BEARISH (85% confidence)
Assets: TSLA, F, GM
[3/3 models agree] | Confidence range: 78-92%

Post:
"Tesla is destroying the auto industry..."

Thesis:
Strong negative EV sentiment expected to pressure auto sector

[Note: GPT-4 neutral on F, Claude/Grok bearish]
```

Implementation: Add an optional `_format_ensemble_section()` to `format_telegram_alert()`:

```python
def _format_ensemble_section(alert: dict) -> str:
    """Format ensemble metadata for alert message."""
    metadata = alert.get("ensemble_metadata")
    if not metadata:
        return ""

    level = metadata.get("agreement_level", "single")
    n_succeeded = metadata.get("providers_succeeded", 1)
    n_queried = metadata.get("providers_queried", 1)

    if level == "unanimous":
        return escape_markdown(f"\n[{n_succeeded}/{n_queried} models agree]")
    elif level == "majority":
        return escape_markdown(f"\n[{n_succeeded}/{n_queried} models, majority agree]")
    elif level == "split":
        return escape_markdown(f"\n[{n_succeeded}/{n_queried} models, split decision]")
    return ""
```

---

## Frontend Display

### Model Comparison View

Add an expandable section to the existing ShitpostCard component showing per-model results:

```
+------------------------------------------------------+
|  Model Comparison                              [v]   |
+------------------------------------------------------+
|  GPT-4o          | TSLA bearish, F neutral  | 85%    |
|  Claude Sonnet 4 | TSLA bearish             | 78%    |
|  Grok 2          | TSLA,F,GM all bearish    | 92%    |
+------------------------------------------------------+
|  Consensus: MAJORITY (3/3 responded)                 |
|  Asset Agreement: 33% | Sentiment Agreement: 83%    |
+------------------------------------------------------+
```

### API Changes

Add `ensemble_results` and `ensemble_metadata` to the `FeedResponse` prediction schema:

```python
# api/schemas/feed.py
class PredictionResponse(BaseModel):
    # ... existing fields ...
    ensemble_results: Optional[dict] = None
    ensemble_metadata: Optional[dict] = None
```

The `api/services/feed_service.py` already passes through prediction data -- no query changes needed since these are columns on the predictions table.

---

## Configuration

### New Settings (in `shit/config/shitpost_settings.py`)

```python
# Ensemble Configuration
ENSEMBLE_ENABLED: bool = Field(default=False)  # Opt-in initially
ENSEMBLE_PROVIDERS: str = Field(default="openai,anthropic,grok")
ENSEMBLE_MIN_PROVIDERS: int = Field(default=2)
ENSEMBLE_TIMEOUT_SECONDS: float = Field(default=30.0)
```

### Railway Environment Variables

```
ENSEMBLE_ENABLED=true
ENSEMBLE_PROVIDERS=openai,anthropic,grok
ANTHROPIC_API_KEY=sk-ant-xxx
XAI_API_KEY=xai-xxx
OPENAI_API_KEY=sk-xxx
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `shit/llm/ensemble.py` | **NEW** - `EnsembleAnalyzer`, `ConsensusBuilder`, dataclasses |
| `shit/llm/__init__.py` | Export `EnsembleAnalyzer` |
| `shit/config/shitpost_settings.py` | Add `ENSEMBLE_*` settings |
| `shitpost_ai/shitpost_analyzer.py` | Integrate `EnsembleAnalyzer` in `_analyze_shitpost()` |
| `shitvault/shitpost_models.py` | Add `ensemble_results`, `ensemble_metadata` columns |
| `notifications/telegram_sender.py` | Add `_format_ensemble_section()` |
| `api/schemas/feed.py` | Add ensemble fields to response |
| `shit_tests/shit/llm/test_ensemble.py` | **NEW** - Unit tests |
| `shit_tests/shitpost_ai/test_analyzer_ensemble.py` | **NEW** - Integration tests |

---

## Testing Strategy

### Unit Tests (`shit_tests/shit/llm/test_ensemble.py`)

1. **ConsensusBuilder tests**:
   - `test_unanimous_agreement`: 3 identical results -> unanimous
   - `test_majority_agreement`: 2/3 agree -> majority with correct sentiment
   - `test_split_decision`: All different -> neutral fallback
   - `test_single_provider`: Only 1 success -> single mode
   - `test_confidence_aggregation_agreement_bonus`: Tight spread boosts confidence
   - `test_confidence_aggregation_disagreement_penalty`: Wide spread reduces confidence
   - `test_asset_union`: All provider assets included in consensus
   - `test_dissenting_views_captured`: Disagreements recorded correctly
   - `test_empty_assets_all_agree`: All providers say no financial relevance

2. **EnsembleAnalyzer tests**:
   - `test_all_providers_succeed`: Happy path
   - `test_one_provider_fails`: Graceful degradation
   - `test_all_providers_fail`: Raises EnsembleError
   - `test_timeout_handling`: Slow provider times out, others succeed
   - `test_ensemble_disabled`: Falls through to single-model

3. **Provider normalization**:
   - `test_grok_extra_assets_included`: Grok sees more assets
   - `test_manual_parse_fallback_low_weight`: Manual-parsed result contributes low confidence

### Integration Tests (`shit_tests/shitpost_ai/test_analyzer_ensemble.py`)

1. `test_analyze_shitpost_ensemble_mode`: Mock all 3 providers, verify consensus stored
2. `test_analyze_shitpost_ensemble_fallback_to_single`: When `ENSEMBLE_ENABLED=False`
3. `test_ensemble_results_stored_in_prediction`: Verify JSON columns populated
4. `test_event_emission_uses_consensus`: PREDICTION_CREATED event has consensus values

### Mock Strategy

All tests mock the actual LLM API calls. Use `unittest.mock.AsyncMock` for `LLMClient.analyze()`:

```python
@pytest.fixture
def mock_openai_result():
    return {
        "assets": ["TSLA"],
        "market_impact": {"TSLA": "bearish"},
        "confidence": 0.85,
        "thesis": "Negative Tesla sentiment",
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
    }
```

---

## Open Questions

1. **Should ensemble be the default?** Initially `ENSEMBLE_ENABLED=False` to avoid 3x cost surprise. Switch to default-on after validating accuracy improvement.

2. **Should we weight providers differently?** If historical data shows GPT-4o is 20% more accurate than Grok, should its vote count more? This could be added later using calibration data from Feature 06.

3. **Per-asset vs. per-prediction ensemble?** Current design ensembles the entire prediction. An alternative is per-asset voting where we only consult 3 models when confidence is borderline. Deferred for simplicity.

4. **Should the thesis be a merge of all three, or the best single thesis?** Current design picks the thesis from the highest-confidence individual result. Alternative: use a 4th LLM call to synthesize all three theses. Rejected for cost reasons.

5. **Rate limiting across providers**: If we're analyzing 15 posts/day, that's 45 LLM calls. Well within all providers' rate limits (60 RPM each). Not a concern at current volume, but monitor if volume increases.

6. **Interaction with confidence calibration (Feature 06)**: Calibration curves should be built on consensus confidence, not individual model confidence. Ensure the calibration pipeline reads from the top-level `predictions.confidence` field (which will be consensus when ensemble is enabled).

---

## Implementation Order

1. **Phase 1**: Create `shit/llm/ensemble.py` with `ConsensusBuilder` and `EnsembleAnalyzer`. Full unit tests.
2. **Phase 2**: Add schema columns, settings, and integrate into `ShitpostAnalyzer`.
3. **Phase 3**: Update alert formatting and frontend display.
4. **Phase 4**: Deploy with `ENSEMBLE_ENABLED=false`, test in production with manual dry runs, then flip to `true`.
