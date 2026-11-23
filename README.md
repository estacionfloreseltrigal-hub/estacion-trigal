# Estación portátil de monitoreo – Flores El Trigal

Estación climática portátil para invernadero de snapdragon (*Antirrhinum majus*), desarrollada en el curso
Plataformas de Agricultura Inteligente. Una ESP32-S3 lee los sensores y los envía por USB a una Raspberry Pi 4,
que guarda los datos, toma fotos y publica el tablero en **https://iot.trigal-digital.com** por 4G.

```
Sensores → ESP32-S3 ──USB── Raspberry Pi 4 ── Mosquitto → Node-RED → InfluxDB → Grafana
           (trama $EST)        │  cámara USB (fastapi-cam, fotos 4:00 / 12:00 / 20:00 → Google Drive)
                               └─ 4G SIM7600 ── túnel Cloudflare ── iot.trigal-digital.com
```

## Contenido

| Carpeta | Qué hay | Dónde va en la Pi |
| --- | --- | --- |
| `docs/` | Manual técnico completo y guías (4G, operación, índices, descargas) | — |
| `firmware/` | Código de la ESP32-S3 (`PAYLOAD/PAYLOAD.ino`) | Se carga con Arduino IDE |
| `raspberry/app/` | Puente ESP32 → MQTT (`serial_mqtt.py`) y ejemplos de `trigal.env` e `influx-sistema.env` | `/opt/trigal/app/` |
| `raspberry/camara/` | Servidor de cámara y fotos (FastAPI) | `/home/trigal/fastapi-cam/` |
| `raspberry/bin/` | `revisar-estacion`, `prueba-final`, `esperar-hora`, `lte-watchdog.sh`, `fotos-nube.sh`, `metricas-sistema` | `/usr/local/bin/` |
| `raspberry/systemd/` | Servicios y temporizadores | `/etc/systemd/system/` |
| `raspberry/udev/` | Regla que crea `/dev/esp32` | `/etc/udev/rules.d/` |
| `raspberry/sistema/` | Registros persistentes (journald) | `/etc/systemd/journald.conf.d/` |
| `docker/` | YML de cada contenedor y `mosquitto.conf` | `/opt/trigal/stacks/`, `/opt/trigal/mosquitto/config/` |
| `node-red/` | `flows.json` (estación, ciclos, descargas), `settings.js` y `package.json` | `/opt/trigal/nodered/data/` |
| `influxdb/` | Tarea `indices_diarios` (Tmáx, Tmín, DLI, fotoperiodo) | InfluxDB → Tasks |
| `grafana/dashboards/` | Tableros *Estación Trigal* y *Estación Trigal - Administración* | Grafana → Import |

Qué archivo viene de dónde y cómo se comparó con la Pi: [`RESCATE.md`](RESCATE.md). Contenedores que corren: `docker/contenedores.txt`.

La instalación desde cero, los accesos, el uso del tablero y la solución de problemas están en
[`docs/manual-tecnico.md`](docs/manual-tecnico.md) (sección 14: respaldo y reinstalación).

## Lo que NO está en el repositorio (a propósito)

Claves, tokens y hashes nunca se suben. En los archivos aparecen como marcadores (`<CAM_CLAVE>`, `<MQTT_PASS>`,
`<HASH_BCRYPT>`…) y hay que ponerlos al instalar:

- `/opt/trigal/app/trigal.env` e `influx-sistema.env` (claves de MQTT, cámara y token de InfluxDB)
- `/opt/trigal/mosquitto/config/passwd` (usuarios de Mosquitto)
- `flows_cred.json` de Node-RED (credenciales de los nodos); `settings.js` sí se sube, pero con los hashes reemplazados
- `~/.config/rclone/rclone.conf` (autorización de Google Drive)
- Token del túnel de Cloudflare y claves de Grafana/InfluxDB (variables de Portainer)

Las claves de El Trigal se guardan en su gestor de contraseñas, no aquí.

## Actualizar el repositorio con lo que tiene la Pi

El script `recolectar-desde-la-pi.sh` copia las versiones actuales de la Pi a esta carpeta y quita las claves:

```bash
scp -r estacion-trigal trigal@10.10.80.48:~/      # desde el PC
ssh trigal@10.10.80.48
cd ~/estacion-trigal && bash recolectar-desde-la-pi.sh
```
Al final revisa que no queden claves y deja `~/estacion-trigal.tar.gz` listo para traer al PC:
`scp trigal@10.10.80.48:~/estacion-trigal.tar.gz .`

## Equipo

Proyecto del curso Plataformas de Agricultura Inteligente (2026-2), entregado a Flores El Trigal en noviembre de 2026.
