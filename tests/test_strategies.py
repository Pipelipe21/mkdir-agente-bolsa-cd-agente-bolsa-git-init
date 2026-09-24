import numpy as np
import pandas as pd
import pytest

from core.indicators import add_indicators
from core.models import Asset, AssetType, Direction
from core.strategies import (
    BollingerStrategy,
    RsiStrategy,
    SmaCrossStrategy,
    VolumeSpikeStrategy,
    run_strategies,
)

ASSET = Asset("SPY", AssetType.STOCK)


def frame(**columns) -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(columns, index=idx, dtype=float)


# --- RSI ---

def test_rsi_buy_on_cross_into_oversold():
    signal = RsiStrategy().evaluate(ASSET, frame(rsi_14=[35, 25]))
    assert signal.direction is Direction.BUY
    assert signal.strategy == "rsi"
    assert signal.ts == pd.Timestamp("2024-01-02", tz="UTC")
    assert 0.5 < signal.strength <= 1


def test_rsi_sell_on_cross_into_overbought():
    assert RsiStrategy().evaluate(ASSET, frame(rsi_14=[65, 75])).direction is Direction.SELL


@pytest.mark.parametrize("values", [[25, 20], [50, 55], [np.nan, 20], [20]])
def test_rsi_no_signal_without_cross_or_history(values):
    assert RsiStrategy().evaluate(ASSET, frame(rsi_14=values)) is None


# --- SMA ---

def test_golden_cross():
    signal = SmaCrossStrategy().evaluate(ASSET, frame(sma_50=[99, 101], sma_200=[100, 100]))
    assert signal.direction is Direction.BUY


def test_death_cross():
    signal = SmaCrossStrategy().evaluate(ASSET, frame(sma_50=[101, 99], sma_200=[100, 100]))
    assert signal.direction is Direction.SELL


def test_no_cross_when_already_above():
    assert SmaCrossStrategy().evaluate(ASSET, frame(sma_50=[102, 103], sma_200=[100, 100])) is None


# --- Bollinger ---

def test_bollinger_buy_below_lower_band():
    df = frame(close=[95, 89], bb_lower=[90, 90], bb_upper=[110, 110])
    signal = BollingerStrategy().evaluate(ASSET, df)
    assert signal.direction is Direction.BUY
    assert signal.strength == pytest.approx(0.55)


def test_bollinger_sell_above_upper_band():
    df = frame(close=[105, 112], bb_lower=[90, 90], bb_upper=[110, 110])
    assert BollingerStrategy().evaluate(ASSET, df).direction is Direction.SELL


def test_bollinger_no_repeat_while_outside():
    df = frame(close=[88, 87], bb_lower=[90, 90], bb_upper=[110, 110])
    assert BollingerStrategy().evaluate(ASSET, df) is None


# --- Volumen ---

def test_volume_spike_direction_follows_candle():
    up = frame(open=[10, 10], close=[10, 11], rel_volume_20=[1.0, 3.0])
    down = frame(open=[10, 11], close=[10, 10], rel_volume_20=[1.0, 3.0])
    assert VolumeSpikeStrategy().evaluate(ASSET, up).direction is Direction.BUY
    assert VolumeSpikeStrategy().evaluate(ASSET, down).direction is Direction.SELL


def test_volume_spike_ignores_normal_volume():
    df = frame(open=[10, 10], close=[10, 11], rel_volume_20=[1.0, 1.5])
    assert VolumeSpikeStrategy().evaluate(ASSET, df) is None


# --- Integración ---

def test_run_strategies_end_to_end_on_crash():
    # 60 velas estables y luego una caída fuerte con volumen alto.
    rng = np.random.default_rng(0)
    close = np.concatenate([100 + rng.normal(0, 0.5, 60), [90]])
    volume = np.concatenate([np.full(60, 1000.0), [5000.0]])
    candles = add_indicators(frame(open=close + 0.5, high=close + 1, low=close - 1,
                                   close=close, volume=volume))
    names = {s.strategy for s in run_strategies(ASSET, candles)}
    assert {"rsi", "bollinger", "volume_spike"} <= names
    assert "sma_cross" not in names  # sin 200 velas no hay SMA 200
