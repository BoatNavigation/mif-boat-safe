from __future__ import annotations

import logging
from typing import Protocol

from robot_core.base_system import BaseSystem
from robot_core.types import DriveCommand, DriveDirection


logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO  # type: ignore[import]
except ImportError:  # не на Raspberry Pi или библиотека не установлена
    GPIO = None  # type: ignore[assignment]


class MotorDriver(Protocol):
    """
    Интерфейс низкоуровневого драйвера моторов.

    Реальная реализация — GPIO-драйвер на Raspberry Pi.
    """

    def forward(self, left_speed: int, right_speed: int) -> None: ...

    def backward(self, left_speed: int, right_speed: int) -> None: ...

    def turn_left(self, speed: int) -> None: ...

    def turn_right(self, speed: int) -> None: ...

    def stop(self) -> None: ...


class DummyMotorDriver:
    """
    Заглушка драйвера моторов.

    Используется, если RPi.GPIO недоступен (например, при запуске не на плате).
    """

    def forward(self, left_speed: int, right_speed: int) -> None:
        logger.info("DummyMotorDriver: forward L=%d R=%d", left_speed, right_speed)

    def backward(self, left_speed: int, right_speed: int) -> None:
        logger.info("DummyMotorDriver: backward L=%d R=%d", left_speed, right_speed)

    def turn_left(self, speed: int) -> None:
        logger.info("DummyMotorDriver: turn_left speed=%d", speed)

    def turn_right(self, speed: int) -> None:
        logger.info("DummyMotorDriver: turn_right speed=%d", speed)

    def stop(self) -> None:
        logger.info("DummyMotorDriver: stop")


class GPIOMotorDriver:
    """
    GPIO-драйвер моторов для Raspberry Pi 4B.

    Логика основана на существующем коде из LocalNavigation/machine.py:
    - те же пины
    - та же схема управления направлением
    """

    # Пины для левого двигателя
    PWMA_L = 36
    AIN1_L = 40
    AIN2_L = 38

    # Пины для правого двигателя
    PWMB_R = 33
    BIN1_R = 35
    BIN2_R = 37

    PWM_FREQUENCY = 255  # Гц

    def __init__(self) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not available, cannot use GPIOMotorDriver")

        GPIO.setmode(GPIO.BOARD)

        # инициализация пинов
        GPIO.setup(self.PWMA_L, GPIO.OUT)
        GPIO.setup(self.AIN1_L, GPIO.OUT)
        GPIO.setup(self.AIN2_L, GPIO.OUT)

        GPIO.setup(self.PWMB_R, GPIO.OUT)
        GPIO.setup(self.BIN1_R, GPIO.OUT)
        GPIO.setup(self.BIN2_R, GPIO.OUT)

        # ШИМ
        self._pwm_l = GPIO.PWM(self.PWMA_L, self.PWM_FREQUENCY)
        self._pwm_r = GPIO.PWM(self.PWMB_R, self.PWM_FREQUENCY)

        self._pwm_l.start(0)
        self._pwm_r.start(0)

    @staticmethod
    def _clamp_speed(value: int) -> int:
        return max(0, min(100, value))

    def forward(self, left_speed: int, right_speed: int) -> None:
        left_speed = self._clamp_speed(left_speed)
        right_speed = self._clamp_speed(right_speed)

        # левый мотор: по часовой стрелке
        GPIO.output(self.AIN1_L, GPIO.LOW)
        GPIO.output(self.AIN2_L, GPIO.HIGH)
        self._pwm_l.ChangeDutyCycle(left_speed)

        # правый мотор: по часовой стрелке
        GPIO.output(self.BIN1_R, GPIO.HIGH)
        GPIO.output(self.BIN2_R, GPIO.LOW)
        self._pwm_r.ChangeDutyCycle(right_speed)

    def backward(self, left_speed: int, right_speed: int) -> None:
        left_speed = self._clamp_speed(left_speed)
        right_speed = self._clamp_speed(right_speed)

        # левый мотор: против часовой
        GPIO.output(self.AIN1_L, GPIO.HIGH)
        GPIO.output(self.AIN2_L, GPIO.LOW)
        self._pwm_l.ChangeDutyCycle(left_speed)

        # правый мотор: против часовой
        GPIO.output(self.BIN1_R, GPIO.LOW)
        GPIO.output(self.BIN2_R, GPIO.HIGH)
        self._pwm_r.ChangeDutyCycle(right_speed)

    def turn_left(self, speed: int) -> None:
        speed = self._clamp_speed(speed)
        # левый назад, правый вперёд
        self.backward(speed, speed)

    def turn_right(self, speed: int) -> None:
        speed = self._clamp_speed(speed)
        # левый вперёд, правый назад
        self.forward(speed, speed)
        # затем инверсия правого
        GPIO.output(self.BIN1_R, GPIO.LOW)
        GPIO.output(self.BIN2_R, GPIO.HIGH)

    def stop(self) -> None:
        GPIO.output(self.AIN1_L, GPIO.LOW)
        GPIO.output(self.AIN2_L, GPIO.LOW)
        self._pwm_l.ChangeDutyCycle(0)

        GPIO.output(self.BIN1_R, GPIO.LOW)
        GPIO.output(self.BIN2_R, GPIO.LOW)
        self._pwm_r.ChangeDutyCycle(0)

    def cleanup(self) -> None:
        """
        Остановка ШИМ и очистка GPIO.
        """
        try:
            self.stop()
        finally:
            self._pwm_l.stop()
            self._pwm_r.stop()
            GPIO.cleanup()


class ActuatorsSystem(BaseSystem):
    """
    Система «Приводы».

    Получает абстрактные команды движения от КВМ и передаёт их
    низкоуровневому драйверу моторов.
    """

    def __init__(self, driver: MotorDriver | None = None, name: str = "actuators") -> None:
        super().__init__(name)

        if driver is not None:
            self._driver: MotorDriver = driver
        else:
            # если доступен RPi.GPIO — используем реальный GPIO-драйвер,
            # иначе — заглушку
            if GPIO is not None:
                logger.info("ActuatorsSystem: using GPIOMotorDriver")
                self._driver = GPIOMotorDriver()
            else:
                logger.info("ActuatorsSystem: using DummyMotorDriver (no GPIO)")
                self._driver = DummyMotorDriver()

    def apply_command(self, cmd: DriveCommand) -> None:
        logger.debug("ActuatorsSystem: apply_command %r", cmd)

        if cmd.direction is DriveDirection.FORWARD:
            self._driver.forward(cmd.left_speed, cmd.right_speed)
        elif cmd.direction is DriveDirection.BACKWARD:
            self._driver.backward(cmd.left_speed, cmd.right_speed)
        elif cmd.direction is DriveDirection.LEFT:
            self._driver.turn_left(max(cmd.left_speed, cmd.right_speed))
        elif cmd.direction is DriveDirection.RIGHT:
            self._driver.turn_right(max(cmd.left_speed, cmd.right_speed))
        elif cmd.direction is DriveDirection.STOP:
            self._driver.stop()
        else:
            logger.warning("ActuatorsSystem: unknown direction %r", cmd.direction)

    def tick(self, dt: float) -> None:
        """
        В текущей простой модели приводы действуют только по событиям
        apply_command, поэтому tick ничего не делает.
        """
        return

    def stop(self) -> None:
        """
        Останавливает приводы и, если доступно, очищает GPIO.
        """
        try:
            self._driver.stop()
        finally:
            if hasattr(self._driver, "cleanup"):
                try:
                    getattr(self._driver, "cleanup")()
                except Exception:
                    logger.exception("ActuatorsSystem: error during driver cleanup")
        super().stop()

