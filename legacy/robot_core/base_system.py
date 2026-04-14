from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSystem(ABC):
    """
    Абстрактная базовая система.

    Все системы (датчики, позиционирование, КВМ, приводы, телеметрия, bus)
    наследуются от этого класса и реализуют общий жизненный цикл.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._started: bool = False

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        """
        Инициализация ресурсов системы.
        """
        self._started = True

    def stop(self) -> None:
        """
        Освобождение ресурсов системы.
        """
        self._started = False

    @abstractmethod
    def tick(self, dt: float) -> None:
        """
        Периодический вызов главного цикла.
        dt — прошедшее время в секундах с прошлого шага.
        """

    def handle_message(self, message: Any) -> None:
        """
        Опциональный обработчик сообщений от шины/других систем.
        """
        # По умолчанию ничего не делает
        return

