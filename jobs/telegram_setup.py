"""Encuentra el chat_id y se lo envía por Telegram a quien le haya escrito al bot.

Uso: escribe cualquier mensaje a tu bot y luego
    TELEGRAM_BOT_TOKEN=... uv run python -m jobs.telegram_setup

El chat_id no se imprime (los logs de GitHub Actions de un repo público son visibles).
"""

import os
import sys

from notifier.telegram import API_URL, TelegramNotifier, _post_json


def find_chat_ids(updates: list[dict]) -> list[int]:
    ids: list[int] = []
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is not None and chat_id not in ids:
            ids.append(chat_id)
    return ids


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Falta TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 1
    url = API_URL.replace("sendMessage", "getUpdates").format(token=token)
    try:
        result = _post_json(url, {})
    except Exception as exc:  # noqa: BLE001
        print(f"Telegram rechazó el token ({type(exc).__name__}). ¿Lo copiaste completo?",
              file=sys.stderr)
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
