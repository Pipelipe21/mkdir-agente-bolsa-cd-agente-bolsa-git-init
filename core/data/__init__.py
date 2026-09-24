from core.data.base import OHLCV_COLUMNS, DataProvider, drop_incomplete, parse_timeframe
from core.models import Asset, AssetType


def get_provider(asset: Asset) -> DataProvider:
    """Elige el proveedor según el tipo de activo. Imports diferidos para no cargar ambas libs."""
    if asset.type is AssetType.STOCK:
        from core.data.yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    from core.data.ccxt_provider import CcxtProvider

    return CcxtProvider(asset.exchange or "binance")


__all__ = ["OHLCV_COLUMNS", "DataProvider", "drop_incomplete", "get_provider", "parse_timeframe"]
