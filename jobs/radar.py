"""Job de la fase 1: watchlist → datos → indicadores → estrategias → executor.

Uso local:
    uv run --env-file .env python -m jobs.radar            # envía por Telegram
    uv run python -m jobs.radar --dry-run                  # imprime en consola

Si ANTHROPIC_API_KEY está definida, cada alerta incluye un resumen de noticias con Claude.
"""

import argparse
import logging
import os
import sys

from core.config import get_execution_mode, load_watchlist
from core.data import drop_incomplete, get_provider
from core.executors import build_executor
from core.indicators import add_indicators
from core.models import Asset, ExecutionMode, Signal
from core.strategies import run_strategies
from notifier import ConsoleNotifier, Notifier, TelegramNotifier

log = logging.getLogger("radar")


def scan_asset(asset: Asset, timeframe: str) -> list[Signal]:
    candles = get_provider(asset).get_candles(asset, timeframe=timeframe)
    candles = drop_incomplete(candles, timeframe)
    return run_strategies(asset, add_indicators(candles))


def run(assets: list[Asset], executor, notifier: Notifier, timeframe: str = "1d") -> int:
    """Escanea cada activo; un error en uno no detiene al resto. Devuelve el código de salida."""
    failures: list[str] = []
    total = 0
    for asset in assets:
        try:
            signals = scan_asset(asset, timeframe)
        except Exception as exc:  # noqa: BLE001 — se reporta y se sigue con el siguiente
            log.exception("Error escaneando %s", asset.symbol)
            failures.append(f"{asset.symbol}: {type(exc).__name__}")
            continue
        for signal in signals:
            executor.execute(signal)
        total += len(signals)
        log.info("%s: %d señal(es)", asset.symbol, len(signals))

    if failures:
        notifier.send("⚠️ Radar con errores\n" + "\n".join(failures))
    log.info("Fin: %d señal(es), %d error(es) de %d activos", total, len(failures), len(assets))
    return 1 if assets and len(failures) == len(assets) else 0


def build_news_context():
    """Resumen de noticias solo si hay llave de Claude; si no, las alertas salen sin él."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY no definida: alertas sin resumen de noticias")
        return None
    import anthropic

    from core.data.news import fetch_headlines
    from core.llm import NewsSummarizer

    return NewsSummarizer(anthropic.Anthropic(), fetch_headlines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Radar de señales (fase 1)")
    parser.add_argument("--dry-run", action="store_true", help="imprimir en vez de enviar")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--no-news", action="store_true", help="no agregar resumen de noticias")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.dry_run:
        notifier: Notifier = ConsoleNotifier()
        mode = ExecutionMode.ALERT
    else:
        notifier = TelegramNotifier(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        mode = get_execution_mode()

    executor = build_executor(mode, notifier, None if args.no_news else build_news_context())
    return run(load_watchlist(), executor, notifier, args.timeframe)


if __name__ == "__main__":
    sys.exit(main())
