"""Interfaz de estrategias: reciben velas con indicadores y producen señales.

Una estrategia no sabe en qué modo corre (alert/backtest/paper/live): solo mira datos.
"""

from abc import ABC, abstractmethod

import pandas as pd

from core.models import Asset, Direction, Signal


class BaseStrategy(ABC):
    name: str
    required_columns: tuple[str, ...]

    def evaluate(self, asset: Asset, candles: pd.DataFrame) -> Signal | None:
        """Evalúa la última vela contra la anterior. Devuelve None si falta historia."""
        if len(candles) < 2:
            return None
        window = candles.iloc[-2:]
        if window[list(self.required_columns)].isna().any().any():
            return None
        prev, curr = window.iloc[0], window.iloc[1]
        result = self.check(prev, curr)
        if result is None:
            return None
        direction, strength, reason = result
        return Signal(
            asset=asset,
            strategy=self.name,
            direction=direction,
            strength=round(min(max(strength, 0.0), 1.0), 3),
            reason=reason,
            ts=candles.index[-1].to_pydatetime(),
        )

    @abstractmethod
    def check(self, prev: pd.Series, curr: pd.Series) -> tuple[Direction, float, str] | None:
        """Lógica de la regla sobre dos velas consecutivas: (dirección, fuerza 0–1, motivo)."""


def crossed_below(prev: float, curr: float, level: float) -> bool:
    return prev >= level > curr


def crossed_above(prev: float, curr: float, level: float) -> bool:
    return prev <= level < curr
