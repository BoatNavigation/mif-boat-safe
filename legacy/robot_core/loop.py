from __future__ import annotations

import logging
import time
from typing import List

from robot_core.base_system import BaseSystem
from robot_core.config import kafka_config
from robot_core.systems.actuators import ActuatorsSystem
from robot_core.systems.bus import BusSystem
from robot_core.systems.mission_control import MissionControlSystem
from robot_core.systems.positioning import PositioningSystem
from robot_core.systems.sensors import SensorsSystem
from robot_core.systems.telemetry import TelemetrySystem
from robot_core.types import Mission, Pose


logger = logging.getLogger(__name__)


class RobotCore:
    """
    Главный оркестратор систем машинки.
    """

    def __init__(self) -> None:
        # базовая шина
        self.bus = BusSystem()

        # телеметрия
        self.telemetry = TelemetrySystem(bus=self.bus)

        # датчики
        self.sensors = SensorsSystem(telemetry=self.telemetry)

        # приводы
        self.actuators = ActuatorsSystem()

        # позиционирование
        self.positioning = PositioningSystem(bus=self.bus, telemetry=self.telemetry)

        # КВМ
        self.mission_control = MissionControlSystem(
            positioning=self.positioning,
            actuators=self.actuators,
        )

        # регистрируем получение миссий от сервера через шину
        self.bus.subscribe(kafka_config.mission_topic, self._on_mission_message)

        self._systems: List[BaseSystem] = [
            self.bus,
            self.telemetry,
            self.sensors,
            self.positioning,
            self.mission_control,
            self.actuators,
        ]

    def _on_mission_message(self, mission: Mission) -> None:
        logger.info("RobotCore: received mission %r", mission)
        self.mission_control.set_mission(mission)

    def start(self) -> None:
        for system in self._systems:
            logger.info("Starting system %s", system.name)
            system.start()

    def stop(self) -> None:
        for system in reversed(self._systems):
            logger.info("Stopping system %s", system.name)
            system.stop()

    def tick(self, dt: float) -> None:
        for system in self._systems:
            system.tick(dt)


def run(loop_hz: float = 20.0) -> None:
    """
    Запуск основного цикла робот-ядра.

    loop_hz — частота вызова tick в Гц.
    """
    logging.basicConfig(level=logging.INFO)

    core = RobotCore()
    core.start()

    period = 1.0 / loop_hz
    last_time = time.time()

    try:
        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            core.tick(dt)

            # ограничиваем частоту цикла
            sleep_time = max(0.0, period - (time.time() - now))
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Stopping RobotCore loop by KeyboardInterrupt")
    finally:
        core.stop()


if __name__ == "__main__":
    run()

