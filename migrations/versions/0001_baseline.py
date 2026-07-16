"""Baseline schema (item 6). Creates reference tables + TimescaleDB hypertables.

Run with:  alembic upgrade head   (requires a TimescaleDB instance)

Notes:
  * `symbols` is the unified NSE/BSE/ISIN master (reconciliation target).
  * `prices_eod` / `prices_intraday` are hypertables partitioned by trading_day.
  * `options_chain` stores full per-expiry chains; `vix` the India VIX series.
  * `corporate_actions` drives point-in-time total-return adjustments.
  * Continuous aggregates precompute daily rollups for fast feature queries.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION


def upgrade() -> None:
    # ---- reference tables ----
    op.create_table(
        "symbols",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("nse_ticker", sa.String(32), nullable=False, unique=True),
        sa.Column("bse_code", sa.String(32)),
        sa.Column("isin", sa.String(12)),
        sa.Column("industry", sa.String(64)),
        sa.Column("series", sa.String(8), server_default="EQ"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_symbols_isin", "symbols", ["isin"])

    # ---- time-series tables (hypertables added below) ----
    op.create_table(
        "prices_eod",
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("open", DOUBLE_PRECISION(), nullable=False),
        sa.Column("high", DOUBLE_PRECISION(), nullable=False),
        sa.Column("low", DOUBLE_PRECISION(), nullable=False),
        sa.Column("close", DOUBLE_PRECISION(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("delivery_pct", DOUBLE_PRECISION()),
        sa.Column("adjusted_close", DOUBLE_PRECISION()),
        sa.Column("as_of_ts", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("symbol", "trading_day"),
    )
    op.create_table(
        "prices_intraday",
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("open", DOUBLE_PRECISION()),
        sa.Column("high", DOUBLE_PRECISION()),
        sa.Column("low", DOUBLE_PRECISION()),
        sa.Column("close", DOUBLE_PRECISION()),
        sa.Column("volume", sa.BigInteger()),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )
    op.create_table(
        "options_chain",
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("strike", DOUBLE_PRECISION(), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),  # CE/PE
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("oi", sa.BigInteger()),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("iv", DOUBLE_PRECISION()),
        sa.Column("last_price", DOUBLE_PRECISION()),
        sa.PrimaryKeyConstraint("symbol", "expiry", "strike", "option_type", "trading_day"),
    )
    op.create_table(
        "vix",
        sa.Column("trading_day", sa.Date(), primary_key=True),
        sa.Column("close", DOUBLE_PRECISION(), nullable=False),
        sa.Column("open", DOUBLE_PRECISION()),
        sa.Column("high", DOUBLE_PRECISION()),
        sa.Column("low", DOUBLE_PRECISION()),
    )
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.String(16)),  # SPLIT/BONUS/DIVIDEND
        sa.Column("ratio", DOUBLE_PRECISION()),
        sa.Column("dividend", DOUBLE_PRECISION()),
        sa.Column("disclosure_ts", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_ca_symbol", "corporate_actions", ["symbol", "ex_date"])

    # ---- TimescaleDB hypertables ----
    op.execute("SELECT create_hypertable('prices_eod', 'trading_day');")
    op.execute("SELECT create_hypertable('prices_intraday', 'ts');")
    op.execute("SELECT create_hypertable('options_chain', 'trading_day');")

    # ---- continuous aggregate: daily EOD rollup (fast feature scans) ----
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS vw_daily_rollup
        WITH (timescaledb.continuous) AS
        SELECT symbol,
               time_bucket('1 day', trading_day) AS day,
               last(close, trading_day) AS close,
               sum(volume) AS volume
        FROM prices_eod
        GROUP BY symbol, day;
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS vw_daily_rollup;")
    for t in ("corporate_actions", "vix", "options_chain",
              "prices_intraday", "prices_eod", "symbols"):
        op.execute(f"DROP TABLE IF EXISTS {t};")
