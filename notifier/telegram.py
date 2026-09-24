"""Envío de mensajes por Telegram (Bot API) usando solo la librería estándar."""

import html
import json
import urllib.request
from collections.abc import Callable
from typing import Protocol

from core.models import Direction, Signal

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier(Protocol):
    def send(self, text: str) -> None: ...


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, post: Callable[[str, dict], dict] = _post_json):
        if not token or not chat_id:
            raise ValueError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        self._url = API_URL.format(token=token)
        self._chat_id = chat_id
        self._post = post

    def send(self, text: str) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        result = self._post(self._url, payload)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram rechazó el mensaje: {result.get('description')}")


class ConsoleNotifier:
    """Imprime en vez de enviar. Para pruebas locales (--dry-run)."""

    def send(self, text: str) -> None:
        print(text, end="\n\n")


def format_signal(signal: Signal, context: str | None = None) -> str:
    icon, label = ("🟢", "COMPRA") if signal.direction is Direction.BUY else ("🔴", "VENTA")
    asset = signal.asset
    text = (
        f"{icon} <b>{label} · {html.escape(asset.symbol)}</b> ({asset.type})\n"
        f"Estrategia: <code>{html.escape(signal.strategy)}</code> · fuerza {signal.strength:.2f}\n"
        f"{html.escape(signal.reason)}\n"
        f"Vela: {signal.ts:%Y-%m-%d %H:%M} UTC"
    )
    if context:
        text += (
            "\n\n📰 <b>Contexto</b> (resumen de noticias con IA, no es recomendación)\n"
            f"{html.escape(context)}"
        )
    return text
