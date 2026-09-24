import numpy as np
import pandas as pd
import pytest

from core.indicators import add_indicators, bollinger, relative_volume, rsi, sma


def series(values) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_sma_values():
    result = sma(series([1, 2, 3, 4, 5]), 3)
    assert result.isna().sum() == 2
    assert result.iloc[2:].tolist() == [2.0, 3.0, 4.0]


def test_rsi_hand_computed():
    # diffs: +1, +1, -1 → con length=2: avg_gain 1 → 0.5, avg_loss 0 → 0.5
    result = rsi(series([1, 2, 3, 2]), 2)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(100.0)
    assert result.iloc[3] == pytest.approx(50.0)


def test_rsi_extremes_and_flat():
    assert rsi(series(range(1, 31)), 14).iloc[-1] == pytest.approx(100.0)
    assert rsi(series(range(30, 0, -1)), 14).iloc[-1] == pytest.approx(0.0)
    assert rsi(series([10] * 30), 14).iloc[-1] == pytest.approx(50.0)


def test_rsi_bounded_on_random_walk():
    rng = np.random.default_rng(42)
    close = series(100 + rng.normal(0, 1, 500).cumsum())
    result = rsi(close, 14).dropna()
    assert ((result >= 0) & (result <= 100)).all()


def test_bollinger_constant_series_collapses_to_mid():
    bands = bollinger(series([5] * 25), 20).dropna()
    assert (bands["bb_lower"] == 5).all() and (bands["bb_upper"] == 5).all()


def test_bollinger_width_uses_population_std():
    # [1, 3]: media 2, std poblacional 1 → bandas 0 y 4 con k=2
    bands = bollinger(series([1, 3]), 2)
    assert bands.iloc[-1].tolist() == [0.0, 2.0, 4.0]


def test_relative_volume_flags_spike():
    rel = relative_volume(series([100] * 20 + [300]), 20)
    assert rel.iloc[:20].isna().all()
    assert rel.iloc[-1] == pytest.approx(3.0)


def test_add_indicators_columns():
    n = 250
    close = series(np.linspace(100, 200, n))
    candles = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000.0}
    )
    out = add_indicators(candles)
    expected = {"rsi_14", "sma_50", "sma_200", "bb_lower", "bb_mid", "bb_upper", "rel_volume_20"}
    assert expected <= set(out.columns)
    assert out.iloc[-1][list(expected)].notna().all()
    assert "rsi_14" not in candles.columns  # no muta la entrada
