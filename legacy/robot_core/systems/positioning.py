from __future__ import annotations

import logging
import time
from typing import Optional

from robot_core.base_system import BaseSystem
from robot_core.config import kafka_config
from robot_core.systems.bus import BusSystem
from robot_core.systems.telemetry import TelemetrySystem
from robot_core.types import Pose


logger = logging.getLogger(__name__)


class PositioningSystem(BaseSystem):
    """
    Система «Позиционирование».

    Получает координаты и угол поворота (rotation) от навигационного сервера
    через BusSystem и хранит последнюю позу. Предоставляет API для КВМ и
    отправляет данные в телеметрию.
    """

    def __init__(self, bus: BusSystem, telemetry: TelemetrySystem, name: str = "positioning") -> None:
        super().__init__(name)
        self._bus = bus
        self._telemetry = telemetry
        self._current_pose: Optional[Pose] = None

        # подписываемся на топик позы от навигационного сервера
        self._bus.subscribe(kafka_config.pose_topic, self._on_pose_message)

    def _on_pose_message(self, message: Pose) -> None:
        """
        Callback для сообщений от навигационного сервера.

        Предполагается, что извне уже сформирован объект Pose
        (x: int, y: int, rotation: int).
        """
        logger.debug("PositioningSystem: received pose %r", message)
        self.update_pose(message)

    def update_pose(self, pose: Pose) -> None:
        self._current_pose = pose
        self._telemetry.report_pose(pose)

    def get_pose(self) -> Optional[Pose]:
        """
        API для КВМ: вернуть последнюю известную позу.
        """
        return self._current_pose

    def tick(self, dt: float) -> None:
        """
        Сама по себе система позиционирования на каждом тике может
        ничего не делать, так как обновляется по сообщениям.
        """
        return

