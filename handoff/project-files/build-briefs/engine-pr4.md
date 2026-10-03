# Engine PR 4: extraction and similarity

> **Update, 2 Oct 22:03 UTC (Chris's decision):** the AI picker uses two models, `gpt-4.1-2025-04-14` and `claude-haiku-4-5-20251001`, and a market link or name counts only when both make it. If either fails, the post uses the rules' picks, marked `ai_fallback`. The test window starts 2025-11-01. No xAI model votes: none still served has a published training cutoff by July 2025. Grok's answers on the 300 posts are reported as a comparison only. This replaces every "three models" and "2 of 3" below.

You are building PR 4 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists:
- **PR 1** (draft #258, branch `claude/engine-foundation-k6mh6s`): settings, Alembic with the `engine`, `prices` and `app` schemas, the lease, the scheduler, `StageRunner`, the worker registry and the grants step.
- **PR 2** (draft #259, branch `claude/engine-sources-i0sp5e`): the feeds, `engine.sources`, `engine.signals` and the history import. New text posts wait at stage `score`; reposts, media-only posts and imported history are saved at `done`.
- **PR 3** (draft #260, branch `claude/engine-prices-f67iio`): the Alpaca adapter, `engine.instruments`, `engine.instrument_aliases` with its add function, the "what counts" rule, the collision list (`engine/engine/market/collisions.json`), the calendar and daily bars.

Read all three first and build on them.

PR 4 decides what each post is about. It adds:
- the topic list and the name rules (the **rules picker**);
- the **AI picker**: three models, 2 of 3 vote;
- the precision of both pickers on 300 hand-labelled posts;
- the similarity model, every post's vector and the match rule;
- the reason-line function;
- the records tables, the live `score` stage and the replay harness.

Nothing is backtested, graded or sent yet: PR 5 runs the backtest on what PR 4 builds and freezes. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use DEV_DATABASE_URL.
- **Old key names.**
  - Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist.
  - The `openai` and `anthropic` SDKs read those old names from the environment when no key is passed. So every client is built with its key passed explicitly from settings.
  - No client is built when its ENGINE_ key is unset. Tests use stubs and never build a real client.
- **Paid AI calls.**
  - Only with ENGINE_OPENAI_KEY, ENGINE_XAI_KEY and ENGINE_ANTHROPIC_KEY. Each is under a spend cap of $75 a month that Chris set.
  - Keep PR 4's total AI spend under $15. Track it from the recorded costs, and stop and tell the engine planner before it would pass that.
  - Keys never appear in logs, fixtures, the PR or chat. Recorded answers keep the response body only, never request headers.
- **No market moves.**
  - The topics, the name rules, the AI prompt and the match rule are set by reading post text only.
  - While drafting them, never look at prices, returns or the old system's predictions, and don't compute any.
- **Prices stay private.** Raw prices live only in the `prices` schema. Nothing in this PR publishes a price.
- **Other services.** Never call Truth Social's API or ScrapeCreators. Alpaca: market data only (`data.alpaca.markets`). No Telegram, email or SMS. No crons. No Railway calls.
- **Scope.**
  - Design from first principles and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **shitpost_dev** holds about 36,600 posts from PR 2's import and the seeds' daily bars from PR 3. If this session's database is empty, rebuild it with `python -m engine import-history` and `python -m engine backfill-bars` first.
- **Alpaca** keys and host are set up from PR 3. Adding an instrument needs them, because it checks "what counts".
- **New hosts and keys.** Chris is adding seven hosts and three keys. They reach only sessions started after he does.
  - Hosts: `huggingface.co`, `cdn-lfs.hf.co`, `cdn-lfs-us-1.hf.co` and `cas-bridge.xethub.hf.co` for the model download, plus `api.openai.com`, `api.x.ai` and `api.anthropic.com`.
  - Keys: `ENGINE_OPENAI_KEY`, `ENGINE_XAI_KEY` and `ENGINE_ANTHROPIC_KEY`.
  - **Check:**
    - the three variables exist (never print them);
    - `curl -sS -o /dev/null -w '%{http_code}' https://huggingface.co/api/models/BAAI/bge-small-en-v1.5` answers 200;
    - each AI host answers any HTTP status to a keyless request, rather than `000` with "CONNECT tunnel failed".
- **Outputs for review** go in `/mnt/project-files/engine/pr4/` (create it). Never commit post-level samples beyond ids and labels.

## Three parts
- **Part A** needs no new hosts or keys: everything not listed under B1 or B2, including the AI picker's and reason line's code, tested against hand-made answers in fixtures named `*.unverified.json`.
- **Part B1** needs the Hugging Face hosts: sections 4 and 5.
- **Part B2** needs the AI keys and hosts: the real-call half of sections 6 and 7, and the AI precision in section 3.

Do what this session can. If anything is missing, open the draft PR with the rest listed as not done, and stop. A later session on the same branch finishes it and updates the PR. B1 and B2 can come in either order.

## Scope
**1. Topics (versioned data, Part A).**
- **The file.** A data file in the repo, like the collision list: 8 to 12 topics plus `other`. Each topic has an id, a name, a one-line description, a market flag and its keyword and phrase rules.
- **One topic per post.** The first topic that matches, in the file's priority order, with market topics first; else `other`.
- **Drafting.**
  - Read at least 400 text posts drawn with a fixed seed across February 2022 to now, excluding the 300 precision posts.
  - List the recurring subjects and merge them into topics.
  - Note in the PR how many posts you read and what you merged.
  - The reading decides the topics. For example, trade and tariffs, the Fed and rates, energy, crypto, taxes, named companies and deals, and war and sanctions may be market topics; elections, the media and court cases may not.
- **Topics are rules-only.** The AI picker returns a market link and names, not a topic.

**2. Name rules (Part A).** The rules picker finds instruments named in the text:
- **Cashtags:** `$TSLA`.
- **Bare tickers:** a bare ticker of an instrument already in `engine.instruments`, at least 2 letters, not on the collision list.
- **Name aliases:** case-insensitive and on word boundaries, so "Apple" never matches "pineapple". "Bitcoin" maps to BTC; "Ethereum" and "Ether" map to ETH.
- **No implied names.** Those are the AI picker's job.

**Aliases.**
- Draft them by reading: list the companies and products he names across all posts (frequent capitalised words and phrases, reviewed by hand), then add an alias for each US-listed one with PR 3's add function.
- Private, foreign-only and delisted names stay unmapped.
- Keep the aliases as a versioned data file in the repo, synced idempotently into `engine.instrument_aliases`.

**Collision list.** For every instrument symbol that appears in posts as a bare word, read up to 10 of those posts. If any use isn't the company, add the symbol to the collision list.

**One rules version.** It covers the topic file, the alias file and the collision list. Bump it on any change, and record it on every extraction. Freeze version 1 at the end of PR 4.

**3. The 300-post precision sample.**
- **Draw it first,** before drafting anything, with a fixed seed: 300 text posts (no reposts, no media-only posts).
  - 200 from the AI picker's planned test window, from 2025-11-01 to the newest post;
  - 100 from 2022-02-01 to 2025-10-31.

  If B2 moves the window start, report the posts before the new start as their own group.
- **Hold it out.** Keep these posts out of all drafting and prompt writing.
- **Label guide first.** Write a short guide in the repo saying what counts as a market link and as an implied name.
- **Labels.** Label each post by reading its text, and the quoted post's text if any, before running either picker on it:
  - market link, yes or no;
  - topic;
  - the US-listed stocks, ETFs and coins it names or clearly implies, each marked explicit or implied.
- **Commit the labels before any precision run,** so the history shows they came first. Commit ids and labels only, no text.
- **Precision and recall** with Wilson intervals, for:
  - the rules picker;
  - the AI vote;
  - each AI model alone, reported but not judged.

  Measure at post level (market link) and at name level, with explicit and implied names apart, for each of the two groups.
- **Rules first.** Run the rules' numbers in Part A. Add the AI numbers in B2.
- **Spot-check file.** Write `/mnt/project-files/engine/pr4/precision-sample.csv` with each post's id, text, labels and both pickers' output, so Chris can spot-check it.

**4. Similarity model (B1).**
- **Model.** BAAI/bge-small-en-v1.5 (MIT licence), using the ONNX file in that repo.
  - Run it with `onnxruntime` and `tokenizers` on the CPU, with no torch.
  - Pin the repo's commit and every file's SHA-256.
  - Pool as the repo's `1_Pooling/config.json` says (CLS), and normalise the vectors.
  - If the repo has no ONNX file, ask the engine planner before adding torch.
- **Download.** `python -m engine fetch-model` downloads the pinned files with plain httpx, following redirects: no `huggingface_hub` and no Xet client.
  - Files go to `ENGINE_MODEL_DIR`, outside the repo by default.
  - It checks each hash and refuses a mismatch.
  - Report the hosts the redirects used. Never commit model files. PR 7 decides how Railway gets them.
- **Text.** One normalising function for live and history: remove links and collapse whitespace. No instruction prefix: post-to-post similarity is symmetric. Truncate at 512 tokens and count the truncated posts.
- **Vectors.** `engine.signal_embeddings` holds one vector per text post per model version, with a hash of the text. `python -m engine embed` fills it, idempotent and resumable.
- **Matching.** One in-memory numpy matrix, with no vector database. `similar(post, before, k=50, min_score)` returns up to 50 earlier posts at or above the threshold, best first:
  - It excludes the post itself and anything at or after `before`. PR 5 passes "windows already closed".
  - A test shows one query against 40,000 vectors in well under 100 ms.

**5. Match rule (B1).** How similar a past post must be. Set it by reading text only:
- **Sample.** Draw 30 posts with a fixed seed, outside the 300.
- **Read.** For each, read its matches in score bands (0.90 and up, 0.85–0.90, 0.80–0.85, 0.75–0.80, 0.70–0.75). Mark each pair "same subject" or not. Same subject means the same specific matter, such as tariffs on China, the same company or the Fed chair, not just the same broad topic.
- **Pick.** The threshold is the lowest band where at least 80% of pairs are the same subject.
- **Record.**
  - The reading table goes in `/mnt/project-files/engine/pr4/match-rule.md`.
  - The rule goes in a versioned file as match rule version 1: model version, threshold, at most 50 matches, and the text normalisation.

**6. AI picker (code in Part A, real calls in B2).**

**Models.** One each from OpenAI, xAI and Anthropic. Record each model's choice in a table in the PR, with source links. Each model must:
- have a published training cutoff. Where a provider gives both a knowledge cutoff and a training-data cutoff, use the later one.
- be still served, with no announced retirement before the end of 2027. Check the provider's models list API and its deprecation page.
- have a cutoff no later than July 2025.
- take temperature 0 (or the provider's equivalent) and strict structured output.

Among those, take the strongest one whose PR 5 run projects to $50 or less. Pin dated snapshots, never aliases.

My expectations, to verify:
- **Anthropic:** `claude-sonnet-4-5-20250929` (training data to July 2025), with `claude-haiku-4-5-20251001` as the cheaper fallback with the same cutoff.
- **OpenAI:** a dated `gpt-4.1` snapshot (cutoff June 2024) if it is still served; otherwise the newest OpenAI model that meets the rule.
- **xAI:** the Grok model with the earliest published cutoff that is still served.

**The test window** starts 3 months after the latest of the three cutoffs, at the start of the next day. Write it into the frozen settings and tell the engine planner.

**Clients.**
- The official `anthropic` and `openai` SDKs. xAI goes through the `openai` SDK with base URL `https://api.x.ai/v1`, if strict structured output works there; otherwise use xAI's own SDK.
- Each call has a 15 s timeout. Live, the three run side by side.

**Prompt.**
- **Input:** the post's text, plus the quoted post's text when the engine has it. No date, engagement or prices.
- **Output** (strict JSON):
  - `market_link` (bool);
  - `instruments`: at most 8 items, each with `name`, `ticker` (or null), `asset` (`stock`, `etf` or `coin`), `link` (`explicit` or `implied`) and `why` (100 characters or fewer).
- **What to name:** only US-listed stocks and ETFs, and BTC and ETH. Implied names only for a direct, first-order link (steel tariffs point to US steel makers). No broad index funds: SPY and QQQ come from the market link.
- **Writing it:**
  - Put the fixed instructions first, so the providers' prompt caching applies.
  - Write it on a dev set of about 100 posts outside the 300.
  - Use few rounds; each round costs money.

**Settings.**
- Temperature 0, with no extended thinking or reasoning, or its minimum where it can't be turned off.
- A cap on output tokens.
- **Stability check:** rerun 50 dev posts once per model, store the reruns without overwriting the first answers, and report the share that match exactly.

**Vote.** A market link or an instrument counts when at least 2 of 3 models make it, after their names map to the same instrument.
- If one model fails (an error, an invalid answer or more than 15 s), the other two must agree.
- If two or three fail, the post uses the rules' picks and is marked `ai_fallback`.
- Batch runs retry rate-limit and server errors with back-off. Timeouts aren't retried: they count as missed, as they would live.

**Mapping.** AI names map through the same aliases and collision list as the rules.
- A ticker on the collision list counts only when the model's name for it matches that instrument's alias.
- A new ticker is added with PR 3's function only if it counts at the post's time.
- Unmapped names are kept, with a reason.

**Review list.** `python -m engine review-list` prints the names the AI vote counted and the rules missed, with counts, for the next rules version.

**Frozen as AI picker version 1, with its hash:**
- the prompt;
- the schema;
- the three model ids;
- the settings;
- a price table per model (input, cached input and output, with the date each pricing page was checked);
- the window start.

**7. Reason line (code in Part A, samples in B2).**
- **Model.** One designated model, by default the pinned Anthropic one.
- **What it writes.** One line of 120 characters or fewer, saying why the post may matter for the named instruments. Its input is the post's text, the topic and the instruments' names.
- **What it never does.** It decides nothing, and never states a direction, a price, a target or advice. A rule check rejects lines that break this or the length limit.
- **Failure.** On a timeout (15 s), an error or a rejected line, it returns nothing and the alert goes out without a reason line.
- **Scope now.** PR 6 uses it. PR 4 builds the function, its prompt (versioned) and its check, with 10 real samples in the PR.

**8. Records (a new migration; add-then-remove only).**
- **`engine.extractions`.** One row per signal, method and version, where method is `rules`, `ai:openai`, `ai:xai`, `ai:anthropic` or `ai:vote`. Each row holds:
  - the model id;
  - started and finished times;
  - the raw response body;
  - the normalised result;
  - `market_link` and `topic` (rules) as columns;
  - input, cached-input and output tokens;
  - the cost in USD, from the price table;
  - the error, if any.

  Reruns never overwrite an earlier answer.
- **`engine.signal_mentions`.** One row per name per signal per picker and version. Each row holds:
  - the name as written and normalised;
  - the ticker given;
  - the instrument, or null with an unmapped reason;
  - how it was found (`cashtag`, `ticker`, `alias`, `ai_explicit` or `ai_implied`);
  - for the AI, how many models named it;
  - whether it counted;
  - the post time, copied from the signal.

  Index it by instrument and post time.
- **`engine.signal_embeddings`,** as in section 4.
- **Grants.** These tables are in `engine`, which the web role already reads. Add nothing to `app` or `prices`.

**9. Live `score` stage and history in batch (Part A).**
- **The `score` stage.** Register its handler on signals:
  - the rules picker and its mentions;
  - the embedding;
  - the AI picker, only when `ENGINE_AI_LIVE` is on. It is off by default; PR 7 turns it on.

  After `score`, a signal moves to `done` until PR 6 adds the alert stage. If the model files are missing, the stage fails with a clear error, so a misconfigured deploy shows up.
- **History never goes through the live stage.** It runs in batch:
  - `python -m engine extract` runs the rules picker over all text posts. It is idempotent per rules version.
  - `python -m engine embed` (section 4).
  - `python -m engine ai-pick`:
    - It takes an id list or a date range.
    - It prints the projected cost before starting, and refuses above `--max-usd` (default 5).
    - In PR 4, run it only on the dev set, the 300 posts and the stability reruns. PR 5 runs the window.

**10. Replay harness (Part A, test-only).**
- **What it does.** Recorded posts go through the store path and the `score` stage with:
  - stub AI clients that return fixed answers per post;
  - a stub embedder that makes deterministic vectors, or the real model when its files are present.

  It reports each post's outputs and step timings.
- **Delivery.** Leave one hook point for dry-run delivery, which PRs 6 and 8 fill; build no delivery.
- **Data.** Use the recorded CNN and trumpstruth fixtures from PR 2.

**Data notes.**
- **Quotes in history.** CNN's copies have no "RE:" quote marker, so quotes in imported history read as plain posts. Leave them as posts, build no detector, and say so in the PR.
- **Quoted text.** It goes to the AI only when the signal points to a post whose text the engine has.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Rules:**
  - a cashtag;
  - a bare ticker;
  - a collision symbol that needs a cashtag or a name;
  - word boundaries;
  - `fb` before and after 2022-06-08;
  - topic priority and `other`.
- **AI mapping:**
  - by alias and by ticker;
  - a collision ticker that needs its name;
  - a new ticker added only when it counts;
  - an unmapped name kept with its reason.
- **Vote:**
  - all three agree;
  - 2 of 3;
  - one fails, and the other two must agree;
  - two fail, so it falls back to the rules;
  - a timeout counts as missed.
- **Keys:** with no ENGINE_ AI keys, no client is built and the AI picker is off; keys never appear in logs.
- **Embedding:**
  - With stubs in unit tests.
  - With the real files (skipped when they're absent): the same text gives the same vector, vectors are normalised, and a paraphrase scores above an unrelated post.
- **Matching:**
  - it excludes the post itself and later posts;
  - it returns at most 50;
  - it applies the threshold;
  - the speed test.
- **Records:**
  - reruns are idempotent per version;
  - stability reruns don't overwrite;
  - the mentions index exists.
- **Stage and replay:**
  - a new text post at `score` ends at `done` with its rules extraction, mentions and embedding;
  - the AI is off by default;
  - with stub AI on, there are three answers and a vote;
  - the replay harness runs recorded posts.
- **Cost guard:** `ai-pick` refuses a run over `--max-usd`.

By hand, with results in the PR body:
- **Part A:**
  - the topic list;
  - the reading notes for topics and aliases;
  - the label guide;
  - the rules' precision;
  - the rules over all history: posts per topic, the share with a market link, and the most-named instruments.
- **B1:**
  - the download hosts;
  - posts embedded, how many were truncated, and how long it took;
  - the match-rule threshold and its reading table.
- **B2:**
  - the model table, with each cutoff, its source and retirement status, and prices;
  - the window start;
  - the AI precision (the vote and each model);
  - the stability share;
  - the reason-line samples;
  - PR 4's AI spend;
  - **the PR 5 projection:** the average cost per post for each model on the 300, times the number of text posts in the window, per provider, at standard prices and at batch-API prices where a provider offers them.

  If any provider's projection is over $60, tell the engine planner before anything else.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 3's branch `claude/engine-prices-f67iio` while #260 is unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 4: extraction and similarity", saying near the top that it goes in after #258, #259 and #260. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the results listed above;
   - any part not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Report.** Send the engine planner the window start, the three models and the PR 5 projection when you have them.
5. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
