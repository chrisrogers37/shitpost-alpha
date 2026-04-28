# Play 1: The Learning Machine

**Status**: Planning
**Created**: 2026-04-27

The mission's core flywheel — a system that genuinely gets smarter over time by feeding prediction accuracy back into analysis.

## North Star

Every prediction that resolves makes the next prediction more accurate.

## Components

### F7: Self-Learning Prompt Enrichment

Inject a factual accuracy summary into the LLM prompt before each analysis call. The prompt's `context` parameter already accepts an optional dict — add a `self_assessment` key.

**New module:** `shit/llm/accuracy_context.py`

`get_accuracy_context(llm_provider: str, llm_model: str) -> dict` queries the last 30 days of `prediction_outcomes` joined to `predictions` and returns:

```python
{
    "overall_accuracy": 0.58,
    "total_evaluated": 142,
    "bullish_accuracy": 0.67,
    "bearish_accuracy": 0.45,
    "by_sector": {"Technology": 0.72, "Energy": 0.38, ...},
    "crowd_accuracy": 0.61,
    "crowd_agreement_rate": 0.73,
}
```

Provider-specific — GPT-5.4's track record differs from Claude's. Filters by `predictions.llm_provider` and `predictions.llm_model`. Falls back to aggregate stats if a specific model has <20 evaluated predictions.

**Prompt injection format** (factual summary, not directive):
```
SELF-ASSESSMENT (last 30 days):
Overall accuracy: 58% (142 predictions evaluated)
Bullish calls: 67% accurate | Bearish calls: 45% accurate
Top sector: Technology (72%) | Weakest: Energy (38%)
Crowd consensus accuracy: 61% | Agreement with your calls: 73%
```

**Key files:**
- `shit/llm/prompts.py` — `get_analysis_prompt()` already accepts `context: Optional[Dict]` (line 41). Inject self-assessment into the context string.
- `shitpost_ai/shitpost_analyzer.py` — Call `get_accuracy_context()` before LLM call, pass into prompt context.
- `shit/market_data/outcome_calculator.py` — Has `get_accuracy_stats()` (line 663) but needs per-provider/per-sector extension.

### F1: Conviction Vote Context in Prompts

Inject crowd sentiment data from Telegram conviction votes into the same prompt context.

**Data source:** `notifications/vote_db.py`
- `get_llm_vs_crowd_stats()` (line 235) returns `{total_evaluated, llm_accuracy, crowd_accuracy, agreement_rate}`
- `get_vote_tally(prediction_id)` (line 88) returns `{bull, bear, skip, total}` — but this is per-prediction, not useful for general context

**Injection:** Include crowd accuracy stats in the self-assessment block. No separate prompt section needed — crowd data is part of the accuracy context.

### F10: Accuracy-Weighted Model Selection

Replace equal-weight majority voting in `ConsensusBuilder.merge()` with accuracy-weighted voting.

**Current state:** `shit/llm/compare_providers.py`
- `ConsensusBuilder.merge()` (line 115) uses `Counter.most_common()` — pure majority vote
- `_vote_sentiment()` (line 188) counts votes equally regardless of model track record

**Proposed change:**
- Before ensemble analysis, query per-model accuracy stats (from F7's `get_accuracy_context()`)
- Weight each model's vote by its recent accuracy for the relevant sector/asset type
- `_vote_sentiment()` becomes weighted: a model with 72% accuracy gets more influence than one with 45%
- Fall back to equal-weight if accuracy data is insufficient

**Key data:** `predictions.llm_provider` + `prediction_outcomes.correct_t7` + `ticker_registry.sector` — all exist, just need a JOIN query.

### F3: Calibration Refit Cron

**DONE** — Railway `calibration-refit` service deployed (PR #141, Sunday midnight UTC).

## Architecture

```
Prediction resolves (T+7)
    → outcome_calculator stores correctness
    → calibration curves refit weekly
    → next analysis call:
        1. get_accuracy_context(provider, model)  ← NEW
        2. inject into prompt context              ← NEW  
        3. weight ensemble votes by accuracy       ← NEW
        4. calibrate output confidence             ← EXISTING
    → prediction stored with richer context
    → cycle repeats
```

## Dependencies

- `prediction_outcomes` table must have sufficient data (>20 evaluated per model)
- Calibration curves must be fresh (weekly refit handles this)
- Conviction votes need enough participation for crowd stats to be meaningful

## Open Questions

- Should accuracy context be cached (e.g., recomputed hourly) or queried live per analysis? Live is simpler but adds ~100ms per call.
- Should per-sector accuracy be limited to the sectors relevant to the current post, or always include all sectors?
- How should we handle the cold-start problem for new models added to the ensemble?

## Effort Estimate

| Component | Files | Effort |
|-----------|-------|--------|
| F7: Accuracy context module | 3 files (new module + prompt + analyzer) | Medium |
| F1: Crowd stats in prompt | 1 file (accuracy_context.py) | Low |
| F10: Weighted ensemble | 2 files (compare_providers.py + accuracy_context.py) | Medium |
| Tests | 3-4 test files | Medium |
| **Total** | ~8 files | **1-2 sessions** |
