from __future__ import annotations

import logging
import math
from typing import Optional

from robot_core.base_system import BaseSystem
from robot_core.config import robot_config
from robot_core.systems.actuators import ActuatorsSystem
from robot_core.systems.positioning import PositioningSystem
from robot_core.types import DriveCommand, DriveDirection, Mission, MissionStatus, Pose


logger = logging.getLogger(__name__)


class MissionControlSystem(BaseSystem):
    """
    Система «Контроль выполнения миссии» (КВМ).

    Получает миссии от сервера (через BusSystem), опрашивает позиционирование,
    рассчитывает движение и отдаёт команды приводам.
    """

    def __init__(
        self,
        positioning: PositioningSystem,
        actuators: ActuatorsSystem,
        name: str = "mission_control",
    ) -> None:
        super().__init__(name)
        self._positioning = positioning
        self._actuators = actuators

        self._current_mission: Optional[Mission] = None
        self._mission_status: MissionStatus = MissionStatus.IDLE

        self._position_poll_interval = robot_config.position_poll_interval
        self._goal_check_interval = robot_config.goal_check_interval

        self._time_since_last_position_poll: float = 0.0
        self._time_since_last_goal_check: float = 0.0

    def set_mission(self, mission: Mission) -> None:
        logger.info("MissionControlSystem: new mission %r", mission)
        self._current_mission = mission
        self._mission_status = MissionStatus.IN_PROGRESS

    @property
    def mission_status(self) -> MissionStatus:
        return self._mission_status

    def _compute_drive_command(self, current: Pose, target: Pose) -> DriveCommand:
        """
        Простейший контроллер движения:
        - если далеко от цели — едем вперёд;
        - если прошли — стоп.
        Здесь только заглушка; реальные алгоритмы можно будет доработать.
        """
        dx = target.x - current.x
        dy = target.y - current.y
        distance = math.hypot(dx, dy)

        if distance < 1:
            return DriveCommand(direction=DriveDirection.STOP)

        # простая модель «ехать вперёд»
        speed = 50
        return DriveCommand(direction=DriveDirection.FORWARD, left_speed=speed, right_speed=speed)

    def _check_goal_reached(self, current: Pose, target: Pose) -> bool:
        dx = target.x - current.x
        dy = target.y - current.y
        distance = math.hypot(dx, dy)
        angle_diff = abs(target.rotation - current.rotation)

        return distance < 1 and angle_diff <= 1

    def tick(self, dt: float) -> None:
        if self._current_mission is None:
            return

        self._time_since_last_position_poll += dt
        self._time_since_last_goal_check += dt

        pose: Optional[Pose] = None

        # 2.3 — опрашивать позиционирование реже, чем проверять достижение цели.
        if self._time_since_last_position_poll >= self._position_poll_interval:
            pose = self._positioning.get_pose()
            self._time_since_last_position_poll = 0.0

        # если поза ещё не считана этим тиком — пробуем взять текущую
        if pose is None:
            pose = self._positioning.get_pose()

        if pose is None:
            logger.debug("MissionControlSystem: pose is unknown, skipping tick")
            return

        target = self._current_mission.target_pose

        # расчёт движения и команд приводам
        cmd = self._compute_drive_command(pose, target)
        self._actuators.apply_command(cmd)

        # более частая проверка достижения цели
        if self._time_since_last_goal_check >= self._goal_check_interval:
            self._time_since_last_goal_check = 0.0
            if self._check_goal_reached(pose, target):
                logger.info("MissionControlSystem: mission %s completed", self._current_mission.mission_id)
                self._mission_status = MissionStatus.COMPLETED
                self._actuators.apply_command(DriveCommand(direction=DriveDirection.STOP))

