"""Carga de configuración: watchlist y modo de ejecución."""

import os
from pathlib import Path

import yaml

from core.models import Asset, AssetType, ExecutionMode

DEFAULT_WATCHLIST = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"


def load_watchlist(path: Path = DEFAULT_WATCHLIST) -> list[Asset]:
    data = yaml.safe_load(path.read_text()) or {}
    assets = [Asset(symbol=s["symbol"], type=AssetType.STOCK) for s in data.get("stocks", [])]
    crypto = data.get("crypto") or {}
    exchange = crypto.get("exchange")
    assets += [
        Asset(symbol=s["symbol"], type=AssetType.CRYPTO, exchange=exchange)
        for s in crypto.get("symbols", [])
    ]
    return assets


def get_execution_mode(env: dict[str, str] | None = None) -> ExecutionMode:
    """Modo por defecto: paper. `live` exige además LIVE_TRADING_ENABLED=true."""
    env = os.environ if env is None else env
    mode = ExecutionMode(env.get("EXECUTION_MODE", ExecutionMode.PAPER).lower())
    if mode is ExecutionMode.LIVE and env.get("LIVE_TRADING_ENABLED", "").lower() != "true":
        raise RuntimeError("Modo live pedido sin LIVE_TRADING_ENABLED=true; abortando.")
    return mode
