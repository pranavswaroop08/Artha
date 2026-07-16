"""Alembic env (item 6). Autogenerates against the configured Postgres/Timescale
DSN. Scaffold provides the migration SQL directly (no ORM models yet)."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

# DSN from env (or alembic.ini default). Never commit real creds.
URL = os.getenv("QUANT_DB_DSN", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", URL or "")

target_metadata = None  # schema managed via explicit SQL migrations


def run_migrations_offline() -> None:
    context.configure(url=URL, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not URL:
        raise RuntimeError("QUANT_DB_DSN not set; cannot run migrations.")
    engine = engine_from_config({"sqlalchemy.url": URL}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
