# WS11 — LLM Robustness (ensemble, JSON fallback, rate limiting, injection)

**Priority**: MEDIUM
**Type**: bug / security
**Findings**: H15, H16, M6, M7, M8
**Primary files**: `shit/llm/compare_providers.py`, `shit/llm/llm_client.py`, `shit/llm/prompts.py`, `shit/llm/embeddings.py`, `shit/utils/error_handling.py`, `shitpost_ai/shitpost_analyzer.py`

---

## Findings

### H16 — Manual JSON fallback stores junk predictions
`llm_client.py:238-259` `_parse_manual_response()` invents assets from words containing "inc"/"corp" and sets a default confidence of 0.5 when JSON parsing fails. A malformed model response becomes a plausible-looking but fabricated prediction stored in the DB.

**Fix**: On JSON parse failure, fail the analysis (write `analysis_status='error'` per WS06) instead of fabricating assets/confidence. At most, retry with a stricter/JSON-mode prompt.

### H15 — `analyze_ensemble()` drops `prompt_func`/`kwargs`
`compare_providers.py:358-376,441-449`: the signature accepts `prompt_func` and `**kwargs`, but `_analyze_with_provider()` calls `client.analyze(content)` only. Ensembles silently use the default prompt.

**Fix**: Thread `prompt_func`/`kwargs` through to each provider call, or remove the parameters if unsupported.

### M6 — Prompt-injection surface
`shitpost_ai/shitpost_analyzer.py:707` concatenates post text into the prompt with no delimiter hardening (`shit/llm/prompts.py`). Post content can steer the model.

**Fix**: Wrap user content in clear delimiters / a dedicated message role, add an instruction that content between delimiters is data not instructions, and (optionally) sanitize obvious injection markers.

### M7 — No LLM rate limiting / backoff
`provider_config.py` defines `rate_limit_rpm` but it’s unused. Single calls have only a 30s timeout (`llm_client.py:166-199`); ensembles fire all providers concurrently via `asyncio.gather` (`compare_providers.py:374-378`) with no throttling or 429 backoff.

**Fix**: Enforce `rate_limit_rpm` (token-bucket/semaphore) and add exponential backoff on rate-limit/5xx.

### M8 — Dead resilience utilities + sync-context bug
`error_handling.py:186-201` defines global `llm_circuit_breaker`/`llm_rate_limiter` that nothing uses; `CircuitBreaker._on_failure`/`_should_attempt_reset` (`:145,156`) call `asyncio.get_running_loop().time()`, raising `RuntimeError` if used from sync code.

**Fix**: Either wire the circuit breaker/rate limiter into `LLMClient` (satisfying M7) or delete the dead globals; make `CircuitBreaker` time source not depend on a running loop.

### Minor
- `EmbeddingClient` uses a sync `OpenAI()` client (`embeddings.py:8-24`) and passes the key with no guard; blocks the loop if called from async without `to_thread`.
- Duplicate agreement logic in `compare_providers.py` (`_compute_*_agreement` vs `_calculate_agreement`).

## Acceptance criteria

- [ ] JSON-parse failures do not produce fabricated predictions (test asserts an `error` status, not invented assets).
- [ ] Ensemble honors a passed `prompt_func` (test), or the unused params are removed.
- [ ] User content is delimiter-hardened in prompts.
- [ ] LLM calls honor `rate_limit_rpm` and back off on 429/5xx (test).
- [ ] Dead circuit-breaker/rate-limiter globals are wired in or removed; no `get_running_loop()` in sync paths.
