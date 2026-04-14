"""Flask веб-сервер для управления навигацией."""

from flask import Flask, render_template, request, jsonify
import threading
import time

app = Flask(__name__)

# Глобальные переменные для обмена данными между потоками
current_coords = {"x": None, "y": None}
target_coords = {"x": None, "y": None}
navigation_controller = None
movement_executor = None


@app.route('/')
def index():
    """Главная страница."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Получить текущий статус системы."""
    nav_status = navigation_controller.get_status() if navigation_controller else {}
    
    return jsonify({
        "current_coords": current_coords,
        "target_coords": target_coords,
        "navigation": nav_status
    })


@app.route('/api/set_target', methods=['POST'])
def set_target():
    """Установить целевую точку."""
    data = request.json
    x = float(data.get('x', 0))
    y = float(data.get('y', 0))
    
    if navigation_controller:
        navigation_controller.set_target(x, y)
        target_coords["x"] = x
        target_coords["y"] = y
        # Координаты автоматически отправляются на машинку через NavigationController.set_target()
        return jsonify({"success": True, "message": f"Цель установлена: ({x:.3f}, {y:.3f})"})
    
    return jsonify({"success": False, "message": "Контроллер навигации не инициализирован"}), 400


@app.route('/api/stop', methods=['POST'])
def stop():
    """Остановить движение."""
    if navigation_controller:
        navigation_controller.clear_target()
        target_coords["x"] = None
        target_coords["y"] = None
        # Машинка сама перезаписывает новую целевую точку, поэтому команда очистки не отправляется
        return jsonify({"success": True, "message": "Движение остановлено"})
    
    return jsonify({"success": False, "message": "Контроллер навигации не инициализирован"}), 400


@app.route('/api/update_coords', methods=['POST'])
def update_coords():
    """Обновить текущие координаты (вызывается из основного потока)."""
    data = request.json
    current_coords["x"] = data.get('x')
    current_coords["y"] = data.get('y')
    return jsonify({"success": True})


def run_server(host='0.0.0.0', port=5000, debug=False):
    """Запустить Flask сервер."""
    app.run(host=host, port=port, debug=debug, threaded=True)


def init_navigation(nav_controller, mov_executor):
    """Инициализировать контроллеры навигации."""
    global navigation_controller, movement_executor
    navigation_controller = nav_controller
    movement_executor = mov_executor

