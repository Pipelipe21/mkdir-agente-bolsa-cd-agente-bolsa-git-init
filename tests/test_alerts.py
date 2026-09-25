from datetime import UTC, datetime

import pandas as pd
import pytest

from core.data import drop_incomplete, parse_timeframe
from core.executors import AlertExecutor, build_executor
from core.models import Asset, AssetType, Direction, ExecutionMode, Signal
from jobs import radar
from notifier import TelegramNotifier, format_signal

ASSET = Asset("BTC/USDT", AssetType.CRYPTO, "binance")


def make_signal(direction=Direction.BUY, reason="RSI cruzó bajo 30 (24.3)") -> Signal:
    return Signal(ASSET, "rsi", direction, 0.72, reason, datetime(2024, 1, 2, tzinfo=UTC))


class RecordingNotifier:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


# --- Formato y Telegram ---

def test_format_signal_contents():
    text = format_signal(make_signal())
    assert "🟢" in text and "COMPRA" in text and "BTC/USDT" in text
    assert "fuerza 0.72" in text and "2024-01-02 00:00 UTC" in text
    assert "🔴" in format_signal(make_signal(Direction.SELL))


def test_format_signal_escapes_html():
    assert "&lt;30" in format_signal(make_signal(reason="RSI <30"))


def test_telegram_notifier_posts_payload():
    calls = []
    notifier = TelegramNotifier("TOKEN", "123", post=lambda url, p: calls.append((url, p)) or {"ok": True})
    notifier.send("hola")
    url, payload = calls[0]
    assert url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert payload["chat_id"] == "123" and payload["text"] == "hola"


def test_telegram_notifier_raises_on_error():
    notifier = TelegramNotifier("T", "1", post=lambda url, p: {"ok": False, "description": "bad"})
    with pytest.raises(RuntimeError, match="bad"):
        notifier.send("x")


def test_telegram_notifier_requires_credentials():
    with pytest.raises(ValueError):
        TelegramNotifier("", "")


# --- Executors ---

def test_alert_executor_sends_and_returns_no_trade():
    notifier = RecordingNotifier()
    assert AlertExecutor(notifier).execute(make_signal()) is None
    assert len(notifier.messages) == 1


def test_build_executor_only_alert_for_now():
    assert isinstance(build_executor(ExecutionMode.ALERT, RecordingNotifier()), AlertExecutor)
    with pytest.raises(NotImplementedError):
        build_executor(ExecutionMode.PAPER, RecordingNotifier())


# --- Velas incompletas ---

def test_parse_timeframe():
    assert parse_timeframe("4h") == pd.Timedelta(hours=4)
    assert parse_timeframe("1wk") == pd.Timedelta(weeks=1)
    with pytest.raises(ValueError):
        parse_timeframe("abc")


def test_drop_incomplete_removes_open_candle():
    idx = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    candles = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=idx)
    now = datetime(2024, 1, 3, 12, tzinfo=UTC)  # la vela del 3 sigue abierta
    assert drop_incomplete(candles, "1d", now).index[-1] == pd.Timestamp("2024-01-02", tz="UTC")


# --- Job ---

def test_run_continues_after_asset_error(monkeypatch):
    good, bad = Asset("SPY", AssetType.STOCK), Asset("FAIL", AssetType.STOCK)

    def fake_scan(asset, timeframe):
        if asset is bad:
            raise ConnectionError("sin red")
        return [make_signal()]

    monkeypatch.setattr(radar, "scan_asset", fake_scan)
    notifier = RecordingNotifier()
    code = radar.run([bad, good], AlertExecutor(notifier), notifier)
    assert code == 0
    assert any("COMPRA" in m for m in notifier.messages)
    assert any("FAIL: ConnectionError" in m for m in notifier.messages)


def test_run_fails_when_every_asset_fails(monkeypatch):
    monkeypatch.setattr(radar, "scan_asset", lambda a, t: (_ for _ in ()).throw(OSError()))
    notifier = RecordingNotifier()
    assert radar.run([ASSET], AlertExecutor(notifier), notifier) == 1


class FailingRepo:
    def save_signal(self, signal):
        raise ConnectionError("db caída")

    def save_alert(self, signal, channel, llm_summary):
        raise AssertionError("no debería llamarse: la señal no tiene id")


def test_run_still_alerts_when_db_fails(monkeypatch):
    monkeypatch.setattr(radar, "scan_asset", lambda a, t: [make_signal(), make_signal(Direction.SELL)])
    notifier = RecordingNotifier()
    repo = FailingRepo()
    code = radar.run([ASSET], AlertExecutor(notifier, repo=repo), notifier, repo=repo)
    assert code == 0  # hubo errores de DB, pero el activo se escaneó
    assert sum("COMPRA" in m or "VENTA" in m for m in notifier.messages) == 2
    assert any("DB BTC/USDT" in m for m in notifier.messages)


class FlakyNotifier(RecordingNotifier):
    """Falla en el primer envío y funciona en los siguientes."""

    def __init__(self):
        super().__init__()
        self.failed = False

    def send(self, text):
        if not self.failed:
            self.failed = True
            raise ConnectionError("telegram caído")
        super().send(text)


def test_run_continues_and_fails_when_an_alert_cannot_be_sent(monkeypatch):
    monkeypatch.setattr(radar, "scan_asset", lambda a, t: [make_signal(), make_signal(Direction.SELL)])
    notifier = FlakyNotifier()
    code = radar.run([ASSET], AlertExecutor(notifier), notifier)
    assert code == 1  # para que Cloud Run reintente
    assert sum("VENTA" in m for m in notifier.messages) == 1  # la segunda señal sí salió
    assert any("Envío BTC/USDT/rsi" in m for m in notifier.messages)


def test_is_fresh_evaluates_each_daily_candle_once():
    from core.data import is_fresh

    friday = pd.Timestamp("2024-01-05 05:00", tz="UTC")  # vela diaria de acciones (00:00 NY)
    saturday_run = datetime(2024, 1, 6, 12, tzinfo=UTC)
    sunday_run = datetime(2024, 1, 7, 12, tzinfo=UTC)
    assert is_fresh(friday, "1d", saturday_run)
    assert not is_fresh(friday, "1d", sunday_run)  # fin de semana: no se repite

    crypto = pd.Timestamp("2024-01-06", tz="UTC")
    assert is_fresh(crypto, "1d", sunday_run)


def test_find_chat_ids_dedupes_and_ignores_non_messages():
    from jobs.telegram_setup import find_chat_ids

    updates = [
        {"message": {"chat": {"id": 42}}},
        {"message": {"chat": {"id": 42}}},
        {"edited_message": {"chat": {"id": 7}}},
        {"my_chat_member": {}},
    ]
    assert find_chat_ids(updates) == [42, 7]


def test_describe_token_shape_never_reveals_token():
    from jobs.telegram_setup import TOKEN_RE, describe_token_shape

    secret = "123456789:AAEabcdefghijklmnopqrstuvwxyz012345"
    assert TOKEN_RE.match(secret)
    hint = describe_token_shape(" bot" + secret + "\n")
    assert "AAE" not in hint and "123456789" not in hint
    assert "espacios" in hint


def test_summary_sent_when_no_alerts(monkeypatch):
    monkeypatch.setattr(radar, "scan_asset", lambda a, t: [])
    notifier = RecordingNotifier()
    assert radar.run([ASSET], AlertExecutor(notifier), notifier, summary=True) == 0
    assert notifier.messages == ["✅ Radar corrió: 1 activos, 0 alerta(s)"]
    silent = RecordingNotifier()
    radar.run([ASSET], AlertExecutor(silent), silent)
    assert silent.messages == []


def test_describe_url_classifies_without_revealing():
    from jobs.migrate import describe_url

    direct = describe_url("postgresql://postgres:s3cr3t@db.abcd.supabase.co:5432/postgres")
    assert "Direct" in direct and "s3cr3t" not in direct and "abcd" not in direct
    pooler = describe_url("postgresql://postgres.abcd:s3cr3t@aws-0-sa-east-1.pooler.supabase.com:5432/postgres")
    assert "Session pooler" in pooler
    assert "YOUR-PASSWORD" in describe_url("postgresql://u:[YOUR-PASSWORD]@h.pooler.supabase.com:5432/p")


def test_password_problem_detects_special_chars_without_revealing():
    from jobs.migrate import password_problem

    host = "aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
    msg = password_problem(f"postgresql://postgres.ab:abc@SECRETO9@{host}")
    assert msg and "@" in msg and "SECRETO9" not in msg
    assert password_problem(f"postgresql://postgres.ab:ab#cd@{host}")
    assert password_problem(f"postgresql://postgres.ab:Abc123xyz@{host}") is None
