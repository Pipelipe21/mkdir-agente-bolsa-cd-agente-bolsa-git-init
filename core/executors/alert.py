"""Executor de la fase 1: no opera, solo avisa."""

from collections.abc import Callable

from core.executors.base import BaseExecutor
from core.models import ExecutionMode, Signal, Trade
from notifier import Notifier, format_signal


class AlertExecutor(BaseExecutor):
    mode = ExecutionMode.ALERT

    def __init__(
        self, notifier: Notifier, context: Callable[[Signal], str | None] | None = None
    ):
        self.notifier = notifier
        self.context = context

    def execute(self, signal: Signal) -> Trade | None:
        extra = self.context(signal) if self.context else None
        self.notifier.send(format_signal(signal, extra))
        return None
