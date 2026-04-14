from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


@dataclass
class Pose:
    """
    Поза машинки в целочисленных координатах.

    Важно: по требованию системы x, y и rotation задаются целыми числами.
    """

    x: int
    y: int
    rotation: int  # угол поворота в условных целочисленных единицах
    timestamp: float


@dataclass
class Mission:
    """
    Миссия для КВМ.
    """

    mission_id: str
    vehicle_id: str
    target_pose: Pose


class DriveDirection(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"


@dataclass
class DriveCommand:
    """
    Абстрактная команда движения.

    На этом уровне задаём целевой режим движения, который далее адаптируется
    к конкретной реализации приводов.
    """

    direction: DriveDirection
    left_speed: int = 0   # 0-100 условных процентов
    right_speed: int = 0  # 0-100 условных процентов


class MissionStatus(str, Enum):
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SensorReading:
    """
    Унифицированное представление показаний датчиков.
    """

    sensor_type: str
    values: Dict[str, float]
    timestamp: float


@dataclass
class TelemetryData:
    """
    Телеметрия, отправляемая наружу.
    """

    pose: Optional[Pose] = None
    mission_status: MissionStatus = MissionStatus.IDLE
    sensor_readings: List[SensorReading] = field(default_factory=list)

