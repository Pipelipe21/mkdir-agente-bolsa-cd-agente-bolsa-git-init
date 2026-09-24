"""Proveedor de acciones/ETFs vía yfinance."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from core.data.base import OHLCV_COLUMNS, DataProvider
from core.models import Asset

# Duración de cada timeframe; se piden días de calendario de más por fines de semana y feriados.
TIMEFRAMES = {"1h": timedelta(hours=1), "1d": timedelta(days=1), "1wk": timedelta(weeks=1)}
CALENDAR_BUFFER = 1.6


def normalize_yfinance(raw: pd.DataFrame, limit: int) -> pd.DataFrame:
    """Columnas en minúscula, solo OHLCV, índice en UTC, últimas `limit` velas."""
    df = raw.rename(columns=str.lower)[OHLCV_COLUMNS].astype(float)
    index = pd.DatetimeIndex(df.index)
    df.index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    df.index.name = "ts"
    return df.dropna().tail(limit)


class YFinanceProvider(DataProvider):
    def get_candles(self, asset: Asset, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"timeframe no soportado por yfinance: {timeframe}")
        start = datetime.now(UTC) - TIMEFRAMES[timeframe] * limit * CALENDAR_BUFFER
        raw = yf.Ticker(asset.symbol).history(start=start, interval=timeframe, auto_adjust=True)
        if raw.empty:
            raise LookupError(f"yfinance no devolvió datos para {asset.symbol}")
        return normalize_yfinance(raw, limit)
