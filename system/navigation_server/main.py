"""Navigation Server entry point.

Captures frames, detects ArUco markers, publishes vehicle positions via MQTT.
"""

import logging
import sys
import time

import cv2

# Allow running as ``python -m system.navigation_server.main`` from repo root
sys.path.insert(0, __file__.rsplit("/system/", 1)[0])

from system.common.config import NavigationServerConfig, component_dotenv_path
from system.common.messages import PositionMessage
from system.common.topics import Topics
from system.navigation_server.camera import CameraManager
from system.navigation_server.aruco_detector import ArucoDetector
from system.navigation_server.coordinate_system import CoordinateSystem
from system.navigation_server.mqtt_client import NavMqttClient
from system.navigation_server.map_provider import MapProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [NAV] %(message)s")
log = logging.getLogger(__name__)


def main():
    cfg = NavigationServerConfig.load(env_path=component_dotenv_path(__file__))

    log.info("Initializing camera (device=%s, %dx%d)...",
             cfg.camera_device, cfg.camera_width, cfg.camera_height)
    camera = CameraManager(
        device=cfg.camera_device,
        skip_devices=cfg.camera_skip_devices,
        width=cfg.camera_width,
        height=cfg.camera_height,
    )
    if not camera.open():
        log.error("No camera found. Exiting.")
        return

    log.info("Camera ready: %s", camera.camera_path)

    detector = ArucoDetector(
        reference_ids=cfg.reference_marker_ids,
        mobile_ids=cfg.mobile_marker_ids,
    )
    coord = CoordinateSystem(
        map_width=cfg.map_width,
        map_height=cfg.map_height,
    )
    map_provider = MapProvider(cfg)

    mqtt = NavMqttClient(cfg, on_map_request=lambda: map_provider.publish_map(mqtt))
    mqtt.connect()

    frame_interval = 1.0 / cfg.publish_rate_hz
    log.info("Publishing positions at %d Hz", cfg.publish_rate_hz)

    vehicle_id_map = {mid: f"vehicle_{mid}" for mid in cfg.mobile_marker_ids}

    try:
        while True:
            t_start = time.time()
            ret, frame = camera.read_frame()
            if not ret:
                log.warning("Failed to read frame")
                time.sleep(0.1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            corners, ids, _ = detector.detect(gray)

            ref_markers = detector.filter_reference_markers(corners, ids)
            if ref_markers is not None:
                if not coord.is_calibrated:
                    if coord.calibrate(ref_markers):
                        log.info("Coordinate system calibrated")

            if coord.is_calibrated:
                mobiles = detector.get_mobile_markers(corners, ids)

                all_positions: dict[int, dict] = {}
                for mid, (m_corners, m_center) in mobiles.items():
                    xy = coord.transform_point(m_center, marker_id=mid)
                    rot = coord.calculate_rotation(m_corners, m_center, marker_id=mid)
                    if xy is not None:
                        all_positions[mid] = {
                            "vehicle_id": vehicle_id_map.get(mid, f"vehicle_{mid}"),
                            "x": xy[0],
                            "y": xy[1],
                            "rotation": rot if rot is not None else 0.0,
                        }

                for mid, pos in all_positions.items():
                    neighbors = [
                        {"vehicle_id": v["vehicle_id"], "x": v["x"], "y": v["y"], "rotation": v["rotation"]}
                        for other_mid, v in all_positions.items() if other_mid != mid
                    ]
                    msg = PositionMessage(
                        vehicle_id=pos["vehicle_id"],
                        x=pos["x"],
                        y=pos["y"],
                        rotation=pos["rotation"],
                        neighbors=neighbors,
                    )
                    mqtt.publish(Topics.vehicle_position(pos["vehicle_id"]), msg.to_json())

            elapsed = time.time() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        mqtt.disconnect()
        camera.release()


if __name__ == "__main__":
    main()
