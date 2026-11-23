# De dónde salió cada archivo

Rescate del 22-nov-2026 a partir de las conversaciones del proyecto y de los archivos del Project de Claude.
Cuando se pudo, el archivo se reconstruyó **repitiendo en orden los mismos cambios** que se hicieron en las
conversaciones (versión original + cada parche), y se comprobó que compila o que la sintaxis es correcta.

**La versión que manda es la de la Pi.** Si se corre `recolectar-desde-la-pi.sh`, sus copias reemplazan a estas.

## Rescatados

| Archivo | Fuente | Confianza |
| --- | --- | --- |
| `firmware/PAYLOAD/PAYLOAD.ino` | Chat "Subdominio y túnel Cloudflare": versión con intervalos + ventilador 25/22 °C + `Wire.setTimeOut` + arreglo del SCD30 | Alta, pero comparar con el cargado en la ESP32 |
| `raspberry/app/serial_mqtt.py` | Chat "Comunicación USB serial": original + 5 parches; luego `SIN_DATOS_S = 180` y el vigilante de suelo (chat del túnel) | Alta. Probado: lee la trama `$EST` igual que en los registros de la Pi |
| `raspberry/udev/99-esp32.rules` | Chat "Comunicación USB serial" (línea final del CP210x) | Alta |
| `raspberry/systemd/trigal-serial.service` | Chat "Comunicación USB serial" | Alta |
| `raspberry/systemd/trigal-serial.service.d/esperar-hora.conf` | **Reconstruido**: el original solo estaba en un .zip | Media: comparar con `systemctl cat trigal-serial` |
| `raspberry/bin/esperar-hora` | Project | Alta |
| `raspberry/camara/main.py` | Chat "Optimizar transmisión de cámara": versión optimizada + 4 parches; luego la protección `CAM_CLAVE` (chat "Raspi, cámara y red 4G") | Alta. Probado con cámara simulada |
| `raspberry/camara/requirements.txt` | Reconstruido a partir de los `import` | Media |
| `raspberry/systemd/camara.service`, `fotos-nube.service`, `fotos-nube.timer`, `raspberry/bin/fotos-nube.sh` | Chat de la cámara | Alta |
| `raspberry/bin/metricas-sistema` + `.service` + `.timer` | Chat del túnel | Alta |
| `raspberry/bin/prueba-final` | Chat del túnel (revisión de la noche del 20-nov) | Alta |
| `raspberry/bin/revisar-estacion` + `.service` + `.timer` | Project | Alta |
| `raspberry/bin/lte-watchdog.sh` + `.service` + `.timer` | Project (vigilante 4G v2) | Alta |
| `raspberry/sistema/journald.conf.d/50-persistente.conf` | Documentado en `docs/modulo-4g.md` | Alta |
| `docker/stacks/*.yml`, `docker/mosquitto/mosquitto.conf` | Manual técnico, sección 14 | Alta (las claves van como variables de Portainer) |
| `node-red/flujo_estacion_trigal.json` | Project (12-nov) | Alta para esa pestaña |
| `influxdb/indices_diarios.flux` | Project, con `DT_MAX = 150` (recomendado al pasar la ESP32 a 60 s) | Alta |
| `docs/manual-tecnico.md` | Documento "Manual técnico" exportado | Alta |

## Faltan (solo están en la Pi)

| Qué | Por qué no se rescató | Cómo obtenerlo |
| --- | --- | --- |
| Flujos de Node-RED de ciclos, descargas y formularios | Se generaron con scripts y se cambiaron varias veces; la reconstrucción saldría vieja | `recolectar-desde-la-pi.sh` o Node-RED → ☰ → Exportar → Todos los flujos |
| Tableros de Grafana (`trigal-estacion`, `trigal-administracion`) | Igual, y además se editaron a mano en Grafana | `recolectar-desde-la-pi.sh` o *Share → Export → Save to file* |
| `settings.js` de Node-RED | Tiene los hashes de las claves | `recolectar-desde-la-pi.sh` (lo copia sin hashes) |
| Configuración de rclone, `passwd` de Mosquitto, `trigal.env` | Son claves: no van al repositorio | Gestor de contraseñas de El Trigal |
