"""Executor de la fase 1: no opera, solo avisa."""

from collections.abc import Callable

from core.db import NullRepository, Repository
from core.executors.base import BaseExecutor
from core.models import ExecutionMode, Signal, Trade
from notifier import Notifier, format_signal


class AlertExecutor(BaseExecutor):
    mode = ExecutionMode.ALERT

    def __init__(
        self,
        notifier: Notifier,
        context: Callable[[Signal], str | None] | None = None,
        repo: Repository | None = None,
    ):
        self.notifier = notifier
        self.context = context
        self.repo = repo or NullRepository()

    def execute(self, signal: Signal) -> Trade | None:
        extra = self.context(signal) if self.context else None
        self.notifier.send(format_signal(signal, extra))
        if signal.id is not None:
            self.repo.save_alert(signal, getattr(self.notifier, "channel", "unknown"), extra)
        return None
