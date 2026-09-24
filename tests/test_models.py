import pytest

from core.models import Asset, AssetType, Direction, Signal


def make_signal(strength: float) -> Signal:
    asset = Asset(symbol="SPY", type=AssetType.STOCK)
    return Signal(asset, "rsi", Direction.BUY, strength, "RSI < 30")


def test_signal_accepts_valid_strength():
    assert make_signal(0.7).strength == 0.7


@pytest.mark.parametrize("strength", [-0.1, 1.5])
def test_signal_rejects_out_of_range_strength(strength):
    with pytest.raises(ValueError):
        make_signal(strength)
