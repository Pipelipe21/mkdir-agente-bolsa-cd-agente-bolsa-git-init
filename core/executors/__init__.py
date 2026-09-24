from collections.abc import Callable

from core.executors.alert import AlertExecutor
from core.executors.base import BaseExecutor
from core.models import ExecutionMode, Signal
from notifier import Notifier


def build_executor(
    mode: ExecutionMode,
    notifier: Notifier,
    context: Callable[[Signal], str | None] | None = None,
) -> BaseExecutor:
    """Único punto donde el modo decide qué executor se usa."""
    if mode is ExecutionMode.ALERT:
        return AlertExecutor(notifier, context)
    raise NotImplementedError(f"El executor '{mode}' llega en una fase posterior")


__all__ = ["AlertExecutor", "BaseExecutor", "build_executor"]
