from datetime import UTC, datetime

import psycopg
import pytest

from core.db import PostgresRepository, apply_migrations
from core.executors import AlertExecutor
from core.models import Asset, AssetType, Direction, Signal
from jobs import radar

SPY = Asset("SPY", AssetType.STOCK)
BTC = Asset("BTC/USDT", AssetType.CRYPTO, "binance")
TS = datetime(2024, 1, 2, tzinfo=UTC)


def make_signal(asset=SPY, strategy="rsi") -> Signal:
    return Signal(asset, strategy, Direction.BUY, 0.7, "RSI cruzó bajo 30", TS)


class RecordingNotifier:
    channel = "test"

    def __init__(self):
        self.messages = []

    def send(self, text):
        self.messages.append(text)


def test_migrations_are_idempotent(db_conn):
    assert apply_migrations(db_conn) == []
    tables = {r[0] for r in db_conn.execute(
        "select tablename from pg_tables where schemaname = 'public'")}
    assert {"assets", "candles", "signals", "alerts", "trades"} <= tables


def test_rls_enabled_on_all_tables(db_conn):
    rows = db_conn.execute(
        "select relname from pg_class where relname in "
        "('assets','candles','signals','alerts','trades') and not relrowsecurity"
    ).fetchall()
    assert rows == []


def test_save_signal_assigns_id_and_dedupes(db_conn):
    repo = PostgresRepository(db_conn)
    first = repo.save_signal(make_signal())
    assert first.id is not None
    assert repo.save_signal(make_signal()) is None  # misma vela, misma estrategia
    assert repo.save_signal(make_signal(strategy="bollinger")).id != first.id


def test_asset_reused_across_instances(db_conn):
    PostgresRepository(db_conn).save_signal(make_signal(BTC))
    PostgresRepository(db_conn).save_signal(make_signal(BTC, "bollinger"))
    count = db_conn.execute("select count(*) from assets").fetchone()[0]
    assert count == 1


def test_alert_executor_records_alert(db_conn):
    repo = PostgresRepository(db_conn)
    notifier = RecordingNotifier()
    signal = repo.save_signal(make_signal())
    AlertExecutor(notifier, context=lambda s: "• contexto", repo=repo).execute(signal)
    row = db_conn.execute("select signal_id, channel, llm_summary from alerts").fetchone()
    assert row == (signal.id, "test", "• contexto")


def test_save_alert_requires_saved_signal(db_conn):
    with pytest.raises(ValueError):
        PostgresRepository(db_conn).save_alert(make_signal(), "test", None)


def test_constraints_reject_bad_data(db_conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        db_conn.execute(
            "insert into trades (mode, side, qty, price, ts) values ('real', 'buy', 1, 1, now())"
        )


def test_run_does_not_repeat_alerts(db_conn, monkeypatch):
    monkeypatch.setattr(radar, "scan_asset", lambda asset, tf: [make_signal(asset)])
    repo = PostgresRepository(db_conn)
    notifier = RecordingNotifier()
    executor = AlertExecutor(notifier, repo=repo)
    radar.run([SPY, BTC], executor, notifier, repo=repo)
    radar.run([SPY, BTC], executor, notifier, repo=repo)  # segunda corrida, mismas velas
    assert len(notifier.messages) == 2
    assert db_conn.execute("select count(*) from alerts").fetchone()[0] == 2
