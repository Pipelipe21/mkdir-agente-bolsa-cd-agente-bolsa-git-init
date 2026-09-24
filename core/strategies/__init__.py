import pandas as pd

from core.models import Asset, Signal
from core.strategies.base import BaseStrategy
from core.strategies.rules import (
    BollingerStrategy,
    RsiStrategy,
    SmaCrossStrategy,
    VolumeSpikeStrategy,
)


def default_strategies() -> list[BaseStrategy]:
    return [RsiStrategy(), SmaCrossStrategy(), BollingerStrategy(), VolumeSpikeStrategy()]


def run_strategies(
    asset: Asset, candles: pd.DataFrame, strategies: list[BaseStrategy] | None = None
) -> list[Signal]:
    """Corre todas las estrategias sobre velas que ya traen indicadores."""
    strategies = default_strategies() if strategies is None else strategies
    return [s for s in (st.evaluate(asset, candles) for st in strategies) if s is not None]


__all__ = [
    "BaseStrategy",
    "BollingerStrategy",
    "RsiStrategy",
    "SmaCrossStrategy",
    "VolumeSpikeStrategy",
    "default_strategies",
    "run_strategies",
]
