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
    
    def __init__(self, static_marker_ids=None, mobile_marker_id=0):
        """
        Args:
            static_marker_ids: Список ID стационарных меток (по умолчанию [1, 2, 3, 4])
            mobile_marker_id: ID метки на машинке (по умолчанию 0)
        """
        self.static_marker_ids = static_marker_ids or [1, 2, 3, 4]
        self.mobile_marker_id = mobile_marker_id
        
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
        """Детектирует метки на изображении.
        
        Returns:
            tuple: (corners, ids, rejected)
        """
        return self.detector.detectMarkers(gray_frame)
    
    @staticmethod
    def get_marker_center(corners):
        """Вычисляет центр метки как среднее значение её углов."""
        corners_2d = corners[0].reshape(-1, 2)
        center = np.mean(corners_2d, axis=0)
        return center.astype(np.float32)
    
    def filter_static_markers(self, corners, ids):
        """Фильтрует стационарные метки и возвращает их центры.
        
        Args:
            corners: Углы меток от detectMarkers
            ids: ID меток от detectMarkers
            
        Returns:
            dict: {marker_id: center_pixel} или None если не все метки найдены
        """
        if ids is None:
            return None
        
        static_markers = {}
        ids_flat = ids.flatten()
        
        for i, marker_id in enumerate(ids_flat):
            if marker_id in self.static_marker_ids:
                center = self.get_marker_center(corners[i])
                static_markers[marker_id] = center
        
        return static_markers if len(static_markers) == 4 else None
    
    def get_mobile_marker(self, corners, ids):
        """Находит метку на машинке и возвращает её углы и центр.
        
        Args:
            corners: Углы меток от detectMarkers
            ids: ID меток от detectMarkers
            
        Returns:
            tuple: (marker_corners, center_pixel) или (None, None) если метка не найдена
        """
        if ids is None:
            return None, None
        
        ids_flat = ids.flatten()
        for i, marker_id in enumerate(ids_flat):
            if marker_id == self.mobile_marker_id:
                center = self.get_marker_center(corners[i])
                return corners[i], center
        
        return None, None
    
    def draw_mobile_marker(self, frame, marker_corners, center_pixel, rotation=None):
        """Рисует метку машинки с указанием "низа" и "верха".
        
        Использует фиксированный порядок углов ArUco:
        - Угол 0 (первый) = ВЕРХ (FRONT)
        - Угол 2 (третий) = НИЗ (REAR)
        
        Args:
            frame: Кадр для отрисовки
            marker_corners: Углы метки
            center_pixel: Центр метки в пикселях
            rotation: Угол поворота в радианах (опционально)
        """
        if marker_corners is None or center_pixel is None:
            return frame
        
        # Преобразуем углы метки в массив точек
        corners_2d = marker_corners[0].reshape(-1, 2).astype(np.int32)
        
        # Рисуем контур метки
        cv2.polylines(frame, [corners_2d], True, (0, 255, 255), 2)
        
        # Используем фиксированный порядок углов:
        # Угол 0 = ВЕРХ (FRONT) - перед машинки
        # Угол 2 = НИЗ (REAR) - зад машинки
        top_corner = corners_2d[0]  # Первый угол = верх
        bottom_corner = corners_2d[2]  # Третий угол = низ
        
        # Рисуем центр метки
        center_int = tuple(map(int, center_pixel))
        cv2.circle(frame, center_int, 5, (0, 255, 255), -1)
        
        # Рисуем линию от центра к "верху" (перед машинки) - зеленая толстая линия
        cv2.line(frame, center_int, tuple(top_corner), (0, 255, 0), 4)
        cv2.circle(frame, tuple(top_corner), 10, (0, 255, 0), -1)
        cv2.putText(frame, "FRONT", (top_corner[0] + 15, top_corner[1]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Рисуем линию от центра к "низу" (зад машинки) - красная толстая линия
        cv2.line(frame, center_int, tuple(bottom_corner), (0, 0, 255), 4)
        cv2.circle(frame, tuple(bottom_corner), 10, (0, 0, 255), -1)
        cv2.putText(frame, "REAR", (bottom_corner[0] + 15, bottom_corner[1]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Рисуем стрелку направления (от центра к "верху")
        cv2.arrowedLine(frame, center_int, tuple(top_corner), (0, 255, 0), 3, tipLength=0.2)
        
        # Подписываем ID метки
        cv2.putText(frame, f"ID:{self.mobile_marker_id}",
                   (center_int[0] + 20, center_int[1]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return frame

