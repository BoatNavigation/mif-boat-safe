"""Camera management for the navigation server."""

import cv2
import glob


class CameraManager:
    """Finds and manages a V4L2 camera device."""

    def __init__(self, device: str | None = None, skip_devices: list[str] | None = None,
                 width: int = 1280, height: int = 720):
        self.device = device
        self.skip_devices = skip_devices or []
        self.width = width
        self.height = height
        self.cap: cv2.VideoCapture | None = None
        self.camera_path: str | None = None

    def open(self) -> bool:
        """Open a specific device or auto-detect an available one."""
        if self.device:
            return self._try_open(self.device)
        return self._find_available()

    def _try_open(self, path: str) -> bool:
        cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap = cap
                self.camera_path = path
                return True
            cap.release()
        return False

    def _find_available(self) -> bool:
        for path in sorted(glob.glob("/dev/video*")):
            if path in self.skip_devices:
                continue
            if self._try_open(path):
                return True
        return False

    def read_frame(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
