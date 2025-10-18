from machine import Pin, PWM
import time
import network
from umqtt.simple import MQTTClient

# === CONFIGURACIÓN DE RED ===
SSID = "Familia puentes"
PASSWORD = "Matteo2023"

# === CONFIGURACIÓN MQTT ===
MQTT_BROKER = "192.168.1.9"
MQTT_CLIENT_ID = "ESP32_Agitador"
TOPIC_ESTADO = b"agitador/estado"
TOPIC_PWM = b"agitador/pwm"
TOPIC_CONTROL = b"agitador/control"

# === PINES ===
PIN_MOTOR = 4     # Pin del motor PWM
PIN_LED = 2       # LED indicador
PIN_BOTON = 15    # Botón de inicio

# === CONFIGURACIÓN PWM ===
FREQ = 1000
pwm_motor = PWM(Pin(PIN_MOTOR), freq=FREQ, duty=0)
led = Pin(PIN_LED, Pin.OUT)
boton = Pin(PIN_BOTON, Pin.IN, Pin.PULL_UP)

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
        client.publish(TOPIC_PWM, str(int(duty / 4)))  # 0–255
        time.sleep(delay)

def ramp_down(pwm, step=5, delay=0.2):
    for duty in range(1023, -1, -step):
        pwm.duty(duty)
        client.publish(TOPIC_PWM, str(int(duty / 4)))
        time.sleep(delay)

# === CICLO DE AGITACIÓN ===
def ciclo_agitacion():
    publicar_estado(b"Iniciando agitación (rampa subida)")
    led.on()  # 🔴 Enciende LED al iniciar
    ramp_up(pwm_motor, step=4, delay=0.15)  # Más suave

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
    client.publish(TOPIC_PWM, "0")
    led.off()
    publicar_estado(b"Agitador apagado")
    print("✅ Ciclo completo finalizado\n")

# === CALLBACK MQTT (si quieres control remoto desde Node-RED) ===
def sub_cb(topic, msg):
    msg = msg.decode()
    print(f"📩 Mensaje recibido en {topic}: {msg}")
    if msg == "iniciar":
        ciclo_agitacion()
    elif msg == "detener":
        pwm_motor.duty(0)
        led.off()
        publicar_estado(b"Agitador detenido manualmente")

# === PROGRAMA PRINCIPAL ===
wlan = conectar_wifi()
client = conectar_mqtt()
if client:
    client.set_callback(sub_cb)
    client.subscribe(TOPIC_CONTROL)

publicar_estado(b"ESP32 listo. Esperando orden o botón...")

while True:
    client.check_msg()  # Revisa si hay mensajes MQTT
    if boton.value() == 0:  # Botón presionado (activo en LOW)
        publicar_estado(b"Botón presionado: iniciando ciclo")
        ciclo_agitacion()
        time.sleep(1)
