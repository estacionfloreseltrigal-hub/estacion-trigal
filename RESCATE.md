# De dónde salió cada archivo

Rescate del 22-nov-2026 a partir de las conversaciones del proyecto y de los archivos del Project de Claude.
Cuando se pudo, el archivo se reconstruyó **repitiendo en orden los mismos cambios** que se hicieron en las
conversaciones (versión original + cada parche), y se comprobó que compila o que la sintaxis es correcta.

**La versión que manda es la de la Pi.** El 23-nov-2026 se corrió `recolectar-desde-la-pi.sh` en `rpi4trigal` y se
comparó archivo por archivo (ver al final).

## Rescatados

| Archivo | Fuente | Confianza |
| --- | --- | --- |
| `firmware/PAYLOAD/PAYLOAD.ino` | Chat "Subdominio y túnel Cloudflare": versión con intervalos + ventilador 25/22 °C + `Wire.setTimeOut` + arreglo del SCD30 | Alta, pero comparar con el cargado en la ESP32 |
| `raspberry/app/serial_mqtt.py` | Chat "Comunicación USB serial": original + 5 parches; luego `SIN_DATOS_S = 180` y el vigilante de suelo (chat del túnel) | Alta. Probado: lee la trama `$EST` igual que en los registros de la Pi |
| `raspberry/udev/99-esp32.rules` | Chat "Comunicación USB serial" (línea final del CP210x) | Alta |
| `raspberry/systemd/trigal-serial.service` | Chat "Comunicación USB serial" | Alta |
| `raspberry/systemd/trigal-serial.service.d/esperar-hora.conf` | Pi (23-nov). La reconstrucción coincidía | Copia de la Pi |
| `raspberry/bin/esperar-hora` | Project | Alta |
| `raspberry/camara/main.py` | Chat "Optimizar transmisión de cámara": versión optimizada + 4 parches; luego la protección `CAM_CLAVE` (chat "Raspi, cámara y red 4G") | Alta. Probado con cámara simulada |
| `raspberry/camara/requirements.txt`, `pyproject.toml`, `uv.lock` | Pi (23-nov), versiones fijas | Copia de la Pi |
| `raspberry/systemd/camara.service`, `fotos-nube.service`, `fotos-nube.timer`, `raspberry/bin/fotos-nube.sh` | Chat de la cámara | Alta |
| `raspberry/bin/metricas-sistema` + `.service` + `.timer` | Chat del túnel | Alta |
| `raspberry/bin/prueba-final` | Chat del túnel (revisión de la noche del 20-nov) | Alta |
| `raspberry/bin/revisar-estacion` + `.service` + `.timer` | Project | Alta |
| `raspberry/bin/lte-watchdog.sh` + `.service` + `.timer` | Project (vigilante 4G v2) | Alta |
| `raspberry/sistema/journald.conf.d/50-persistente.conf` | Documentado en `docs/modulo-4g.md` | Alta |
| `docker/stacks/*.yml`, `docker/mosquitto/mosquitto.conf` | Manual técnico, sección 14 | Alta (las claves van como variables de Portainer) |
| `node-red/flows.json`, `settings.js`, `package.json` | Pi (23-nov): las 3 pestañas (Estación Trigal, Ciclos del cultivo, Consulta y descarga) | Copia de la Pi, sin hashes |
| `grafana/dashboards/*.json` | Pi (23-nov), por la API de Grafana | Copia de la Pi, con `<CAM_CLAVE>` |
| `raspberry/app/prueba_serial.py` | Pi (23-nov): prueba inicial del puerto serial (de cuando la ESP32 mandaba JSON) | Copia de la Pi |
| `docker/contenedores.txt` | Pi (23-nov): `docker ps -a` | Copia de la Pi |
| `influxdb/indices_diarios.flux` | Project, con `DT_MAX = 150` (recomendado al pasar la ESP32 a 60 s) | Alta |
| `docs/manual-tecnico.md` | Documento "Manual técnico" exportado | Alta |

## Comparación con la Pi (23-nov-2026)

**Idénticos a lo rescatado:** `serial_mqtt.py`, `main.py` de la cámara, `esperar-hora`, `fotos-nube.sh`,
`metricas-sistema`, `prueba-final`, `mosquitto.conf`, la regla udev, journald y los servicios
`trigal-serial`, `camara`, `fotos-nube` y `metricas-sistema`.

**Solo cambian comentarios** (se dejó la versión del repo, más documentada): `lte-watchdog.sh` y sus
`.service`/`.timer`, `trigal.env.ejemplo`, e `influxdb/indices_diarios.flux` (InfluxDB guarda la tarea sin
comentarios; la lógica es la misma, se comprobó quitando comentarios y espacios).

**No se trajeron de la Pi:** `docker/stacks/*.yml` (en `/opt/trigal/stacks` solo había un `nodered.yml` vacío:
los stacks viven dentro de Portainer, así que quedan los del manual), copias de respaldo
(`*.antes-parche`, `*.antes-clave`, `lte-watchdog.sh.v1`) y duplicados viejos en `/opt/trigal/app`.

`revisar-estacion` (+ `.service`/`.timer`) no apareció en `/usr/local/bin` ni en `/etc/systemd/system`:
puede que nunca se haya instalado. Revisar con `systemctl list-timers | grep revisar`.

## Lo que no va al repositorio

Configuración de rclone, `passwd` de Mosquitto, `trigal.env`, `influx-sistema.env` y `flows_cred.json`:
son claves. Están en el gestor de contraseñas de El Trigal.
