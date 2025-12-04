"""Модуль для навигации и управления движением."""

import time
import math
from typing import Optional, Tuple


class NavigationController:
    """Контроллер навигации для управления движением машинки."""
    
    def __init__(self, tolerance=0.02, max_speed=100, movement_executor=None):
        """
        Args:
            tolerance: Допустимая погрешность достижения цели (в относительных единицах)
            max_speed: Максимальная скорость движения (0-100) - не используется для HTTP команд
            movement_executor: Опциональный исполнитель для отправки координат на машинку
        """
        self.tolerance = tolerance
        self.max_speed = max_speed
        self.target_coords = None
        self.is_moving = False
        self.last_command = None
        self.movement_executor = movement_executor
    
    def set_target(self, x: float, y: float):
        """Устанавливает целевую точку для движения.
        
        Args:
            x: Координата X (0-1)
            y: Координата Y (0-1)
        """
        # Ограничиваем координаты
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        
        self.target_coords = (x, y)
        self.is_moving = True
        self.last_command = None
        
        # Отправляем координаты на машинку один раз при установке цели
        if self.movement_executor:
            self.movement_executor.send_target_coordinates(x, y)
        
        print(f"🎯 Установлена цель: ({x:.3f}, {y:.3f})")
    
    def clear_target(self):
        """Очищает целевую точку."""
        self.target_coords = None
        self.is_moving = False
        # Машинка сама перезаписывает новую целевую точку, поэтому не отправляем команду очистки
        print("🛑 Цель очищена, движение остановлено")
    
    def calculate_movement(self, current_x: float, current_y: float) -> Optional[dict]:
        """Вычисляет необходимые команды движения на основе текущей и целевой позиции.
        
        Args:
            current_x: Текущая координата X
            current_y: Текущая координата Y
            
        Returns:
            Словарь с командами движения или None если цель достигнута
        """
        if self.target_coords is None:
            return None
        
        target_x, target_y = self.target_coords
        
        # Вычисляем расстояние до цели
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Проверяем, достигнута ли цель
        if distance < self.tolerance:
            self.is_moving = False
            return {"action": "stop"}
        
        # Вычисляем направление (в радианах)
        # В системе координат: угол 0 = вправо (ось X), угол π/2 = вверх (ось Y)
        angle = math.atan2(dy, dx)
        
        # Определяем команды движения для дифференциального привода
        # Доступные команды: forward, backward, left, right, stop
        
        # Порог для поворота на месте (в радианах)
        turn_threshold = math.pi / 6  # 30 градусов
        
        if abs(angle) < turn_threshold:
            # Движемся прямо вперед
            return {"action": "forward"}
        elif abs(angle) > math.pi - turn_threshold:
            # Движемся назад
            return {"action": "backward"}
        elif angle > 0:
            # Поворачиваем влево (положительный угол = движение вверх по Y)
            if abs(angle) > math.pi / 2 - turn_threshold:
                # Почти перпендикулярно - поворот на месте
                return {"action": "left"}
            else:
                # Движение вперед с поворотом влево
                return {"action": "forward", "turn": "left"}
        else:
            # Поворачиваем вправо (отрицательный угол)
            if abs(angle) > math.pi / 2 - turn_threshold:
                # Почти перпендикулярно - поворот на месте
                return {"action": "right"}
            else:
                # Движение вперед с поворотом вправо
                return {"action": "forward", "turn": "right"}
    
    def get_status(self) -> dict:
        """Возвращает текущий статус навигации."""
        return {
            "is_moving": self.is_moving,
            "target": self.target_coords,
            "tolerance": self.tolerance
        }


class MovementExecutor:
    """Исполнитель для отправки координат целевой точки на машинку через HTTP запросы."""
    
    def __init__(self, robot_ip="192.168.1.100", robot_port=5000, timeout=2):
        """
        Инициализация исполнителя команд.
        
        Args:
            robot_ip: IP адрес машинки на Raspberry Pi
            robot_port: Порт Flask сервера на машинке (по умолчанию 5000)
            timeout: Таймаут для HTTP запросов в секундах
        """
        self.robot_url = f"http://{robot_ip}:{robot_port}"
        self.timeout = timeout
        
        try:
            import requests
            self.requests = requests
            print(f"✓ MovementExecutor инициализирован для {self.robot_url}")
        except ImportError:
            raise ImportError("Библиотека 'requests' не установлена. Установите: pip install requests")
    
    def send_target_coordinates(self, x: float, y: float):
        """Отправляет координаты целевой точки на машинку один раз.
        
        Args:
            x: Координата X целевой точки (0-1)
            y: Координата Y целевой точки (0-1)
        """
        url = f"{self.robot_url}/set_target"
        data = {"x": float(x), "y": float(y)}
        
        try:
            response = self.requests.post(url, json=data, timeout=self.timeout)
            if response.status_code == 200:
                print(f"✓ Координаты цели отправлены на {self.robot_url}: ({x:.3f}, {y:.3f})")
                return True
            else:
                print(f"✗ Ошибка отправки координат: статус {response.status_code}")
                print(f"  Ответ сервера: {response.text}")
                return False
        except self.requests.exceptions.ConnectionError as e:
            print(f"✗ Ошибка подключения к машинке ({self.robot_url}): {e}")
            print(f"  Убедитесь, что Flask сервер на машинке запущен и доступен")
            return False
        except self.requests.exceptions.Timeout as e:
            print(f"✗ Таймаут при отправке координат на {self.robot_url}: {e}")
            return False
        except self.requests.exceptions.RequestException as e:
            print(f"✗ Ошибка запроса к машинке ({self.robot_url}): {e}")
            return False
    
    def send_current_coordinates(self, x: float, y: float, rotation: float = None):
        """Отправляет текущие координаты местоположения машинки и угол поворота на машинку.
        
        Args:
            x: Координата X текущего местоположения (0-1)
            y: Координата Y текущего местоположения (0-1)
            rotation: Угол поворота в радианах (опционально)
        """
        url = f"{self.robot_url}/update_position"
        data = {"x": float(x), "y": float(y)}
        if rotation is not None:
            data["rotation"] = float(rotation)
        
        try:
            response = self.requests.post(url, json=data, timeout=self.timeout)
            if response.status_code == 200:
                # Не логируем каждую отправку, чтобы не засорять консоль
                return True
            else:
                # Логируем только ошибки
                if not hasattr(self, '_last_error_log') or time.time() - self._last_error_log > 5:
                    print(f"✗ Ошибка отправки координат местоположения: статус {response.status_code}")
                    self._last_error_log = time.time()
                return False
        except self.requests.exceptions.ConnectionError as e:
            # Логируем ошибки подключения реже, чтобы не засорять консоль
            if not hasattr(self, '_last_conn_error_log') or time.time() - self._last_conn_error_log > 10:
                print(f"✗ Ошибка подключения к машинке ({self.robot_url}): {e}")
                self._last_conn_error_log = time.time()
            return False
        except self.requests.exceptions.Timeout:
            # Таймауты не логируем, так как они могут быть частыми
            return False
        except self.requests.exceptions.RequestException:
            # Другие ошибки не логируем, чтобы не засорять консоль
            return False
    
    def stop(self):
        """Останавливает машинку.
        
        Примечание: Машинка сама перезаписывает новую целевую точку,
        поэтому команда очистки не отправляется. Для остановки просто
        установите новую целевую точку или не устанавливайте её вообще.
        """
        # Машинка сама управляет остановкой, поэтому не отправляем команду
        print(f"ℹ Остановка: машинка сама управляет движением на основе целевой точки")
        return True
    
    def cleanup(self):
        """Очистка ресурсов."""
        # Машинка сама управляет остановкой, поэтому ничего не отправляем
        pass
