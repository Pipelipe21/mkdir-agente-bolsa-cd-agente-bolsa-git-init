# Configurar el bot de Telegram

## 1. Renovar el token (el anterior quedó expuesto)

1. En Telegram, abre el chat con **@BotFather**.
2. Envía `/revoke`.
3. Elige tu bot de la lista.
4. BotFather responde con un **token nuevo** (formato `123456789:AA...`). El anterior deja de funcionar al instante.

> Si prefieres empezar de cero: `/deletebot` y luego `/newbot`.

## 2. Obtener tu chat_id

1. Busca tu bot en Telegram y envíale cualquier mensaje (por ejemplo `hola`).
2. En el navegador abre (reemplaza `<TOKEN>` por el token nuevo):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. En la respuesta busca `"chat":{"id":123456789,...}`. Ese número es tu `chat_id`.

> Si ves `"result":[]`, envía otro mensaje al bot y recarga la página.

## 3. Pegarlos en `.env`

En la raíz del repo:

```bash
cp .env.example .env
```

Abre `.env` y reemplaza los placeholders:

```
TELEGRAM_BOT_TOKEN=123456789:AA...tu-token-nuevo
TELEGRAM_CHAT_ID=123456789
```

`.env` está en `.gitignore`: nunca se sube al repo. No pegues el token en chats, issues ni commits.

## 4. Probar

```bash
uv run --env-file .env python -c "
import os; from notifier import TelegramNotifier
TelegramNotifier(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID']).send('✅ Radar conectado')"
```

Si llega el mensaje, corre el radar completo:

```bash
uv run --env-file .env python -m jobs.radar
```

## Resumen de noticias con Claude (opcional)

Crea una API key en https://console.anthropic.com → **API Keys** y agrégala a `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Sin esta llave, las alertas salen igual pero sin el bloque 📰 de contexto. Para desactivarlo teniendo la llave: `--no-news`.

## En producción (GCP)

Los mismos valores van en **Secret Manager**, no en archivos. Se configura al desplegar el Cloud Run Job.
