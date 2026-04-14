"""Модуль для детекции ArUco меток и работы с камерой."""

import cv2
import glob
import numpy as np


class CameraManager:
    """Управление камерой."""
    
    def __init__(self, skip_devices=None):
        """
        Args:
            skip_devices: Список устройств для пропуска (например, ['/dev/video0'])
        """
        self.skip_devices = skip_devices or []
        self.cap = None
        self.camera_path = None
    
    def find_available_camera(self):
        """Автоматически находит доступную камеру среди /dev/video* устройств."""
        video_devices = sorted(glob.glob("/dev/video*"))
        
        print(f"Найдено видеоустройств: {len(video_devices)}")
        for device in video_devices:
            print(f"  - {device}")
        
        for device_path in video_devices:
            if device_path in self.skip_devices:
                continue
            print(f"\nПробуем открыть {device_path}...")
            cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✓ Камера {device_path} успешно открыта!")
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    self.cap = cap
                    self.camera_path = device_path
                    return True
                else:
                    cap.release()
            else:
                print(f"✗ Не удалось открыть {device_path}")
        
        return False
    
    def read_frame(self):
        """Читает кадр с камеры."""
        if self.cap is None:
            return None, None
        ret, frame = self.cap.read()
        return ret, frame
    
    def release(self):
        """Освобождает ресурсы камеры."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class ArucoDetector:
    """Детектор ArUco меток."""
    
    def __init__(self, static_marker_ids=None, mobile_marker_ids=None):
        """
        Args:
            static_marker_ids: Список ID стационарных меток (по умолчанию [1, 2, 3, 4])
            mobile_marker_ids: Список ID подвижных меток на машинке (по умолчанию [8, 0])
                              Первая метка - передняя, вторая - задняя
        """
        self.static_marker_ids = static_marker_ids or [1, 2, 3, 4]
        if mobile_marker_ids is None:
            mobile_marker_ids = [8, 0]  # По умолчанию: 8 - передняя, 0 - задняя
        self.mobile_marker_ids = mobile_marker_ids
        self.front_marker_id = mobile_marker_ids[0]
        self.rear_marker_id = mobile_marker_ids[1]
        
        # Инициализация детектора ArUco
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        parameters = cv2.aruco.DetectorParameters()
        parameters.adaptiveThreshWinSizeMin = 3
        parameters.adaptiveThreshWinSizeMax = 23
        parameters.adaptiveThreshWinSizeStep = 10
        parameters.minMarkerPerimeterRate = 0.03
        parameters.maxMarkerPerimeterRate = 4.0
        parameters.polygonalApproxAccuracyRate = 0.03
        parameters.minCornerDistanceRate = 0.05
        
        self.detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    
    def detect_markers(self, gray_frame):
        """Детектирует метки на изображении."""
        return self.detector.detectMarkers(gray_frame)
    
    @staticmethod
    def get_marker_center(corners):
        """Вычисляет центр метки как среднее значение её углов."""
        corners_2d = corners[0].reshape(-1, 2)
        center = np.mean(corners_2d, axis=0)
        return center.astype(np.float32)
    
    def filter_static_markers(self, corners, ids):
        """Фильтрует стационарные метки и возвращает их центры."""
        if ids is None:
            return None
        
        static_markers = {}
        ids_flat = ids.flatten()
        
        for i, marker_id in enumerate(ids_flat):
            if marker_id in self.static_marker_ids:
                center = self.get_marker_center(corners[i])
                static_markers[marker_id] = center
        
        return static_markers if len(static_markers) == 4 else None
    
    def get_mobile_marker_center(self, corners, ids):
        """Находит центр подвижной метки (для обратной совместимости).
        
        Возвращает центр первой метки из mobile_marker_ids.
        """
        if ids is None:
            return None
        
        ids_flat = ids.flatten()
        for i, marker_id in enumerate(ids_flat):
            if marker_id == self.front_marker_id:
                return self.get_marker_center(corners[i])
        return None
    
    def get_mobile_markers(self, corners, ids):
        """Находит обе метки на машинке (переднюю и заднюю) и возвращает их центры.
        
        Returns:
            tuple: (front_center, rear_center) или (None, None) если метки не найдены
                   front_center - центр передней метки
                   rear_center - центр задней метки
        """
        if ids is None:
            return None, None
        
        front_center = None
        rear_center = None
        ids_flat = ids.flatten()
        
        for i, marker_id in enumerate(ids_flat):
            if marker_id == self.front_marker_id:
                front_center = self.get_marker_center(corners[i])
            elif marker_id == self.rear_marker_id:
                rear_center = self.get_marker_center(corners[i])
        
        return front_center, rear_center

