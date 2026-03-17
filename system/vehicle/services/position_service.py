"""Listens for position updates from the navigation server via MQTT."""

from __future__ import annotations

import logging
import threading

from system.common.messages import PositionMessage
from system.common.topics import Topics
from system.vehicle.shared_state import SharedState

log = logging.getLogger(__name__)


class PositionService:
    """Subscribes to ``nav/{vehicle_id}/position`` and updates SharedState."""

    def __init__(self, vehicle_id: str, shared: SharedState, mqtt_client):
        self._vehicle_id = vehicle_id
        self._shared = shared
        self._mqtt = mqtt_client
        self._thread: threading.Thread | None = None

    def start(self):
        topic = Topics.vehicle_position(self._vehicle_id)
        self._mqtt.subscribe(topic, self._on_position)
        log.info("PositionService subscribed to %s", topic)

    def _on_position(self, msg):
        try:
            pos = PositionMessage.from_json(msg.payload)
            self._shared.update_position(pos.x, pos.y, pos.rotation)
            self._shared.update_neighbors(pos.neighbors)
        except Exception:
            log.exception("Failed to parse position message")
