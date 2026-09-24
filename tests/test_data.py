import pandas as pd

from core.data import OHLCV_COLUMNS, get_provider
from core.data.ccxt_provider import CcxtProvider, normalize_ccxt
from core.data.yfinance_provider import YFinanceProvider, normalize_yfinance
from core.models import Asset, AssetType


def test_normalize_yfinance_converts_to_utc_and_drops_extra_columns():
    idx = pd.date_range("2024-01-02", periods=3, freq="D", tz="America/New_York")
    raw = pd.DataFrame(
        {
            "Open": [1, 2, 3], "High": [2, 3, 4], "Low": [0, 1, 2], "Close": [1.5, 2.5, 3.5],
            "Volume": [10, 20, 30], "Dividends": 0, "Stock Splits": 0,
        },
        index=idx,
    )
    df = normalize_yfinance(raw, limit=2)
    assert list(df.columns) == OHLCV_COLUMNS
    assert str(df.index.tz) == "UTC"
    assert len(df) == 2 and df["close"].iloc[-1] == 3.5


def test_normalize_ccxt():
    rows = [[1704067200000, 1, 2, 0.5, 1.5, 100], [1704153600000, 1.5, 3, 1, 2.5, 200]]
    df = normalize_ccxt(rows, limit=10)
    assert list(df.columns) == OHLCV_COLUMNS
    assert df.index[0] == pd.Timestamp("2024-01-01", tz="UTC")


class FakeExchange:
    def fetch_ohlcv(self, symbol, timeframe, limit):
        self.called_with = (symbol, timeframe, limit)
        return [[1704067200000, 1, 2, 0.5, 1.5, 100]]


def test_ccxt_provider_uses_injected_client():
    fake = FakeExchange()
    df = CcxtProvider(client=fake).get_candles(Asset("BTC/USDT", AssetType.CRYPTO), "1h", 5)
    assert fake.called_with == ("BTC/USDT", "1h", 5)
    assert len(df) == 1


def test_get_provider_by_asset_type():
    assert isinstance(get_provider(Asset("SPY", AssetType.STOCK)), YFinanceProvider)
    assert isinstance(get_provider(Asset("BTC/USDT", AssetType.CRYPTO, "binance")), CcxtProvider)
