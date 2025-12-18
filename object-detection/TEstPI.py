# stereo_fast_depth.py

import os
# Убираем принудительную установку Qt платформы для headless систем
# OpenCV будет использовать доступный бэкенд автоматически
if 'QT_QPA_PLATFORM' in os.environ:
    # Если уже установлено, оставляем как есть
    pass
else:
    # Проверяем, есть ли дисплей (X11)
    display = os.environ.get('DISPLAY')
    if not display:
        # Если нет дисплея, устанавливаем offscreen режим
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import cv2
import numpy as np
import time
import yaml
from ultralytics import YOLO
import warnings
import requests
import base64
import threading
import argparse
import socket
warnings.filterwarnings('ignore')

# ======================= БЫСТРЫЕ НАСТРОЙКИ =======================
YOLO_WEIGHTS = 'yolov8n.pt'
CAMERA_INDICES = [0, 2]
CALIB_FILE = 'stereo.yaml'
# Настройки сервера для отправки изображений (по умолчанию)
# ВАЖНО: Укажите IP адрес ноутбука (сервера) через --server-ip при запуске
# или измените значение по умолчанию ниже
DEFAULT_SERVER_URL = 'http://localhost:5001'  # IP ноутбука с ArUcoTracking сервером
SERVER_ENDPOINT = '/api/upload_frame'
ENABLE_SERVER_UPLOAD = True  # Включить/выключить отправку на сервер
SEND_FRAME_INTERVAL = 3  # Отправлять каждый N-й кадр (для снижения нагрузки)

class Config:
    DETECTION_INTERVAL = 8
    SHOW_STEREO = True  # Отображение стерео изображения (требует дисплей)
    SHOW_DEPTH = True   # Отображение карты глубины (требует дисплей)
    CAMERA_WIDTH = 300
    CAMERA_HEIGHT = 300
    CAMERA_FPS = 15  # Увеличили FPS
    YOLO_SIZE = 160
    MAX_REAL_DISTANCE = 8.0

def init_camera_fast(camera_id):
    """Быстрая инициализация камеры"""
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, Config.CAMERA_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Минимальный буфер
    return cap

class FastDetector:
    def __init__(self, weights_path):
        try:
            self.model = YOLO(weights_path)
            self.frame_counter = 0
            self.last_detections = []
        except:
            self.model = None

    def detect(self, image):
        if self.model is None:
            return self.last_detections

        self.frame_counter += 1
        # Детекция реже для скорости
        if self.frame_counter % Config.DETECTION_INTERVAL != 0:
            return self.last_detections

        try:
            # Быстрая детекция с минимальными параметрами
            results = self.model(image, imgsz=Config.YOLO_SIZE, conf=0.5, verbose=False, half=False)

            if len(results) == 0 or results[0].boxes is None:
                self.last_detections = []
                return []

            boxes = results[0].boxes.xyxy.cpu().numpy()
            class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
            confidences = results[0].boxes.conf.cpu().numpy()

            detections = []
            for box, cls_id, conf in zip(boxes, class_ids, confidences):
                if cls_id == 0 and conf > 0.5:  # person с хорошей уверенностью
                    x1, y1, x2, y2 = box.astype(int)
                    width, height = x2 - x1, y2 - y1
                    if width > 25 and height > 50:  # Фильтр по размеру
                        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                        detections.append({
                            'bbox': (x1, y1, x2, y2),
                            'center': (center_x, center_y),
                            'confidence': conf,
                            'area': width * height
                        })

            # Сортируем по размеру (предполагаем, что ближайшие объекты крупнее)
            detections.sort(key=lambda x: x['area'], reverse=True)
            self.last_detections = detections[:2]  # Не более 2 объектов

            return self.last_detections
        except:
            return self.last_detections

class FastDepthCalculator:
    def __init__(self):
        self.focal_length = 280  # Оптимизировано для 300x300
        self.baseline = 0.12     # Оптимизированный базис
        self.depth_cache = {}    # Кэш для скорости
        self.last_depth_map = None
        self.last_depth_time = 0

    def calculate_fast_depth(self, rect_left, rect_right):
        """Сверхбыстрое вычисление глубины"""
        try:
            # Меньший даунсэмпл для скорости
            small_size = (120, 80)  # Еще меньше!
            small_left = cv2.resize(rect_left, small_size, interpolation=cv2.INTER_NEAREST)
            small_right = cv2.resize(rect_right, small_size, interpolation=cv2.INTER_NEAREST)

            # Быстрое преобразование в grayscale
            gray_left = cv2.cvtColor(small_left, cv2.COLOR_BGR2GRAY)
            gray_right = cv2.cvtColor(small_right, cv2.COLOR_BGR2GRAY)

            # Оптимизированный StereoBM
            stereo = cv2.StereoBM_create(numDisparities=48, blockSize=9)  # Быстрые параметры
            disparity = stereo.compute(gray_left, gray_right)

            if disparity is None:
                return None

            disparity = disparity.astype(np.float32) / 16.0
            disparity[disparity < 2.0] = 2.0  # Минимальная диспарити

            # Быстрое вычисление глубины
            with np.errstate(divide='ignore', invalid='ignore'):
                depth = (self.focal_length * self.baseline) / disparity
                # Агрессивная фильтрация
                depth[disparity <= 2.0] = np.nan
                depth[depth > Config.MAX_REAL_DISTANCE] = np.nan
                depth[depth < 0.5] = np.nan

            # Быстрый ресайз
            depth = cv2.resize(depth, (rect_left.shape[1], rect_left.shape[0]),
                             interpolation=cv2.INTER_NEAREST)

            self.last_depth_map = depth
            self.last_depth_time = time.time()
            return depth

        except Exception as e:
            return None

    def get_object_depth_fast(self, detection, object_id=0):
        """Быстрое получение расстояния до объекта"""
        if self.last_depth_map is None:
            return None

        x1, y1, x2, y2 = detection['bbox']
        center_x, center_y = detection['center']

        # Быстрая выборка глубины вокруг центра
        roi_size = 8  # Маленькая область для скорости
        roi_x1 = max(0, center_x - roi_size)
        roi_y1 = max(0, center_y - roi_size)
        roi_x2 = min(self.last_depth_map.shape[1], center_x + roi_size)
        roi_y2 = min(self.last_depth_map.shape[0], center_y + roi_size)

        depth_roi = self.last_depth_map[roi_y1:roi_y2, roi_x1:roi_x2]
        valid_depths = depth_roi[~np.isnan(depth_roi)]

        if len(valid_depths) == 0:
            return None

        # Быстрая медиана (берем среднее из небольшой выборки)
        sample_size = min(10, len(valid_depths))
        sampled_depths = np.random.choice(valid_depths, sample_size, replace=False)
        current_depth = np.median(sampled_depths)

        # Простое сглаживание
        if object_id not in self.depth_cache:
            self.depth_cache[object_id] = current_depth
        else:
            # Экспоненциальное сглаживание
            alpha = 0.7  # Сильное сглаживание
            self.depth_cache[object_id] = (alpha * self.depth_cache[object_id] +
                                         (1 - alpha) * current_depth)

        return self.depth_cache[object_id]

def send_frame_to_server(frame, server_url, endpoint):
    """Отправляет кадр на сервер в отдельном потоке."""
    def send_async():
        try:
            # Кодируем изображение в JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if buffer is None:
                print("⚠ Ошибка: не удалось закодировать изображение")
                return
            
            frame_bytes = buffer.tobytes()
            if len(frame_bytes) == 0:
                print("⚠ Ошибка: пустой буфер изображения")
                return
            
            # Отправляем как multipart/form-data
            files = {'image': ('frame.jpg', frame_bytes, 'image/jpeg')}
            url = f"{server_url}{endpoint}"
            
            response = requests.post(
                url,
                files=files,
                timeout=2.0  # Увеличили таймаут для надежности
            )
            
            if response.status_code == 200:
                # Успешная отправка (выводим редко, чтобы не засорять вывод)
                if not hasattr(send_async, '_success_count'):
                    send_async._success_count = 0
                send_async._success_count += 1
                if send_async._success_count % 30 == 0:  # Каждые 30 успешных отправок
                    print(f"✓ Кадры отправляются на сервер (успешно: {send_async._success_count})")
            else:
                print(f"⚠ Ошибка отправки кадра: HTTP {response.status_code}")
                try:
                    error_msg = response.json().get('message', 'Неизвестная ошибка')
                    print(f"   Сообщение сервера: {error_msg}")
                except:
                    print(f"   Ответ сервера: {response.text[:100]}")
                    
        except requests.exceptions.ConnectionError as e:
            if not hasattr(send_async, '_conn_error_shown'):
                print(f"❌ Ошибка подключения к серверу {server_url}:")
                print(f"   Убедитесь, что сервер запущен и доступен по сети")
                print(f"   Проверьте IP адрес и порт сервера")
                send_async._conn_error_shown = True
        except requests.exceptions.Timeout as e:
            if not hasattr(send_async, '_timeout_shown'):
                print(f"⚠ Таймаут при отправке на сервер {server_url}")
                send_async._timeout_shown = True
        except requests.exceptions.RequestException as e:
            if not hasattr(send_async, '_req_error_shown'):
                print(f"⚠ Ошибка запроса: {type(e).__name__}: {str(e)[:100]}")
                send_async._req_error_shown = True
        except Exception as e:
            if not hasattr(send_async, '_error_shown'):
                print(f"❌ Неожиданная ошибка при отправке: {type(e).__name__}: {str(e)[:100]}")
                send_async._error_shown = True
    
    # Запускаем отправку в отдельном потоке
    thread = threading.Thread(target=send_async, daemon=True)
    thread.start()

def create_fast_depth_display(depth_map, detections, depth_calculator, display_size=(200, 150)):
    """Быстрое отображение глубины"""
    if depth_map is None:
        # Быстрый черный экран
        display = np.zeros((display_size[1], display_size[0], 3), dtype=np.uint8)
        cv2.putText(display, "CALCULATING...", (30, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return display

    # Быстрая визуализация глубины
    valid_mask = ~np.isnan(depth_map)

    if not np.any(valid_mask):
        display = np.zeros((display_size[1], display_size[0], 3), dtype=np.uint8)
        cv2.putText(display, "MOVE OBJECT CLOSER", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return display

    # Быстрая нормализация
    valid_depths = depth_map[valid_mask]
    min_depth = np.min(valid_depths)
    max_depth = np.min([np.max(valid_depths), Config.MAX_REAL_DISTANCE])

    depth_vis = np.zeros_like(depth_map)
    depth_vis[valid_mask] = (depth_map[valid_mask] - min_depth) / (max_depth - min_depth) * 255
    depth_vis = np.clip(depth_vis, 0, 255).astype(np.uint8)

    # Быстрое применение colormap
    depth_colored = cv2.applyColorMap(255 - depth_vis, cv2.COLORMAP_JET)
    depth_colored[~valid_mask] = [0, 0, 0]

    # Быстрое отображение объектов
    for i, detection in enumerate(detections):
        object_depth = depth_calculator.get_object_depth_fast(detection, i)

        if object_depth is not None and 0.5 <= object_depth <= Config.MAX_REAL_DISTANCE:
            x1, y1, x2, y2 = detection['bbox']

            # Масштабирование координат
            scale_x = display_size[0] / depth_map.shape[1]
            scale_y = display_size[1] / depth_map.shape[0]

            disp_x1 = int(x1 * scale_x)
            disp_y1 = int(y1 * scale_y)
            disp_x2 = int(x2 * scale_x)
            disp_y2 = int(y2 * scale_y)

            # Быстрое рисование
            cv2.rectangle(depth_colored, (disp_x1, disp_y1), (disp_x2, disp_y2),
                         (0, 255, 0), 1)

            # Текст с расстоянием
            depth_text = f"{object_depth:.1f}m"
            cv2.putText(depth_colored, depth_text,
                       (disp_x1, disp_y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)

    return depth_colored

def get_local_ip():
    """Получить локальный IP адрес этого Raspberry Pi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "не определен"

def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Стереосистема с детекцией объектов и отправкой на сервер')
    parser.add_argument('--server-ip', type=str, default=None,
                       help='IP адрес ноутбука с ArUcoTracking сервером (например: 192.168.1.100)')
    parser.add_argument('--server-port', type=int, default=5001,
                       help='Порт сервера (по умолчанию: 5001)')
    parser.add_argument('--disable-upload', action='store_true',
                       help='Отключить отправку изображений на сервер')
    parser.add_argument('--headless', action='store_true',
                       help='Режим без дисплея (отключить отображение окон)')
    args = parser.parse_args()
    
    # Определяем URL сервера
    if args.server_ip:
        server_url = f'http://{args.server_ip}:{args.server_port}'
    else:
        server_url = DEFAULT_SERVER_URL
    
    if args.disable_upload:
        global ENABLE_SERVER_UPLOAD
        ENABLE_SERVER_UPLOAD = False
    
    if args.headless:
        Config.SHOW_STEREO = False
        Config.SHOW_DEPTH = False
        print("⚠ Режим без дисплея: отображение окон отключено")
    
    print("=" * 60)
    print("=== БЫСТРАЯ СТЕРЕОСИСТЕМА ===")
    print("⚡ Оптимизировано для максимального FPS")
    print(f"🎯 Целевой FPS: {Config.CAMERA_FPS}")
    print("=" * 60)
    
    local_ip = get_local_ip()
    print(f"\n📍 Этот Raspberry Pi: {local_ip}")
    print(f"📡 Сервер (ноутбук): {server_url}")
    print(f"   Endpoint: {SERVER_ENDPOINT}")
    if ENABLE_SERVER_UPLOAD:
        print(f"✅ Отправка изображений: ВКЛЮЧЕНА (каждый {SEND_FRAME_INTERVAL}-й кадр)")
        # Проверяем доступность сервера
        try:
            test_url = f"{server_url}/api/status"
            test_response = requests.get(test_url, timeout=2)
            if test_response.status_code == 200:
                print(f"✓ Сервер доступен и отвечает")
            else:
                print(f"⚠ Сервер отвечает, но с кодом {test_response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Сервер недоступен! Проверьте:")
            print(f"   - Запущен ли main.py на ноутбуке?")
            print(f"   - Правильный ли IP адрес? ({server_url})")
            print(f"   - Открыт ли порт в файрволе?")
        except Exception as e:
            print(f"⚠ Не удалось проверить доступность сервера: {e}")
    else:
        print("❌ Отправка изображений: ВЫКЛЮЧЕНА")
    print()

    # Инициализация
    left_cap = init_camera_fast(0)
    right_cap = init_camera_fast(2)

    if not left_cap.isOpened() or not right_cap.isOpened():
        print("❌ Ошибка камер!")
        return

    detector = FastDetector(YOLO_WEIGHTS)
    depth_calculator = FastDepthCalculator()

    print("\n=== СИСТЕМА ЗАПУЩЕНА ===")
    print("Управление:")
    print("  D - Вкл/выкл карту глубины")
    print("  F - Показать/скрыть FPS")
    print("  +/- - Настроить максимальное расстояние")
    print("  ESC - Выход")

    fps_counter = 0
    fps_time = time.time()
    show_fps = True
    depth_frame_counter = 0
    frame_send_counter = 0  # Счетчик для отправки кадров
    frames_sent_in_period = 0  # Счетчик отправленных кадров за текущий период статистики

    try:
        while True:
            start_time = time.time()

            # Быстрое чтение кадров
            ret_left, frame_left = left_cap.read()
            ret_right, frame_right = right_cap.read()

            if not ret_left or not ret_right:
                continue

            # Быстрая детекция
            detections = detector.detect(frame_left)

            # Быстрая отрисовка на левой камере
            frame_to_send = frame_left.copy()  # Копируем кадр для отправки
            for detection in detections:
                x1, y1, x2, y2 = detection['bbox']
                cv2.rectangle(frame_left, (x1, y1), (x2, y2), (0, 255, 0), 1)
                cv2.rectangle(frame_to_send, (x1, y1), (x2, y2), (0, 255, 0), 1)

            # Отправка кадра на сервер
            if ENABLE_SERVER_UPLOAD:
                frame_send_counter += 1
                if frame_send_counter >= SEND_FRAME_INTERVAL:
                    send_frame_to_server(frame_to_send, server_url, SERVER_ENDPOINT)
                    frames_sent_in_period += 1
                    frame_send_counter = 0

            # ВЫЧИСЛЕНИЕ ГЛУБИНЫ КАЖДЫЙ КАДР (быстрая версия)
            depth_map = depth_calculator.calculate_fast_depth(frame_left, frame_right)
            depth_frame_counter += 1

            # Быстрое отображение
            display_size = (200, 150)

            if Config.SHOW_STEREO:
                left_display = cv2.resize(frame_left, (display_size[0]//2, display_size[1]))
                right_display = cv2.resize(frame_right, (display_size[0]//2, display_size[1]))
                stereo_view = np.hstack([left_display, right_display])

                if show_fps:
                    cv2.putText(stereo_view, f"FPS: {fps_counter}", (10, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

                try:
                    cv2.imshow('Stereo View', stereo_view)
                except cv2.error:
                    # Если нет дисплея, просто пропускаем отображение
                    pass

            if Config.SHOW_DEPTH and depth_map is not None:
                depth_display = create_fast_depth_display(
                    depth_map, detections, depth_calculator, display_size
                )
                try:
                    cv2.imshow('Depth Map', depth_display)
                except cv2.error:
                    # Если нет дисплея, просто пропускаем отображение
                    pass

            # Быстрый расчет FPS
            fps_counter += 1
            current_time = time.time()
            if current_time - fps_time >= 2.0:
                actual_fps = fps_counter / (current_time - fps_time)
                depth_fps = depth_frame_counter / (current_time - fps_time)

                # Статистика
                object_depths = []
                for i, detection in enumerate(detections):
                    depth = depth_calculator.depth_cache.get(i)
                    if depth is not None:
                        object_depths.append(f"{depth:.1f}m")

                depths_text = ", ".join(object_depths) if object_depths else "no objects"
                
                # Статистика отправки кадров
                upload_status = ""
                if ENABLE_SERVER_UPLOAD:
                    upload_status = f" | Отправлено кадров: {frames_sent_in_period}"
                
                print(f"FPS: {actual_fps:.1f} | Depth FPS: {depth_fps:.1f} | Objects: {len(detections)} | Distances: [{depths_text}]{upload_status}")
                
                # Сбрасываем счетчики для следующего периода
                frames_sent_in_period = 0

                fps_counter = 0
                depth_frame_counter = 0
                fps_time = current_time

            # Быстрая обработка клавиш (только если есть дисплей)
            try:
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                elif key == ord('d'):
                    Config.SHOW_DEPTH = not Config.SHOW_DEPTH
                elif key == ord('f'):
                    show_fps = not show_fps
                elif key == ord('+'):
                    Config.MAX_REAL_DISTANCE = min(15.0, Config.MAX_REAL_DISTANCE + 1.0)
                    print(f"📏 Макс. расстояние: {Config.MAX_REAL_DISTANCE} м")
                elif key == ord('-'):
                    Config.MAX_REAL_DISTANCE = max(3.0, Config.MAX_REAL_DISTANCE - 1.0)
                    print(f"📏 Макс. расстояние: {Config.MAX_REAL_DISTANCE} м")
            except cv2.error:
                # Если нет дисплея, просто продолжаем работу
                pass

            # Минимальная задержка для стабильности FPS
            processing_time = time.time() - start_time
            if processing_time < 0.066:  # ~15 FPS
                time.sleep(0.066 - processing_time)

    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        left_cap.release()
        right_cap.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass  # Если нет дисплея, игнорируем ошибку
        print("✅ Завершено")

if __name__ == "__main__":
    main()
