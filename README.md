# Agente Bolsa

Radar personal de señales para acciones (EE.UU.) y cripto. Ver [CLAUDE.md](CLAUDE.md) para diseño, fases y reglas.

## Setup

```bash
uv sync
cp .env.example .env   # completar llaves
uv run pytest
```

## Radar (fase 1)

```bash
uv run python -m jobs.radar --dry-run          # imprime las señales en consola
uv run --env-file .env python -m jobs.radar    # las envía por Telegram
```

Evalúa solo velas cerradas. Pensado para correr una vez al día (p. ej. 12:00 UTC),
cuando ya cerró la vela diaria de acciones y de cripto.

Configuración:
- Telegram y API de Claude: [docs/telegram.md](docs/telegram.md)
- Supabase (historial y deduplicación): [docs/supabase.md](docs/supabase.md)
- Despliegue en GCP (Cloud Run Job diario): [docs/gcp.md](docs/gcp.md)
