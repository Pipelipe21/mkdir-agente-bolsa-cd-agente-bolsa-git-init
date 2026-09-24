"""Encuentra el chat_id y se lo envía por Telegram a quien le haya escrito al bot.

Uso: escribe cualquier mensaje a tu bot y luego
    TELEGRAM_BOT_TOKEN=... uv run python -m jobs.telegram_setup

El chat_id no se imprime (los logs de GitHub Actions de un repo público son visibles).
"""

import json
import os
import re
import sys
import urllib.error

from notifier.telegram import API_URL, TelegramNotifier, _post_json


def find_chat_ids(updates: list[dict]) -> list[int]:
    ids: list[int] = []
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is not None and chat_id not in ids:
            ids.append(chat_id)
    return ids


TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")


def describe_token_shape(token: str) -> str:
    """Pistas sobre el formato sin revelar el token."""
    hints = [f"{len(token)} caracteres"]
    if token != token.strip():
        hints.append("tiene espacios o saltos de línea al inicio/fin")
    if " " in token.strip():
        hints.append("tiene espacios en medio (¿pegaste texto de más?)")
    if token.strip().lower().startswith("bot"):
        hints.append("empieza con 'bot' (pega solo el token, sin 'bot')")
    if ":" not in token:
        hints.append("no tiene ':' (un token se ve como 123456789:AAE...)")
    return "; ".join(hints)


def main() -> int:
    raw = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not raw:
        print("Falta el secret TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 1
    token = raw.strip()
    if token.lower().startswith("bot"):
        token = token[3:]
    if not TOKEN_RE.match(token):
        print(f"El secret no tiene formato de token: {describe_token_shape(raw)}", file=sys.stderr)
        return 1
    url = API_URL.replace("sendMessage", "getUpdates").format(token=token)
    try:
        result = _post_json(url, {})
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("description", "")
        except Exception:  # noqa: BLE001
            detail = ""
        reasons = {
            401: "token inválido o revocado (¿guardaste el token viejo en vez del nuevo?)",
            404: "token mal formado (¿se cortó al copiarlo?)",
            409: "el bot tiene un webhook activo; desactívalo o crea otro bot",
        }
        reason = reasons.get(exc.code, "error inesperado")
        print(f"Telegram respondió {exc.code}: {reason}. Detalle: {detail}", file=sys.stderr)
        return 1
    chat_ids = find_chat_ids(result.get("result", []))
    if not chat_ids:
        print("El bot no tiene mensajes recientes: escríbele 'hola' y vuelve a correr esto.")
        return 1
    for chat_id in chat_ids:
        TelegramNotifier(token, str(chat_id)).send(
            "✅ <b>Bot conectado</b>\n"
            f"Tu TELEGRAM_CHAT_ID es: <code>{chat_id}</code>\n\n"
            "Cópialo en GitHub → Settings → Secrets and variables → Actions → "
            "New repository secret, con el nombre TELEGRAM_CHAT_ID."
        )
    print(f"Listo: se envió el chat_id por Telegram a {len(chat_ids)} chat(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
