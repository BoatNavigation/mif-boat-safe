"""Модуль для работы с системой координат на основе ArUco меток."""

import cv2
import numpy as np
import math


class CoordinateSystem:
    """Система координат на основе стационарных меток полигона.
    
    Полигон задается метками с индексами 1-4:
    - Метка 1: (0, 0) - начало координат
    - Метка 2: (0, 100) - по часовой стрелке
    - Метка 3: (100, 100)
    - Метка 4: (100, 0)
    Размер полигона: 100x100 условных единиц
    """
    
    # Целевые координаты меток в системе полигона (целые числа)
    TARGET_COORDS = {
        1: (0, 0),
        2: (0, 100),
        3: (100, 100),
        4: (100, 0)
    }
    
    def __init__(self, smoothing_factor=0.7):
        """
        Args:
            smoothing_factor: Коэффициент сглаживания координат (0-1)
        """
        self.smoothing_factor = smoothing_factor
        self.prev_coords = None
        self.prev_rotation = None
        self.transform_matrix = None
        self.is_calibrated = False
    
    def calibrate(self, marker_centers):
        """Калибрует систему координат на основе центров меток полигона.
        
        Args:
            marker_centers: Словарь {marker_id: center_pixel} для меток 1-4
            
        Returns:
            bool: True если калибровка успешна, False иначе
        """
        if len(marker_centers) != 4:
            return False
        
        # Проверяем, что все метки присутствуют
        for marker_id in [1, 2, 3, 4]:
            if marker_id not in marker_centers:
                return False
        
        # Создаем массивы исходных и целевых точек
        src_points = []
        dst_points = []
        
        for marker_id in [1, 2, 3, 4]:
            src_points.append(marker_centers[marker_id])
            dst_points.append(self.TARGET_COORDS[marker_id])
        
        src_points = np.array(src_points, dtype=np.float32)
        dst_points = np.array(dst_points, dtype=np.float32)
        
        # Вычисляем матрицу преобразования
        self.transform_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        self.is_calibrated = True
        return True
    
    def transform_point(self, pixel_point):
        """Преобразует точку из пикселей камеры в координаты полигона.
        
        Args:
            pixel_point: Точка (x, y) в пикселях камеры
            
        Returns:
            tuple: (x, y) в координатах полигона (целые числа) или None
        """
        if not self.is_calibrated or self.transform_matrix is None:
            return None
        
        point_homogeneous = np.array([[pixel_point[0], pixel_point[1]]], dtype=np.float32)
        point_homogeneous = cv2.perspectiveTransform(
            point_homogeneous.reshape(-1, 1, 2),
            self.transform_matrix
        )
        coords = point_homogeneous[0][0]
        
        # Ограничиваем координаты диапазоном [0, 100]
        coords[0] = np.clip(coords[0], 0.0, 100.0)
        coords[1] = np.clip(coords[1], 0.0, 100.0)
        
        # Применяем сглаживание
        if self.prev_coords is not None:
            coords = self.smoothing_factor * self.prev_coords + (1 - self.smoothing_factor) * coords
        
        self.prev_coords = coords.copy()
        
        # Возвращаем целые числа
        return (int(round(coords[0])), int(round(coords[1])))
    
    def calculate_rotation_from_marker(self, marker_corners, marker_center_pixel):
        """Вычисляет поворот машинки на основе одной ArUco метки.
        
        Определяет "низ" метки (угол с минимальной Y координатой в системе камеры),
        который соответствует "заду" машинки. Вычисляет направление от центра метки
        к "низу" и преобразует его в угол поворота в системе координат полигона.
        
        Args:
            marker_corners: Углы ArUco метки (формат OpenCV)
            marker_center_pixel: Центр метки в пикселях камеры (x, y)
            
        Returns:
            float: Угол поворота в радианах в системе координат полигона:
                   - 0 = вдоль +X (вправо)
                   - Положительное направление против часовой стрелки
                   - π/2 = вдоль +Y (вверх)
                   - π = вдоль -X (влево)
                   - -π/2 = вдоль -Y (вниз)
                   или None если не удалось вычислить
        """
        if not self.is_calibrated or self.transform_matrix is None:
            return None
        
        # Преобразуем углы метки в массив точек
        corners_2d = marker_corners[0].reshape(-1, 2)
        
        # Находим угол с минимальной Y координатой (в системе камеры) = "низ" метки
        bottom_corner_idx = np.argmax(corners_2d[:, 1])  # Максимальная Y = нижний угол
        bottom_corner = corners_2d[bottom_corner_idx]
        
        # Вычисляем направление от центра метки к "низу" (в пикселях камеры)
        dx_pixel = bottom_corner[0] - marker_center_pixel[0]
        dy_pixel = bottom_corner[1] - marker_center_pixel[1]
        
        # Преобразуем это направление в систему координат полигона
        # Для этого преобразуем две точки: центр и центр + направление
        center_point = np.array([[marker_center_pixel[0], marker_center_pixel[1]]], dtype=np.float32)
        direction_point = np.array([[marker_center_pixel[0] + dx_pixel, marker_center_pixel[1] + dy_pixel]], dtype=np.float32)
        
        center_transformed = cv2.perspectiveTransform(
            center_point.reshape(-1, 1, 2),
            self.transform_matrix
        )[0][0]
        
        direction_transformed = cv2.perspectiveTransform(
            direction_point.reshape(-1, 1, 2),
            self.transform_matrix
        )[0][0]
        
        # Вычисляем направление в системе координат полигона
        dx = direction_transformed[0] - center_transformed[0]
        dy = direction_transformed[1] - center_transformed[1]
        
        # Вычисляем угол поворота (направление "зада" машинки)
        # Но нам нужен угол "носа" машинки, который противоположен "заду"
        # Поэтому добавляем π
        rotation = math.atan2(dy, dx) + math.pi
        
        # Нормализуем угол в диапазон [-π, π]
        rotation = math.atan2(math.sin(rotation), math.cos(rotation))
        
        # Применяем сглаживание
        if self.prev_rotation is not None:
            # Учитываем переход через границу -π/π
            diff = rotation - self.prev_rotation
            if diff > math.pi:
                diff -= 2 * math.pi
            elif diff < -math.pi:
                diff += 2 * math.pi
            rotation = self.prev_rotation + (1 - self.smoothing_factor) * diff
            rotation = math.atan2(math.sin(rotation), math.cos(rotation))
        
        self.prev_rotation = rotation
        return rotation
    
    def draw_polygon(self, frame, marker_centers):
        """Рисует границы полигона на кадре.
        
        Args:
            frame: Кадр для отрисовки
            marker_centers: Словарь {marker_id: center_pixel} для меток 1-4
            
        Returns:
            frame: Кадр с отрисованным полигоном
        """
        if len(marker_centers) != 4:
            return frame
        
        # Порядок меток для отрисовки полигона: 1 -> 2 -> 3 -> 4 -> 1
        polygon_points = []
        for marker_id in [1, 2, 3, 4]:
            if marker_id in marker_centers:
                center = marker_centers[marker_id]
                polygon_points.append(tuple(map(int, center)))
        
        if len(polygon_points) == 4:
            pts = np.array(polygon_points, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            
            # Подписываем метки
            for marker_id, center in marker_centers.items():
                center_int = tuple(map(int, center))
                cv2.putText(frame, f"ID:{marker_id}",
                           (center_int[0] - 20, center_int[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame

