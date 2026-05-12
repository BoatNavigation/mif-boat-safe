"""Motor control service – reads commands from a queue and drives GPIO.

Pin layout and motor functions taken directly from LocalNavigation/machine.py.
On non-Raspberry Pi systems a mock GPIO is used so the rest of the stack can
be developed and tested without hardware.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

log = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False
    log.warning("RPi.GPIO not available – using mock driver")


# ---------------------------------------------------------------------------
# Pin definitions (BOARD numbering)
# ---------------------------------------------------------------------------

PWMA_L = 36
AIN1_L = 40
AIN2_L = 38

PWMB_R = 33
BIN1_R = 35
BIN2_R = 37

PWM_FREQ = 255


class DriveService:
    """Consumes drive commands from a thread-safe queue and actuates motors."""

    _HUMAN_RU = {
        "forward": "ВПЕРЁД",
        "backward": "НАЗАД",
        "left": "ВЛЕВО (поворот)",
        "right": "ВПРАВО (поворот)",
        "stop": "СТОП",
    }

    def __init__(self, duty_cycle: int = 20):
        self._duty = duty_cycle
        self._cmd_queue: queue.Queue[str] = queue.Queue(maxsize=32)
        self._thread: threading.Thread | None = None
        self._running = False
        self._pwm_l = None
        self._pwm_r = None
        self._last_cmd: str | None = None

    def start(self):
        self._init_gpio()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DriveService")
        self._thread.start()
        log.info("DriveService started (GPIO=%s, duty=%d)", _HAS_GPIO, self._duty)

    def send_command(self, command: str):
        """Push a command: 'forward', 'backward', 'left', 'right', 'stop'."""
        try:
            self._cmd_queue.put_nowait(command)
        except queue.Full:
            pass

    def stop(self):
        self._running = False
        self.send_command("stop")
        if self._thread:
            self._thread.join(timeout=2)
        self._cleanup_gpio()

    # -- internal ----------------------------------------------------------

    def _loop(self):
        while self._running:
            try:
                cmd = self._cmd_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._execute(cmd)

    def _execute(self, cmd: str):
        self._motor_left("stop")
        self._motor_right("stop")

        human = self._HUMAN_RU.get(cmd, cmd)
        if cmd != self._last_cmd:
            log.info("DRIVE >> %s (%s) | duty=%d%%", cmd.upper(), human, self._duty)
        else:
            log.debug("DRIVE .. %s (%s)", cmd, human)
        self._last_cmd = cmd

        if cmd == "forward":
            self._motor_left("forward")
            self._motor_right("forward")
        elif cmd == "backward":
            self._motor_left("backward")
            self._motor_right("backward")
        elif cmd == "left":
            self._motor_left("backward")
            self._motor_right("forward")
        elif cmd == "right":
            self._motor_left("forward")
            self._motor_right("backward")
        elif cmd == "stop":
            pass
        else:
            log.warning("Unknown drive command: %s", cmd)

    # -- GPIO helpers (mirror machine.py) ----------------------------------

    def _init_gpio(self):
        if not _HAS_GPIO:
            return
        GPIO.setmode(GPIO.BOARD)
        for pin in (PWMA_L, AIN1_L, AIN2_L, PWMB_R, BIN1_R, BIN2_R):
            GPIO.setup(pin, GPIO.OUT)
        self._pwm_l = GPIO.PWM(PWMA_L, PWM_FREQ)
        self._pwm_l.start(0)
        self._pwm_r = GPIO.PWM(PWMB_R, PWM_FREQ)
        self._pwm_r.start(0)

    def _cleanup_gpio(self):
        if not _HAS_GPIO:
            return
        if self._pwm_l:
            self._pwm_l.stop()
        if self._pwm_r:
            self._pwm_r.stop()
        GPIO.cleanup()

    def _motor_left(self, direction: str):
        if not _HAS_GPIO:
            return
        if direction == "forward":
            GPIO.output(AIN1_L, GPIO.LOW)
            GPIO.output(AIN2_L, GPIO.HIGH)
            self._pwm_l.ChangeDutyCycle(self._duty)
        elif direction == "backward":
            GPIO.output(AIN1_L, GPIO.HIGH)
            GPIO.output(AIN2_L, GPIO.LOW)
            self._pwm_l.ChangeDutyCycle(self._duty)
        else:
            GPIO.output(AIN1_L, GPIO.LOW)
            GPIO.output(AIN2_L, GPIO.LOW)
            self._pwm_l.ChangeDutyCycle(0)

    def _motor_right(self, direction: str):
        if not _HAS_GPIO:
            return
        if direction == "forward":
            GPIO.output(BIN1_R, GPIO.HIGH)
            GPIO.output(BIN2_R, GPIO.LOW)
            self._pwm_r.ChangeDutyCycle(self._duty)
        elif direction == "backward":
            GPIO.output(BIN1_R, GPIO.LOW)
            GPIO.output(BIN2_R, GPIO.HIGH)
            self._pwm_r.ChangeDutyCycle(self._duty)
        else:
            GPIO.output(BIN1_R, GPIO.LOW)
            GPIO.output(BIN2_R, GPIO.LOW)
            self._pwm_r.ChangeDutyCycle(0)
