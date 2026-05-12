"""Manual control service – listens for manual drive commands via MQTT.

When a manual command arrives, the active mission (if any) is paused so the
navigation loop stops issuing commands, then the command is forwarded to the
drive service.
"""

from __future__ import annotations

import logging

from system.common.messages import ManualControlMessage
from system.common.topics import Topics
from system.vehicle.services.drive_service import DriveService
from system.vehicle.shared_state import SharedState

log = logging.getLogger(__name__)

_ALLOWED = {"forward", "backward", "left", "right", "stop"}


class ManualControlService:
    def __init__(self, vehicle_id: str, shared: SharedState,
                 drive: DriveService, mqtt_client, mission_service=None):
        self._vehicle_id = vehicle_id
        self._shared = shared
        self._drive = drive
        self._mqtt = mqtt_client
        self._mission_svc = mission_service

    def start(self):
        topic = Topics.vehicle_manual(self._vehicle_id)
        self._mqtt.subscribe(topic, self._on_manual)
        log.info("ManualControlService subscribed to %s", topic)

    def _on_manual(self, msg):
        try:
            payload = ManualControlMessage.from_json(msg.payload)
        except Exception:
            log.exception("Bad manual control payload")
            return

        cmd = payload.command
        if cmd not in _ALLOWED:
            log.warning("Manual command rejected: %s", cmd)
            return

        mission = self._shared.get_mission()
        if mission.status == "executing":
            log.info("MANUAL pauses mission %s", mission.mission_id)
            self._shared.set_mission_status("paused")
            if self._mission_svc:
                self._mission_svc.notify_paused_by_manual()

        log.info("MANUAL >> %s", cmd.upper())
        self._drive.send_command(cmd)
