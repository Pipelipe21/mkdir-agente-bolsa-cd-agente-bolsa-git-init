# Desplegar el radar en GCP

El radar corre como **Cloud Run Job** una vez al día, lo dispara **Cloud Scheduler**, y las llaves
viven en **Secret Manager**. Todo lo hace `deploy/gcp.sh` leyendo tu `.env`.

```
Cloud Scheduler (12:00 UTC) ──▶ Cloud Run Job "radar" ──▶ Telegram
                                     │  ▲
                        Secret Manager ┘  └──▶ Supabase (historial)
```

## Antes de empezar

1. `.env` completo y probado en tu máquina (ver [telegram.md](telegram.md) y [supabase.md](supabase.md)).
   Mínimo: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. Recomendado: `DATABASE_URL`
   (sin base de datos, los fines de semana se repetiría la alerta de acciones del viernes).
2. Tablas creadas en Supabase: `uv run --env-file .env python -m jobs.migrate`.
3. Instalar **gcloud CLI**: https://cloud.google.com/sdk/docs/install

## 1. Proyecto de GCP

```bash
gcloud auth login
gcloud projects create agente-bolsa-XXXX      # el ID debe ser único; cambia XXXX
gcloud config set project agente-bolsa-XXXX
```

Asocia una cuenta de facturación en https://console.cloud.google.com/billing (Cloud Build la
exige aunque el uso quede dentro del nivel gratuito).

> **Alerta de presupuesto:** en *Facturación → Presupuestos y alertas* crea un presupuesto de
> USD 5 con aviso al 50% y al 100%.

## 2. Desplegar

Desde la raíz del repo:

```bash
PROJECT_ID=agente-bolsa-XXXX ./deploy/gcp.sh all
```

Esto hace, en orden (cada paso se puede correr solo: `setup`, `secrets`, `deploy`, `schedule`):

| Paso | Qué hace |
|---|---|
| `setup` | Habilita las APIs y crea dos cuentas de servicio: `radar-job` y `radar-scheduler` |
| `secrets` | Sube las variables de `.env` a Secret Manager; solo `radar-job` puede leerlas |
| `deploy` | Construye la imagen con Cloud Build (usa el `Dockerfile`) y crea/actualiza el job |
| `schedule` | Crea el disparador diario a las 12:00 UTC; solo `radar-scheduler` puede ejecutar el job |

La primera vez tarda ~5 minutos (construcción de la imagen).

## 3. Probar

```bash
PROJECT_ID=agente-bolsa-XXXX ./deploy/gcp.sh run
```

Ejecuta el job al tiro y espera a que termine. Los logs se ven en
*Cloud Run → Jobs → radar → Logs*, o:

```bash
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="radar"' \
  --limit 50 --format 'value(textPayload)'
```

Si no hay cruces ese día, no llega nada a Telegram: es lo normal. En los logs verás
`Fin: 0 alerta(s)...`.

## Operación diaria

- **Cambiar una llave** (p. ej. renovaste el token de Telegram): actualiza `.env` y corre
  `./deploy/gcp.sh secrets`. El job usa siempre la versión `latest`.
- **Cambiar código o watchlist**: `./deploy/gcp.sh deploy`.
- **Pausar el radar**: `gcloud scheduler jobs pause radar-daily --location southamerica-west1`
  (y `resume` para reanudar).
- **Cambiar la hora**: `SCHEDULE="0 13 * * *" ./deploy/gcp.sh schedule` (cron en UTC).

## Detalles

- **Región:** `southamerica-west1` (Santiago). Para otra: `REGION=us-central1 ./deploy/gcp.sh all`.
  Si Cloud Scheduler no estuviera disponible en tu región, usa `SCHEDULER_REGION=us-central1`.
- **Hora:** 12:00 UTC (8:00 o 9:00 en Chile). A esa hora ya cerró la vela diaria de cripto
  (00:00 UTC) y la de acciones del día anterior. El radar ignora velas sin cerrar.
- **Reintentos:** si falla el envío de alguna alerta, el job termina con error y Cloud Run lo
  reintenta 1 vez. Con base de datos, las alertas ya enviadas no se repiten.
- **Costo esperado:** ~USD 0. Una ejecución diaria de ~1 minuto cabe en el nivel gratuito de
  Cloud Run; Cloud Scheduler da 3 jobs gratis; Secret Manager, 6 versiones activas gratis.
  Aparte: la API de Claude, si la usas (centavos al día).
- **Seguridad:** la imagen no contiene secretos (`.dockerignore` excluye `.env`) y corre sin
  privilegios. Las cuentas de servicio no tienen roles sobre el proyecto, solo acceso a sus
  secretos y al job.
