from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KafkaConfig:
    """
    Конфигурация Kafka.

    Сейчас используется только как описание; реальные подключения
    будут добавлены позже.
    """

    bootstrap_servers: str = "localhost:9092"
    mission_topic: str = "missions"
    pose_topic: str = "poses"
    telemetry_topic: str = "telemetry"


@dataclass
class RobotConfig:
    """
    Общая конфигурация машинки.
    """

    vehicle_id: str = "vehicle-1"
    position_poll_interval: float = 0.2
    goal_check_interval: float = 0.05


kafka_config = KafkaConfig()
robot_config = RobotConfig()

