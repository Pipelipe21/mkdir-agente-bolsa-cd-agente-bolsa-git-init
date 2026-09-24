import pytest

from core.config import get_execution_mode, load_watchlist
from core.models import AssetType, ExecutionMode


def test_watchlist_loads_stocks_and_crypto():
    assets = load_watchlist()
    types = {a.type for a in assets}
    assert types == {AssetType.STOCK, AssetType.CRYPTO}
    assert all(a.exchange for a in assets if a.type is AssetType.CRYPTO)


def test_default_mode_is_paper():
    assert get_execution_mode({}) is ExecutionMode.PAPER


def test_live_requires_explicit_flag():
    with pytest.raises(RuntimeError):
        get_execution_mode({"EXECUTION_MODE": "live"})
    env = {"EXECUTION_MODE": "live", "LIVE_TRADING_ENABLED": "true"}
    assert get_execution_mode(env) is ExecutionMode.LIVE
