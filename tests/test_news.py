from datetime import UTC, datetime
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from core.data.news import Headline, news_symbol, parse_news
from core.executors import AlertExecutor
from core.llm import NewsSummarizer, build_prompt
from core.models import Asset, AssetType, Direction, Signal
from notifier import format_signal

BTC = Asset("BTC/USDT", AssetType.CRYPTO, "binance")
SIGNAL = Signal(BTC, "rsi", Direction.BUY, 0.7, "RSI cruzó bajo 30 (24.3)",
                datetime(2024, 1, 2, tzinfo=UTC))
HEADLINES = [Headline("Bitcoin cae tras datos de inflación", "Reuters", "Resumen breve")]


# --- Noticias ---

def test_news_symbol():
    assert news_symbol(BTC) == "BTC-USD"
    assert news_symbol(Asset("SPY", AssetType.STOCK)) == "SPY"


def test_parse_news_new_and_old_formats():
    items = [
        {"content": {"title": "Nuevo", "summary": "s", "pubDate": "2024-01-02T10:00:00Z",
                     "provider": {"displayName": "Yahoo"}}},
        {"title": "Antiguo", "publisher": "Reuters", "providerPublishTime": 1704189600},
        {"content": {"title": ""}},  # sin título: se descarta
    ]
    parsed = parse_news(items)
    assert [h.title for h in parsed] == ["Nuevo", "Antiguo"]
    assert parsed[0].publisher == "Yahoo" and parsed[0].published.year == 2024
    assert parsed[1].publisher == "Reuters" and parsed[1].published.tzinfo is not None


def test_build_prompt_includes_signal_and_headlines():
    prompt = build_prompt(SIGNAL, HEADLINES)
    assert "BTC/USDT" in prompt and "RSI cruzó bajo 30" in prompt
    assert "Bitcoin cae tras datos de inflación" in prompt and "Reuters" in prompt


# --- Resumidor ---

def text_response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )


class FakeClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.calls = []
        self._response, self._error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def test_summarizer_returns_text_and_caches_per_asset():
    client = FakeClient(text_response("• La caída sigue a datos de inflación."))
    summarize = NewsSummarizer(client, lambda asset: HEADLINES)
    assert summarize(SIGNAL) == "• La caída sigue a datos de inflación."
    assert summarize(SIGNAL) == "• La caída sigue a datos de inflación."
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "claude-opus-5" and call["fallbacks"] == "default"


def test_summarizer_skips_call_without_headlines():
    client = FakeClient(text_response("x"))
    assert NewsSummarizer(client, lambda asset: [])(SIGNAL) is None
    assert client.calls == []


def test_summarizer_survives_news_fetch_error():
    def boom(asset):
        raise ConnectionError("sin red")

    assert NewsSummarizer(FakeClient(text_response("x")), boom)(SIGNAL) is None


def test_summarizer_handles_refusal():
    client = FakeClient(text_response("", stop_reason="refusal"))
    assert NewsSummarizer(client, lambda asset: HEADLINES)(SIGNAL) is None


@pytest.mark.parametrize("status", [401, 429, 500])
def test_summarizer_handles_api_errors(status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    error = {401: anthropic.AuthenticationError, 429: anthropic.RateLimitError}.get(
        status, anthropic.InternalServerError
    )("error", response=response, body=None)
    assert NewsSummarizer(FakeClient(error=error), lambda asset: HEADLINES)(SIGNAL) is None


def test_summarizer_handles_connection_error():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=request)
    assert NewsSummarizer(FakeClient(error=error), lambda asset: HEADLINES)(SIGNAL) is None


# --- Integración con la alerta ---

def test_format_signal_with_context_is_escaped():
    text = format_signal(SIGNAL, "• Caída <fuerte>")
    assert "📰" in text and "no es recomendación" in text and "&lt;fuerte&gt;" in text


def test_alert_executor_adds_context():
    sent = []
    notifier = SimpleNamespace(send=sent.append)
    AlertExecutor(notifier, context=lambda s: "• contexto").execute(SIGNAL)
    assert "• contexto" in sent[0]
