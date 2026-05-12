"""Navigation service – steers the vehicle toward the current waypoint.

Simple proportional controller:
1. Compute angle to target.
2. If heading error is large -> rotate in place (left / right).
3. Otherwise -> drive forward.
4. When within tolerance -> waypoint reached, advance mission.
"""

from __future__ import annotations

import logging
import math
import threading
import time

from system.vehicle.shared_state import SharedState
from system.vehicle.services.drive_service import DriveService
from system.vehicle.services.obstacle_avoidance import ObstacleAvoidanceService

log = logging.getLogger(__name__)


class NavigationService:
    def __init__(self, shared: SharedState, drive: DriveService,
                 avoidance: ObstacleAvoidanceService,
                 mission_service=None,
                 position_tolerance: float = 5.0,
                 angle_tolerance: float = 0.2,
                 loop_rate_hz: int = 10):
        self._shared = shared
        self._drive = drive
        self._avoidance = avoidance
        self._mission_svc = mission_service
        self._pos_tol = position_tolerance
        self._ang_tol = angle_tolerance
        self._dt = 1.0 / loop_rate_hz
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_target_idx: int | None = None
        self._last_cmd: str | None = None
        self._tick_count = 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="NavigationService")
        self._thread.start()
        log.info("NavigationService started (tol=%.1f, ang_tol=%.2f)", self._pos_tol, self._ang_tol)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while self._running:
            t0 = time.time()
            self._tick()
            elapsed = time.time() - t0
            remaining = self._dt - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _tick(self):
        mission = self._shared.get_mission()
        if mission.status != "executing":
            return

        wp = self._shared.get_current_waypoint()
        if wp is None:
            return

        pos = self._shared.get_position()
        if not pos.valid:
            return

        target_x = wp["x"]
        target_y = wp["y"]
        idx = mission.current_waypoint_idx
        total = len(mission.waypoints)

        if idx != self._last_target_idx:
            log.info("TARGET >> wp %d/%d -> (%.2f, %.2f) [action=%s]",
                     idx + 1, total, target_x, target_y, wp.get("action", "none"))
            self._last_target_idx = idx

        dx = target_x - pos.x
        dy = target_y - pos.y
        dist = math.hypot(dx, dy)

        if dist < self._pos_tol:
            action = wp.get("action", "none")
            params = wp.get("params", {})

            log.info("REACHED wp %d/%d at (%.2f, %.2f) | dist=%.2f | action=%s",
                     idx + 1, total, pos.x, pos.y, dist, action)

            if action == "wait":
                duration = params.get("duration", 0)
                if duration > 0:
                    log.info("WAIT %.1fs at wp %d", duration, idx + 1)
                    self._drive.send_command("stop")
                    time.sleep(duration)

            if action == "stop":
                self._drive.send_command("stop")

            self._shared.advance_waypoint()
            if self._mission_svc:
                new_mission = self._shared.get_mission()
                if new_mission.status == "completed":
                    log.info("MISSION COMPLETED (%s)", new_mission.mission_id)
                    self._mission_svc.notify_completed()
                    self._drive.send_command("stop")
                else:
                    self._mission_svc.notify_waypoint_reached(idx)
            return

        desired_angle = math.atan2(dy, dx)
        heading_error = desired_angle - pos.rotation
        # Normalise to [-pi, pi]
        heading_error = math.atan2(math.sin(heading_error), math.cos(heading_error))

        raw_cmd: str
        if abs(heading_error) > self._ang_tol:
            raw_cmd = "left" if heading_error > 0 else "right"
        else:
            raw_cmd = "forward"

        cmd = self._avoidance.filter_command(raw_cmd)

        self._tick_count += 1
        if cmd != self._last_cmd or self._tick_count % 20 == 0:
            log.info(
                "NAV pos=(%.2f, %.2f, %.0f°) -> wp%d=(%.2f, %.2f) | dist=%.2f | hdg_err=%.0f° | cmd=%s%s",
                pos.x, pos.y, math.degrees(pos.rotation),
                idx + 1, target_x, target_y, dist,
                math.degrees(heading_error), cmd,
                "" if cmd == raw_cmd else f" (raw={raw_cmd}, avoidance)",
            )
        self._last_cmd = cmd
        self._drive.send_command(cmd)
