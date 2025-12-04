"""Модуль для навигации и управления движением к целевой точке."""

import time
import math
import requests
from typing import Optional, Tuple


class NavigationController:
    """Контроллер навигации для управления движением машинки к целевой точке."""
    
    def __init__(self, robot_ip="192.168.1.100", robot_port=5000, tolerance=5, 
                 angle_tolerance=0.2, timeout=2):
        """
        Args:
            robot_ip: IP адрес машинки на Raspberry Pi
            robot_port: Порт Flask сервера на машинке (по умолчанию 5000)
            tolerance: Допустимая погрешность достижения цели в условных единицах (по умолчанию 5)
            angle_tolerance: Допустимая погрешность угла поворота в радианах (по умолчанию 0.2 ≈ 11°)
            timeout: Таймаут для HTTP запросов в секундах
        """
        self.robot_url = f"http://{robot_ip}:{robot_port}"
        self.tolerance = tolerance
        self.angle_tolerance = angle_tolerance
        self.timeout = timeout
        self.target_coords = None
        self.is_moving = False
        self.last_command_time = 0
        self.command_interval = 0.5  # Интервал между командами в секундах
        
        try:
            import requests
            self.requests = requests
            print(f"✓ NavigationController инициализирован для {self.robot_url}")
        except ImportError:
            raise ImportError("Библиотека 'requests' не установлена. Установите: pip install requests")
    
    def set_target(self, x: int, y: int):
        """Устанавливает целевую точку для движения.
        
        Args:
            x: Координата X (0-100)
            y: Координата Y (0-100)
        """
        # Ограничиваем координаты
        x = max(0, min(100, int(x)))
        y = max(0, min(100, int(y)))
        
        self.target_coords = (x, y)
        self.is_moving = True
        print(f"🎯 Установлена цель: ({x}, {y})")
    
    def clear_target(self):
        """Очищает целевую точку и останавливает движение."""
        self.target_coords = None
        self.is_moving = False
        self.send_command('stop')
        print("🛑 Цель очищена, движение остановлено")
    
    def send_command(self, direction: str):
        """Отправляет команду движения на машинку.
        
        Args:
            direction: Направление движения ('forward', 'backward', 'left', 'right', 'stop')
        """
        # Ограничиваем частоту отправки команд
        current_time = time.time()
        if current_time - self.last_command_time < self.command_interval:
            return
        
        url = f"{self.robot_url}/move"
        data = {"direction": direction}
        
        try:
            response = self.requests.post(url, json=data, timeout=self.timeout)
            if response.status_code == 200:
                self.last_command_time = current_time
                return True
            else:
                print(f"✗ Ошибка отправки команды: статус {response.status_code}")
                return False
        except self.requests.exceptions.ConnectionError as e:
            if not hasattr(self, '_last_conn_error_log') or time.time() - self._last_conn_error_log > 10:
                print(f"✗ Ошибка подключения к машинке ({self.robot_url}): {e}")
                self._last_conn_error_log = time.time()
            return False
        except self.requests.exceptions.Timeout:
            return False
        except self.requests.exceptions.RequestException as e:
            if not hasattr(self, '_last_error_log') or time.time() - self._last_error_log > 5:
                print(f"✗ Ошибка запроса к машинке: {e}")
                self._last_error_log = time.time()
            return False
    
    def update(self, current_x: int, current_y: int, current_rotation: float):
        """Обновляет навигацию на основе текущей позиции и поворота.
        
        Args:
            current_x: Текущая координата X (0-100)
            current_y: Текущая координата Y (0-100)
            current_rotation: Текущий угол поворота в радианах
        """
        if self.target_coords is None or not self.is_moving:
            return
        
        target_x, target_y = self.target_coords
        
        # Вычисляем расстояние до цели
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Проверяем, достигнута ли цель
        if distance < self.tolerance:
            self.is_moving = False
            self.send_command('stop')
            print(f"✓ Цель достигнута! Текущая позиция: ({current_x}, {current_y}), цель: ({target_x}, {target_y})")
            return
        
        # Вычисляем угол к целевой точке
        target_angle = math.atan2(dy, dx)
        
        # Вычисляем разницу между текущим поворотом и углом к цели
        angle_diff = target_angle - current_rotation
        
        # Нормализуем разницу угла в диапазон [-π, π]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Если угол отклонения больше порога, поворачиваем
        if abs(angle_diff) > self.angle_tolerance:
            if angle_diff > 0:
                # Поворачиваем влево
                self.send_command('left')
            else:
                # Поворачиваем вправо
                self.send_command('right')
        else:
            # Угол правильный, движемся вперед
            self.send_command('forward')
    
    def get_status(self) -> dict:
        """Возвращает текущий статус навигации."""
        return {
            "is_moving": self.is_moving,
            "target": self.target_coords,
            "tolerance": self.tolerance,
            "angle_tolerance": math.degrees(self.angle_tolerance)
        }

