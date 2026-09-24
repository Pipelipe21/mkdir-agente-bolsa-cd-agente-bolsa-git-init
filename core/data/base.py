"""Interfaz común para proveedores de datos (yfinance, ccxt)."""

from abc import ABC, abstractmethod

import pandas as pd

from core.models import Asset

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataProvider(ABC):
    @abstractmethod
    def get_candles(self, asset: Asset, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame:
        """Devuelve un DataFrame indexado por timestamp (UTC) con columnas OHLCV_COLUMNS."""
