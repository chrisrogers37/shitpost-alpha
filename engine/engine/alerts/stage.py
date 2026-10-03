"""The live `alert` stage, after `score` on signals (engine/pipeline.py runs both).

For each scored post it reads both pickers' answers. The picker in use (send_rule.json)
makes the alert when it found a market link: its calls, their similar-post evidence, the
reason line when the AI is live, and send rule v1's decision. The other picker, the
challenger, gets the same calls and evidence in engine.challenger_calls, never sent.

A picker makes calls only on a post it gave a market link. Gate 0 counts a company pair's
call whenever the picker counted the company (its rule 1). The rules never count one
without a link, but the AI vote decides names and the link apart, so its live company
calls (as challenger now, or as the picker in use after Gate 0) cover fewer posts than
Gate 0 measured for it.

The alert and its revision 1 are written in the stage's one transaction, under the seq
lock (engine/alerts/store.py), whose time is the alert time; the wake hook rings after
the commit. A crash leaves the post at `alert` with nothing written, and the retry writes
the alert once: the unique alert per post makes a second one impossible.
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import Row, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.alerts.evidence import Drafted, Evidencer, Post, targets
from engine.alerts.model import AlertV1, Call, Instrument
from engine.alerts.public import check_public, quote
from engine.alerts.rule import Decided, decide
from engine.alerts.send_rule import Picker, SendRule
from engine.alerts.store import recently_sent, take_seq, write_alert
from engine.alerts.wake import Wake
from engine.backtest.evaluate import Pick
from engine.extract.ai import AiPicker
from engine.extract.reason import reason_line
from engine.extract.rules import OTHER
from engine.market import calendar
from engine.market.instruments import Instrument as Listed
from engine.market.instruments import all_instruments
from engine.notify import notify_operator
from engine.tables import (
    alerts,
    challenger_calls,
    extractions,
    instruments,
    signal_embeddings,
    signal_mentions,
)
from engine.text import has_words, normalize

log = logging.getLogger(__name__)

ALERT = "alert"
SEND_WINDOW = timedelta(minutes=15)
"""send_until is the post time plus this: later, nothing is sent (rule 5)."""


class NoAnswer(RuntimeError):
    """The picker in use has no answer for the post (it was scored with that picker off)."""


@dataclass(frozen=True)
class Answer:
    """One picker's answer for one post."""

    version: int
    pick: Pick


async def answers(
    conn: AsyncConnection, key: str, rules_version: int, ai: AiPicker | None
) -> dict[Picker, Answer]:
    """The rules' answer and, when the AI is live, the AI vote recorded with this
    version's files, each with the counted companies it named."""
    which = [and_(extractions.c.method == "rules", extractions.c.version == rules_version)]
    if ai is not None:
        which.append(
            and_(
                extractions.c.method == "ai:vote",
                extractions.c.version == ai.config.version,
                extractions.c.result["picker_hash"].astext == ai.config.hash,
            )
        )
    rows = (
        await conn.execute(
            select(
                extractions.c.id,
                extractions.c.method,
                extractions.c.version,
                extractions.c.market_link,
                extractions.c.topic,
            ).where(
                extractions.c.signal_key == key,
                extractions.c.run == 1,
                extractions.c.error.is_(None),
                or_(*which),
            )
        )
    ).all()
    companies: dict[int, set[int]] = {}
    if rows:
        named = await conn.execute(
            select(signal_mentions.c.extraction_id, signal_mentions.c.instrument_id)
            .join(instruments, instruments.c.id == signal_mentions.c.instrument_id)
            .where(
                signal_mentions.c.extraction_id.in_([row.id for row in rows]),
                signal_mentions.c.counted,
                instruments.c.asset_class == "stock",
            )
        )
        for extraction_id, instrument_id in named:
            companies.setdefault(extraction_id, set()).add(instrument_id)
    return {
        ("rules" if row.method == "rules" else "ai"): Answer(
            row.version,
            Pick(bool(row.market_link), frozenset(companies.get(row.id, ())), row.topic),
        )
        for row in rows
    }


async def post_vector(conn: AsyncConnection, key: str, model_version: str) -> Any:
    vector = (
        await conn.execute(
            select(signal_embeddings.c.vector).where(
                signal_embeddings.c.signal_key == key,
                signal_embeddings.c.model_version == model_version,
            )
        )
    ).scalar()
    return None if vector is None else np.frombuffer(vector, dtype="<f4")


async def database_time(conn: AsyncConnection) -> datetime:
    """The database clock now: clock_timestamp(), not now(), which is when the stage's
    transaction began."""
    now: datetime = (await conn.execute(select(func.clock_timestamp()))).scalar_one()
    return now


@dataclass(frozen=True)
class Alerted:
    """What the stage did for one post, for the replay harness and tests."""

    key: str
    alert: AlertV1 | None
    challenger: list[Call] | None
    seconds: dict[str, float] = field(default_factory=dict)


@dataclass
class Alerter:
    send_rule: SendRule
    rules_version: int
    evidencer: Evidencer
    model_version: str
    """The similarity model whose vectors the pool holds."""
    ai: AiPicker | None = None
    wake: Wake = field(default_factory=Wake)
    observe: Callable[[Alerted], None] | None = None
    """Called with each post's outputs before its transaction commits (the replay harness;
    the crash test stops the process there)."""

    async def handle(self, conn: AsyncConnection, row: Row[Any]) -> None:
        """The stage handler: runs in one transaction with the move to `done`."""
        seconds: dict[str, float] = {}
        clock = time.perf_counter()
        found = await answers(conn, row.key, self.rules_version, self.ai)
        if self.send_rule.picker not in found:
            raise NoAnswer(f"no {self.send_rule.picker} answer; was it scored with that off?")
        vector = await post_vector(conn, row.key, self.model_version)
        if not has_words(row.text):
            vector = None  # matches nothing, as in the backtest's sample
        drafted = await self._draft(conn, Post(row.key, row.posted_at, vector), found)
        seconds["evidence"], clock = time.perf_counter() - clock, time.perf_counter()

        topic = (found["rules"].pick.topic if "rules" in found else None) or OTHER
        reason = None
        if self.ai is not None and self.send_rule.picker in drafted:
            reason = await self._reason(row.text, topic, drafted[self.send_rule.picker])
            seconds["reason"], clock = time.perf_counter() - clock, time.perf_counter()

        alert, challenger = await self._write(conn, row, found, drafted, topic, reason)
        if vector is not None:
            self.evidencer.pool.add(row.key, row.posted_at, vector)
        seconds["write"] = time.perf_counter() - clock
        if self.observe:
            self.observe(Alerted(row.key, alert, challenger, seconds))

    async def _draft(
        self, conn: AsyncConnection, post: Post, found: Mapping[Picker, Answer]
    ) -> dict[Picker, list[Drafted]]:
        """Each picker with a market link: its calls (rule 1) with their evidence, as of the
        post's alert time (or the database clock now, if that is earlier)."""
        listed = {i.id: i for i in await all_instruments(conn)}
        calls = {
            picker: targets(self.send_rule, answer.pick, listed)
            for picker, answer in found.items()
            if answer.pick.market_link
        }
        if not calls:
            return {}
        return await self.evidencer.draft(conn, post, calls, listed, await database_time(conn))

    async def _reason(self, text: str, topic: str, drafted: Sequence[Drafted]) -> str | None:
        """The reason line, given the names of the instruments the post brings in itself
        (its companies, its topic's sector fund), not those of SPY, QQQ and BTC, which any
        market link calls: so a line never brings up Bitcoin by itself, and "500" from
        "S&P 500" is no number it may state. A line the public check refuses is dropped:
        the reason line fails closed, it never holds up an alert."""
        assert self.ai is not None
        own = (d.target.instrument.name for d in drafted if d.target.named_by_post)
        spec = self.ai.config.reason
        line = await reason_line(
            self.ai.clients[spec.provider], self.ai.config, normalize(text), topic,
            list(dict.fromkeys(own)), secrets=self.ai.secrets,
        )  # fmt: skip
        if line is not None and (problems := check_public({"reason": line})):
            log.warning("reason line dropped: %s", "; ".join(problems))
            return None
        return line

    async def _write(
        self,
        conn: AsyncConnection,
        row: Row[Any],
        found: Mapping[Picker, Answer],
        drafted: Mapping[Picker, Sequence[Drafted]],
        topic: str,
        reason: str | None,
    ) -> tuple[AlertV1 | None, list[Call] | None]:
        """The alert under the seq lock, whose time is the alert time, and the challenger's
        record at that time."""
        rule, send_until = self.send_rule, row.posted_at + SEND_WINDOW
        alert = challenger = None
        if not drafted:
            return None, None
        taken = await take_seq(conn) if rule.picker in drafted else None
        at = taken.at if taken else await database_time(conn)
        if taken is not None:
            mine = drafted[rule.picker]
            ids = {d.target.instrument.id for d in mine}
            recent = await recently_sent(conn, alerts.c.alerted_at, at, ids)
            decided = decide(mine, rule.passing[rule.picker], at, send_until, recent)
            alert = self._alert(
                row, found[rule.picker], decided, mine, topic, reason, at, send_until
            )
            await write_alert(
                conn,
                alert,
                taken,
                picker=rule.picker,
                picker_version=found[rule.picker].version,
                send_rule_version=rule.version,
                instrument_ids=ids,
                sent_instrument_ids=decided.sent_instrument_ids,
            )
        if rule.challenger in drafted:
            theirs = drafted[rule.challenger]
            challenger = await self._challenger(
                conn, row.key, found[rule.challenger], theirs, at, send_until
            )
        return alert, challenger

    def after_commit(self) -> None:
        self.wake.ring()

    def _alert(
        self,
        row: Row[Any],
        answer: Answer,
        decided: Decided,
        drafted: Sequence[Drafted],
        topic: str,
        reason: str | None,
        at: datetime,
        send_until: datetime,
    ) -> AlertV1:
        rule = self.send_rule
        shown = list({d.target.instrument.id: d.target.instrument for d in drafted}.values())
        lead = decided.lead
        return AlertV1(
            public_id=row.public_id,
            signal_key=row.key,
            posted_at=row.posted_at,
            alerted_at=at,
            send_until=send_until,
            excerpt=quote(row.text),
            topic=topic,
            picker=f"{rule.picker} v{answer.version}",
            send_rule=f"v{rule.version}",
            reason=reason,
            market_open=market_open(lead.target.instrument, at) if lead else calendar.is_open(at),
            disposition="sent" if decided.disposition == "sent" else "fyi",
            fyi_reason=decided.fyi_reason,
            lead=f"{lead.target.instrument.slug}:{lead.target.pair.window}" if lead else None,
            instruments=[
                Instrument(
                    slug=i.slug,
                    symbol=i.symbol,
                    asset_class=i.asset_class,
                    market_open=market_open(i, at),
                )
                for i in shown
            ],
            calls=decided.calls,
        )

    async def _challenger(
        self,
        conn: AsyncConnection,
        key: str,
        answer: Answer,
        drafted: Sequence[Drafted],
        at: datetime,
        send_until: datetime,
    ) -> list[Call] | None:
        """The challenger's calls, judged against its own passing pairs and its own sends,
        stored apart. A retried stage writes nothing more. Calls the public check refuses
        aren't recorded (one operator message), and the alert goes ahead without them."""
        picker = self.send_rule.challenger
        ids = {d.target.instrument.id for d in drafted}
        recent = await recently_sent(conn, challenger_calls.c.created_at, at, ids)
        decided = decide(drafted, self.send_rule.passing[picker], at, send_until, recent)
        calls = [call.model_dump(mode="json") for call in decided.calls]
        if problems := check_public({"calls": calls}):
            refused = "; ".join(problems)
            await notify_operator("challenger_not_public", f"{key}: not recorded: {refused}")
            return None
        await conn.execute(
            insert(challenger_calls)
            .values(
                signal_key=key,
                picker=picker,
                picker_version=answer.version,
                created_at=at,
                disposition=decided.disposition,
                fyi_reason=decided.fyi_reason,
                instrument_ids=sorted(ids),
                sent_instrument_ids=sorted(decided.sent_instrument_ids),
                calls=calls,
            )
            .on_conflict_do_nothing(constraint="challenger_calls_signal_key_picker_key")
        )
        return decided.calls


def market_open(instrument: Listed, at: datetime) -> bool:
    """Coins trade all the time; stocks and ETFs in the regular session."""
    return instrument.is_coin or calendar.is_open(at)
