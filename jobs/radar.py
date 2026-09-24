"""Job de la fase 1: watchlist → datos → indicadores → estrategias → executor.

Uso local:
    uv run --env-file .env python -m jobs.radar            # envía por Telegram
    uv run python -m jobs.radar --dry-run                  # imprime en consola, no guarda

Si ANTHROPIC_API_KEY está definida, cada alerta incluye un resumen de noticias con Claude.
Si DATABASE_URL está definida, señales y alertas se guardan y no se repite una alerta ya enviada.
"""

import argparse
import logging
import os
import sys

from core.config import get_execution_mode, load_watchlist
from core.data import drop_incomplete, get_provider, is_fresh
from core.db import NullRepository, PostgresRepository, Repository, connect
from core.executors import BaseExecutor, build_executor
from core.indicators import add_indicators
from core.models import Asset, ExecutionMode, Signal
from core.strategies import run_strategies
from notifier import ConsoleNotifier, Notifier, TelegramNotifier

log = logging.getLogger("radar")


def scan_asset(asset: Asset, timeframe: str) -> list[Signal]:
    candles = get_provider(asset).get_candles(asset, timeframe=timeframe)
    candles = drop_incomplete(candles, timeframe)
    if candles.empty or not is_fresh(candles.index[-1], timeframe):
        log.info("%s: sin vela nueva desde la última corrida", asset.symbol)
        return []
    return run_strategies(asset, add_indicators(candles))


def run(
    assets: list[Asset],
    executor: BaseExecutor,
    notifier: Notifier,
    timeframe: str = "1d",
    repo: Repository | None = None,
) -> int:
    """Escanea cada activo; un error en uno no detiene al resto.

    Código de salida 1 si no se pudo escanear ningún activo o si falló el envío de alguna
    alerta: así Cloud Run reintenta, y las alertas ya enviadas no se repiten.
    """
    repo = repo or NullRepository()
    failures: list[str] = []
    sent = skipped = scan_errors = send_errors = 0
    for asset in assets:
        try:
            signals = scan_asset(asset, timeframe)
        except Exception as exc:  # noqa: BLE001 — se reporta y se sigue con el siguiente
            log.exception("Error escaneando %s", asset.symbol)
            failures.append(f"{asset.symbol}: {type(exc).__name__}")
            scan_errors += 1
            continue
        for signal in signals:
            try:
                saved = repo.save_signal(signal)
            except Exception as exc:  # noqa: BLE001 — la alerta importa más que el registro
                log.exception("No se pudo guardar la señal de %s", asset.symbol)
                failures.append(f"DB {asset.symbol}: {type(exc).__name__}")
                saved = signal
            if saved is None:
                log.info("%s/%s ya fue alertada, se omite", asset.symbol, signal.strategy)
                skipped += 1
                continue
            try:
                executor.execute(saved)
            except Exception as exc:  # noqa: BLE001 — se sigue con las demás señales
                log.exception("No se pudo ejecutar la señal de %s", asset.symbol)
                failures.append(f"Envío {asset.symbol}/{signal.strategy}: {type(exc).__name__}")
                send_errors += 1
                continue
            sent += 1
        log.info("%s: %d señal(es)", asset.symbol, len(signals))

    if failures:
        try:
            notifier.send("⚠️ Radar con errores\n" + "\n".join(failures))
        except Exception:  # noqa: BLE001 — si el canal está caído, queda al menos en el log
            log.exception("No se pudo enviar el resumen de errores")
    log.info(
        "Fin: %d alerta(s), %d repetida(s), %d error(es) de %d activos",
        sent, skipped, len(failures), len(assets),
    )
    all_scans_failed = bool(assets) and scan_errors == len(assets)
    return 1 if all_scans_failed or send_errors else 0


def build_news_context():
    """Resumen de noticias solo si hay llave de Claude; si no, las alertas salen sin él."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY no definida: alertas sin resumen de noticias")
        return None
    import anthropic

    from core.data.news import fetch_headlines
    from core.llm import NewsSummarizer

    return NewsSummarizer(anthropic.Anthropic(), fetch_headlines)


def build_repository() -> Repository:
    url = os.environ.get("DATABASE_URL")
    if not url:
        log.info("DATABASE_URL no definida: no se guarda historial")
        return NullRepository()
    return PostgresRepository(connect(url))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Radar de señales (fase 1)")
    parser.add_argument("--dry-run", action="store_true", help="imprimir en vez de enviar")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--no-news", action="store_true", help="no agregar resumen de noticias")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.dry_run:
        # En dry-run no se guarda: si guardara, la alerta real posterior se omitiría por repetida.
        notifier: Notifier = ConsoleNotifier()
        mode = ExecutionMode.ALERT
        repo: Repository = NullRepository()
    else:
        notifier = TelegramNotifier(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        mode = get_execution_mode()
        repo = build_repository()

    context = None if args.no_news else build_news_context()
    executor = build_executor(mode, notifier, context, repo)
    return run(load_watchlist(), executor, notifier, args.timeframe, repo)


if __name__ == "__main__":
    sys.exit(main())
