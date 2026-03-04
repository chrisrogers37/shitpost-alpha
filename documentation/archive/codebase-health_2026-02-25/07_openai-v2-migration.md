# Phase 07 — OpenAI SDK v2 Migration

## Header

| Field | Value |
|-------|-------|
| **PR Title** | chore: migrate OpenAI Python SDK from v1.x to v2.x |
| **Risk Level** | Medium |
| **Estimated Effort** | Medium (~3 hours) |
| **Files Modified** | 3 (`requirements.txt`, `shit/llm/llm_client.py`, `shit_tests/conftest.py`) |
| **Files Created** | 0 |
| **Files Deleted** | 0 |

---

## Context

The project currently pins `openai>=1.0.0` in `requirements.txt` and has v1.102.0 installed. The OpenAI Python SDK released v2.0.0 on September 30, 2025, and the latest version is v2.24.0 (February 2026). Staying on v1.x means missing security patches, new model support, and accumulating drift that makes future upgrades harder.

**Critical finding from research:** The v2.0.0 release contains a single documented breaking change — a type expansion on `ResponseFunctionToolCallOutputItem.output` and `ResponseCustomToolCallOutput.output` in the Responses API. This project does NOT use the Responses API; it exclusively uses `client.chat.completions.create()` with `response.choices[0].message.content`, which is **unchanged** across v1 to v2.

The actual migration risk is therefore **lower than initially estimated**. The work centers on:
1. Updating the version pin in `requirements.txt`
2. Future-proofing the `max_tokens` parameter (soft-deprecated in favor of `max_completion_tokens` for newer models)
3. Cleaning up a dead legacy fixture in `conftest.py` that references the ancient v0.x API (`openai.ChatCompletion.acreate`)
4. Verifying all existing tests pass with the new SDK version

Phase 06 (Safe Dependency Upgrades) must be completed first to establish a clean, tested dependency baseline before introducing this larger SDK change.

---

## Dependencies

| Dependency | Phase | Reason |
|-----------|-------|--------|
| **Requires** Phase 06 | Safe Dependency Upgrades | Clean dependency baseline before major SDK change |
| **Blocks** nothing | — | No downstream phases depend on this |

---

## Detailed Implementation Plan

### Step 1: Update `requirements.txt`

**File:** `/Users/chris/Projects/shitpost-alpha/requirements.txt` (line 15)

**Before (line 15):**
```python
openai>=1.0.0
```

**After (line 15):**
```python
openai>=2.0.0,<3.0.0
```

**Why:** Pin to the v2.x major version range. The `<3.0.0` upper bound protects against future v3 breaking changes being pulled in automatically.

**After changing the pin, install the updated dependency:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

Verify the installed version:
```bash
python -c "import openai; print(openai.__version__)"
```
Expected: `2.24.0` or higher (whatever is latest v2.x at time of implementation).

---

### Step 2: Update `max_tokens` to `max_completion_tokens` in `llm_client.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py`

The `max_tokens` parameter still works in the v2 SDK for non-reasoning models, but OpenAI is soft-deprecating it in favor of `max_completion_tokens`. To future-proof the codebase (especially for when the project might use o-series reasoning models), rename the parameter.

**Before (lines 168-179):**
```python
            if self._sdk_type == "openai":
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_message or "You are a helpful AI assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    ),
                    timeout=30.0  # 30 second timeout
                )
```

**After (lines 168-179):**
```python
            if self._sdk_type == "openai":
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_message or "You are a helpful AI assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        max_completion_tokens=1000,
                        temperature=0.3
                    ),
                    timeout=30.0  # 30 second timeout
                )
```

**Why:** `max_completion_tokens` is the forward-compatible parameter name. It is supported by all models in v2.x, including GPT-4o, GPT-4o-mini, and o-series reasoning models. The older `max_tokens` still works for non-reasoning models but will eventually be removed.

**Important:** This change does NOT affect the Anthropic SDK path (lines 182-195), which uses its own `max_tokens` parameter name. Only the OpenAI SDK path is affected.

---

### Step 3: Clean up dead legacy fixture in `conftest.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py` (lines 393-401)

The `mock_openai_client` fixture references the v0.x API (`openai.ChatCompletion.acreate`), which was removed in v1.0.0 (November 2023). This fixture is defined but **never used** by any test (confirmed via grep). It should be removed to avoid confusion.

**Before (lines 393-401):**
```python
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('openai.ChatCompletion.acreate') as mock_create:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = '{"assets": ["TSLA"], "market_impact": {"TSLA": "bearish"}, "confidence": 0.85, "thesis": "Test analysis"}'
        mock_create.return_value = mock_response
        yield mock_create
```

**After:** Delete lines 393-401 entirely. Remove the entire `mock_openai_client` fixture.

**Why:** This fixture patches `openai.ChatCompletion.acreate`, a class that does not exist in openai v1.x or v2.x. It has been dead code since the project moved to the client-based API (`AsyncOpenAI`). No test uses this fixture (verified: the only match for `mock_openai_client` in `shit_tests/` is the fixture definition itself).

---

### Step 4: Verify no other v1-specific patterns exist

The following files were audited and require **no changes**:

| File | Audit Result |
|------|-------------|
| `/Users/chris/Projects/shitpost-alpha/shit/llm/__init__.py` | Only re-exports `LLMClient` and prompt functions. No SDK usage. |
| `/Users/chris/Projects/shitpost-alpha/shit/llm/prompts.py` | Pure string formatting, no SDK dependency. |
| `/Users/chris/Projects/shitpost-alpha/shit/llm/provider_config.py` | Data classes only, no SDK imports. |
| `/Users/chris/Projects/shitpost-alpha/shit/llm/compare_providers.py` | Uses `LLMClient` abstraction, no direct SDK calls. |
| `/Users/chris/Projects/shitpost-alpha/shitpost_ai/shitpost_analyzer.py` | Uses `LLMClient` abstraction via `self.llm_client.analyze()`. No direct SDK usage. |
| `/Users/chris/Projects/shitpost-alpha/shitpost_ai/compare_cli.py` | CLI wrapper, references "openai" as a provider name string only. |
| `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_models.py` | String reference to "openai" in `llm_provider` column comment. |

**Key architectural advantage:** The `LLMClient` class in `llm_client.py` is the **only place** in the entire codebase that imports from the `openai` package directly (`from openai import AsyncOpenAI`). All other modules consume the abstraction. This means the SDK migration is fully contained to a single file plus its tests.

---

## OpenAI SDK v2 API Changes Reference

This section documents EVERY breaking change in v2.0.0 for the implementer's reference.

### Breaking Changes in v2.0.0 (September 30, 2025)

| Change | Impact on This Project |
|--------|----------------------|
| `ResponseFunctionToolCallOutputItem.output` type expanded from `string` to `string \| Array<ResponseInputText \| ResponseInputImage \| ResponseInputFile>` | **NONE** — This project does not use the Responses API or function tool calls. It uses `chat.completions.create()` exclusively. |
| `ResponseCustomToolCallOutput.output` same type expansion | **NONE** — Same reason as above. |

### Non-Breaking Changes Worth Noting

| Change | Relevance |
|--------|-----------|
| `max_tokens` soft-deprecated for `max_completion_tokens` | **Addressed in Step 2** — Renamed proactively for forward compatibility. |
| New error classes (same hierarchy as v1) | **No impact** — `llm_client.py` catches generic `Exception`, not SDK-specific error classes. |
| `AsyncOpenAI` constructor unchanged | **No impact** — Same `api_key` and `base_url` kwargs work. |
| `chat.completions.create()` method signature unchanged | **No impact** — Same `model`, `messages`, `temperature` kwargs work. |
| `response.choices[0].message.content` response shape unchanged | **No impact** — Same attribute access works. |
| `httpx` remains the HTTP transport layer | **No impact** — Already installed as transitive dependency (v0.28.1). |

### Rollback Instructions

If the v2 migration causes unexpected issues in production:

1. **Revert `requirements.txt`** back to `openai>=1.0.0`
2. **Revert `llm_client.py`** — change `max_completion_tokens=1000` back to `max_tokens=1000`
3. **Restore conftest.py fixture** if needed (though it was dead code)
4. **Reinstall dependencies:** `pip install -r requirements.txt`

The rollback is trivial because v2.0.0 has minimal breaking changes that affect this codebase.

---

## Test Plan

### Existing Tests to Verify (NO changes needed)

All existing LLM tests mock `openai.AsyncOpenAI` and `client.chat.completions.create`. Since these APIs are unchanged in v2, all existing mocks remain valid. Run the full suite to confirm:

| Test File | Tests | Expected Result |
|-----------|-------|-----------------|
| `shit_tests/shit/llm/test_llm_client.py` | ~40 tests | All pass (mocks match v2 API shape) |
| `shit_tests/shit/llm/test_llm_client_grok.py` | 5 tests | All pass (same OpenAI SDK path) |
| `shit_tests/shit/llm/test_compare_providers.py` | 4 tests | All pass (no SDK dependency) |
| `shit_tests/shit/llm/test_provider_config.py` | 11 tests | All pass (no SDK dependency) |
| `shit_tests/shit/llm/test_prompts.py` | All tests | All pass (no SDK dependency) |
| `shit_tests/integration/test_full_pipeline.py` | All tests | All pass (mocks LLMClient) |

### Verification That `mock_openai_client` Is Unused

Before deleting the fixture, confirm no test references it:

```bash
cd /Users/chris/Projects/shitpost-alpha
grep -r "mock_openai_client" shit_tests/ --include="*.py"
```

Expected output: Only the fixture definition in `conftest.py`, no usage.

### New Test: Verify `max_completion_tokens` Is Passed

Add one new test to `shit_tests/shit/llm/test_llm_client.py` to verify the parameter is correctly forwarded:

```python
@pytest.mark.asyncio
async def test_call_llm_uses_max_completion_tokens(self):
    """Verify chat.completions.create receives max_completion_tokens (not max_tokens)."""
    with patch('openai.AsyncOpenAI') as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        # Mock successful init
        mock_init_response = MagicMock()
        mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]

        # Mock call response
        mock_call_response = MagicMock()
        mock_call_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        mock_client.chat.completions.create = AsyncMock(
            side_effect=[mock_init_response, mock_call_response]
        )

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test-key")
        await client.initialize()

        await client._call_llm("Test prompt")

        # Verify the second call (first is init) uses max_completion_tokens
        call_args = mock_client.chat.completions.create.call_args_list[1]
        assert 'max_completion_tokens' in call_args.kwargs
        assert call_args.kwargs['max_completion_tokens'] == 1000
        assert 'max_tokens' not in call_args.kwargs
```

**Why this test matters:** It explicitly validates that the old `max_tokens` parameter was replaced with `max_completion_tokens`, preventing regressions if someone accidentally reverts the change.

### Manual Verification Steps

After all automated tests pass:

1. **Dry-run the pipeline** to verify the LLM client works end-to-end:
   ```bash
   source venv/bin/activate
   python shitpost_alpha.py --mode incremental --dry-run
   ```

2. **Check the SDK version at runtime:**
   ```bash
   python -c "import openai; print(f'OpenAI SDK: {openai.__version__}')"
   ```
   Expected: `2.x.x`

3. **Verify imports work:**
   ```bash
   python -c "from openai import AsyncOpenAI; print('AsyncOpenAI import OK')"
   ```

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **OpenAI SDK v2 Migration** — Upgraded `openai` dependency from v1.x to v2.x
  - Updated version pin in `requirements.txt` to `openai>=2.0.0,<3.0.0`
  - Migrated `max_tokens` to `max_completion_tokens` for forward compatibility with reasoning models
  - Removed dead `mock_openai_client` fixture from test conftest (referenced v0.x API that was removed in v1.0)
```

### Inline Code Comments

No new comments needed. The existing code comments in `llm_client.py` are sufficient.

---

## Stress Testing & Edge Cases

### Edge Case: Grok Provider Uses OpenAI SDK

The Grok provider (`provider="grok"`) routes through the same `AsyncOpenAI` client with a custom `base_url`. The `max_completion_tokens` parameter must also work with the xAI API since it is OpenAI-compatible. This is validated by the existing `test_llm_client_grok.py` tests which mock the same `client.chat.completions.create` path.

### Edge Case: Anthropic Provider Is Unaffected

The Anthropic SDK path (lines 182-195 in `llm_client.py`) uses `max_tokens` as its own parameter name, which is correct for the Anthropic SDK. Do NOT change this to `max_completion_tokens` — that is an OpenAI-specific parameter name.

### Edge Case: httpx Version Compatibility

OpenAI v2.x depends on `httpx`. The project already has `httpx==0.28.1` installed as a transitive dependency. If OpenAI v2.x requires a newer httpx version, `pip install` will resolve it automatically. No manual intervention needed.

### Edge Case: Existing Database Records

This migration does NOT change the analysis output format. The `llm_provider` and `llm_model` fields stored in the `predictions` table remain the same string values (`"openai"`, `"gpt-4o"`, etc.). No database migration or backfill is needed.

### Error Scenario: API Key Issues

If the OpenAI API key is invalid or expired, the error handling in `_call_llm()` (line 197: `except Exception as e`) catches all exceptions generically. This works identically in v1 and v2 since the error class hierarchy is preserved.

---

## Verification Checklist

- [ ] `requirements.txt` updated to `openai>=2.0.0,<3.0.0`
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `python -c "import openai; print(openai.__version__)"` shows `2.x.x`
- [ ] `max_tokens` changed to `max_completion_tokens` in `llm_client.py` line 176 (OpenAI path only)
- [ ] `max_tokens` is NOT changed in `llm_client.py` line 187 (Anthropic path — leave as-is)
- [ ] Dead `mock_openai_client` fixture removed from `shit_tests/conftest.py`
- [ ] New test `test_call_llm_uses_max_completion_tokens` added to `test_llm_client.py`
- [ ] `source venv/bin/activate && pytest shit_tests/shit/llm/` — all tests pass
- [ ] `source venv/bin/activate && pytest` — full test suite passes
- [ ] `ruff check .` — no linting errors
- [ ] `ruff format .` — code is formatted
- [ ] CHANGELOG.md updated with migration entry
- [ ] `python shitpost_alpha.py --mode incremental --dry-run` works (if API key available)

---

## What NOT To Do

1. **Do NOT change `max_tokens` in the Anthropic SDK path.** The Anthropic SDK uses `max_tokens` as its own parameter name. `max_completion_tokens` is OpenAI-specific. Changing it for Anthropic will break that provider.

2. **Do NOT add OpenAI-specific error handling.** The current generic `except Exception as e` pattern is intentional — it catches all errors regardless of SDK version. Adding `except openai.RateLimitError` etc. would create tight coupling. The error class hierarchy exists in v2 but is not needed here.

3. **Do NOT upgrade to `openai>=2.0.0` without the `<3.0.0` upper bound.** Future v3 could have real breaking changes to `chat.completions.create()`.

4. **Do NOT confuse this with the v0.x → v1.x migration.** That was the massive rewrite (November 2023) from module-level API (`openai.ChatCompletion.create()`) to client-based API (`AsyncOpenAI().chat.completions.create()`). The v1 → v2 migration is narrow — a single type change in the Responses API that does not affect this project.

5. **Do NOT run this migration before Phase 06.** Phase 06 establishes the clean dependency baseline. Running this first could mask transitive dependency conflicts.

6. **Do NOT change any prompt templates or analysis output formats.** This is a pure infrastructure change. The LLM prompts, response parsing, and analysis output structure must remain identical to ensure prediction quality continuity.

7. **Do NOT delete or modify the `mock_anthropic_client` fixture in conftest.py.** Only `mock_openai_client` is dead code. The `mock_anthropic_client` fixture (lines 404-414) may be used elsewhere or may be needed in the future.
