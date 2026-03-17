"""MQTT topic constants for inter-component communication."""


class Topics:
    """Centralized MQTT topic definitions.

    Naming convention:
        nav/{vehicle_id}/position    - navigation server -> vehicle / control center
        vehicle/{vehicle_id}/...     - vehicle-related topics
        control/...                  - control center requests
    """

    @staticmethod
    def vehicle_position(vehicle_id: str) -> str:
        return f"nav/{vehicle_id}/position"

    @staticmethod
    def vehicle_position_wildcard() -> str:
        return "nav/+/position"

    @staticmethod
    def mission_assign(vehicle_id: str) -> str:
        return f"vehicle/{vehicle_id}/mission/assign"

    @staticmethod
    def mission_control(vehicle_id: str) -> str:
        return f"vehicle/{vehicle_id}/mission/control"

    @staticmethod
    def mission_status(vehicle_id: str) -> str:
        return f"vehicle/{vehicle_id}/mission/status"

    @staticmethod
    def mission_status_wildcard() -> str:
        return "vehicle/+/mission/status"

    @staticmethod
    def vehicle_status(vehicle_id: str) -> str:
        return f"vehicle/{vehicle_id}/status"

    @staticmethod
    def vehicle_status_wildcard() -> str:
        return "vehicle/+/status"

    MAP_REQUEST = "control/map/request"
    MAP_RESPONSE = "control/map/response"
