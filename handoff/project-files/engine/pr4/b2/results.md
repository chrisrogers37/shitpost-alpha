# Engine PR 4, Part B2: results (2026-10-02)

These were run on the sandbox database only. **AI picker version 1 is frozen on option A** (Chris, 2026-10-02 22:03 UTC): gpt-4.1 and Haiku 4.5 must both make a link or a name for it to count, and if either fails the rules stand in. The window starts 2025-11-01. Grok is a comparison only: it's not in the engine and has no vote. Its 500 recorded answers are in `grok-comparison.jsonl`.

## Models

| Provider | Model | Cutoff | Source | Still served, retirement | Price per M tokens (in / cached / out), checked 2026-10-02 |
| --- | --- | --- | --- | --- | --- |
| OpenAI | gpt-4.1-2025-04-14 | 2024-06-01 | developers.openai.com/api/docs/models/gpt-4.1 | yes; no shutdown listed on the deprecations page (only gpt-4.1-nano, 2026-10-23) | $2.00 / $0.50 / $8.00 |
| Anthropic | claude-haiku-4-5-20251001 | training data Jul 2025 (reliable knowledge Feb 2025) | platform.claude.com/docs/en/models/overview | yes; Active, "not sooner than 2026-10-15", no deprecation notice | $1.00 / $0.10 / $5.00 |
| xAI (comparison only, not in the engine) | grok-4.20-0309-non-reasoning | 2025-09-01, **unofficial**: xAI publishes none; OpenRouter's date | openrouter.ai/x-ai/grok-4.20 | yes; none announced | $1.25 / $0.20 / $2.50 |

These models were ruled out:
- claude-sonnet-4-5-20250929 was deprecated 2026-09-30 and retires 2026-11-30.
- Opus 4.5's training data runs to Aug 2025.
- gpt-5-2025-08-07 shuts down 2026-12-11 and gpt-5.1-2025-11-13 on 2027-04-01.
- gpt-5.2 and later have cutoffs after Jul 2025.
- Every older Grok was retired 2026-05-15.
- Grok 4.3 (Dec 2025 per grok.com), 4.5 (Jan 2026), 4.6 and 4.7 (May 2026) all have cutoffs that are too late.

All three models take temperature 0 with a strict JSON schema; one probe call each confirmed it. Haiku gets `temperature` in the body because the SDK has no argument for it. These facts come from web search of each provider's own pages, because this sandbox can't open their docs hosts.

**Window start (frozen):** **2025-11-01** at New York midnight (Haiku Jul 2025 + 3 months, next day). Option B would have started on 2025-12-02.

## Precision on the 300 held-out posts (95% Wilson)

Rules and each model alone (from `scripts/precision.py`):

| Picker | Window: market link precision | Window: market link recall | Window: names precision | Window: names recall |
| --- | --- | --- | --- | --- |
| rules v1 | 65% (34/52; 52-77%) | 77% (34/44; 63-87%) | 100% (4/4) | 40% (4/10) |
| gpt-4.1 alone | 66% (35/53; 53-77%) | 80% (35/44; 65-89%) | 29% (7/24) | 70% (7/10) |
| Haiku 4.5 alone | 88% (28/32; 72-95%) | 64% (28/44; 49-76%) | 60% (6/10) | 60% (6/10) |
| Grok 4.20 alone | 96% (23/24; 80-99%) | 52% (23/44; 38-66%) | 50% (5/10) | 50% (5/10) |

After the freeze, the sandbox's `ai:vote` rows were rebuilt from the recorded gpt-4.1 and Haiku answers with the engine's own `vote()` and `record()`. Every recorded answer was made after the last change to the prompt, schema and settings (21:52:59 UTC), with the same model ids. When the prices and the reason line left the version (gauntlet round 2), every AI row was re-stamped with version 1's frozen hash, 750126437c71…; the answers and votes didn't change. Re-mapping and re-voting every recorded answer with 178bbab's code (the round 2 dedup and vote-sort changes) gives the recorded run 1 mentions and votes exactly. No model was called again. `scripts/precision.py` on those rows gives row A below exactly. No model failed, so the rules never stood in. Row B is kept for the record.

| Vote | Group | Market link precision | Market link recall | Names precision | Names recall |
| --- | --- | --- | --- | --- | --- |
| **A, frozen v1**: gpt-4.1 + Haiku, both must agree | window (200) | 89% (25/28; 73-96%) | 57% (25/44; 42-70%) | 100% (5/5) | 50% (5/10) |
| A | early (100) | 100% (4/4) | 44% (4/9) | 100% (1/1) | 14% (1/7) |
| B (not chosen): 2 of 3 | window from 2025-12-02 (179) | 89% (24/27; 72-96%) | 62% (24/39; 46-75%) | 86% (6/7) | 60% (6/10) |
| B | Nov 2025 (21) | 100% (2/2) | 40% (2/5) | none | none |
| B | early (100) | 100% (5/5) | 56% (5/9) | 100% (1/1) | 14% (1/7) |

Only 11 of the 300 posts name anything, so the name intervals are wide. The spot-check file is `/mnt/project-files/engine/pr4/precision-sample.csv`; its AI columns show the frozen v1 vote.

## Stability (the 50 `dev_market` posts, run 1 against run 2)

| Model | Same answer, word for word | Same link and names |
| --- | --- | --- |
| gpt-4.1 | 74% (37/50) | 92% (46/50) |
| Grok 4.20 (comparison) | 88% (44/50) | 94% (47/50) |
| Haiku 4.5 | 94% (47/50) | 98% (49/50) |

## PR 5 projection (frozen: column A)

This is each model's average cost per post on the 300, multiplied by the window's text posts with words, through 2026-10-02.

| Provider | Average cost per post | A: 3,691 posts, standard / batch | B: 3,317 posts, standard / batch |
| --- | --- | --- | --- |
| OpenAI (batch 50% off) | $0.00248 | $9.16 / $4.58 | $8.23 / $4.11 |
| Anthropic (batch 50% off) | $0.00164 | $6.04 / $3.02 | $5.43 / $2.71 |
| xAI (batch 20% off for 4.20) | $0.00044 | n/a | $1.47 / $1.18 |
| **Total** | | **$15.20 / $7.60** | **$15.13 / $8.01** |

No provider comes near $60. Live use costs about half a cent per text post for the whole vote.

## PR 4 AI spend so far: about $3.69

- Scratch prompt rounds, probes and reason samples: $1.44 (`spend.md`).
- Recorded `ai-pick` runs: $2.25 (dev set of 150, the 300, and 50 stability reruns).

## review-list on the frozen v1 votes (the 450 posts)

The vote counted these names that the rules missed: F and GM (2 posts each), and AEO, BTC, BUD, ETH, STLA and TSN (1 each). Both models also named ABC, Conair, Jaguar and Twitter, which mapped to nothing (no ticker).
