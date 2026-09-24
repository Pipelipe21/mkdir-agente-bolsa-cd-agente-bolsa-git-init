#!/usr/bin/env bash
# Despliegue del radar en GCP: Cloud Run Job + Cloud Scheduler + Secret Manager.
#
# Uso (desde la raíz del repo, con gcloud autenticado):
#   PROJECT_ID=mi-proyecto ./deploy/gcp.sh all        # todo, en orden
#   PROJECT_ID=mi-proyecto ./deploy/gcp.sh <paso>     # setup | secrets | deploy | schedule | run
#
# Los secretos se leen de .env y se suben a Secret Manager; nunca se escriben en la terminal.
set -euo pipefail

: "${PROJECT_ID:?Define PROJECT_ID (ej: PROJECT_ID=agente-bolsa-123 ./deploy/gcp.sh all)}"
REGION="${REGION:-southamerica-west1}"            # Santiago
SCHEDULER_REGION="${SCHEDULER_REGION:-$REGION}"
JOB="${JOB:-radar}"
SCHEDULE="${SCHEDULE:-0 12 * * *}"                # 12:00 UTC: ya cerró la vela diaria de acciones y cripto
ENV_FILE="${ENV_FILE:-.env}"

JOB_SA="radar-job@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="radar-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

# Variable de .env → nombre del secreto en Secret Manager.
declare -A SECRETS=(
  [TELEGRAM_BOT_TOKEN]=telegram-bot-token
  [TELEGRAM_CHAT_ID]=telegram-chat-id
  [ANTHROPIC_API_KEY]=anthropic-api-key
  [DATABASE_URL]=database-url
)
REQUIRED=(TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID)

gc() { gcloud --project "$PROJECT_ID" --quiet "$@"; }

env_value() {
  # Lee KEY=valor de .env sin ejecutarlo (no usa `source`). Vacío si falta o es placeholder.
  local value
  value="$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  value="${value%\"}"; value="${value#\"}"; value="${value%\'}"; value="${value#\'}"
  [[ "$value" == *changeme* ]] && value=""
  printf '%s' "$value"
}

ensure_sa() {
  local name="$1" description="$2"
  if ! gc iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gc iam service-accounts create "$name" --display-name "$description"
  fi
}

cmd_setup() {
  echo "==> Habilitando APIs"
  gc services enable run.googleapis.com cloudscheduler.googleapis.com \
    secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
  echo "==> Cuentas de servicio (sin roles de proyecto: solo acceso puntual)"
  ensure_sa radar-job "Radar: ejecuta el job"
  ensure_sa radar-scheduler "Radar: dispara el job"
}

cmd_secrets() {
  [[ -f "$ENV_FILE" ]] || { echo "No existe $ENV_FILE" >&2; exit 1; }
  for key in "${REQUIRED[@]}"; do
    [[ -n "$(env_value "$key")" ]] || { echo "Falta $key en $ENV_FILE" >&2; exit 1; }
  done
  for key in "${!SECRETS[@]}"; do
    local name="${SECRETS[$key]}" value
    value="$(env_value "$key")"
    if [[ -z "$value" ]]; then
      echo "--  $key vacío en $ENV_FILE: se omite"
      continue
    fi
    if ! gc secrets describe "$name" >/dev/null 2>&1; then
      gc secrets create "$name" --replication-policy automatic
    fi
    gc secrets add-iam-policy-binding "$name" \
      --member "serviceAccount:${JOB_SA}" --role roles/secretmanager.secretAccessor >/dev/null
    # Solo se agrega versión si el valor cambió (cada versión activa sobre 6 tiene costo).
    if [[ "$(gc secrets versions access latest --secret "$name" 2>/dev/null || true)" == "$value" ]]; then
      echo "=   $key sin cambios"
      continue
    fi
    printf '%s' "$value" | gc secrets versions add "$name" --data-file=- >/dev/null
    echo "ok  $key → secreto '$name' (nueva versión)"
  done
}

cmd_deploy() {
  local mappings=()
  for key in "${!SECRETS[@]}"; do
    if gc secrets describe "${SECRETS[$key]}" >/dev/null 2>&1; then
      mappings+=("${key}=${SECRETS[$key]}:latest")
    fi
  done
  local joined
  joined="$(IFS=,; echo "${mappings[*]}")"
  echo "==> Construyendo y desplegando el job '$JOB' en $REGION"
  gc run jobs deploy "$JOB" \
    --source . \
    --region "$REGION" \
    --service-account "$JOB_SA" \
    --set-env-vars EXECUTION_MODE=alert \
    --set-secrets "$joined" \
    --memory 1Gi --cpu 1 \
    --task-timeout 15m \
    --max-retries 1
}

cmd_schedule() {
  echo "==> Permiso para que el scheduler ejecute el job"
  gc run jobs add-iam-policy-binding "$JOB" --region "$REGION" \
    --member "serviceAccount:${SCHEDULER_SA}" --role roles/run.invoker >/dev/null
  local uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB}:run"
  local args=(--location "$SCHEDULER_REGION" --schedule "$SCHEDULE" --time-zone "Etc/UTC"
              --uri "$uri" --http-method POST --oauth-service-account-email "$SCHEDULER_SA")
  if gc scheduler jobs describe "${JOB}-daily" --location "$SCHEDULER_REGION" >/dev/null 2>&1; then
    gc scheduler jobs update http "${JOB}-daily" "${args[@]}"
  else
    gc scheduler jobs create http "${JOB}-daily" "${args[@]}"
  fi
  echo "ok  '${JOB}-daily' corre '${SCHEDULE}' (UTC)"
}

cmd_run() {
  echo "==> Ejecutando el job ahora (espera a que termine)"
  gc run jobs execute "$JOB" --region "$REGION" --wait
}

case "${1:-}" in
  setup) cmd_setup ;;
  secrets) cmd_secrets ;;
  deploy) cmd_deploy ;;
  schedule) cmd_schedule ;;
  run) cmd_run ;;
  all) cmd_setup; cmd_secrets; cmd_deploy; cmd_schedule ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
