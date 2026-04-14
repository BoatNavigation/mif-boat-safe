from __future__ import annotations

import logging
from typing import List, Optional

from robot_core.base_system import BaseSystem
from robot_core.config import kafka_config
from robot_core.systems.bus import BusSystem
from robot_core.types import Pose, SensorReading, TelemetryData, MissionStatus


logger = logging.getLogger(__name__)


class TelemetrySystem(BaseSystem):
    """
    Система телеметрии.

    Принимает данные от позиционирования и датчиков, агрегирует и
    отправляет наружу через BusSystem (Kafka-топик телеметрии).
    """

    def __init__(self, bus: BusSystem, name: str = "telemetry") -> None:
        super().__init__(name)
        self._bus = bus
        self._latest_pose: Optional[Pose] = None
        self._mission_status: MissionStatus = MissionStatus.IDLE
        self._sensor_buffer: List[SensorReading] = []

    def report_pose(self, pose: Pose) -> None:
        self._latest_pose = pose

    def report_sensors(self, readings: List[SensorReading]) -> None:
        self._sensor_buffer.extend(readings)

    def report_mission_status(self, status: MissionStatus) -> None:
        self._mission_status = status

    def _build_telemetry(self) -> TelemetryData:
        data = TelemetryData(
            pose=self._latest_pose,
            mission_status=self._mission_status,
            sensor_readings=list(self._sensor_buffer),
        )
        # после сборки очищаем буфер датчиков
        self._sensor_buffer.clear()
        return data

    def tick(self, dt: float) -> None:
        """
        На каждом шаге собираем текущие данные и публикуем их наружу.
        В реальной системе можно будет ограничить частоту отправки.
        """
        telemetry = self._build_telemetry()
        logger.debug("TelemetrySystem: publishing telemetry %r", telemetry)
        self._bus.publish(kafka_config.telemetry_topic, telemetry)

