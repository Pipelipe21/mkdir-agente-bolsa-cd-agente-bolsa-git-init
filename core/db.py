"""Persistencia en Postgres (Supabase) con psycopg.

Sin DATABASE_URL se usa NullRepository: el radar funciona igual, solo que sin historial
ni deduplicación.
"""

import logging
from pathlib import Path
from typing import Protocol

import psycopg

from core.models import Asset, Signal

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect(url: str) -> psycopg.Connection:
    # prepare_threshold=None: el pooler de Supabase (modo transacción) no soporta
    # prepared statements.
    return psycopg.connect(url, autocommit=True, prepare_threshold=None)


def apply_migrations(conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Aplica en orden los .sql que aún no están en schema_migrations. Devuelve los aplicados."""
    conn.execute(
        "create table if not exists schema_migrations ("
        " name text primary key, applied_at timestamptz not null default now())"
    )
    done = {row[0] for row in conn.execute("select name from schema_migrations")}
    applied = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
        applied.append(path.name)
        log.info("Migración aplicada: %s", path.name)
    return applied


class Repository(Protocol):
    def save_signal(self, signal: Signal) -> Signal | None:
        """Guarda la señal y la devuelve con id. None si esa señal ya existía (duplicada)."""

    def save_alert(self, signal: Signal, channel: str, llm_summary: str | None) -> None: ...


class NullRepository:
    """No guarda nada. Para --dry-run o cuando no hay base de datos configurada."""

    def save_signal(self, signal: Signal) -> Signal | None:
        return signal

    def save_alert(self, signal: Signal, channel: str, llm_summary: str | None) -> None:
        return None


class PostgresRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        self._asset_ids: dict[Asset, int] = {}

    def asset_id(self, asset: Asset) -> int:
        if asset not in self._asset_ids:
            row = self.conn.execute(
                """
                insert into assets (symbol, type, exchange) values (%s, %s, %s)
                on conflict (symbol, type, exchange) do update set symbol = excluded.symbol
                returning id
                """,
                (asset.symbol, asset.type.value, asset.exchange or ""),
            ).fetchone()
            self._asset_ids[asset] = row[0]
        return self._asset_ids[asset]

    def save_signal(self, signal: Signal) -> Signal | None:
        row = self.conn.execute(
            """
            insert into signals (asset_id, strategy, direction, strength, reason, ts)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (asset_id, strategy, direction, ts) do nothing
            returning id
            """,
            (
                self.asset_id(signal.asset),
                signal.strategy,
                signal.direction.value,
                signal.strength,
                signal.reason,
                signal.ts,
            ),
        ).fetchone()
        return None if row is None else signal.with_id(row[0])

    def save_alert(self, signal: Signal, channel: str, llm_summary: str | None) -> None:
        if signal.id is None:
            raise ValueError("La señal debe guardarse antes que su alerta")
        self.conn.execute(
            "insert into alerts (signal_id, channel, llm_summary) values (%s, %s, %s)",
            (signal.id, channel, llm_summary),
        )
