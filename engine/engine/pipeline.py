"""The live stages every new text post goes through, in one StageRunner on signals:
`score` (engine/extract/score.py), then `alert` (engine/alerts/stage.py), then done.

What both stages need is checked when the worker starts: the model files, the names, the
AI picker's files when it is live, the send rule's picker and instruments. If anything is
wrong the worker fails with a clear error (and the operator message every failed worker
sends), and posts wait where they are until a fixed deploy picks them up.
"""

import asyncio
from collections.abc import Callable
from contextlib import AsyncExitStack

from sqlalchemy import select

from engine.alerts.evidence import Evidencer, LivePool
from engine.alerts.send_rule import BadSendRule, SendRule, current_send_rule
from engine.alerts.stage import ALERT, Alerted, Alerter
from engine.extract.ai import AiPicker
from engine.extract.names import load_book
from engine.extract.rules import RulesFileChanged, current_rules
from engine.extract.score import Scored, Scorer, live_ai, other_files
from engine.extract.similarity import Embedder, load_embedder, load_match_rule
from engine.feeds.store import SCORE
from engine.market.alpaca import Alpaca
from engine.market.instruments import Listings
from engine.registry import EngineContext, WorkerFunc
from engine.settings import Settings
from engine.stages import Stage, StageRunner
from engine.tables import instruments, signals


def signals_worker(
    embedder_loader: Callable[[Settings], Embedder] = load_embedder,
    ai_loader: Callable[[Settings], AiPicker | None] = live_ai,
    observe_score: Callable[[Scored], None] | None = None,
    observe_alert: Callable[[Alerted], None] | None = None,
    send_rule: Callable[[], SendRule] = current_send_rule,
) -> WorkerFunc:
    """The worker build_registry() registers. Tests pass stub loaders."""

    async def run(ctx: EngineContext) -> None:
        settings = ctx.settings
        embedder = await asyncio.to_thread(embedder_loader, settings)  # ModelMissing: fail here
        rules, ai, rule = current_rules(), ai_loader(settings), send_rule()
        match = load_match_rule()
        if rule.picker == "ai" and ai is None:
            raise BadSendRule("send_rule.json's picker is ai, but the AI picker isn't live")
        async with ctx.db.connect() as conn:
            await load_book(conn, rules)  # NamesNotSynced: fail here, not on every post
            if ai is not None and (problem := await other_files(conn, ai.config)):
                raise RulesFileChanged(problem)
            slugs = set((await conn.execute(select(instruments.c.slug))).scalars())
            if missing := {p.instrument for p in rule.calls} - slugs - {"company"}:
                raise BadSendRule(f"send_rule.json calls on unknown instruments: {missing}")
            pool = await LivePool.load(conn, embedder.version)
        async with AsyncExitStack() as stack:
            listings = None
            if ai is not None and settings.alpaca_keys is not None:
                listings = Listings(await stack.enter_async_context(Alpaca(settings)))
            scorer = Scorer(rules, embedder, ai, listings, observe_score)
            alerter = Alerter(
                rule, rules.version, Evidencer(pool, match), embedder.version, ai, ctx.wake,
                observe_alert,
            )  # fmt: skip
            runner = StageRunner(
                ctx.db,
                signals,
                [Stage(SCORE, scorer.handle), Stage(ALERT, alerter.handle, alerter.after_commit)],
                max_attempts=settings.max_attempts,
            )
            while True:
                await runner.run_once()
                await asyncio.sleep(settings.score_tick_seconds)

    return run
