"""Camera management for the navigation server."""

import cv2
import glob


class CameraManager:
    """Local V4L2 camera or IP camera (RTSP)."""

    def __init__(
        self,
        device: str | None = None,
        rtsp_url: str | None = None,
        skip_devices: list[str] | None = None,
        width: int = 1280,
        height: int = 720,
    ):
        self.device = device
        self.rtsp_url = rtsp_url
        self.skip_devices = skip_devices or []
        self.width = width
        self.height = height
        self.cap: cv2.VideoCapture | None = None
        self.camera_path: str | None = None

    def open(self) -> bool:
        """Open RTSP stream, a specific V4L2 device, or auto-detect."""
        if self.rtsp_url:
            return self._try_open_rtsp(self.rtsp_url)
        if self.device:
            return self._try_open_v4l2(self.device)
        return self._find_available()

    def _try_open_rtsp(self, url: str) -> bool:
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap = cap
                self.camera_path = url
                return True
            cap.release()
        return False

    def _try_open_v4l2(self, path: str) -> bool:
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
            if self._try_open_v4l2(path):
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
