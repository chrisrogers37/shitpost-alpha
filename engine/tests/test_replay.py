"""The replay harness (tests/replay.py): recorded posts through `score` and `alert` with
stub models and a dry-run delivery, on a planted history, and the engine's time per post.

REPLAY_HISTORY_POSTS sets how many unrelated past posts fill the match pool (500 by
default; the PR's timings used 16,000, about the real history's text posts). The real
similarity model is used when its files are present; run with -s to see the report."""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.tables import challenger_calls, signals
from tests.alert_helpers import ReasonStub, stub_ai_clients
from tests.extract_helpers import ready_config, sync_names
from tests.replay import plant_history, recorded_posts, replay, replay_embedder
from tests.test_similarity import REAL_DIR

OTHERS = int(os.environ.get("REPLAY_HISTORY_POSTS", "500"))
SIMILAR = 60
"""Past posts close to each recorded one: more than the 50 a call keeps."""
P95_SECONDS = 5.0
"""The brief's bound on the engine's own time per post, at the 95th percentile."""


async def test_the_replay_runs_recorded_posts_through_score_and_alert(db: AsyncEngine) -> None:
    await sync_names(db)
    feeds = recorded_posts()
    assert all(feeds.values())
    embedder = replay_embedder(REAL_DIR)
    await plant_history(db, embedder, feeds, similar=SIMILAR, others=OTHERS)
    result = await replay(
        db, feeds, embedder=embedder, clients=stub_ai_clients(), config=ready_config()
    )
    print("\n".join(result.report()))

    assert result.posts and all(post.stage == "done" for post in result.posts)
    async with db.connect() as conn:
        not_scored = set(
            (
                await conn.execute(
                    select(signals.c.key).where(
                        signals.c.key.in_([post.key for post in result.posts]),
                        signals.c.not_scored.is_not(None),
                    )
                )
            ).scalars()
        )
        challenged = len((await conn.execute(select(challenger_calls.c.id))).all())
    scored = [post for post in result.posts if post.scored]
    assert {post.key for post in result.posts if not post.scored} == not_scored

    # The rules pick (send rule v1): an alert for each post they link to the market, all
    # FYI no_passing_pair, with the reason line; the AI's calls go to the challenger.
    alerts = {p.key: p.alerted.alert for p in scored if p.alerted and p.alerted.alert}
    linked = {p.key for p in scored if p.scored and p.scored.rules.market_link}
    assert alerts and set(alerts) == linked
    assert {(a.disposition, a.fyi_reason) for a in alerts.values()} == {("fyi", "no_passing_pair")}
    assert {a.reason for a in alerts.values()} == {ReasonStub.line}
    assert challenged == sum(1 for post in scored if post.alerted and post.alerted.challenger)

    # Each alert's evidence keeps the match rule's 50 of its 60 planted look-alikes (or of
    # other posts' look-alikes as close: the stub's vectors are all near one another).
    for alert in alerts.values():
        spy = next(c for c in alert.calls if c.instrument == "spy" and c.window == "1h")
        assert spy.evidence.matches == 50 and not spy.evidence.low_sample

    # The dry-run delivery read every alert's revision 1 once, in seq order.
    assert [r.seq for r in result.delivered] == list(range(1, len(alerts) + 1))
    assert {r.doc["signal_key"] for r in result.delivered} == set(alerts)

    assert len(result.timings()) == len(scored)
    assert result.percentile(95) < P95_SECONDS
