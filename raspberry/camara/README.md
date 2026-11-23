# Cámara y fotos

`main.py` es el servidor de la cámara USB (FastAPI, puerto 3333). Parte del repositorio `fastapi-cam` del docente,
con estos cambios: la cámara se apaga sola tras `CAM_IDLE` s sin uso, toma fotos con luz blanca y con UV, y exige
`CAM_CLAVE` cuando se entra desde internet.

| Ruta | Qué hace |
| --- | --- |
| `/` | Página con el video en vivo |
| `/video_feed`, `/video_lite` | Video MJPEG (normal y liviano, para 4G) |
| `/snapshot.jpg`, `/status` | Una foto suelta y el estado de la cámara |
| `POST /foto` | Toma la foto blanca y la UV (pide las luces a la ESP32 por MQTT) |
| `/foto/estado`, `/foto/ultima/{blanca,uv}.jpg` | Estado y últimas fotos (las usa Grafana) |

Las fotos se toman solas a las horas de `HORAS_FOTO` (por defecto 04:00, 12:00 y 20:00) y quedan en
`~/fotos/<automaticas|manuales>/<mes>/`. `fotos-nube.sh` las sube cada hora a Google Drive.

Desde internet (`cam.trigal-digital.com`), toda ruta debe empezar por `/<CAM_CLAVE>/`; en la red local no se pide.

## Instalación en la Pi

```bash
mkdir -p ~/fastapi-cam && cp main.py requirements.txt ~/fastapi-cam/ && cd ~/fastapi-cam
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo apt install -y libgl1        # si OpenCV pide libGL
```

Lee la configuración de `/opt/trigal/app/trigal.env` (`MQTT_*`, `ESTACION`, `CAM_CLAVE`, `HORAS_FOTO`; ver
`raspberry/app/trigal.env.ejemplo`). El servicio es `raspberry/systemd/camara.service`.
