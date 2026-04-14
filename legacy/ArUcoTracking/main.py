"""Главный файл для запуска системы отслеживания ArUco."""

import cv2
import time
import threading
import sys
import os
import argparse
import math
import socket

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(__file__))

from aruco_tracker import ArucoDetector, CameraManager
from coordinate_system import CoordinateSystem
from navigation import NavigationController
from web_server import run_server, init_navigation, update_state


def main():
    """Главная функция."""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Система отслеживания ArUco для управления машинкой')
    parser.add_argument('--robot-ip', type=str, default='192.168.1.100',
                       help='IP адрес машинки на Raspberry Pi (по умолчанию: 192.168.1.100)')
    parser.add_argument('--robot-port', type=int, default=5000,
                       help='Порт Flask сервера на машинке (по умолчанию: 5000)')
    parser.add_argument('--mobile-marker', type=int, default=0,
                       help='ID метки на машинке (по умолчанию: 0)')
    parser.add_argument('--enable-video-stream', action='store_true',
                       help='Включить потоковое видео MJPEG')
    parser.add_argument('--web-port', type=int, default=5001,
                       help='Порт веб-сервера (по умолчанию: 5001)')
    parser.add_argument('--skip-device', type=str, default='/dev/video0',
                       help='Устройство камеры для пропуска (по умолчанию: /dev/video0)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Система отслеживания ArUco")
    print("=" * 60)
    
    # Инициализация компонентов
    print("\n[1/5] Инициализация камеры...")
    camera = CameraManager(skip_devices=[args.skip_device])
    if not camera.find_available_camera():
        print("\nОшибка: Не удалось найти доступную камеру")
        print("Проверьте, что камера подключена и доступна")
        print("Убедитесь, что вы в группе 'video': sudo usermod -a -G video $USER")
        return
    
    print(f"✓ Камера найдена: {camera.camera_path}")
    print(f"  Разрешение: {int(camera.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(camera.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    
    print("\n[2/5] Инициализация детектора ArUco...")
    detector = ArucoDetector(static_marker_ids=[1, 2, 3, 4], mobile_marker_id=args.mobile_marker)
    print(f"✓ Детектор инициализирован (метка машинки: ID {args.mobile_marker})")
    
    print("\n[3/5] Инициализация системы координат...")
    coord_system = CoordinateSystem(smoothing_factor=0.7)
    print("✓ Система координат инициализирована")
    
    print("\n[4/5] Инициализация навигации...")
    print(f"  Подключение к машинке: {args.robot_ip}:{args.robot_port}")
    try:
        nav_controller = NavigationController(
            robot_ip=args.robot_ip,
            robot_port=args.robot_port,
            tolerance=5,
            angle_tolerance=0.2
        )
        print("✓ Навигация инициализирована")
    except Exception as e:
        print(f"✗ Ошибка инициализации навигации: {e}")
        print("  Продолжаем без управления машинкой (только отслеживание координат)")
        nav_controller = None
    
    init_navigation(nav_controller)
    
    print("\n[5/5] Запуск веб-сервера...")
    # Определяем IP адрес сервера для отображения
    def get_local_ip():
        """Получить локальный IP адрес сервера."""
        try:
            # Подключаемся к внешнему адресу (не отправляем данные)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"
    
    server_ip = get_local_ip()
    
    # Запускаем Flask сервер в отдельном потоке
    server_thread = threading.Thread(
        target=run_server,
        args=('0.0.0.0', args.web_port, False),
        daemon=True
    )
    server_thread.start()
    
    # Даем серверу время на инициализацию
    time.sleep(1.0)
    
    # Проверяем, что сервер запустился
    try:
        import requests
        test_response = requests.get(f'http://localhost:{args.web_port}/api/status', timeout=2)
        if test_response.status_code == 200:
            print(f"✓ Веб-сервер запущен и отвечает на http://0.0.0.0:{args.web_port}")
        else:
            print(f"⚠ Веб-сервер запущен, но отвечает с кодом {test_response.status_code}")
    except ImportError:
        print(f"⚠ Модуль requests не установлен, пропускаем проверку сервера")
        print(f"   Сервер должен быть доступен на http://0.0.0.0:{args.web_port}")
    except Exception as e:
        print(f"⚠ Не удалось проверить сервер: {e}")
        print(f"   Сервер должен быть доступен на http://0.0.0.0:{args.web_port}")
    
    print(f"  Локальный доступ: http://localhost:{args.web_port}")
    print(f"  Сетевой доступ: http://{server_ip}:{args.web_port}")
    print(f"  Endpoint для TEstPI: http://{server_ip}:{args.web_port}/api/upload_frame")
    print()
    print("=" * 60)
    print("📋 ИНСТРУКЦИИ ПО ПОДКЛЮЧЕНИЮ:")
    print("=" * 60)
    print(f"1. Для TEstPI.py (на Raspberry Pi):")
    print(f"   python TEstPI.py --server-ip {server_ip} --server-port {args.web_port}")
    print()
    print(f"2. Для машинки (Raspberry Pi с machine.py):")
    print(f"   Убедитесь, что machine.py запущен на {args.robot_ip}:{args.robot_port}")
    print("=" * 60)
    print()
    if args.enable_video_stream:
        print("  Потоковое видео: ВКЛЮЧЕНО")
    else:
        print("  Потоковое видео: ВЫКЛЮЧЕНО (используется /api/frame)")
    
    print("\n" + "=" * 60)
    print("Система готова к работе!")
    print(f"Откройте браузер и перейдите на http://localhost:{args.web_port}")
    print(f"Или с другого устройства: http://{server_ip}:{args.web_port}")
    print("Нажмите 'q' для выхода")
    print("=" * 60 + "\n")
    
    # Небольшая задержка для инициализации камеры
    time.sleep(0.5)
    
    frame_count = 0
    last_nav_update = 0
    nav_update_interval = 0.2  # Обновлять навигацию 5 раз в секунду (уменьшено для производительности)
    
    try:
        while True:
            ret, frame = camera.read_frame()
            if not ret:
                print(f"Ошибка: Не удалось прочитать кадр")
                break
            
            frame_count += 1
            
            if frame_count == 1:
                print(f"✓ Первый кадр получен! Размер: {frame.shape}")
            
            # Обработка изображения
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            # Детекция меток
            corners, ids, rejected = detector.detect_markers(gray)
            
            mobile_coords = None
            mobile_rotation = None
            
            # Отладочная информация о детекции меток
            if frame_count % 30 == 0:  # Каждые 30 кадров
                if ids is not None:
                    detected_ids_list = ids.flatten().tolist()
                    print(f"🔍 Обнаружены метки: {detected_ids_list}")
                else:
                    print("🔍 Метки не обнаружены")
            
            if ids is not None:
                # Фильтруем стационарные метки
                static_markers = detector.filter_static_markers(corners, ids)
                
                if static_markers is not None:
                    # Калибруем систему координат
                    if not coord_system.is_calibrated:
                        if coord_system.calibrate(static_markers):
                            print("✓ Система координат откалибрована")
                    
                    # Рисуем полигон
                    frame = coord_system.draw_polygon(frame, static_markers)
                    
                    # Определяем метку машинки
                    mobile_corners, mobile_center_pixel = detector.get_mobile_marker(corners, ids)
                    
                    if mobile_corners is not None and mobile_center_pixel is not None:
                        # Преобразуем координаты машинки
                        mobile_coords = coord_system.transform_point(mobile_center_pixel)
                        
                        if mobile_coords is not None:
                            # Вычисляем поворот машинки
                            mobile_rotation = coord_system.calculate_rotation_from_marker(
                                mobile_corners, mobile_center_pixel
                            )
                            
                            # Рисуем метку машинки
                            frame = detector.draw_mobile_marker(
                                frame, mobile_corners, mobile_center_pixel, mobile_rotation
                            )
                            
                            # Отображаем координаты на кадре
                            coord_text = f"({mobile_coords[0]}, {mobile_coords[1]})"
                            if mobile_rotation is not None:
                                rotation_deg = int(math.degrees(mobile_rotation))
                                coord_text += f" Rot:{rotation_deg}°"
                            
                            center_int = tuple(map(int, mobile_center_pixel))
                            cv2.putText(frame, coord_text,
                                       (center_int[0] + 20, center_int[1] + 40),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                            
                            # Обновляем навигацию
                            current_time = time.time()
                            if current_time - last_nav_update >= nav_update_interval:
                                if nav_controller is not None:
                                    nav_controller.update(
                                        mobile_coords[0],
                                        mobile_coords[1],
                                        mobile_rotation if mobile_rotation is not None else 0.0
                                    )
                                last_nav_update = current_time
                            
                            if frame_count % 30 == 0:
                                rotation_deg = math.degrees(mobile_rotation) if mobile_rotation is not None else None
                                print(f"✓ Машинка: ({mobile_coords[0]}, {mobile_coords[1]}), "
                                      f"rotation: {rotation_deg:.1f}°" if rotation_deg is not None else
                                      f"✓ Машинка: ({mobile_coords[0]}, {mobile_coords[1]})")
                        else:
                            if frame_count % 60 == 0:
                                print("⚠ Не удалось преобразовать координаты машинки")
                    else:
                        if frame_count % 60 == 0:
                            detected_ids_list = ids.flatten().tolist() if ids is not None else []
                            print(f"⚠ Метка машинки (ID {args.mobile_marker}) не обнаружена!")
                            print(f"   Обнаружены метки: {detected_ids_list}")
                else:
                    if frame_count % 60 == 0:
                        detected_ids_list = ids.flatten().tolist()
                        print(f"⚠ Не все стационарные метки найдены. Обнаружены: {detected_ids_list}")
                        print(f"   Ожидаются: [1, 2, 3, 4]")
                
                # Рисуем все обнаруженные метки
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            # Обновляем состояние для веб-интерфейса
            # Всегда передаем frame для /api/frame endpoint (даже если потоковое видео выключено)
            if mobile_coords is not None:
                update_state(
                    mobile_coords[0],
                    mobile_coords[1],
                    mobile_rotation,
                    frame
                )
            else:
                update_state(None, None, None, frame)
            
            # Отображение кадра (опционально, если есть дисплей)
            try:
                cv2.imshow("ArUco Tracking System", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("\nВыход по нажатию 'q'")
                    break
            except cv2.error:
                # Если нет дисплея, продолжаем работу без отображения
                pass
    
    except KeyboardInterrupt:
        print("\n\nПрерывание пользователем")
    
    finally:
        print("\nЗавершение работы...")
        if nav_controller is not None:
            nav_controller.clear_target()
        camera.release()
        cv2.destroyAllWindows()
        print("Готово!")


if __name__ == "__main__":
    main()

