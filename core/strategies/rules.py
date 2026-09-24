"""Reglas de la fase 1. Umbrales configurables por constructor."""

import pandas as pd

from core.models import Direction
from core.strategies.base import BaseStrategy, crossed_above, crossed_below


class RsiStrategy(BaseStrategy):
    """Compra cuando el RSI entra en sobreventa; vende cuando entra en sobrecompra."""

    name = "rsi"
    required_columns = ("rsi_14",)

    def __init__(self, oversold: float = 30, overbought: float = 70):
        self.oversold, self.overbought = oversold, overbought

    def check(self, prev: pd.Series, curr: pd.Series):
        p, c = prev["rsi_14"], curr["rsi_14"]
        if crossed_below(p, c, self.oversold):
            strength = 0.5 + (self.oversold - c) / self.oversold
            return Direction.BUY, strength, f"RSI cruzó bajo {self.oversold} ({c:.1f})"
        if crossed_above(p, c, self.overbought):
            strength = 0.5 + (c - self.overbought) / (100 - self.overbought)
            return Direction.SELL, strength, f"RSI cruzó sobre {self.overbought} ({c:.1f})"
        return None


class SmaCrossStrategy(BaseStrategy):
    """Cruce dorado (SMA 50 sobre SMA 200) y cruce de la muerte (SMA 50 bajo SMA 200)."""

    name = "sma_cross"
    required_columns = ("sma_50", "sma_200")

    def check(self, prev: pd.Series, curr: pd.Series):
        prev_diff = prev["sma_50"] - prev["sma_200"]
        curr_diff = curr["sma_50"] - curr["sma_200"]
        if crossed_above(prev_diff, curr_diff, 0):
            return Direction.BUY, 0.8, "Cruce dorado: SMA 50 cruzó sobre SMA 200"
        if crossed_below(prev_diff, curr_diff, 0):
            return Direction.SELL, 0.8, "Cruce de la muerte: SMA 50 cruzó bajo SMA 200"
        return None


class BollingerStrategy(BaseStrategy):
    """Cierre que sale de las bandas: bajo la inferior → compra, sobre la superior → venta."""

    name = "bollinger"
    required_columns = ("close", "bb_lower", "bb_upper")

    def check(self, prev: pd.Series, curr: pd.Series):
        close = curr["close"]
        width = curr["bb_upper"] - curr["bb_lower"]
        if width <= 0:
            return None
        if prev["close"] >= prev["bb_lower"] and close < curr["bb_lower"]:
            strength = 0.5 + (curr["bb_lower"] - close) / width
            return Direction.BUY, strength, f"Cierre {close:.2f} bajo la banda inferior"
        if prev["close"] <= prev["bb_upper"] and close > curr["bb_upper"]:
            strength = 0.5 + (close - curr["bb_upper"]) / width
            return Direction.SELL, strength, f"Cierre {close:.2f} sobre la banda superior"
        return None


class VolumeSpikeStrategy(BaseStrategy):
    """Volumen anómalo; la dirección la da el color de la vela."""

    name = "volume_spike"
    required_columns = ("open", "close", "rel_volume_20")

    def __init__(self, threshold: float = 2.0):
        self.threshold = threshold

    def check(self, prev: pd.Series, curr: pd.Series):
        rel = curr["rel_volume_20"]
        if rel < self.threshold or prev["rel_volume_20"] >= self.threshold:
            return None
        if curr["close"] == curr["open"]:
            return None
        direction = Direction.BUY if curr["close"] > curr["open"] else Direction.SELL
        candle = "alcista" if direction is Direction.BUY else "bajista"
        strength = 0.4 + (rel - self.threshold) / (2 * self.threshold)
        return direction, strength, f"Volumen {rel:.1f}x el promedio con vela {candle}"
