"""Obstacle detection service – STUB.

Future implementation will use sensors / camera to detect nearby obstacles.
"""

from __future__ import annotations

import logging
import threading

from system.vehicle.shared_state import SharedState

log = logging.getLogger(__name__)


class ObstacleDetectionService:
    """Stub: always reports no obstacles."""

    def __init__(self, shared: SharedState):
        self._shared = shared
        self._obstacles: list[dict] = []
        self._lock = threading.Lock()

    def start(self):
        log.info("ObstacleDetectionService started (STUB – no obstacles reported)")

    def stop(self):
        pass

    def get_obstacles(self) -> list[dict]:
        """Return list of detected obstacles (empty in stub)."""
        with self._lock:
            return list(self._obstacles)
