from __future__ import annotations

import logging
from typing import Any, Callable, DefaultDict, Dict, List
from collections import defaultdict

from robot_core.base_system import BaseSystem


logger = logging.getLogger(__name__)

MessageCallback = Callable[[Any], None]


class BusSystem(BaseSystem):
    """
    Listener/Publisher система.

    Пока реализована как внутренняя шина с pub/sub и логированием вместо
    реальной Kafka. Интерфейс максимально приближен к тому, что понадобится
    для интеграции с брокером.
    """

    def __init__(self, name: str = "bus") -> None:
        super().__init__(name)
        self._subscribers: DefaultDict[str, List[MessageCallback]] = defaultdict(list)

    def subscribe(self, topic: str, callback: MessageCallback) -> None:
        logger.info("BusSystem: subscribe %s -> %s", topic, callback)
        self._subscribers[topic].append(callback)

    def publish(self, topic: str, message: Any) -> None:
        """
        Публикация сообщения во внутреннюю шину.

        Сейчас: сразу синхронно вызывает callbacks всех подписчиков.
        В будущем: здесь будет отправка в Kafka, а получение — в отдельном
        потоке/процессе.
        """
        logger.debug("BusSystem: publish topic=%s message=%r", topic, message)
        for callback in self._subscribers.get(topic, []):
            try:
                callback(message)
            except Exception:
                logger.exception("BusSystem: error delivering message to %s", callback)

    def tick(self, dt: float) -> None:
        """
        Для stub-реализации ничего не делает.
        """
        return

