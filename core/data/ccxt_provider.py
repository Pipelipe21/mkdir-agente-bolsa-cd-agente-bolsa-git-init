"""Proveedor de cripto vía ccxt (solo lectura de datos públicos, sin llaves)."""

import ccxt
import pandas as pd

from core.data.base import OHLCV_COLUMNS, DataProvider
from core.models import Asset


def normalize_ccxt(rows: list[list[float]], limit: int) -> pd.DataFrame:
    """Convierte la salida de fetch_ohlcv ([ms, o, h, l, c, v]) al formato común."""
    df = pd.DataFrame(rows, columns=["ts", *OHLCV_COLUMNS])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("ts").astype(float).tail(limit)


class CcxtProvider(DataProvider):
    def __init__(self, exchange_id: str = "binance", client: ccxt.Exchange | None = None):
        self.client = client or getattr(ccxt, exchange_id)({"enableRateLimit": True})

    def get_candles(self, asset: Asset, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame:
        rows = self.client.fetch_ohlcv(asset.symbol, timeframe=timeframe, limit=limit)
        if not rows:
            raise LookupError(f"ccxt no devolvió datos para {asset.symbol}")
        return normalize_ccxt(rows, limit)
