"""Главный файл для запуска системы навигации ArUco."""

import cv2
import time
import threading
import sys
import os
import argparse
import math
import numpy as np

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.aruco.detector import ArucoDetector, CameraManager
from src.aruco.coordinates import CoordinateSystem
from src.navigation.controller import NavigationController, MovementExecutor
from src.web.app import run_server, init_navigation, current_coords, target_coords


def main():
    """Главная функция."""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Система навигации ArUco для управления машинкой')
    parser.add_argument('--robot-ip', type=str, default='192.168.1.100',
                       help='IP адрес машинки на Raspberry Pi (по умолчанию: 192.168.1.100)')
    parser.add_argument('--robot-port', type=int, default=5000,
                       help='Порт Flask сервера на машинке (по умолчанию: 5000)')
    parser.add_argument('--front-marker', type=int, default=8,
                       help='ID передней метки на машинке (по умолчанию: 8)')
    parser.add_argument('--rear-marker', type=int, default=0,
                       help='ID задней метки на машинке (по умолчанию: 0)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Система навигации ArUco")
    print("=" * 60)
    
    # Инициализация компонентов
    print("\n[1/5] Инициализация камеры...")
    camera = CameraManager(skip_devices=['/dev/video0'])
    if not camera.find_available_camera():
        print("\nОшибка: Не удалось найти доступную камеру")
        print("Проверьте, что камера подключена и доступна")
        print("Убедитесь, что вы в группе 'video': sudo usermod -a -G video $USER")
        return
    
    print(f"✓ Камера найдена: {camera.camera_path}")
    print(f"  Разрешение: {int(camera.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(camera.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    
    print("\n[2/5] Инициализация детектора ArUco...")
    detector = ArucoDetector(static_marker_ids=[1, 2, 3, 4], mobile_marker_ids=[args.front_marker, args.rear_marker])
    print(f"✓ Детектор инициализирован (передняя метка: ID {args.front_marker}, задняя метка: ID {args.rear_marker})")
    
    print("\n[3/5] Инициализация системы координат...")
    coord_system = CoordinateSystem(smoothing_factor=0.7)
    print("✓ Система координат инициализирована")
    
    print("\n[4/5] Инициализация навигации...")
    print(f"  Подключение к машинке: {args.robot_ip}:{args.robot_port}")
    try:
        movement_executor = MovementExecutor(robot_ip=args.robot_ip, robot_port=args.robot_port)
        nav_controller = NavigationController(tolerance=0.02, max_speed=100, movement_executor=movement_executor)
        print("✓ Навигация инициализирована")
    except Exception as e:
        print(f"✗ Ошибка инициализации навигации: {e}")
        print("  Продолжаем без управления машинкой (только отслеживание координат)")
        movement_executor = None
        nav_controller = NavigationController(tolerance=0.02, max_speed=100)
    
    init_navigation(nav_controller, movement_executor)
    
    print("\n[5/5] Запуск веб-сервера...")
    # Запускаем Flask сервер в отдельном потоке (используем порт 5001 чтобы не конфликтовать с машинкой)
    web_port = 5001
    server_thread = threading.Thread(
        target=run_server,
        args=('0.0.0.0', web_port, False),
        daemon=True
    )
    server_thread.start()
    print(f"✓ Веб-сервер запущен на http://0.0.0.0:{web_port}")
    
    print("\n" + "=" * 60)
    print("Система готова к работе!")
    print(f"Откройте браузер и перейдите на http://localhost:{web_port}")
    print("Нажмите 'q' для выхода")
    print("=" * 60 + "\n")
    
    # Небольшая задержка для инициализации камеры
    time.sleep(0.5)
    
    frame_count = 0
    last_coords_update = 0
    coords_update_interval = 0.5  # Обновлять координаты каждые 1 секунду
    
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
                    if frame_count % 30 == 0:
                        print(f"✓ Стационарные метки найдены: {list(static_markers.keys())}")
                    
                    # Упорядочиваем метки
                    ordered_centers = coord_system.order_markers(static_markers)
                    
                    if ordered_centers is not None:
                        # Вычисляем матрицу преобразования
                        coord_system.compute_transform_matrix(ordered_centers)
                        
                        if frame_count % 60 == 0:
                            print("✓ Система координат инициализирована")
                        
                        # Рисуем систему координат
                        frame = coord_system.draw_coordinate_system(frame, ordered_centers)
                        
                        # Определяем координаты обеих меток на машинке (передняя и задняя)
                        front_center, rear_center = detector.get_mobile_markers(corners, ids)
                        if front_center is not None and rear_center is not None:
                            # Преобразуем координаты обеих меток
                            front_coords = coord_system.transform_coordinates(front_center)
                            rear_coords = coord_system.transform_coordinates(rear_center)
                            
                            # Вычисляем центр машинки (середина между передней и задней метками)
                            center_x = (front_coords[0] + rear_coords[0]) / 2.0
                            center_y = (front_coords[1] + rear_coords[1]) / 2.0
                            mobile_coords = np.array([center_x, center_y])
                            
                            # Вычисляем угол поворота по двум меткам
                            rotation = coord_system.calculate_rotation(front_coords, rear_coords)
                            
                            if frame_count % 30 == 0:
                                rotation_deg = math.degrees(rotation) if rotation is not None else None
                                print(f"✓ Метки найдены: передняя ({front_coords[0]:.3f}, {front_coords[1]:.3f}), "
                                      f"задняя ({rear_coords[0]:.3f}, {rear_coords[1]:.3f})")
                                print(f"  Центр: ({center_x:.3f}, {center_y:.3f}), "
                                      f"угол: {rotation_deg:.1f}°" if rotation is not None else "  Центр: ({center_x:.3f}, {center_y:.3f})")
                            
                            # Обновляем координаты в веб-интерфейсе и отправляем на машинку
                            current_time = time.time()
                            if current_time - last_coords_update >= coords_update_interval:
                                current_coords["x"] = float(mobile_coords[0])
                                current_coords["y"] = float(mobile_coords[1])
                                last_coords_update = current_time
                                
                                # Отправляем координаты местоположения и rotation на машинку
                                if movement_executor is not None:
                                    movement_executor.send_current_coordinates(
                                        float(mobile_coords[0]), 
                                        float(mobile_coords[1]),
                                        float(rotation) if rotation is not None else None
                                    )
                                
                                # Логируем информацию о цели (координаты отправляются один раз при установке цели)
                                if nav_controller.target_coords is not None:
                                    if frame_count % 30 == 0:
                                        rotation_deg = math.degrees(rotation) if rotation is not None else None
                                        print(f"📍 Текущие координаты: ({mobile_coords[0]:.3f}, {mobile_coords[1]:.3f}), "
                                              f"rotation: {rotation_deg:.1f}°" if rotation is not None else 
                                              f"📍 Текущие координаты: ({mobile_coords[0]:.3f}, {mobile_coords[1]:.3f})")
                                        print(f"🎯 Цель: {nav_controller.target_coords}")
                                else:
                                    if frame_count % 60 == 0:
                                        print("ℹ Цель не установлена")
                        else:
                            # Метки машинки не видны
                            if nav_controller.target_coords is not None and frame_count % 30 == 0:
                                detected_ids_list = ids.flatten().tolist() if ids is not None else []
                                print(f"⚠ Метки машинки (ID {args.front_marker} и {args.rear_marker}) не обнаружены!")
                                print(f"   Обнаружены метки: {detected_ids_list}")
                else:
                    if frame_count % 60 == 0:
                        detected_ids_list = ids.flatten().tolist()
                        print(f"⚠ Не все стационарные метки найдены. Обнаружены: {detected_ids_list}")
                        print(f"   Ожидаются: [1, 2, 3, 4]")
                
                # Логируем информацию о системе координат
                if nav_controller.target_coords is not None:
                    if coord_system.transform_matrix is None:
                        if frame_count % 60 == 0:  # Логируем каждые 60 кадров
                            print("⚠ Система координат не инициализирована (не видны все 4 стационарные метки)")
                    elif mobile_coords is None:
                        if frame_count % 30 == 0:
                            print("⚠ Подвижная метка не видна")
                
                # Рисуем все обнаруженные метки
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                
                # Добавляем подписи ID для стационарных меток
                if static_markers is not None:
                    for marker_id, center in static_markers.items():
                        center_int = tuple(map(int, center))
                        cv2.putText(frame, f"ID:{marker_id}",
                                   (center_int[0] - 20, center_int[1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Отображаем координаты подвижной метки
                if mobile_coords is not None:
                    mobile_center = detector.get_mobile_marker_center(corners, ids)
                    if mobile_center is not None:
                        center_int = tuple(map(int, mobile_center))
                        cv2.circle(frame, center_int, 15, (0, 255, 255), 3)
                        coord_text = f"({mobile_coords[0]:.3f}, {mobile_coords[1]:.3f})"
                        cv2.putText(frame, coord_text,
                                   (center_int[0] + 20, center_int[1]),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        cv2.putText(frame, f"ID:{detector.front_marker_id},{detector.rear_marker_id}",
                                   (center_int[0] + 20, center_int[1] + 25),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            # Отображение кадра
            try:
                cv2.imshow("ArUco Navigation System", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("\nВыход по нажатию 'q'")
                    break
            except cv2.error as e:
                # Если нет дисплея, продолжаем работу без отображения
                time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n\nПрерывание пользователем")
    
    finally:
        print("\nЗавершение работы...")
        # Машинка сама управляет остановкой на основе целевой точки
        camera.release()
        cv2.destroyAllWindows()
        print("Готово!")


if __name__ == "__main__":
    main()

