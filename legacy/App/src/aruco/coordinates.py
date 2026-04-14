"""Модуль для работы с системой координат."""

import cv2
import numpy as np
import math


class CoordinateSystem:
    """Система координат на основе стационарных меток."""
    
    def __init__(self, smoothing_factor=0.7):
        """
        Args:
            smoothing_factor: Коэффициент сглаживания координат (0-1)
        """
        self.smoothing_factor = smoothing_factor
        self.prev_coords = None
        self.transform_matrix = None
    
    def order_markers(self, markers_dict):
        """Упорядочивает метки в порядке: [левый нижний, правый нижний, правый верхний, левый верхний].
        
        Работает с любым порядком меток на прямоугольнике.
        """
        if len(markers_dict) != 4:
            return None
        
        centers = np.array(list(markers_dict.values()), dtype=np.float32)
        x_coords = centers[:, 0]
        y_coords = centers[:, 1]
        
        # Разделяем точки на верхние и нижние по медиане y
        y_median = np.median(y_coords)
        
        bottom_mask = y_coords >= y_median
        bottom_points = centers[bottom_mask]
        
        top_mask = y_coords < y_median
        top_points = centers[top_mask]
        
        # Если разделение не дало по 2 точки, используем более точный метод
        if len(bottom_points) != 2 or len(top_points) != 2:
            sorted_by_y = centers[np.argsort(y_coords)]
            bottom_points = sorted_by_y[2:]
            top_points = sorted_by_y[:2]
        
        # Определяем углы
        left_bottom = bottom_points[np.argmin(bottom_points[:, 0])]
        right_bottom = bottom_points[np.argmax(bottom_points[:, 0])]
        right_top = top_points[np.argmax(top_points[:, 0])]
        left_top = top_points[np.argmin(top_points[:, 0])]
        
        ordered_centers = np.array([left_bottom, right_bottom, right_top, left_top], dtype=np.float32)
        return ordered_centers
    
    def compute_transform_matrix(self, static_centers):
        """Вычисляет матрицу преобразования из пикселей в относительные координаты (0-1)."""
        if static_centers is None or len(static_centers) != 4:
            return None
        
        # Целевые точки: углы единичного квадрата
        dst_points = np.array([
            [0.0, 1.0],  # левый нижний
            [1.0, 1.0],  # правый нижний
            [1.0, 0.0],  # правый верхний
            [0.0, 0.0]   # левый верхний
        ], dtype=np.float32)
        
        self.transform_matrix = cv2.getPerspectiveTransform(static_centers, dst_points)
        return self.transform_matrix
    
    def transform_coordinates(self, point):
        """Преобразует точку из пикселей в относительные координаты (0-1)."""
        if self.transform_matrix is None:
            return None
        
        point_homogeneous = np.array([[point[0], point[1]]], dtype=np.float32)
        point_homogeneous = cv2.perspectiveTransform(
            point_homogeneous.reshape(-1, 1, 2),
            self.transform_matrix
        )
        coords = point_homogeneous[0][0]
        
        # Ограничиваем координаты диапазоном [0, 1]
        coords[0] = np.clip(coords[0], 0.0, 1.0)
        coords[1] = np.clip(coords[1], 0.0, 1.0)
        
        # Применяем сглаживание
        if self.prev_coords is not None:
            coords = self.smoothing_factor * self.prev_coords + (1 - self.smoothing_factor) * coords
        
        self.prev_coords = coords.copy()
        return coords
    
    def calculate_rotation(self, front_coords, rear_coords):
        """Вычисляет абсолютный yaw машинки в мировой системе координат на основе двух меток.
        
        Args:
            front_coords: Координаты передней метки (x, y) в относительных единицах (0-1)
            rear_coords: Координаты задней метки (x, y) в относительных единицах (0-1)
            
        Returns:
            float: Абсолютный yaw в радианах:
                   - 0 = вдоль +X (вправо)
                   - Положительное направление против часовой стрелки
                   - π/2 = вдоль +Y (вверх)
                   - π = вдоль -X (влево)
                   - -π/2 = вдоль -Y (вниз)
                   или None если координаты невалидны
        """
        if front_coords is None or rear_coords is None:
            return None
        
        # Вычисляем вектор от задней метки к передней
        dx = front_coords[0] - rear_coords[0]
        dy = front_coords[1] - rear_coords[1]
        
        # Вычисляем абсолютный yaw (в радианах)
        # atan2(dy, dx) дает угол от оси +X, положительное направление против часовой стрелки
        # Это соответствует требуемой системе координат
        rotation = math.atan2(dy, dx)
        
        return rotation
    
    def draw_coordinate_system(self, frame, static_centers):
        """Рисует систему координат на кадре."""
        if static_centers is None or self.transform_matrix is None:
            return frame
        
        # Рисуем границы прямоугольника
        pts = static_centers.astype(np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        
        # Рисуем оси координат
        origin = pts[0]
        
        # Ось X
        x_end = pts[1]
        cv2.arrowedLine(frame, tuple(origin), tuple(x_end), (255, 0, 0), 2, tipLength=0.1)
        cv2.putText(frame, "X", (x_end[0] + 10, x_end[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Ось Y
        y_end = pts[3]
        cv2.arrowedLine(frame, tuple(origin), tuple(y_end), (0, 0, 255), 2, tipLength=0.1)
        cv2.putText(frame, "Y", (y_end[0] - 20, y_end[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        return frame

