# Agente Bolsa — contexto para Claude Code

## Qué es
Sistema personal que analiza acciones (EE.UU.) y cripto, detecta oportunidades de compra/venta y
evoluciona en 4 niveles: alertas → backtesting/paper → semi-automático → autónomo.
Proyecto de aprendizaje y portafolio. Idioma del código: inglés. Comentarios, docs y commits: español.

## Principio de diseño (no romper)
Un solo motor de señales alimenta todos los niveles:

    Datos → Indicadores → Señal → Executor [alert | backtest | paper | live]

- La lógica de estrategia NO sabe en qué modo corre. El modo es configuración.
- Todo executor implementa la misma interfaz (`BaseExecutor.execute(signal)`).
- Modo por defecto: `paper`. `live` solo se activa explícitamente por variable de entorno.
- El LLM (Claude API) aporta contexto (resumen de noticias, explicación de alertas).
  Nunca decide una operación: las señales vienen de reglas/modelos testeables.

## Fases y criterios de salida
1. **Radar con alertas** — watchlist ~5 acciones/ETFs + ~5 criptos. RSI, SMA 50/200,
   Bollinger, volumen anómalo. Alertas por Telegram + resumen de noticias con Claude.
   Sale cuando: alertas confiables 2 semanas seguidas.
2. **Backtesting + paper** — vectorbt con comisiones y slippage. Paper en Alpaca (acciones)
   y testnet de Binance (cripto). Sale cuando: 2–3 meses de paper que le gana a buy&hold neto de costos.
3. **Semi-automático** — PWA: propuestas con activo, dirección, tamaño, stop-loss y justificación;
   aprobar/rechazar con un toque. Registrar también las rechazadas.
4. **Autónomo** — Interactive Brokers (acciones), ccxt (cripto). Montos chicos.

**Fase actual: 1 (inicio).**

## Stack
- Python 3.12, gestión con `uv`
- Datos: `yfinance` (acciones), `ccxt` (cripto)
- Indicadores: `pandas` + `pandas-ta`
- Backtesting (fase 2): `vectorbt`
- DB: Supabase (Postgres)
- Infra: GitHub Actions (cron diario; secretos en GitHub Secrets). Alternativa lista: GCP —
  Cloud Run Jobs + Cloud Scheduler + Secret Manager (`deploy/gcp.sh`)
- Cripto: datos de Kraken vía ccxt (Binance bloquea servidores de EE.UU.)
- Alertas: bot de Telegram (fase 1), Web Push en PWA (fase 3)
- API (fase 3): FastAPI. PWA (fase 3): por definir

## Estructura del repo
    core/
      data/          # proveedores de datos (yfinance, ccxt) tras una interfaz común
      indicators/
      strategies/    # reglas que producen Signal
      executors/     # alert, backtest, paper, live
      models.py      # Signal, Trade, Asset (dataclasses/pydantic)
    jobs/            # entrypoints para Cloud Run Jobs
    notifier/        # Telegram
    config/
      watchlist.yaml
    migrations/      # SQL del esquema de Supabase
    .github/workflows/  # radar diario, tests, configuración de Telegram
    deploy/          # gcp.sh: Cloud Run Job + Scheduler + Secret Manager
    docs/            # guías de configuración (GitHub Actions, Telegram, Supabase, GCP)
    tests/
    pwa/             # fase 3

## Modelo de datos (Supabase)
Esquema en `migrations/` (SQL plano, aplicado con `python -m jobs.migrate`). Acceso con `psycopg`.
- `assets` — symbol, type (stock/crypto), exchange, active
- `candles` — asset_id, timeframe, ts, OHLCV
- `signals` — asset_id, strategy, direction, strength, reason, ts (único por vela: evita alertas repetidas)
- `alerts` — signal_id, channel, sent_at, llm_summary
- `trades` — signal_id, mode (backtest/paper/live), side, qty, price, fees, pnl, ts
- RLS activo en todas las tablas y sin políticas: la API REST pública de Supabase no ve nada.

## Reglas de seguridad (obligatorias)
- Nunca commitear llaves ni `.env`. Usar `.env.example` con placeholders.
- Llaves de exchange SIN permiso de retiro.
- Límites duros en `live`: máx 1–2% del capital en riesgo por operación, tope de pérdida diaria
  que apaga el bot, kill switch accesible.
- Guardar historial completo de operaciones (para tributación en Chile).
- Toda estrategia nueva pasa por backtest antes de paper, y por paper antes de live.

## Cómo trabajar en este repo
- Tests con `pytest` para indicadores y estrategias (datos fijos, sin red).
- Cambios chicos y commits frecuentes.
- Antes de agregar una dependencia nueva, proponerla y explicar por qué.
