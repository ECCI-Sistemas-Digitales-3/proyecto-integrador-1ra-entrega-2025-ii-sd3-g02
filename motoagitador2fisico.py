from machine import Pin, PWM
import time
import network
from umqtt.simple import MQTTClient

# === CONFIGURACIÓN DE RED ===
SSID = "S22 Ultra de Nicolas"
PASSWORD = "12345678"

# === CONFIGURACIÓN MQTT ===
MQTT_BROKER = "10.152.59.190"
MQTT_CLIENT_ID = "ESP32_Agitador"
TOPIC_ESTADO = b"agitador/estado"
TOPIC_PWM = b"agitador/pwm"
TOPIC_CONTROL = b"agitador/control"

# === PINES (L298N canal A) ===
PIN_PWM = 19       # ENA - PWM motor
PIN_IN1 = 18       # IN1 - Dirección A
PIN_IN2 = 5        # IN2 - Dirección B
PIN_LED = 2        # LED indicador
PIN_BOTON = 15     # Botón de inicio

# === CONFIGURACIÓN PWM/DIGITAL ===
FREQ = 1000
pwm_motor = PWM(Pin(PIN_PWM), freq=FREQ, duty=0)
in1 = Pin(PIN_IN1, Pin.OUT, value=0)
in2 = Pin(PIN_IN2, Pin.OUT, value=0)
led = Pin(PIN_LED, Pin.OUT)
boton = Pin(PIN_BOTON, Pin.IN, Pin.PULL_UP)

# === FUNCIONES DE DIRECCIÓN (L298N) ===
def motor_forward():
    in1.on(); in2.off()

def motor_reverse():
    in1.off(); in2.on()

def motor_brake():
    # Freno activo (ambos HIGH en L298N)
    in1.on(); in2.on()

def motor_coast():
    # Rueda libre (ambos LOW)
    in1.off(); in2.off()

# === CONFIGURACIÓN WIFI ===
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("📡 Conectando a WiFi...")
        wlan.connect(SSID, PASSWORD)
        intento = 1
        while not wlan.isconnected() and intento <= 10:
            print(f"⏳ Intento {intento}/10")
            time.sleep(2)
            intento += 1
    if wlan.isconnected():
        print("✅ WiFi conectado:", wlan.ifconfig())
    else:
        print("❌ No se pudo conectar a WiFi")
    return wlan

# === MQTT ===
def conectar_mqtt():
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
    try:
        client.connect()
        print("🔗 Conectado al broker MQTT")
        return client
    except Exception as e:
        print("❌ Error al conectar MQTT:", e)
        return None

# === FUNCIONES DE PUBLICACIÓN ===
def publicar_estado(msg):
    print("📤 Estado:", msg)
    client.publish(TOPIC_ESTADO, msg)

# === RAMPAS PWM ===
def ramp_up(pwm, step=5, delay=0.2):
    for duty in range(0, 1024, step):  # 0–1023 = 0–100%
        pwm.duty(duty)
        client.publish(TOPIC_PWM, str(int(duty / 4)))  # 0–255 aprox
        time.sleep(delay)

def ramp_down(pwm, step=5, delay=0.2):
    for duty in range(1023, -1, -step):
        pwm.duty(duty)
        client.publish(TOPIC_PWM, str(int(duty / 4)))
        time.sleep(delay)

# === CICLO DE AGITACIÓN ===
def ciclo_agitacion():
    publicar_estado(b"Iniciando agitación (rampa subida)")
    led.on()
    motor_forward()                     # Dirección por defecto: adelante
    ramp_up(pwm_motor, step=4, delay=0.15)

    publicar_estado(b"Agitador a máxima velocidad")
    print("⚙️  Agitación en curso (5s)")
    tiempo_total = 5
    start_time = time.time()

    while (time.time() - start_time) < tiempo_total:
        elapsed = int(time.time() - start_time)
        current_duty = int(pwm_motor.duty() / 4)
        client.publish(TOPIC_PWM, str(current_duty))
        print(f"⏱️ {elapsed:02d}s | PWM: {current_duty}/255")
        time.sleep(1)

    publicar_estado(b"Finalizando agitación (rampa bajada)")
    ramp_down(pwm_motor, step=4, delay=0.15)
    pwm_motor.duty(0)
    motor_brake()                       # Frena el motor al terminar
    time.sleep(0.1)
    client.publish(TOPIC_PWM, "0")
    led.off()
    publicar_estado(b"Agitador apagado")
    print("✅ Ciclo completo finalizado\n")

# === CALLBACK MQTT (control remoto desde Node-RED) ===
def sub_cb(topic, msg):
    msg = msg.decode()
    print(f"📩 Mensaje recibido en {topic}: {msg}")
    if msg == "iniciar":
        ciclo_agitacion()
    elif msg == "detener":
        pwm_motor.duty(0)
        motor_brake()
        led.off()
        publicar_estado(b"Agitador detenido manualmente")
    elif msg == "adelante":
        motor_forward()
        publicar_estado(b"Direccion: adelante")
    elif msg == "atras":
        motor_reverse()
        publicar_estado(b"Direccion: atras")
    elif msg == "libre":
        motor_coast()
        publicar_estado(b"Motor en rueda libre")
    elif msg == "freno":
        motor_brake()
        publicar_estado(b"Freno activo")

# === PROGRAMA PRINCIPAL ===
wlan = conectar_wifi()
client = conectar_mqtt()
if client:
    client.set_callback(sub_cb)
    client.subscribe(TOPIC_CONTROL)

publicar_estado(b"ESP32 listo. Esperando orden o boton...")

while True:
    client.check_msg()  # Revisa si hay mensajes MQTT
    if boton.value() == 0:  # Botón presionado (activo en LOW)
        publicar_estado(b"Boton presionado: iniciando ciclo")
        ciclo_agitacion()
        time.sleep(1)
