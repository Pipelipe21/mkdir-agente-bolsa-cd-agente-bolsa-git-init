"""Interfaz común para proveedores de datos (yfinance, ccxt)."""

import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import pandas as pd

from core.models import Asset

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

_UNITS = {"m": "minutes", "h": "hours", "d": "days", "wk": "weeks", "w": "weeks"}


class DataProvider(ABC):
    @abstractmethod
    def get_candles(self, asset: Asset, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame:
        """Devuelve un DataFrame indexado por timestamp (UTC) con columnas OHLCV_COLUMNS."""


def parse_timeframe(timeframe: str) -> timedelta:
    """'1h' → 1 hora, '4h' → 4 horas, '1d' → 1 día, '1wk'/'1w' → 1 semana."""
    match = re.fullmatch(r"(\d+)(m|h|d|wk|w)", timeframe)
    if not match:
        raise ValueError(f"timeframe no reconocido: {timeframe}")
    return timedelta(**{_UNITS[match[2]]: int(match[1])})


def drop_incomplete(
    candles: pd.DataFrame, timeframe: str, now: datetime | None = None
) -> pd.DataFrame:
    """Quita velas que aún no cierran: una señal sobre una vela en curso puede desaparecer."""
    now = now or datetime.now(UTC)
    closes_at = candles.index + parse_timeframe(timeframe)
    return candles[closes_at <= now]
