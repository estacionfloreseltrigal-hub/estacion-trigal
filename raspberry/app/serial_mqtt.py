#!/usr/bin/env python3
"""
Puente serial -> MQTT - Estación Trigal

Lee lo que manda la ESP32 por USB y lo publica en Mosquitto:
    $EST,co2=612,ta=19.4,...,s1h=38.5,...  ->  trigal/estacion1/datos   (toda la trama en un solo mensaje)
    Estado: LUZ_BLANCA / #OK,... / #ERR,... ->  trigal/estacion1/esp   (estados y avisos de la ESP)
    (también acepta líneas JSON {"t":"ambiente",...}, como el sketch de prueba)
Y en sentido contrario, lo que llegue a trigal/estacion1/cmd se reenvía a la ESP32.

Estado del puente (retenido): trigal/estacion1/puente = "online" / "offline".

Configuración en /opt/trigal/app/trigal.env (o la ruta en la variable TRIGAL_ENV):
    MQTT_HOST=localhost
    MQTT_PORT=1883
    MQTT_USER=estacion
    MQTT_PASS=la_clave_de_bitwarden
    ESTACION=estacion1
    SERIAL_PORT=            # vacío = detectar solo
    SERIAL_BAUD=115200

Se recupera solo si se desconecta el USB o se reinicia Mosquitto.
"""
import glob
import json
import logging
import math
import os
import queue
import signal
import sys
import time

try:
    import serial
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Faltan librerías. Instálalas con:  sudo apt install -y python3-serial python3-paho-mqtt")

TIPOS_DATOS = {"ambiente", "suelo", "sistema"}

# Nombres de la trama $EST -> nombres que se guardan en InfluxDB
NOMBRES = {
    "co2": "co2", "ta": "temperatura", "hra": "humedad", "lux": "lux", "par": "par",
    "tc": "temp_caja", "vent": "ventilador", "luz": "luz",
    "s1h": "s1_humedad", "s1t": "s1_temp", "s1ce": "s1_ce", "s1ph": "s1_ph",
    "s2h": "s2_humedad", "s2t": "s2_temp", "s2ce": "s2_ce", "s2ph": "s2_ph",
    "s3h": "s3_humedad", "s3t": "s3_temp", "s3ce": "s3_ce", "s3ph": "s3_ph",
}


def leer_trama(texto):
    """$EST,co2=612,ta=19.4,... -> un solo diccionario. Los valores 'nan' se descartan."""
    datos = {}
    for parte in texto.split(",")[1:]:
        if "=" not in parte:
            continue
        clave, valor = parte.split("=", 1)
        clave = clave.strip()
        try:
            numero = float(valor)
        except ValueError:
            continue
        if math.isnan(numero):
            continue
        datos[NOMBRES.get(clave, clave)] = numero
    return [("datos", datos)] if datos else []


def interpretar_linea(texto):
    """Devuelve lista de (subtopic, datos) para publicar, o [] si la línea no se reconoce."""
    if texto.startswith("$EST"):
        return leer_trama(texto)
    if texto.startswith("Estado:"):
        return [("esp", {"estado_luces": texto.split(":", 1)[1].strip()})]
    if texto.startswith("#OK") or texto.startswith("#ERR"):
        nivel, _, mensaje = texto[1:].partition(",")
        return [("esp", {"nivel": nivel.lower(), "msg": mensaje.strip()})]
    try:
        dato = json.loads(texto)
    except ValueError:
        return []
    if not isinstance(dato, dict):
        return []
    tipo = dato.pop("t", None)
    if tipo in TIPOS_DATOS:
        return [(tipo, dato)]
    if tipo:
        dato["t"] = tipo
    return [("esp", dato)]
SIN_DATOS_S = 180   # sin tramas $EST completas en este tiempo, se reinicia la ESP32
SIN_SUELO_S = 1800  # sin datos de suelo en este tiempo (las sondas van cada 15 min), se reinicia la ESP32

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("puente")


def cargar_env(ruta):
    """Lee un archivo KEY=valor sencillo (sin depender de python-dotenv)."""
    conf = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                conf[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    else:
        log.warning("No existe %s; uso solo variables de entorno", ruta)
    for k in list(conf) + ["MQTT_HOST", "MQTT_PORT", "MQTT_USER", "MQTT_PASS",
                           "ESTACION", "SERIAL_PORT", "SERIAL_BAUD"]:
        if os.environ.get(k):
            conf[k] = os.environ[k]
    return conf


# Puertos que NO son la ESP32: el SIM7600 crea varios /dev/ttyUSB* (AT, GPS, PPP...)
EXCLUIR = ("SimTech", "SIM7600", "Qualcomm", "Quectel")
# Nombres típicos de la ESP32-S3: USB nativo (Espressif) o chips CH340 / CP210x
PREFERIR = ("Espressif", "esp32", "1a86", "CH340", "CP210", "Silicon_Labs")


def abrir_serial(puerto, baudios):
    """Abre el puerto SIN mover DTR/RTS, para no dejar la ESP32 en modo de carga de programa."""
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = puerto, baudios, 1
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def reiniciar_esp(ser):
    """Reinicio normal de la ESP32 (EN abajo y arriba con IO0 en alto): arranca ejecutando el programa."""
    try:
        ser.dtr = False
        ser.rts = True
        time.sleep(0.2)
        ser.rts = False
    except (OSError, serial.SerialException):
        pass  # algunos puertos no tienen estas señales


def buscar_puerto_esp():
    """Busca la ESP32 sin confundirla con los puertos del módulo 4G."""
    if os.path.exists("/dev/esp32"):          # enlace creado por la regla udev 99-esp32.rules
        return "/dev/esp32"
    por_id = sorted(glob.glob("/dev/serial/by-id/*"))
    candidatos = [p for p in por_id if not any(x.lower() in p.lower() for x in EXCLUIR)]
    for p in candidatos:
        if any(x.lower() in p.lower() for x in PREFERIR):
            return p
    if candidatos:
        return candidatos[0]
    if not por_id:                             # sin /dev/serial/by-id: último recurso
        acm = sorted(glob.glob("/dev/ttyACM*"))
        if acm:
            return acm[0]
    return None


def buscar_puerto(preferido):
    if preferido:
        return preferido if os.path.exists(preferido) else None
    return buscar_puerto_esp()


def crear_cliente(conf, base, ordenes):
    cid = f"{conf.get('ESTACION', 'estacion1')}-puente-serial"
    try:  # paho-mqtt 2.x
        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
    except AttributeError:  # paho-mqtt 1.x (la de apt en Raspberry Pi OS Bookworm)
        cliente = mqtt.Client(client_id=cid)

    if conf.get("MQTT_USER"):
        cliente.username_pw_set(conf["MQTT_USER"], conf.get("MQTT_PASS", ""))
    cliente.will_set(f"{base}/puente", "offline", qos=1, retain=True)
    cliente.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(c, userdata, flags, rc, properties=None):
        codigo = getattr(rc, "value", rc)
        if codigo == 0:
            log.info("Conectado a Mosquitto")
            c.publish(f"{base}/puente", "online", qos=1, retain=True)
            c.subscribe(f"{base}/cmd", qos=1)
        else:
            log.error("Mosquitto rechazó la conexión (código %s). ¿Usuario/clave de 'estacion'?", rc)

    def on_disconnect(c, userdata, *args):
        log.warning("Desconectado de Mosquitto; reintentando...")

    def on_message(c, userdata, msg):
        texto = msg.payload.decode("utf-8", errors="replace").strip()
        try:
            json.loads(texto)
        except ValueError:
            log.warning("Orden ignorada en %s (no es JSON): %r", msg.topic, texto)
            return
        ordenes.put(texto)

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect
    cliente.on_message = on_message
    host, puerto = conf.get("MQTT_HOST", "localhost"), int(conf.get("MQTT_PORT", 1883))
    cliente.connect_async(host, puerto, keepalive=30)
    cliente.loop_start()
    return cliente


def _detener(*_):
    raise KeyboardInterrupt  # systemd manda SIGTERM al detener el servicio


def main():
    signal.signal(signal.SIGTERM, _detener)
    conf = cargar_env(os.environ.get("TRIGAL_ENV", "/opt/trigal/app/trigal.env"))
    base = f"trigal/{conf.get('ESTACION', 'estacion1')}"
    baud = int(conf.get("SERIAL_BAUD", 115200))
    ordenes = queue.Queue()
    cliente = crear_cliente(conf, base, ordenes)
    contador = 0

    try:
        while True:
            puerto = buscar_puerto(conf.get("SERIAL_PORT"))
            if not puerto:
                log.warning("No veo la ESP32 conectada; reintento en 5 s")
                time.sleep(5)
                continue
            try:
                with abrir_serial(puerto, baud) as ser:
                    log.info("Leyendo %s a %d baudios (reiniciando la ESP32)", puerto, baud)
                    reiniciar_esp(ser)
                    time.sleep(2.5)               # se descarta lo que imprime al arrancar
                    ser.reset_input_buffer()
                    ultimo_dato = time.time()
                    ultimo_suelo = time.time()
                    while True:
                        if time.time() - ultimo_dato > SIN_DATOS_S:
                            log.warning("La ESP32 no manda tramas completas hace %d s; la reinicio", SIN_DATOS_S)
                            reiniciar_esp(ser)
                            ultimo_dato = ultimo_suelo = time.time()
                        if time.time() - ultimo_suelo > SIN_SUELO_S:
                            log.warning("Sin datos de suelo hace %d s (¿bus RS485 trabado?); reinicio la ESP32", SIN_SUELO_S)
                            reiniciar_esp(ser)
                            ultimo_dato = ultimo_suelo = time.time()

                        while not ordenes.empty():
                            orden = ordenes.get()
                            ser.write((orden + "\n").encode("utf-8"))
                            log.info("-> ESP32: %s", orden)

                        crudo = ser.readline()
                        if not crudo:
                            continue
                        texto = crudo.decode("utf-8", errors="replace").strip()
                        mensajes = interpretar_linea(texto)
                        if not mensajes:
                            log.warning("Línea no reconocida, ignorada: %r", texto[:120])
                            continue

                        for tipo, dato in mensajes:
                            if tipo == "datos":
                                if "ventilador" in dato:
                                    ultimo_dato = time.time()
                                else:
                                    log.warning("Trama $EST incompleta: %r", texto[:200])
                                if any(k.startswith(("s1_", "s2_", "s3_")) for k in dato):
                                    ultimo_suelo = time.time()
                            topic = f"{base}/{tipo}"
                            info = cliente.publish(topic, json.dumps(dato, separators=(",", ":")), qos=1)
                            contador += 1
                            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                                log.warning("No se pudo publicar (Mosquitto caído?) %s", topic)
                            elif tipo == "esp" or contador % 30 == 1:
                                log.info("%s <- %s", topic, dato)
            except (serial.SerialException, OSError) as e:
                log.error("Se perdió el puerto serial (%s); reintento en 3 s", e)
                time.sleep(3)
    except KeyboardInterrupt:
        log.info("Detenido por el usuario")
    finally:
        cliente.publish(f"{base}/puente", "offline", qos=1, retain=True)
        time.sleep(0.5)
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    main()
