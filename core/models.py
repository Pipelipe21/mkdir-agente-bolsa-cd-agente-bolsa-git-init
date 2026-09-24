"""Modelos de dominio compartidos por todos los niveles (alert, backtest, paper, live)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class AssetType(StrEnum):
    STOCK = "stock"
    CRYPTO = "crypto"


class Direction(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class ExecutionMode(StrEnum):
    ALERT = "alert"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class Asset:
    symbol: str
    type: AssetType
    exchange: str | None = None
    active: bool = True


@dataclass(frozen=True)
class Signal:
    """Salida de una estrategia. No sabe en qué modo se va a ejecutar."""

    asset: Asset
    strategy: str
    direction: Direction
    strength: float  # 0.0–1.0
    reason: str
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength debe estar entre 0 y 1, llegó {self.strength}")


@dataclass(frozen=True)
class Trade:
    signal: Signal
    mode: ExecutionMode
    side: Side
    qty: float
    price: float
    fees: float = 0.0
    pnl: float | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))
