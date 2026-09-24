"""Executor de la fase 1: no opera, solo avisa."""

from core.executors.base import BaseExecutor
from core.models import ExecutionMode, Signal, Trade
from notifier import Notifier, format_signal


class AlertExecutor(BaseExecutor):
    mode = ExecutionMode.ALERT

    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def execute(self, signal: Signal) -> Trade | None:
        self.notifier.send(format_signal(signal))
        return None
