"""Flask веб-сервер для управления навигацией с потоковым видео."""

from flask import Flask, render_template, request, jsonify, Response
import threading
import time
import cv2
import numpy as np
import io
import base64


app = Flask(__name__)

# Глобальные переменные для обмена данными между потоками
current_state = {
    "x": None,
    "y": None,
    "rotation": None,
    "frame": None,
    "frame_encoded": None
}
# Состояние для второго изображения от TEstPI.py
testpi_state = {
    "frame": None,
    "frame_encoded": None
}
target_coords = {"x": None, "y": None}
navigation_controller = None
frame_lock = threading.Lock()
testpi_frame_lock = threading.Lock()


def generate_frames():
    """Генератор для потокового видео MJPEG (ArUco)."""
    while True:
        with frame_lock:
            if current_state["frame_encoded"] is not None:
                frame_bytes = base64.b64decode(current_state["frame_encoded"])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # Отправляем черный кадр если нет данных
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                _, buffer = cv2.imencode('.jpg', black_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS


def generate_testpi_frames():
    """Генератор для потокового видео MJPEG (TEstPI)."""
    while True:
        with testpi_frame_lock:
            if testpi_state["frame_encoded"] is not None:
                frame_bytes = base64.b64decode(testpi_state["frame_encoded"])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # Отправляем черный кадр если нет данных
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                _, buffer = cv2.imencode('.jpg', black_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS


@app.route('/')
def index():
    """Главная страница."""
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    """Потоковое видео MJPEG (ArUco)."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed_testpi')
def video_feed_testpi():
    """Потоковое видео MJPEG (TEstPI)."""
    return Response(generate_testpi_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Получить текущий статус системы."""
    nav_status = navigation_controller.get_status() if navigation_controller else {}
    
    return jsonify({
        "current_coords": {
            "x": current_state["x"],
            "y": current_state["y"],
            "rotation": current_state["rotation"]
        },
        "target_coords": target_coords,
        "navigation": nav_status
    })


@app.route('/api/set_target', methods=['POST'])
def set_target():
    """Установить целевую точку."""
    data = request.json
    x = int(data.get('x', 0))
    y = int(data.get('y', 0))
    
    if navigation_controller:
        navigation_controller.set_target(x, y)
        target_coords["x"] = x
        target_coords["y"] = y
        return jsonify({"success": True, "message": f"Цель установлена: ({x}, {y})"})
    
    return jsonify({"success": False, "message": "Контроллер навигации не инициализирован"}), 400


@app.route('/api/stop', methods=['POST'])
def stop():
    """Остановить движение."""
    if navigation_controller:
        navigation_controller.clear_target()
        target_coords["x"] = None
        target_coords["y"] = None
        return jsonify({"success": True, "message": "Движение остановлено"})
    
    return jsonify({"success": False, "message": "Контроллер навигации не инициализирован"}), 400


@app.route('/api/frame', methods=['GET'])
def get_frame():
    """Получить текущий кадр ArUco (если потоковое видео выключено)."""
    with frame_lock:
        if current_state["frame_encoded"] is not None:
            return jsonify({
                "success": True,
                "frame": current_state["frame_encoded"]
            })
        else:
            return jsonify({
                "success": False,
                "message": "Кадр недоступен"
            })


@app.route('/api/frame_testpi', methods=['GET'])
def get_frame_testpi():
    """Получить текущий кадр TEstPI (если потоковое видео выключено)."""
    with testpi_frame_lock:
        if testpi_state["frame_encoded"] is not None:
            return jsonify({
                "success": True,
                "frame": testpi_state["frame_encoded"]
            })
        else:
            return jsonify({
                "success": False,
                "message": "Кадр недоступен"
            })


@app.route('/api/upload_frame', methods=['POST'])
def upload_frame():
    """Принять изображение от TEstPI.py."""
    try:
        frame = None
        
        # Пробуем получить из multipart/form-data
        if 'image' in request.files:
            file = request.files['image']
            file_bytes = file.read()
            nparr = np.frombuffer(file_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Пробуем получить из JSON (base64)
        elif request.is_json and 'frame' in request.json:
            frame_data = request.json['frame']
            frame_bytes = base64.b64decode(frame_data)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return jsonify({"success": False, "message": "Изображение не найдено в запросе"}), 400
        
        if frame is None:
            return jsonify({"success": False, "message": "Не удалось декодировать изображение"}), 400
        
        # Сохраняем кадр
        with testpi_frame_lock:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            testpi_state["frame_encoded"] = base64.b64encode(frame_bytes).decode('utf-8')
            testpi_state["frame"] = frame
        
        return jsonify({"success": True, "message": "Кадр успешно получен"})
    
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка обработки изображения: {str(e)}"}), 500


def update_state(x, y, rotation, frame):
    """Обновляет состояние для веб-интерфейса."""
    global current_state
    
    with frame_lock:
        current_state["x"] = x
        current_state["y"] = y
        current_state["rotation"] = rotation
        
        if frame is not None:
            # Кодируем кадр в JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            current_state["frame_encoded"] = base64.b64encode(frame_bytes).decode('utf-8')
            current_state["frame"] = frame


def init_navigation(nav_controller):
    """Инициализирует контроллер навигации."""
    global navigation_controller
    navigation_controller = nav_controller


def run_server(host='0.0.0.0', port=5001, debug=False):
    """Запустить Flask сервер."""
    app.run(host=host, port=port, debug=debug, threaded=True)

