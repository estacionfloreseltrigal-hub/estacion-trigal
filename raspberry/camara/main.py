"""
Servidor de video para la cámara USB de la estación (versión optimizada).

Endpoints:
  /                -> página de prueba con los dos videos
  /video_feed      -> video en calidad completa (para calibrar el lente, uso local)
                      parámetro opcional: ?fps=15
  /video_lite      -> video liviano, menor resolución y fps (para ver remoto / 4G)
                      parámetros opcionales: ?fps=5&q=60
  /snapshot.jpg    -> una sola foto (la última captura)
  /status          -> dice si la cámara está encendida y cuántos cuadros lleva
  POST /foto       -> toma la foto con luz blanca y la foto con luz UV (MEF de fotos)
  /foto/estado     -> estado de la MEF de fotos y última foto tomada
  /foto/ultima/blanca.jpg y /foto/ultima/uv.jpg -> últimas fotos guardadas

Las fotos se toman solas a las horas de HORAS_FOTO (por defecto 04:00,12:00,20:00)
y se guardan con fecha, hora y tipo de luz impresos, una carpeta por mes:
  ~/fotos/automaticas/2026-11 noviembre/2026-11-10_20h00_blanca.jpg   (horas programadas)
  ~/fotos/manuales/2026-11 noviembre/2026-11-10_15h32_blanca.jpg      (botón de Grafana)
Los LEDs se piden a la ESP32 por MQTT (trigal/<estacion>/cmd), igual que desde Node-RED.

La cámara se enciende sola cuando alguien pide video o foto, y se apaga sola
cuando nadie la ha usado durante CAM_IDLE segundos (por defecto 10).

Optimización principal: la cámara ya entrega JPEG (MJPG). En vez de descomprimir
y volver a comprimir cada cuadro, se reenvía el JPEG original tal cual.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

DEVICE = os.getenv("CAM_DEVICE", "/dev/video0")
WIDTH = int(os.getenv("CAM_WIDTH", "1280"))
HEIGHT = int(os.getenv("CAM_HEIGHT", "720"))
IDLE = float(os.getenv("CAM_IDLE", "10"))  # segundos sin uso antes de apagar

app = FastAPI()

# ---------------------------------------------------------------- captura ---
cond = threading.Condition()
current_jpeg: bytes | None = None
frame_id = 0
last_demand = 0.0  # última vez que alguien pidió un cuadro
camera_on = False


def open_camera():
    cam = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # siempre el cuadro más reciente
    cam.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # entregar el JPEG crudo, sin decodificar
    return cam


def capture_loop():
    global current_jpeg, frame_id, camera_on
    camera = None
    fails = 0
    while True:
        # ¿Alguien está usando la cámara?
        if time.monotonic() - last_demand > IDLE:
            if camera is not None:
                camera.release()  # apagar: liberar el dispositivo
                camera = None
                camera_on = False
                print("Cámara apagada (sin uso)", flush=True)
            time.sleep(0.2)
            continue

        if camera is None:
            camera = open_camera()
            camera_on = camera.isOpened()
            fails = 0
            print("Cámara encendida" if camera_on else "No se pudo abrir la cámara", flush=True)

        ok, buf = camera.read()
        if not ok or buf is None or buf.size == 0:
            fails += 1
            if fails >= 50:  # ~5 s sin imagen: reabrir la cámara
                camera.release()
                camera = None
                camera_on = False
                time.sleep(1)
            time.sleep(0.1)
            continue
        fails = 0

        if buf.ndim == 3:
            # La cámara/driver entregó la imagen ya decodificada: comprimir aquí.
            ok, enc = cv2.imencode(".jpg", buf, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue
            data = enc.tobytes()
        else:
            data = buf.tobytes()
            if not data.startswith(b"\xff\xd8"):  # no es un JPEG válido
                continue

        with cond:
            current_jpeg = data
            frame_id += 1
            cond.notify_all()


threading.Thread(target=capture_loop, daemon=True).start()


def mantener_camara():
    """Avisa que se necesita la cámara (la enciende si estaba apagada)."""
    global last_demand
    last_demand = time.monotonic()


def wait_new_frame(last_id: int):
    """Marca que hay alguien mirando y espera un cuadro nuevo."""
    global last_demand
    last_demand = time.monotonic()
    with cond:
        cond.wait_for(lambda: frame_id != last_id and current_jpeg is not None, timeout=5)
        return frame_id, current_jpeg


def mjpeg_part(jpeg: bytes) -> bytes:
    return (
        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
        + str(len(jpeg)).encode()
        + b"\r\n\r\n"
        + jpeg
        + b"\r\n"
    )


# ---------------------------------------------------------------- streams ---
def stream_full(fps: float):
    interval = 1.0 / fps
    last_id, last_sent = -1, 0.0
    while True:
        last_id, jpeg = wait_new_frame(last_id)
        if jpeg is None:
            continue
        now = time.monotonic()
        if now - last_sent < interval:
            time.sleep(interval - (now - last_sent))
        last_sent = time.monotonic()
        yield mjpeg_part(jpeg)


def stream_lite(fps: float, quality: int):
    interval = 1.0 / fps
    last_id = -1
    while True:
        t0 = time.monotonic()
        last_id, jpeg = wait_new_frame(last_id)
        if jpeg is None:
            continue
        # Decodifica directamente a la mitad de tamaño (rápido) y recomprime liviano.
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_REDUCED_COLOR_2)
        if img is None:
            continue
        ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            yield mjpeg_part(enc.tobytes())
        elapsed = time.monotonic() - t0
        if elapsed < interval:
            time.sleep(interval - elapsed)


HEADERS = {"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"}
MEDIA = "multipart/x-mixed-replace; boundary=frame"


@app.get("/video_feed")
def video_feed(fps: float = Query(15, ge=1, le=30)):
    return StreamingResponse(stream_full(fps), media_type=MEDIA, headers=HEADERS)


@app.get("/video_lite")
def video_lite(fps: float = Query(5, ge=1, le=15), q: int = Query(60, ge=20, le=95)):
    return StreamingResponse(stream_lite(fps, q), media_type=MEDIA, headers=HEADERS)


@app.get("/snapshot.jpg")
def snapshot():
    # Enciende la cámara si hace falta y espera una foto fresca (máx. ~5 s).
    with cond:
        start_id = frame_id
    _, jpeg = wait_new_frame(start_id)
    if jpeg is None:
        return Response(status_code=503)
    return Response(content=jpeg, media_type="image/jpeg", headers=HEADERS)


@app.get("/status")
def status():
    return {
        "camara": "encendida" if camera_on else "apagada",
        "cuadros_capturados": frame_id,
        "segundos_sin_uso": round(time.monotonic() - last_demand, 1),
        "apaga_tras_segundos": IDLE,
    }


@app.get("/")
def index():
    return HTMLResponse(
        """
    <html><body style="font-family:sans-serif">
      <h2>Calidad completa (calibrar)</h2>
      <img src="/video_feed" style="max-width:100%">
      <h2>Liviano (remoto)</h2>
      <img src="/video_lite" style="max-width:100%">
      <h2>Últimas fotos</h2>
      <img src="/foto/ultima/blanca.jpg" style="max-width:49%">
      <img src="/foto/ultima/uv.jpg" style="max-width:49%">
    </body></html>
    """
    )


# =================================================================== FOTOS ===
def leer_env(ruta):
    """Lee el archivo trigal.env (CLAVE=valor) que ya usa el puente serial."""
    datos = {}
    try:
        with open(ruta) as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    clave, valor = linea.split("=", 1)
                    datos[clave.strip()] = valor.strip()
    except OSError:
        pass
    return datos


ENV = leer_env(os.getenv("TRIGAL_ENV", "/opt/trigal/app/trigal.env"))


def conf(clave, defecto=""):
    return os.getenv(clave, ENV.get(clave, defecto))


MQTT_HOST = conf("MQTT_HOST", "localhost")
MQTT_PORT = int(conf("MQTT_PORT", "1883"))
MQTT_USER = conf("CAM_MQTT_USER", conf("MQTT_USER"))
MQTT_PASS = conf("CAM_MQTT_PASS", conf("MQTT_PASS"))
ESTACION = conf("ESTACION", "estacion1")
TOPIC_CMD = f"trigal/{ESTACION}/cmd"     # órdenes a la ESP32 (las reenvía el puente serial)
TOPIC_ESP = f"trigal/{ESTACION}/esp"     # respuestas de la ESP32 ("luz lista")
TOPIC_CAM = f"trigal/{ESTACION}/camara"  # avisos de la cámara (foto tomada / error)

FOTOS_DIR = Path(conf("FOTOS_DIR", str(Path.home() / "fotos")))
HORAS_FOTO = [h.strip() for h in conf("HORAS_FOTO", "04:00,12:00,20:00").split(",") if h.strip()]
T_PREPARAR = 2.0                             # s con la cámara encendida antes de prender la luz
T_ESPERA_LUZ = 4.0                           # s máximo esperando "luz lista" de la ESP32
T_EXPO = float(conf("FOTO_T_EXPO", "2.0"))   # s para que la cámara ajuste la exposición a la luz

# Luces de la secuencia: (orden para la ESP32, nombre del archivo, texto de la etiqueta)
LUCES = [("blanco", "blanca", "Luz blanca"), ("uv", "uv", "Luz UV")]

# ---------------------------------------------------------------- MQTT ---
luz_lista = threading.Event()
mqtt_ok = False


def _al_conectar(cliente, userdata, flags, rc, props=None):
    global mqtt_ok
    mqtt_ok = not rc.is_failure
    if mqtt_ok:
        cliente.subscribe(TOPIC_ESP, qos=1)
        print("Cámara conectada a Mosquitto", flush=True)
    else:
        print(f"Mosquitto rechazó la conexión de la cámara: {rc}", flush=True)


def _al_desconectar(cliente, userdata, flags, rc, props=None):
    global mqtt_ok
    mqtt_ok = False


def _al_recibir(cliente, userdata, msg):
    if "luz lista" in msg.payload.decode(errors="ignore"):
        luz_lista.set()


cliente_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"camara-{ESTACION}")
if MQTT_USER:
    cliente_mqtt.username_pw_set(MQTT_USER, MQTT_PASS)
cliente_mqtt.on_connect = _al_conectar
cliente_mqtt.on_disconnect = _al_desconectar
cliente_mqtt.on_message = _al_recibir
cliente_mqtt.reconnect_delay_set(1, 30)
cliente_mqtt.connect_async(MQTT_HOST, MQTT_PORT)
cliente_mqtt.loop_start()


def orden_esp(cmd):
    cliente_mqtt.publish(TOPIC_CMD, json.dumps({"cmd": cmd}), qos=1)


def aviso(datos):
    cliente_mqtt.publish(TOPIC_CAM, json.dumps(datos, ensure_ascii=False), qos=1)


# ------------------------------------------------------ guardar fotos ---
def reloj_sincronizado():
    """True si la hora de la Pi está confirmada por internet (NTP)."""
    try:
        r = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() == "yes"
    except Exception:
        return False


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def buscar_ultima(sufijo):
    # El nombre empieza por la fecha, así que ordenar por nombre = ordenar por fecha
    fotos = sorted(FOTOS_DIR.rglob(f"*_{sufijo}*.jpg"), key=lambda r: r.name)
    return fotos[-1] if fotos else None


ultimas = {luz[1]: buscar_ultima(luz[1]) for luz in LUCES}


# Subcarpeta según quién pidió la foto
CARPETA_ORIGEN = {"programada": "automaticas", "manual": "manuales"}


def guardar_foto(jpeg, sufijo, texto_luz, hora_ok, origen):
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("la imagen de la cámara llegó dañada")
    ahora = datetime.now()

    # Etiqueta abajo a la izquierda: estación, fecha y hora, tipo de luz
    texto = f"Estacion Trigal | {ahora:%Y-%m-%d %H:%M:%S} | {texto_luz}"
    if not hora_ok:
        texto += " | hora sin verificar"
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    escala = img.shape[1] / 1280 * 0.8
    grosor = max(1, round(escala * 2))
    (ancho, alto), base = cv2.getTextSize(texto, fuente, escala, grosor)
    h = img.shape[0]
    cv2.rectangle(img, (0, h - alto - base - 16), (ancho + 20, h), (0, 0, 0), -1)
    cv2.putText(img, texto, (10, h - base - 8), fuente, escala, (255, 255, 255), grosor, cv2.LINE_AA)

    # automaticas/ o manuales/, y dentro una carpeta por mes: "2026-11 noviembre"
    carpeta = FOTOS_DIR / CARPETA_ORIGEN.get(origen, "manuales") / f"{ahora:%Y-%m} {MESES[ahora.month - 1]}"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{ahora:%Y-%m-%d_%Hh%M}_{sufijo}.jpg"
    n = 2
    while ruta.exists():  # dos fotos en el mismo minuto: 2026-11-10_20h00_blanca_2.jpg
        ruta = carpeta / f"{ahora:%Y-%m-%d_%Hh%M}_{sufijo}_{n}.jpg"
        n += 1
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise RuntimeError("no se pudo comprimir la foto")
    tmp = ruta.with_name(ruta.name + ".tmp")  # se escribe aparte y luego se renombra
    tmp.write_bytes(enc.tobytes())
    os.replace(tmp, ruta)
    ultimas[sufijo] = ruta
    return ruta


# ----------------------------------------------------------- MEF fotos ---
# Estados
FOTO_REPOSO = "REPOSO"
FOTO_PREPARAR = "PREPARAR_CAMARA"
FOTO_PEDIR_LUZ = "PEDIR_LUZ"
FOTO_ESPERAR_LUZ = "ESPERAR_LUZ"
FOTO_EXPONER = "AJUSTAR_EXPOSICION"
FOTO_CAPTURAR = "CAPTURAR"
FOTO_APAGAR = "APAGAR_LUZ"
FOTO_ERROR = "ERROR"

estado_fotos = {"estado": FOTO_REPOSO, "origen": None, "inicio": None,
                "ultimo_resultado": None, "ultimo_error": None}
candado_fotos = threading.Lock()


def MEF_fotos(origen):
    estado = FOTO_PREPARAR
    tini = time.monotonic()
    indice = 0          # qué luz de LUCES va
    guardadas = []
    error = None
    hora_ok = reloj_sincronizado()
    estado_fotos.update(origen=origen, inicio=datetime.now().isoformat(timespec="seconds"))
    print(f"Fotos ({origen}): inicio", flush=True)

    while estado != FOTO_REPOSO:
        trel = time.monotonic() - tini
        estado_fotos["estado"] = estado

        if estado == FOTO_PREPARAR:
            # 1. Salidas: encender la cámara
            mantener_camara()
            # 3. Transiciones
            if not mqtt_ok:
                error, estado = "sin conexión con Mosquitto: no se pueden prender los LEDs", FOTO_ERROR
            elif camera_on and trel >= T_PREPARAR:
                estado, tini = FOTO_PEDIR_LUZ, time.monotonic()
            elif trel >= 10:
                error, estado = "la cámara no responde", FOTO_ERROR

        elif estado == FOTO_PEDIR_LUZ:
            # 1. Salidas: pedir la luz a la ESP32
            luz_lista.clear()
            orden_esp(LUCES[indice][0])
            # 3. Transición
            estado, tini = FOTO_ESPERAR_LUZ, time.monotonic()

        elif estado == FOTO_ESPERAR_LUZ:
            mantener_camara()
            if luz_lista.is_set():
                estado, tini = FOTO_EXPONER, time.monotonic()
            elif trel >= T_ESPERA_LUZ:
                error, estado = f"la ESP32 no confirmó la luz {LUCES[indice][0]}", FOTO_ERROR

        elif estado == FOTO_EXPONER:
            # 2. La cámara ajusta sola la exposición a la nueva luz
            mantener_camara()
            if trel >= T_EXPO:
                estado = FOTO_CAPTURAR

        elif estado == FOTO_CAPTURAR:
            # 1. Tomar un cuadro nuevo (posterior a prender la luz) y guardarlo
            with cond:
                id_antes = frame_id
            id_nuevo, jpeg = wait_new_frame(id_antes)
            try:
                if id_nuevo == id_antes or jpeg is None:
                    raise RuntimeError("la cámara no entregó una imagen nueva")
                _, sufijo, texto_luz = LUCES[indice]
                ruta = guardar_foto(jpeg, sufijo, texto_luz, hora_ok, origen)
                guardadas.append(str(ruta))
                aviso({"evento": "foto", "luz": sufijo, "archivo": str(ruta),
                       "origen": origen, "hora_verificada": hora_ok})
                print(f"Fotos ({origen}): guardada {ruta}", flush=True)
                # 3. Transición: siguiente luz o terminar
                indice += 1
                estado = FOTO_PEDIR_LUZ if indice < len(LUCES) else FOTO_APAGAR
            except Exception as e:
                error, estado = str(e), FOTO_ERROR

        elif estado == FOTO_APAGAR:
            orden_esp("apagar")
            estado_fotos.update(ultimo_resultado={"ok": True, "fotos": guardadas,
                                                  "hora": datetime.now().isoformat(timespec="seconds")})
            estado = FOTO_REPOSO

        elif estado == FOTO_ERROR:
            if mqtt_ok:
                orden_esp("apagar")  # nunca dejar un LED prendido
            estado_fotos.update(ultimo_error={"msg": error, "hora": datetime.now().isoformat(timespec="seconds")},
                                ultimo_resultado={"ok": False, "fotos": guardadas, "error": error})
            aviso({"evento": "error", "msg": error, "origen": origen})
            print(f"Fotos ({origen}): ERROR {error}", flush=True)
            estado = FOTO_REPOSO

        time.sleep(0.05)

    estado_fotos["estado"] = FOTO_REPOSO


def iniciar_fotos(origen):
    """Arranca la MEF en segundo plano. False si ya hay una secuencia en curso."""
    if not candado_fotos.acquire(blocking=False):
        return False

    def correr():
        try:
            MEF_fotos(origen)
        finally:
            candado_fotos.release()

    threading.Thread(target=correr, daemon=True).start()
    return True


def programador():
    """Toma las fotos a las horas de HORAS_FOTO (una vez por día y hora)."""
    hechas = set()
    while True:
        ahora = datetime.now()
        hhmm = f"{ahora:%H:%M}"
        clave = f"{ahora:%Y-%m-%d} {hhmm}"
        if hhmm in HORAS_FOTO and clave not in hechas:
            hechas = {c for c in hechas if c.startswith(f"{ahora:%Y-%m-%d}")}
            hechas.add(clave)
            if not iniciar_fotos("programada"):
                print("Fotos programadas: ya había una secuencia en curso", flush=True)
        time.sleep(10)


threading.Thread(target=programador, daemon=True).start()

# Grafana está en otro puerto (3000): se permite que sus botones llamen a este servidor
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.post("/foto")
def tomar_foto():
    if not iniciar_fotos("manual"):
        return JSONResponse({"ok": False, "msg": "Ya se están tomando fotos, espera unos segundos"}, status_code=409)
    return {"ok": True, "msg": "Tomando fotos (blanca y UV)..."}


@app.get("/foto/estado")
def foto_estado():
    return {
        **estado_fotos,
        "mqtt": "conectado" if mqtt_ok else "desconectado",
        "horas_programadas": HORAS_FOTO,
        "reloj_sincronizado": reloj_sincronizado(),
        "ultimas": {k: (str(v) if v else None) for k, v in ultimas.items()},
    }


@app.get("/foto/ultima/{tipo}.jpg")
def foto_ultima(tipo: str):
    ruta = ultimas.get(tipo)
    if not ruta or not Path(ruta).exists():
        return Response(status_code=404)
    return FileResponse(ruta, media_type="image/jpeg", headers=HEADERS)


import os as _os

def _leer_clave():
    v = _os.getenv("CAM_CLAVE", "")
    if v:
        return v
    try:
        for l in open("/opt/trigal/app/trigal.env"):
            if l.strip().startswith("CAM_CLAVE="):
                return l.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


CAM_CLAVE = _leer_clave()
print("Protección remota:", "ACTIVA" if CAM_CLAVE else "SIN CLAVE (todo abierto)", flush=True)


class ClaveRemota:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and CAM_CLAVE:
            if any(k == b"cf-connecting-ip" for k, _ in scope["headers"]):
                pref = "/" + CAM_CLAVE
                p = scope["path"]
                if p == pref or p.startswith(pref + "/"):
                    nuevo = p[len(pref):] or "/"
                    scope = dict(scope, path=nuevo, raw_path=nuevo.encode())
                else:
                    await send({"type": "http.response.start", "status": 403,
                                "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                    await send({"type": "http.response.body", "body": "No autorizado".encode()})
                    return
        await self.app(scope, receive, send)


app.add_middleware(ClaveRemota)
