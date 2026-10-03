"""Market data: instruments and their aliases (engine schema), bars (prices schema).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("symbol", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("asset_class", sa.Text, nullable=False),
        sa.Column("calendar", sa.Text, nullable=False),
        sa.Column("alpaca_symbol", sa.Text, nullable=False, unique=True),
        sa.Column("benchmark_id", sa.Integer, sa.ForeignKey("engine.instruments.id")),
        sa.Column("rebased_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "asset_class IN ('stock', 'etf', 'coin')", name="instruments_asset_class_check"
        ),
        sa.CheckConstraint("calendar IN ('XNYS', '24/7')", name="instruments_calendar_check"),
        sa.CheckConstraint(
            "(asset_class = 'coin') = (calendar = '24/7')", name="instruments_coin_calendar_check"
        ),
        schema="engine",
    )
    # Benchmarks first: SPY for stocks and ETFs, BTC for coins.
    op.execute(
        """
        INSERT INTO engine.instruments (slug, symbol, name, asset_class, calendar, alpaca_symbol)
        VALUES ('spy', 'SPY', 'SPDR S&P 500 ETF Trust', 'etf', 'XNYS', 'SPY'),
               ('btc', 'BTC', 'Bitcoin', 'coin', '24/7', 'BTC/USD')
        """
    )
    op.execute(
        """
        INSERT INTO engine.instruments
            (slug, symbol, name, asset_class, calendar, alpaca_symbol, benchmark_id)
        VALUES
            ('qqq', 'QQQ', 'Invesco QQQ Trust', 'etf', 'XNYS', 'QQQ',
             (SELECT id FROM engine.instruments WHERE slug = 'spy')),
            ('eth', 'ETH', 'Ether', 'coin', '24/7', 'ETH/USD',
             (SELECT id FROM engine.instruments WHERE slug = 'btc'))
        """
    )

    op.create_table(
        "instrument_aliases",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        sa.Column("alias", sa.Text, nullable=False),
        sa.Column(
            "instrument_id", sa.Integer, sa.ForeignKey("engine.instruments.id"), nullable=False
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("valid_from", sa.Date),
        sa.Column("valid_to", sa.Date),
        sa.UniqueConstraint(
            "alias",
            "instrument_id",
            "kind",
            "valid_from",
            name="instrument_aliases_key",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("kind IN ('name', 'old_ticker')", name="instrument_aliases_kind_check"),
        sa.CheckConstraint("alias = lower(alias)", name="instrument_aliases_lowercase_check"),
        sa.CheckConstraint("valid_from <= valid_to", name="instrument_aliases_valid_check"),
        schema="engine",
    )

    op.create_table(
        "market_bars",
        sa.Column(
            "instrument_id", sa.Integer, sa.ForeignKey("engine.instruments.id"), nullable=False
        ),
        sa.Column("timeframe", sa.Text, nullable=False),
        sa.Column("bar_start", sa.DateTime(timezone=True), nullable=False),
        *(
            sa.Column(name, sa.Double, nullable=False)
            for name in ("open", "high", "low", "close", "volume")
        ),
        sa.Column("vwap", sa.Double),
        sa.Column("trades", sa.Integer),
        sa.Column("feed", sa.Text, nullable=False),
        sa.Column("adjustment", sa.Text, nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "bar_start", name="market_bars_pkey"),
        sa.CheckConstraint("timeframe IN ('1Min', '1Day')", name="market_bars_timeframe_check"),
        schema="prices",
    )


def downgrade() -> None:
    op.drop_table("market_bars", schema="prices")
    op.drop_table("instrument_aliases", schema="engine")
    op.drop_table("instruments", schema="engine")
