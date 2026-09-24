"""Interfaz única para todos los executors (alert, backtest, paper, live)."""

from abc import ABC, abstractmethod

from core.models import ExecutionMode, Signal, Trade


class BaseExecutor(ABC):
    mode: ExecutionMode

    @abstractmethod
    def execute(self, signal: Signal) -> Trade | None:
        """Actúa sobre una señal. Devuelve el Trade si hubo operación, None si solo se alertó."""
