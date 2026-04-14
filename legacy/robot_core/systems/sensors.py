from __future__ import annotations

import logging
import time
from typing import List

from robot_core.base_system import BaseSystem
from robot_core.systems.telemetry import TelemetrySystem
from robot_core.types import SensorReading


logger = logging.getLogger(__name__)


class SensorsSystem(BaseSystem):
    """
    Система «Датчики».

    Пока реализована как заглушка: вместо реальных чтений просто
    не генерирует данных. Интерфейс предусмотрен для реальной
    интеграции с конкретными датчиками.
    """

    def __init__(self, telemetry: TelemetrySystem, name: str = "sensors") -> None:
        super().__init__(name)
        self._telemetry = telemetry

    def read_all(self) -> List[SensorReading]:
        """
        Читает показания всех датчиков.

        Сейчас возвращает пустой список как заглушку.
        """
        now = time.time()
        readings: List[SensorReading] = []
        # здесь позже будут реальные чтения
        logger.debug("SensorsSystem: read_all at %s, %d readings", now, len(readings))
        return readings

    def tick(self, dt: float) -> None:
        readings = self.read_all()
        if readings:
            self._telemetry.report_sensors(readings)

