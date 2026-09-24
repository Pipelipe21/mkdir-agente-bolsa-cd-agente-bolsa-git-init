# Radar en GitHub Actions (forma recomendada para empezar)

El radar corre gratis en los servidores de GitHub, todos los días a las 12:00 UTC
(8:00–9:00 en Chile). No hay que instalar nada: solo guardar las llaves como *secrets*.

## Secrets

En el repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Nombre | Obligatorio | De dónde sale |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Sí | @BotFather (`/revoke` o `/newbot`) |
| `TELEGRAM_CHAT_ID` | Sí | Lo envía el workflow *Configurar Telegram* (abajo) |
| `ANTHROPIC_API_KEY` | No | console.anthropic.com → API Keys (resumen de noticias) |
| `DATABASE_URL` | No | Supabase (historial), ver [supabase.md](supabase.md) |

Los secrets van cifrados: no aparecen en el código ni en los logs, aunque el repo sea público.

## Workflows (pestaña **Actions**)

- **Configurar Telegram** — se corre una vez: escríbele al bot y luego *Run workflow*.
  Te llega tu `TELEGRAM_CHAT_ID` por Telegram (no se muestra en el log).
- **Radar diario** — automático a las 12:00 UTC. Con *Run workflow* se corre a mano;
  marcando *Prueba* muestra las alertas en el log sin enviarlas.
- **Tests** — corre en cada cambio, incluidos los tests contra Postgres.

## Notas

- Cripto se descarga de **Kraken**: Binance bloquea los servidores de EE.UU. (error 451).
- Cada vela diaria se evalúa una sola vez (solo velas cerradas desde la corrida anterior):
  el fin de semana no se repite la alerta de acciones del viernes, aun sin base de datos.
- GitHub desactiva los workflows programados si el repo pasa 60 días sin cambios; te avisa
  por correo y se reactivan con un clic en la pestaña Actions.
- Para correr en GCP en vez de GitHub: [gcp.md](gcp.md).
