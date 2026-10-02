"""History in batch: extract, embed, ai-pick (and its cost guard) and review-list; and the
reason line's check."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import PROVIDERS, AiPicker, Client
from engine.extract.batch import (
    Selection,
    review_list,
    run_ai_pick,
    run_embed,
    run_extract,
)
from engine.extract.reason import check_reason, reason_line
from engine.extract.rules import current_rules
from engine.extract.score import Scorer
from engine.feeds.posts import Post
from engine.feeds.store import insert_signals, trump_source_id
from engine.settings import Settings
from engine.tables import extractions, signal_embeddings, signal_mentions, signals
from tests.extract_helpers import (
    CountsAll,
    StubClient,
    StubEmbedder,
    answer,
    ready_config,
    sync_names,
)
from tests.feeds_helpers import status_id_at

WHEN = datetime(2024, 5, 6, 15, tzinfo=UTC)
TEXTS = [
    "Apple is building a great plant",
    "The chip company in Santa Clara is doing great things",
    "https://truthsocial.com/x",  # links only: no words
    "Happy Easter to all!",
]


async def store_history(db: AsyncEngine, texts: list[str] = TEXTS) -> list[Post]:
    posts = [
        Post(status_id_at(WHEN + timedelta(hours=n), n), "post", None, words, False, {})
        for n, words in enumerate(texts, 1)
    ]
    async with db.begin() as conn:
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)
    return posts


async def count(db: AsyncEngine, table: object, *where: object) -> int:
    async with db.connect() as conn:
        query = select(func.count()).select_from(table).where(*where)  # type: ignore[arg-type]
        return int((await conn.execute(query)).scalar_one())


def stub_picker() -> AiPicker:
    nvidia = answer(True, ("Nvidia", "NVDA", "stock", "implied"))
    chip_post = {TEXTS[1]: nvidia}
    clients: dict[str, Client] = {p: StubClient(p, answers=chip_post) for p in PROVIDERS}
    return AiPicker(ready_config(), clients)


async def test_extract_is_idempotent_per_rules_version(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    await store_history(db)
    said: list[str] = []
    assert await run_extract(migrated, said.append) == 0
    assert await count(db, extractions) == len(TEXTS)
    mentions = await count(db, signal_mentions)
    assert await run_extract(migrated, said.append) == 0
    assert (await count(db, extractions), await count(db, signal_mentions)) == (
        len(TEXTS),
        mentions,
    )
    assert said[-1].startswith("rules v1: extracted 0 posts")


async def test_embed_resumes_and_skips_posts_without_words(
    migrated: Settings, db: AsyncEngine
) -> None:
    await store_history(db)
    said: list[str] = []
    assert await run_embed(migrated, said.append, StubEmbedder()) == 0
    assert await count(db, signal_embeddings) == len(TEXTS) - 1
    assert "1 without words skipped" in said[-1]
    assert await run_embed(migrated, said.append, StubEmbedder()) == 0
    assert "embedded 0 posts" in said[-1]


async def test_ai_pick_refuses_a_run_over_max_usd(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    posts = await store_history(db)
    picker = stub_picker()
    said: list[str] = []
    refused = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal("0.001"),
        say=said.append, picker=picker, listings=CountsAll(),
    )  # fmt: skip
    assert refused == 1
    assert said[0] == (
        "4 posts (1 without words, not asked); projected $0.03 "
        "(openai $0.01, anthropic $0.01); spent so far $0.00"
    )
    assert said[-1] == "refused: projected $0.03 is over --max-usd 0.001"
    assert await count(db, extractions) == 0
    assert all(not client.asked for client in picker.clients.values())  # type: ignore[attr-defined]


async def test_ai_pick_records_answers_and_a_rerun_asks_again_without_overwriting(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    chosen = Selection(start=WHEN.date(), end=WHEN.date())
    said: list[str] = []
    assert await run_ai_pick(migrated, Selection(), max_usd=Decimal(5), say=said.append) == 2
    picker = stub_picker()
    done = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append, picker=picker, listings=CountsAll()
    )
    assert done == 0
    asked = 2 * (len(posts) - 1)
    assert await count(db, extractions, extractions.c.method.like("ai:%")) == asked + len(posts)
    assert said[-1] == "spent so far $0.016800"  # 6 answers of 1,000 tokens in and 100 out

    again = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=said.append, picker=picker, listings=CountsAll()
    )
    assert again == 0 and said[-1].startswith("0 posts")
    assert await count(db, extractions) == asked + 2 * len(posts)

    mentions = await count(db, signal_mentions)
    rerun = await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), run=2, say=said.append, picker=picker,
        listings=CountsAll(),
    )  # fmt: skip
    assert rerun == 0
    assert await count(db, extractions, extractions.c.run == 2) == asked + len(posts)
    assert await count(db, signal_mentions) == mentions  # run 2 writes no mentions


async def test_ai_pick_stops_once_a_run_costs_more_than_max_usd(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    wordy: dict[str, Client] = {p: StubClient(p, output_tokens=50_000) for p in PROVIDERS}
    said: list[str] = []
    stopped = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal("0.5"),
        say=said.append, picker=AiPicker(ready_config(), wordy),
        listings=CountsAll(),
    )  # fmt: skip
    assert stopped == 1  # projected $0.03, but the first post's answers cost $0.804
    assert said[-1] == "stopped after 1 posts: this run cost $0.804000, over --max-usd"
    assert await count(db, extractions, extractions.c.method == "ai:vote") == 1


async def test_review_list_shows_names_the_vote_counted_that_the_rules_missed(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    await store_history(db)
    chosen = Selection(start=WHEN.date(), end=WHEN.date())
    await run_ai_pick(
        migrated, chosen, max_usd=Decimal(5), say=lambda line: None, picker=stub_picker(),
        listings=CountsAll(),
    )  # fmt: skip
    async with db.connect() as conn:
        lines = await review_list(conn, 1, ready_config().version)
    assert lines == [
        "rules v1 missed, AI v1 vote counted:",
        "  NVDA   'nvidia' (ai_implied): 1 posts",
        "named by both models, not mapped:",
    ]


async def test_ai_pick_stops_on_a_bad_key_with_nothing_recorded(
    migrated: Settings, db: AsyncEngine
) -> None:
    import openai

    await sync_names(db)
    posts = await store_history(db)
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    revoked = openai.AuthenticationError(
        "Incorrect API key", response=httpx.Response(401, request=request), body=None
    )
    clients: dict[str, Client] = {p: StubClient(p) for p in PROVIDERS}
    clients["openai"] = StubClient("openai", fail=revoked)
    said: list[str] = []
    stopped = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
        say=said.append, picker=AiPicker(ready_config(), clients), listings=CountsAll(),
    )  # fmt: skip
    assert stopped == 1
    assert said[-1] == (
        f"stopped at {posts[0].key}, not recorded: openai (stub-model): "
        "AuthenticationError: Incorrect API key"
    )
    assert await count(db, extractions) == 0
    assert len(clients["anthropic"].asked) == 1  # type: ignore[attr-defined]
    fixed = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5),
        say=said.append, picker=stub_picker(), listings=CountsAll(),
    )  # fmt: skip
    assert fixed == 0
    assert await count(db, extractions, extractions.c.method == "ai:vote") == len(posts)


async def test_ai_pick_without_alpaca_keys_records_new_names_unmapped(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    nucor = answer(True, ("Nucor", "NUE", "stock", "implied"))
    clients: dict[str, Client] = {p: StubClient(p, default=nucor) for p in PROVIDERS}
    said: list[str] = []
    assert migrated.alpaca_keys is None
    done = await run_ai_pick(
        migrated, Selection(keys=[posts[0].key]), max_usd=Decimal(5), say=said.append,
        picker=AiPicker(ready_config(), clients),
    )  # fmt: skip
    assert done == 0
    assert "no Alpaca keys: tickers no rules version reviewed stay unmapped" in said
    async with db.connect() as conn:
        unmapped = (
            await conn.execute(
                select(signal_mentions.c.unmapped).join(extractions)
                .where(extractions.c.method == "ai:vote")
            )
        ).scalars().all()  # fmt: skip
    assert unmapped == ["not_an_instrument"]


async def test_ai_pick_retries_and_the_live_stage_does_not(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked_with: list[int] = []
    real_pick = AiPicker.pick

    async def spy(self: AiPicker, *args: Any, retries: int = 0, **kwargs: Any) -> Any:
        asked_with.append(retries)
        return await real_pick(self, *args, retries=retries, **kwargs)

    monkeypatch.setattr(AiPicker, "pick", spy)
    await sync_names(db)
    posts = await store_history(db)
    await run_ai_pick(
        migrated, Selection(keys=[posts[0].key]), max_usd=Decimal(5), say=lambda line: None,
        picker=stub_picker(), listings=CountsAll(),
    )  # fmt: skip
    scorer = Scorer(current_rules(), StubEmbedder(), stub_picker(), CountsAll())
    async with db.begin() as conn:
        row = (await conn.execute(select(signals).where(signals.c.key == posts[1].key))).one()
        await scorer.handle(conn, row)
    assert asked_with == [3, 0]


async def test_the_projection_counts_output_tokens(db: AsyncEngine) -> None:
    from dataclasses import replace

    from engine.extract.ai import ModelSpec, PostText, Price
    from engine.extract.batch import project_cost

    output_only = Price(Decimal(0), Decimal(0), Decimal(8), WHEN.date())
    config = ready_config()
    config = replace(config, models={p: ModelSpec("m", output_only, 0.0) for p in PROVIDERS})
    async with db.connect() as conn:
        projection = await project_cost(conn, config, [PostText("Tariffs")], list(PROVIDERS))
    assert projection.total > 0
    assert all(cost > 0 for cost in projection.by_provider.values())


async def test_ai_pick_keeps_to_the_total_limit(migrated: Settings, db: AsyncEngine) -> None:
    await sync_names(db)
    posts = await store_history(db)
    keys = Selection(keys=[p.key for p in posts])
    said: list[str] = []
    refused = await run_ai_pick(
        migrated, keys, max_usd=Decimal(5), max_total_usd=Decimal("0.01"), say=said.append,
        picker=stub_picker(), listings=CountsAll(),
    )  # fmt: skip
    assert refused == 1
    assert said[-1] == "refused: spent so far plus projected is over --max-total-usd 0.01"
    wordy: dict[str, Client] = {p: StubClient(p, output_tokens=50_000) for p in PROVIDERS}
    stopped = await run_ai_pick(
        migrated, keys, max_usd=Decimal(5), max_total_usd=Decimal("0.5"), say=said.append,
        picker=AiPicker(ready_config(), wordy), listings=CountsAll(),
    )  # fmt: skip
    assert stopped == 1  # projected $0.03, but the first post's answers cost $0.804
    assert said[-1] == "stopped after 1 posts: spent $0.804000, over --max-total-usd"


async def test_only_one_ai_pick_runs_at_a_time(migrated: Settings, db: AsyncEngine) -> None:
    from engine.extract.batch import AI_PICK_LOCK

    posts = await store_history(db)
    said: list[str] = []
    async with db.connect() as other:
        await other.execute(select(func.pg_advisory_lock(AI_PICK_LOCK)))
        busy = await run_ai_pick(
            migrated, Selection(keys=[posts[0].key]), max_usd=Decimal(5), say=said.append,
            picker=stub_picker(), listings=CountsAll(),
        )  # fmt: skip
        await other.execute(select(func.pg_advisory_unlock(AI_PICK_LOCK)))
    assert busy == 1 and said == ["another ai-pick is running; wait for it to finish"]


async def test_ai_pick_refuses_a_version_whose_files_changed(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    posts = await store_history(db)
    first = Selection(keys=[posts[0].key])
    await run_ai_pick(
        migrated, first, max_usd=Decimal(5), say=lambda line: None, picker=stub_picker(),
        listings=CountsAll(),
    )  # fmt: skip
    edited = stub_picker()
    edited = AiPicker(ready_config(hash="0" * 64), edited.clients)
    said: list[str] = []
    refused = await run_ai_pick(
        migrated, Selection(keys=[posts[1].key]), max_usd=Decimal(5), say=said.append,
        picker=edited, listings=CountsAll(),
    )  # fmt: skip
    assert refused == 2
    assert said == [
        "AI picker version 1 has answers recorded with other files; raise the version in ai.json"
    ]


async def test_a_stability_rerun_asks_only_posts_with_a_first_answer(
    migrated: Settings, db: AsyncEngine
) -> None:
    posts = await store_history(db)
    said: list[str] = []
    done = await run_ai_pick(
        migrated, Selection(keys=[p.key for p in posts]), max_usd=Decimal(5), run=2,
        say=said.append, picker=stub_picker(), listings=CountsAll(),
    )  # fmt: skip
    assert done == 0
    assert said[0] == (
        "4 of the 4 keys are skipped: not stored, not a text post, already answered "
        "or without a run-1 answer"
    )
    assert await count(db, extractions) == 0


# --- the reason line ---------------------------------------------------------------------------


POST = "Nvidia will build 4 chip plants in Arizona, a 500 billion dollar investment"


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("Names Nvidia's plans to build chip plants in Arizona", None),
        ("Names Nvidia's 4 chip plants and its 500 billion dollar plan", None),
        ("", "empty"),
        ("Two\nlines", "more than one line"),
        ("x" * 121, "121 characters, over 120"),
        ("Nvidia shares could rise on this", "direction"),
        ("Buy Apple", "direction"),
        ("A $500 billion plan", "amount"),
        ("Tariffs of 25 percent on steel", "amount"),
        ("You should look at Apple", "direction"),
        ("Steel tariffs could send Nucor higher", "direction"),
        ("Export curbs may push Nvidia lower", "direction"),
        ("Tariff relief could drive Ford up", "direction"),
        ("Drug price cuts may push Pfizer down", "direction"),
        ("New tariffs benefit US steel makers like Nucor", "direction"),
        ("Boeing orders may increase after the trade deal", "direction"),
        ("Chip export ban could cause Nvidia sales to decline", "direction"),
        ("Puts pressure on Apple's China supply chain", "direction"),
        ("A tailwind for Lockheed Martin and Northrop Grumman", "direction"),
        ("A headwind for Apple", "direction"),
        ("Bad news for Pfizer and Merck", "direction"),
        ("Strengthens the case for owning Exxon", "direction"),
        ("Expect Nvidia to outpace rivals", "direction"),
        ("Investors may want to watch Boeing", "direction"),
        ("Apple at 200 after the tariff news", "number the post doesn't have: 200"),
        ("Nvidia's 5 new plants", "number the post doesn't have: 5"),
        ("American Eagle benefits from its ad", "direction"),
        ("Imports harming the auto industry", "direction"),
    ],
)
def test_the_reason_line_check(line: str, problem: str | None) -> None:
    found = check_reason(line, 120, POST)
    assert (found is None) if problem is None else (problem in (found or "")), found


async def test_a_reason_line_that_fails_its_check_or_errors_is_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = ready_config()
    good = StubClient("anthropic", default="Names Nvidia's chip plants")
    assert await reason_line(good, config, "words", "companies", ["NVDA"]) == (
        "Names Nvidia's chip plants"
    )
    pushy = StubClient("anthropic", default="Nvidia should surge")
    broken = StubClient("anthropic", fail=RuntimeError("bad key sk-ant-secret"))
    with caplog.at_level(logging.WARNING):
        assert await reason_line(pushy, config, "words", "companies", ["NVDA"]) is None
        assert (
            await reason_line(
                broken, config, "words", "companies", ["NVDA"], secrets=["sk-ant-secret"]
            )
            is None
        )
    assert "rejected" in caplog.text and "sk-ant-secret" not in caplog.text


async def test_a_reason_line_that_is_cut_off_or_too_slow_is_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from dataclasses import replace

    quick = replace(ready_config(), timeout_seconds=0.05)
    slow = StubClient("anthropic", default="Names Nvidia's chip plants", delay=1.0)
    cut = StubClient("anthropic", default="Names Nvidia's", problem="stopped early: max_tokens")
    with caplog.at_level(logging.WARNING):
        assert await reason_line(slow, quick, "words", "companies", ["NVDA"]) is None
        assert await reason_line(cut, quick, "words", "companies", ["NVDA"]) is None
    assert "timeout after 0.05 s" in caplog.text and "max_tokens" in caplog.text


# --- the commands ------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["nan", "Infinity", "-1", "five"])
def test_spend_limits_must_be_amounts_of_zero_or_more(
    bad: str, capsys: pytest.CaptureFixture[str]
) -> None:
    from engine import cli

    for flag in ("--max-usd", "--max-total-usd"):
        with pytest.raises(SystemExit) as exited:
            cli.main(["ai-pick", "--from", "2025-01-01", flag, bad])
        assert exited.value.code == 2
        assert f"not an amount of 0 or more: {bad!r}" in capsys.readouterr().err


def test_expected_operator_errors_print_one_line(
    migrated: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Any,
) -> None:
    from engine import cli

    monkeypatch.setattr(cli, "configure_logging", lambda: None)  # keep pytest's
    monkeypatch.setenv("ENGINE_DATABASE_URL", migrated.db_url)
    for name in ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    missing = tmp_path / "no-such-keys.txt"
    cases = {
        ("extract",): "names from aliases.json are not in the database",
        ("sync-names",): "ALPACA_API_KEY_ID",
        ("ai-pick", "--keys", str(missing)): f"ai-pick failed: [Errno 2] No such file or "
        f"directory: '{missing}'",
    }
    for argv, said in cases.items():
        assert cli.main(list(argv)) == 1, argv
        err = capsys.readouterr().err
        assert said in err and len(err.strip().splitlines()) == 1, err
