"""Round 2 (fold-in) mutation checks at 4554d3d. Each mutation replaces one exact snippet in
the mutation worktree, runs the named tests with -x, records whether any failed ("killed")
and restores the file. Secrets are stripped from the environment for every run.

V*: round 1 verify's mutations, re-run where they still apply (snippets adapted).
R*: round 1 review's mutations that survived, re-run.
F*: one per new round-1 fix: revert the guard, a committed test should fail.
"""

import os
import subprocess
import sys
from pathlib import Path

SP = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad")
ROOT = SP / "r2fold-261-mut" / "engine"
PY = "/home/user/engine-venv-261/bin/python"
STRIP = {
    "DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY",
    "ENGINE_OPENAI_KEY", "ENGINE_ANTHROPIC_KEY", "ENGINE_XAI_KEY", "ANTHROPIC_BASE_URL",
    "OPENAI_BASE_URL", "ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID", "OPENAI_CUSTOM_HEADERS",
    "ANTHROPIC_CUSTOM_HEADERS",
}
ENV = {k: v for k, v in os.environ.items() if k not in STRIP}
ENV["PYTHONPATH"] = str(ROOT)
ENV["ENGINE_MODEL_DIR"] = "/home/user/engine-models"

AI = "engine/extract/ai.py"
BATCH = "engine/extract/batch.py"
SCORE = "engine/extract/score.py"
RULES = "engine/extract/rules.py"
REASON = "engine/extract/reason.py"
RECORDS = "engine/extract/records.py"
SIM = "engine/extract/similarity.py"
T_AI, T_BATCH, T_SCORE = "tests/test_ai.py", "tests/test_batch.py", "tests/test_score.py"
T_RULES, T_SIM = "tests/test_rules.py", "tests/test_similarity.py"
EXTRACT = [T_AI, T_BATCH, T_SCORE, T_RULES, T_SIM, "tests/test_precision.py"]

# (id, property, file, old, new, tests)
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    # --- verify round 1 (adapted) ---
    ("V1", "no client without an ENGINE_ key", AI,
     "if (key := keys.get(provider)) is None or spec.model is None:",
     "key = keys.get(provider) or 'x'\n        if spec.model is None:", [T_AI]),
    ("V2", "the key is passed to the OpenAI SDK explicitly", AI,
     "            api_key=key,\n            base_url=BASE_URLS[provider],",
     "            api_key=None,\n            base_url=BASE_URLS[provider],", [T_AI]),
    ("V3", "OpenAI/xAI host pinned", AI, "            base_url=BASE_URLS[provider],",
     "            base_url=None,", [T_AI]),
    ("V4", "Anthropic host pinned", AI, '            base_url=BASE_URLS["anthropic"],',
     "            base_url=None,", [T_AI]),
    ("V5", "keys cut out of errors and logs", AI, 'text = text.replace(secret, "[key]")',
     "text = text", [T_AI, T_BATCH]),
    ("V6", "a timeout is never retried", AI,
     "        except TimeoutError:\n            error = f\"timeout after {config.timeout_seconds:g} s\"",
     "        except TimeoutError:\n            if attempt < retries:\n                attempt += 1\n"
     "                continue\n            error = f\"timeout after {config.timeout_seconds:g} s\"",
     [T_AI]),
    ("V7", "2 of 3 needed", AI, "NEEDED = 2", "NEEDED = 1", [T_AI]),
    ("V8", "two failures fall back to the rules", AI,
     "    if len(ok) < NEEDED:\n        return Vote(rules.market_link, rules.mentions, len(ok), fallback=True)",
     "    if len(ok) < 1:\n        return Vote(rules.market_link, rules.mentions, len(ok), fallback=True)",
     [T_AI]),
    ("V9", "AI: a collision ticker in the book needs its name", AI,
     "        if collision and instrument_id not in named:", "        if False:", [T_AI]),
    ("V10", "AI: a new collision ticker is never sent to Alpaca", AI,
     "    if collision:\n        return unmapped(\"collision_without_name\")\n", "", [T_AI]),
    ("V11", "AI: a new ticker is checked at the post's time", AI,
     "listed = await add_new(ticker, item.asset, posted_at)",
     "listed = await add_new(ticker, item.asset, _now())", [T_AI, T_SCORE, T_BATCH]),
    ("V12", "AI: index funds are never named", AI,
     "    if ticker in INDEX_FUNDS:\n        return unmapped(\"index_fund\")\n", "", [T_AI]),
    ("V13", "AI picker files refused when their hash changes", AI,
     "        if hashlib.sha256(raw).hexdigest() != digest:", "        if False:",
     [T_AI, T_BATCH, T_SCORE]),
    ("V14", "rules files refused when their hash changes", RULES,
     "        if _sha256(path) != digest:", "        if False:", [T_RULES]),
    ("V15", "rules: a bare collision ticker doesn't count", RULES,
     "        if not book.rules.collisions.mention_counts(ticker, cashtag=False):\n            continue\n",
     "", [T_RULES]),
    ("V16", "rules: names on word boundaries", RULES,
     'return re.compile(r"(?<!\\w)(?:" + "|".join(parts) + r")(?!\\w)", re.IGNORECASE)',
     'return re.compile(r"(?:" + "|".join(parts) + r")", re.IGNORECASE)', [T_RULES]),
    ("V17", "rules: a ticker holds from the day after its old ticker", RULES,
     "after_old and after_old + timedelta(days=1)", "after_old and after_old", [T_RULES]),
    ("V18", "records: an answer is never overwritten", RECORDS,
     '            .on_conflict_do_nothing(constraint="extractions_key")',
     '            .on_conflict_do_update(constraint="extractions_key", set_={"market_link": values["market_link"], "result": values["result"]})',
     [T_SCORE, T_BATCH]),
    ("V19", "records: run 2 writes no mentions", RECORDS,
     "if extraction_id is None or answer.run != 1 or not answer.mentions:",
     "if extraction_id is None or not answer.mentions:", [T_SCORE, T_BATCH]),
    ("V20", "ai-pick refuses a projection over --max-usd", BATCH,
     "    if projection.total > max_usd:", "    if False:", [T_BATCH]),
    ("V21", "ai-pick stops once a run costs more than --max-usd", BATCH,
     "            if cost > max_usd:", "            if False:", [T_BATCH]),
    ("V22", "the AI is off unless ENGINE_AI_LIVE", SCORE,
     "    if not settings.ai_live:\n        return None\n", "", [T_SCORE]),
    ("V23", "ENGINE_AI_LIVE defaults off", "engine/settings.py", "    ai_live: bool = False",
     "    ai_live: bool = True", [T_SCORE]),
    ("V24", "matching excludes posts at `before`", SIM, "(self.times < before.timestamp())",
     "(self.times <= before.timestamp())", [T_SIM]),
    ("V25", "matching excludes the post itself", SIM, " & (self.keys != key)", "", [T_SIM]),
    ("V26", "matching applies the threshold", SIM, " & (scores >= min_score)", "", [T_SIM]),
    ("V27", "fetch-model refuses a file whose hash differs", SIM,
     "            if got.hexdigest() != digest:", "            if False:", [T_SIM]),
    ("V28", "the score worker fails when the model is missing", SCORE,
     "        embedder = await asyncio.to_thread(embedder_loader, settings)  # ModelMissing: fail here",
     "        try:\n            embedder = await asyncio.to_thread(embedder_loader, settings)\n"
     "        except Exception:\n            from tests.extract_helpers import StubEmbedder\n"
     "            embedder = StubEmbedder()", [T_SCORE]),
    ("V29", "the reason-line check rejects direction words", REASON,
     "    if found := DIRECTION.search(line):", "    if found := None:", [T_BATCH]),
    ("V30", "the reason line is dropped on a timeout", REASON,
     "        async with asyncio.timeout(config.timeout_seconds):\n            reply = await client.ask(",
     "        if True:\n            reply = await client.ask(", [T_BATCH]),
    ("V31", "the reason line's length limit", REASON, "    if len(line) > max_chars:",
     "    if len(line) > max_chars + 1000:", [T_BATCH]),
    ("V32", "quoted text only for a quote", SCORE,
     '    if row.kind != "quote" or not row.points_to:', "    if not row.points_to:", [T_SCORE]),
    ("V33", "live stage asks the AI without batch retries", SCORE,
     "ai_pick = await record_ai(conn, row, book, post, self.ai, rules_pick, adder)",
     "ai_pick = await record_ai(conn, row, book, post, self.ai, rules_pick, adder, retries=3)",
     [T_SCORE, T_BATCH]),
    ("V34", "embed skips a post that already has a vector", BATCH,
     "                    .where(TEXT_POSTS, ~has_vector)", "                    .where(TEXT_POSTS)",
     [T_BATCH]),
    ("V35", "extract only takes posts lacking this rules version", BATCH,
     '                    .where(TEXT_POSTS, _lacks("rules", rules.version))',
     "                    .where(TEXT_POSTS)", [T_BATCH]),
    # --- review round 1 survivors ---
    ("R1", "SDK timeouts are not retried", AI,
     "    if isinstance(exc, openai.APITimeoutError | anthropic.APITimeoutError):\n        return False\n",
     "", [T_AI, T_BATCH]),
    ("R2", "picker built from settings scrubs its keys", AI,
     "return cls(config, clients, tuple(settings.ai_keys.values()))",
     "return cls(config, clients, ())", [T_AI, T_SCORE, T_BATCH]),
    ("R3", "AI keys go through the header-safety validator", "engine/settings.py",
     '        "openai_key",\n        "xai_key",\n        "anthropic_key",\n', "",
     ["tests/test_settings.py", T_AI]),
    ("R5", "batch retries (retries=3)", BATCH, "run=run, retries=3,", "run=run, retries=0,",
     [T_BATCH]),
    ("R12", "projection counts output price", BATCH,
     "cost = (input_tokens * price.input + len(posts) * output * price.output) / Decimal(10**6)",
     "cost = (input_tokens * price.input) / Decimal(10**6)", [T_BATCH]),
    # --- the new fixes (a4c438f) ---
    ("F1", "B1: vote sorts counted mentions first", AI,
     "    mentions.sort(key=lambda m: (not m.counted, m.instrument_id is None, -(m.models or 0)))\n",
     "", [T_AI, T_SCORE, T_BATCH]),
    ("F2", "B1: vote keeps one mention per name", AI,
     "    return Vote(market_link, unique_names(mentions), len(ok), fallback=False)",
     "    return Vote(market_link, tuple(mentions), len(ok), fallback=False)",
     [T_AI, T_SCORE, T_BATCH]),
    ("F3", "B1: each model's mapped names deduped", AI,
     "                mapped[answer.provider] = unique_names(\n"
     "                    [await map_item(book, item, posted_at, add_new) for item in answer.items]\n"
     "                )",
     "                mapped[answer.provider] = tuple(\n"
     "                    [await map_item(book, item, posted_at, add_new) for item in answer.items]\n"
     "                )", [T_AI, T_SCORE, T_BATCH]),
    ("F4", "B1: record() refuses an answer naming one thing twice", RECORDS,
     "    if len(set(names)) != len(names):\n", "    if False:\n", [T_SCORE, T_AI, T_BATCH]),
    ("F5", "B1: record() writes every mention (not last-wins dict)", RECORDS,
     "        for m in answer.mentions\n    ]",
     "        for m in {m.normalized: m for m in answer.mentions}.values()\n    ]",
     [T_SCORE, T_AI, T_BATCH]),
    ("F6", "S1: the adder turns Alpaca errors into CountCheckFailed", SCORE,
     "        except (AlpacaError, httpx.HTTPError) as exc:", "        except DoesNotCount as exc:",
     [T_AI, T_SCORE, T_BATCH]),
    ("F7", "S1: map_item records count_check_failed", AI,
     "    except CountCheckFailed as exc:\n        log.warning(\"%s: %s\", ticker, exc)\n"
     "        return unmapped(\"count_check_failed\")\n",
     "    except ZeroDivisionError:\n        raise\n", [T_AI, T_SCORE, T_BATCH]),
    ("F8", "S1: ai-pick builds no Alpaca client without keys", BATCH,
     "        if listings is None and settings.alpaca_keys is not None:",
     "        if listings is None:", [T_BATCH]),
    ("F9", "S2: a billed failed reply keeps its cost", AI,
     "            client.provider, client.model, started, finished, reply, error=error, cost=cost",
     "            client.provider, client.model, started, finished, reply, error=error",
     [T_AI, T_BATCH]),
    ("F10", "S2: a billed failed reply keeps its body", AI,
     "            client.provider, client.model, started, finished, reply, error=error, cost=cost",
     "            client.provider, client.model, started, finished, None, error=error, cost=cost",
     [T_AI, T_BATCH]),
    ("F11", "S2: OpenAI finish_reason != stop is a problem", AI,
     '        elif choice.finish_reason != "stop":', "        elif False:", [T_AI, T_BATCH]),
    ("F12", "S2: Anthropic stop_reason != end_turn is a problem", AI,
     "            problem=None\n            if response.stop_reason == \"end_turn\"",
     "            problem=None\n            if True", [T_AI, T_BATCH]),
    ("F13", "S2: a reply's problem fails the answer", AI,
     "        if reply.problem:\n            raise InvalidAnswer(reply.problem)\n", "",
     [T_AI, T_BATCH]),
    ("F14", "S3: auth/permission/not-found/bad-request are fatal", AI,
     "            fatal = isinstance(exc, FATAL)", "            fatal = False", [T_AI, T_BATCH]),
    ("F15", "S3: record_ai stops on fatal before recording", SCORE,
     "    if stop_on_fatal and (fatal := [a for a in answer.answers if a.fatal]):",
     "    if False and (fatal := [a for a in answer.answers if a.fatal]):", [T_BATCH, T_SCORE]),
    ("F16", "S3: ai-pick asks record_ai to stop on fatal", BATCH,
     "                        stop_on_fatal=True,", "                        stop_on_fatal=False,",
     [T_BATCH]),
    ("F17", "S3: picker needs all three keys", AI,
     "        if missing := [f\"ENGINE_{p.upper()}_KEY\" for p in PROVIDERS if p not in clients]:",
     "        if not clients and (missing := [f\"ENGINE_{p.upper()}_KEY\" for p in PROVIDERS if p not in clients]):",
     [T_AI, T_SCORE, T_BATCH]),
    ("F18", "S3/C2: picker needs a ready version", AI,
     "        if problems := config.problems():\n            raise NotReady",
     "        if False and (problems := config.problems()):\n            raise NotReady",
     [T_AI, T_SCORE, T_BATCH]),
    ("F19", "S4: the worker checks names are synced at start", SCORE,
     "            await load_book(conn, rules)  # NamesNotSynced: fail here, not on every post",
     "            pass", [T_SCORE]),
    ("F20", "S5: a known ticker off its dates is not_listed_then", AI,
     "    if instrument_id is None and book.knows_ticker(ticker):",
     "    if False and book.knows_ticker(ticker):", [T_AI, T_SCORE, T_BATCH]),
    ("F21", "S5: book.add only for a new instrument", AI,
     "    if instrument_id is None:\n        book.add(listed)",
     "    if True:\n        book.add(listed)", [T_AI, T_SCORE, T_BATCH]),
    ("F22", "S5/S6: an unreviewed existing instrument is checked with Alpaca per post", SCORE,
     "            if not await listings.counts(ticker, asset, at):\n                return None\n", "",
     [T_AI, T_SCORE, T_BATCH]),
    ("F23", "S6: rules bare tickers only for reviewed instruments", RULES,
     "        if instrument_id is not None and instrument_id in book.reviewed:",
     "        if instrument_id is not None:", [T_RULES, T_AI, T_SCORE, T_BATCH]),
    ("F24", "S6: AI maps by ticker without Alpaca only for reviewed instruments", AI,
     "    if instrument_id is not None and instrument_id in book.reviewed:",
     "    if instrument_id is not None:", [T_AI, T_SCORE, T_BATCH]),
    ("F25", "S6: the seeded four are reviewed", RULES,
     "        reviewed = SEEDED | {spec.symbol for spec in rules.aliases}",
     "        reviewed = {spec.symbol for spec in rules.aliases}", [T_RULES, T_AI, T_SCORE, T_BATCH]),
    ("F26", "S7: numbers the post doesn't have are rejected", REASON,
     "    if made_up := set(NUMBER.findall(line)) - set(NUMBER.findall(words)):",
     "    if made_up := set():", [T_BATCH]),
    ("F27", "S7: a cut-off reason reply gives no line", REASON,
     "    if reply.problem:\n        log.warning(\"reason line: %s\", reply.problem)\n        return None\n",
     "", [T_BATCH]),
    ("F28", "S7: up/down/higher/lower...", REASON,
     '    r"up|down|higher|lower|increas\\w*|decreas\\w*|rais\\w*|doubl\\w*|halv\\w*|benefit\\w*|harm\\w*|"\n',
     "", [T_BATCH]),
    ("F29", "S8: keys out of the picker's repr", AI,
     "    secrets: Sequence[str] = field(default_factory=tuple, repr=False)",
     "    secrets: Sequence[str] = field(default_factory=tuple)", [T_AI, T_SCORE]),
    ("F30", "S9: OpenAI/xAI clients refuse redirects", AI,
     "http_client=http_client or openai.DefaultAsyncHttpxClient(follow_redirects=False),",
     "http_client=http_client,", [T_AI]),
    ("F31", "S9: Anthropic client refuses redirects", AI,
     "http_client=http_client or anthropic.DefaultAsyncHttpxClient(follow_redirects=False),",
     "http_client=http_client,", [T_AI]),
    ("F32", "N3: SDK header variables refused", AI,
     "    if found := [name for name in SDK_HEADER_VARIABLES if os.environ.get(name) is not None]:",
     "    if found := []:", [T_AI]),
    ("F33", "N1: spend limits must be finite and >= 0", "engine/cli.py",
     "    if not amount.is_finite() or amount < 0:", "    if False:", [T_BATCH]),
    ("F34", "N1: projection compared unrounded", BATCH, "        projected[provider] = cost\n",
     "        projected[provider] = cost.quantize(Decimal(\"0.01\"))\n", [T_BATCH]),
    ("F35", "N2: expected operator errors print one line", "engine/cli.py",
     "    except (similarity.ModelMissing, NamesNotSynced, RulesFileChanged, AlpacaError) as exc:",
     "    except similarity.ModelMissing as exc:", [T_BATCH, "tests/test_settings.py"]),
    ("F36", "N2: a missing --keys file is one line", "engine/cli.py",
     "    except OSError as exc:  # the --keys file", "    except KeyError as exc:  # the --keys file",
     [T_BATCH]),
    ("F37", "Q4: --max-total-usd refusal", BATCH,
     "    if max_total_usd is not None and so_far + projection.total > max_total_usd:",
     "    if False:", [T_BATCH]),
    ("F38", "Q4: --max-total-usd in-run stop", BATCH,
     "            if max_total_usd is not None and so_far + cost > max_total_usd:",
     "            if False:", [T_BATCH]),
    ("F39", "Q4: one ai-pick at a time", BATCH, "            if not held:", "            if False:",
     [T_BATCH]),
    ("F40", "Q2: refuse a version with other files", BATCH,
     "        if await other_prompt(conn, config):", "        if False:", [T_BATCH]),
    ("F41", "N13: run 2 only for posts with a run-1 answer", BATCH,
     "    if run != 1:\n        query = query.where(~_lacks(\"ai:vote\", version, 1))\n", "",
     [T_BATCH]),
    ("F42", "N8: rules finished_at after pick", SCORE,
     "    finished = datetime.now(UTC)\n    await record(conn, key, posted_at, rules_extraction(rules_pick, started, finished))",
     "    finished = started\n    await record(conn, key, posted_at, rules_extraction(rules_pick, started, finished))",
     [T_SCORE, T_BATCH]),
    ("F43", "N11: precision --window-start at New York midnight", "scripts/precision.py",
     "        start = datetime.combine(window_start, datetime.min.time(), NEW_YORK)",
     "        start = datetime.combine(window_start, datetime.min.time(), UTC)\n"
     "        from datetime import UTC  # noqa", ["tests/test_precision.py"]),
    ("F44", "N15: fetch-model sends the engine User-Agent", SIM,
     '        headers={"User-Agent": USER_AGENT},\n', "", [T_SIM]),
    ("F45", "N6: partial index on unfinished signals (both table and migration)",
     "engine/tables.py",
     "    Index(\"signals_unfinished_idx\", \"key\", postgresql_where=text(\"stage NOT IN ('done', 'error')\")),\n",
     "", ["tests/test_migrate.py", T_SCORE]),
    ("F46", "N9: a new instrument's name is its ticker", SCORE,
     "added = await add_instrument(conn, listings, ticker, ticker.upper(), asset, at)",
     "added = await add_instrument(conn, listings, ticker, 'model text', asset, at)",
     [T_AI, T_SCORE, T_BATCH]),
]


def main() -> None:
    only = set(sys.argv[1:])
    for mid, prop, rel, old, new, tests in MUTATIONS:
        if only and mid not in only:
            continue
        path = ROOT / rel
        original = path.read_text()
        if original.count(old) != 1:
            print(f"{mid} SNIPPET NOT FOUND ONCE ({original.count(old)}): {prop}", flush=True)
            continue
        path.write_text(original.replace(old, new))
        try:
            result = subprocess.run(
                [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=1200,
            )
        finally:
            path.write_text(original)
        tail = (result.stdout.strip().splitlines() or ["?"])[-1]
        verdict = "KILLED" if result.returncode != 0 else "SURVIVED"
        failed = [line for line in result.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{mid} {verdict}: {prop} | {tail} | {failed[0] if failed else ''}", flush=True)


if __name__ == "__main__":
    main()
