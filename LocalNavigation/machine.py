# Программа распределения пинов на планке GPIO на плате RaspBerry PI 4B для 
# управления двигателями 
import RPi.GPIO as GPIO 
import time 
from flask import Flask, request, render_template


app = Flask(__name__)

# Распределение пинов для левого двигателя
PWMA_l = 36
AIN1_l = 40
AIN2_l = 38

# Распределение пинов для правого двигателя
PWMB_r = 33
BIN1_r = 35
BIN2_r = 37

# Выводит информацию по модулям
print(GPIO.RPI_INFO)
GPIO.setmode(GPIO.BOARD)

# Инициализация левого двигателя
GPIO.setup(PWMA_l, GPIO.OUT)
GPIO.setup(AIN1_l, GPIO.OUT)
GPIO.setup(AIN2_l, GPIO.OUT)

# Инициализация правого двигателя
GPIO.setup(PWMB_r, GPIO.OUT)
GPIO.setup(BIN1_r, GPIO.OUT)
GPIO.setup(BIN2_r, GPIO.OUT)

# запуск широтно-импульсную модуляцию (ШИМ) на GPIO пинах левого двигателя
# 255: Это частота ШИМ в герцах (Hz)
pwm_l = GPIO.PWM(PWMA_l, 255)
pwm_l.start(0)

# запуск широтно-импульсную модуляцию (ШИМ) на GPIO пинах правого двигателя
# 255: Это частота ШИМ в герцах (Hz)
pwm_r = GPIO.PWM(PWMB_r, 255)
pwm_r.start(0)

# Функции управления левым двигателем
def control_motor_left(direction):
    # Функция для ротации левого двигателя по часовой 
    if direction == 'forward':
        GPIO.output(AIN1_l, GPIO.LOW)
        GPIO.output(AIN2_l, GPIO.HIGH)
        pwm_l.ChangeDutyCycle(20)
    # Функция для ротации левого двигателя против часовой
    elif direction == 'backward':
        GPIO.output(AIN1_l, GPIO.HIGH)
        GPIO.output(AIN2_l, GPIO.LOW)
        pwm_l.ChangeDutyCycle(20)
    # Функция для остановки работы левого двигателя
    else:
        GPIO.output(AIN1_l, GPIO.LOW)
        GPIO.output(AIN2_l, GPIO.LOW)
        pwm_l.ChangeDutyCycle(0)

# Функция для управления правым двигателем
def control_motor_right(direction):
    # Функция для ротации правого двигателя по часовой 
    if direction == 'forward':
        GPIO.output(BIN1_r, GPIO.HIGH)
        GPIO.output(BIN2_r, GPIO.LOW)
        pwm_r.ChangeDutyCycle(20)
    # Функция для ротации правого двигателя против часовой
    elif direction == 'backward':
        GPIO.output(BIN1_r, GPIO.LOW)
        GPIO.output(BIN2_r, GPIO.HIGH)
        pwm_r.ChangeDutyCycle(20)
    else:
    # Функция для остановки работы правого двигателя
        GPIO.output(BIN1_r, GPIO.LOW)
        GPIO.output(BIN2_r, GPIO.LOW)
        pwm_r.ChangeDutyCycle(0)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/move', methods=['POST'])
def move():
    data = request.get_json()
    direction = data.get('direction')
    control_motor_left('stop')
    control_motor_right('stop')

    # Если команда "Вперёд", то оба двигателя начинают работать в режиме "по часовой стрелке"
    if direction == 'forward':
        print("Forward")
        control_motor_left('forward')
        control_motor_right('forward')
        # Добавляем небольшую задержку для стабилизации
        time.sleep(0.5)
    
    # Если команда "Влево", то левый двигатель - "против часовой", правый двигатель - "по часовой"
    elif direction == 'backward':
        print("Turn left")
        control_motor_left('backward')
        control_motor_right('backward')
        # Добавляем небольшую задержку для стабилизации
        time.sleep(0.5)
        
    # Если команда "Назад", то оба двигателя начинают работать в режиме "против часовой стрелки"
    elif direction == 'left':
        print("Backward")
        control_motor_left('backward')
        control_motor_right('forward')
        # Добавляем небольшую задержку для стабилизации
        time.sleep(0.5)

    # Если команда "Вправо", то левый двигатель - "по часовой", правый двигатель - "против часовой"
    elif direction == 'right':
        print("Turn right")
        control_motor_left('forward')
        control_motor_right('backward')
        # Добавляем небольшую задержку для стабилизации
        time.sleep(0.5)
    elif direction == 'stop':
        control_motor_left('stop')
        control_motor_right('stop')
    # Иначе, двигатели прекращают работу!
    else:
        control_motor_left('stop')
        control_motor_right('stop')
        return "Invalid command", 400
    
    control_motor_left('stop')
    control_motor_right('stop')
    return f"Executed {direction}", 200


@app.route('/shutdown', methods=['GET'])
def shutdown():
    control_motor_left('stop')
    control_motor_right('stop')
    GPIO.cleanup()
    return "Motors stopped and GPIO cleaned up."

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        pwm_l.stop()
        pwm_r.stop()
        # Очищение кэша
        GPIO.cleanup()