# CLAUDE.md — Estación portátil de monitoreo Flores El Trigal

Contexto para Claude (Claude Code o claude.ai) y para cualquier persona que trabaje en este repositorio.
La documentación completa para personas está en `docs/manual-tecnico.md`; este archivo resume lo que hay que saber
antes de tocar algo y las reglas que no se deben romper.

## Qué es el proyecto

Estación climática portátil para invernadero de **snapdragon** (*Antirrhinum majus*, no crisantemo) de Flores El Trigal
(Rionegro, Antioquia, unos 2100 m). Proyecto del curso Plataformas de Agricultura Inteligente, Universidad EAFIT, 2026-2.
Entregada a El Trigal el 22-nov-2026. Todo (cuentas, dominio, claves) queda a nombre de El Trigal; nada debe depender
del celular o el correo de un estudiante.

Equipo: Jayder Juagibioy, Sara Gallego, Sofia Vásquez, Paola Restrepo, Mariana Cardona, Juan Van De Venter.
Contacto técnico en El Trigal: Julián Eduardo Guevara Benavides (administra Hostinger y es administrador en Cloudflare).

```
Sensores → ESP32-S3 ──USB (trama $EST cada 60 s)── Raspberry Pi 4 (rpi4trigal)
                                                    │ trigal-serial → Mosquitto → Node-RED → InfluxDB → Grafana
                                                    │ cámara USB (servicio camara, fastapi, :3333) → fotos → Google Drive (rclone)
                                                    └ 4G SIM7600 (usb0) ── túnel Cloudflare ── iot.trigal-digital.com / cam.trigal-digital.com
```

## Datos clave

| Dato | Valor |
| --- | --- |
| Dashboard público | `https://iot.trigal-digital.com` (Grafana) |
| Kiosco (visitantes) | `/d/trigal-estacion?orgId=1&kiosk` |
| Administración | `/d/trigal-administracion` (carpeta *Administración*, sin rol Viewer) |
| Formularios (Node-RED) | `/ciclo` y `/descarga` (con `httpNodeAuth`) |
| Cámara remota | `https://cam.trigal-digital.com/<CAM_CLAVE>/...` |
| Pi | `rpi4trigal`, usuario Linux `trigal`, Raspberry Pi OS 64 bits (Debian Trixie), Pi 4 de 4 GB |
| IP local de pruebas (EAFIT) | `10.10.80.48` (cambia en otra red) |
| Carpeta principal en la Pi | `/opt/trigal/` |
| InfluxDB 2 | organización `trigal`, bucket `estacion` |
| Mediciones | `datos` (lecturas), `diario` (índices diarios), `sistema` (4G, microSD, CPU, alimentación), `ciclos`, `estado_estacion` |
| MQTT | `trigal/estacion1/datos` (todo en un solo tópico), `.../cmd` (órdenes a la ESP32), `.../esp` (respuestas de texto), `.../camara` (aviso de cada foto) |
| Usuarios MQTT | `estacion` (puente y cámara), `nodered` (Node-RED) |
| Usuarios Grafana | `admin_trigal` (admin), `trigal_visor` (Viewer, único usuario de consulta) |
| Cuenta del proyecto | `estacionfloreseltrigal@gmail.com` (Drive, Cloudflare, Raspberry Pi Connect) |
| Dominio | `trigal-digital.com` (Hostinger, DNS en Cloudflare, plan gratuito). Túnel `rpi4trigal`, equipo Zero Trust `trigal` |
| 4G | Claro prepago, APN `internet.comcel.com.co`, perfil NetworkManager `claro4g`, interfaz `usb0` |
| Claves | Nunca en el repositorio. Están en la bóveda de Bitwarden "Estación Trigal" |
| Manual de usuario | Google Docs del equipo: https://docs.google.com/document/d/1LW2suQzDA31a6bjRcOKA88jZHk_doYz_YGLuGDUzvEo/edit (su parte de la plataforma es general y remite al manual técnico y a este repositorio) |

## Mapa del repositorio

| Carpeta | Qué hay | Dónde va en la Pi |
| --- | --- | --- |
| `docs/manual-tecnico.md` | Manual técnico completo (17 secciones). **Fuente principal de verdad para personas** | — |
| `docs/` (resto) | Guías cortas: `modulo-4g.md`, `operacion.md`, `indices.md`, `descargas.md` | — |
| `firmware/PAYLOAD/PAYLOAD.ino` | Firmware de la ESP32-S3 (el mismo cargado, comparado el 22-nov-2026) | Arduino IDE, placa *ESP32S3 Dev Module* |
| `raspberry/app/` | `serial_mqtt.py` (puente), `prueba_serial.py`, ejemplos `trigal.env.ejemplo` e `influx-sistema.env.ejemplo` | `/opt/trigal/app/` |
| `raspberry/camara/` | `main.py` (FastAPI) y `requirements.txt` | `/home/trigal/fastapi-cam/` (venv en `.venv`) |
| `raspberry/bin/` | `revisar-estacion`, `prueba-final`, `esperar-hora`, `lte-watchdog.sh`, `fotos-nube.sh`, `metricas-sistema` | `/usr/local/bin/` |
| `raspberry/systemd/` | `.service` y `.timer` (y `trigal-serial.service.d/esperar-hora.conf`) | `/etc/systemd/system/` |
| `raspberry/udev/99-esp32.rules` | Crea `/dev/esp32` (chip CP210x) | `/etc/udev/rules.d/` |
| `raspberry/sistema/` | `journald.conf.d/50-persistente.conf` (registros persistentes, 200 MB) | `/etc/systemd/journald.conf.d/` |
| `docker/stacks/*.yml` | Un stack por contenedor (Portainer); `portainer.sh` | `/opt/trigal/stacks/` |
| `docker/mosquitto/mosquitto.conf` | Configuración del broker (sin `passwd`) | `/opt/trigal/mosquitto/config/` |
| `node-red/` | `flows.json` (pestañas *Estación Trigal*, *Ciclos del cultivo*, *Consulta y descarga*), `settings.js` (hashes como `<HASH_BCRYPT>`), `package.json` | `/opt/trigal/nodered/data/` |
| `influxdb/indices_diarios.flux` | Tarea diaria (Tmáx, Tmín, Tmedia, DLI, fotoperiodo) | InfluxDB → Tasks |
| `grafana/dashboards/` | `estacion-trigal.json` (principal, uid `trigal-estacion`) y `estacion-trigal-administracion.json` | Grafana → Import |
| `hardware/` | Fichas técnicas de todos los componentes (`fichas/`, con los registros Modbus del PAR) y proyecto de Proteus | — |
| `recolectar-desde-la-pi.sh` | Copia lo que corre en la Pi a este repositorio, quitando claves | Se ejecuta en la Pi |

## Regla principal: la versión que vale es la de la Pi

El repositorio se comparó archivo por archivo con la Pi el 23-nov-2026. Si se cambia algo en la Pi (flujos, tableros,
scripts, servicios), se actualiza el repositorio así:

```bash
bash ~/estacion-trigal/recolectar-desde-la-pi.sh          # en la Pi; pide sudo y, opcional, la clave de admin_trigal de Grafana
rclone copy ~/estacion-trigal.tar.gz drive:EstacionTrigal/repositorio
```

Luego se descomprime encima del repositorio, se revisa con `git diff` y se sube con un mensaje que diga qué cambió.
Además se anota una línea en el registro de cambios (sección 15 del manual).

Si se cambia algo en el repositorio, hay que llevarlo a la Pi (la tabla de arriba dice a dónde) y probar con
`revisar-estacion`, que debe terminar en "Todo lo esencial está funcionando".

## Seguridad: qué nunca se sube

El `.gitignore` bloquea `*.env` (salvo `*.env.ejemplo`), `passwd`, `flows_cred.json`, `rclone.conf`, llaves y fotos.
En los archivos las claves van como marcadores: `<CAM_CLAVE>`, `<MQTT_PASS>`, `<HASH_BCRYPT>`, `<TOKEN>`…

- No escribir claves, tokens, hashes bcrypt, el token del túnel de Cloudflare ni `CAM_CLAVE` en ningún archivo,
  commit ni mensaje.
- En los dashboards exportados, `data-cam` debe quedar `https://cam.trigal-digital.com/<CAM_CLAVE>`.
- Antes de subir, buscar claves:
  `grep -rnIE 'eyJ[A-Za-z0-9_-]{30,}|-----BEGIN|\$2[aby]\$[0-9]{2}\$' . --exclude-dir=.git`
- No agregar el presupuesto con precios ni archivos del curso con credenciales (ThingWorx, Ubidots).
- Nunca publicar en el túnel el editor de Node-RED (:1880 raíz), InfluxDB (:8086) ni Portainer (:9443).
  Toda ruta pública que cambie datos o encienda luces necesita usuario y clave.

## Invariantes: cosas que deben coincidir

Si se cambia un lado, cambiar el otro en el mismo trabajo.

| Si se cambia… | Hay que ajustar… |
| --- | --- |
| `T_ENVIO` (60 s) en el firmware | `SIN_DATOS_S` en `serial_mqtt.py` (≥ 3 × T_ENVIO, hoy 180) y `DT_MAX` en `indices_diarios.flux` (≈ 2,5 × T_ENVIO, hoy 150) |
| `T_SUELO` (15 min) en el firmware | `SIN_SUELO_S` en `serial_mqtt.py` (hoy 1800) |
| `BAUDIOS_RASPI` (115200) | `SERIAL_BAUD` en `trigal.env` |
| `BAUDIOS_485` (4800) o IDs Modbus (PAR 1; sondas 4, 2, 3) | Configuración de cada sensor RS485 (dirección y velocidad) |
| Un campo nuevo en la trama `$EST` | Nada en el puente: se guarda con su nombre corto. Para un nombre largo, agregarlo al diccionario `NOMBRES` de `serial_mqtt.py`. Luego, panel en Grafana |
| `ESTACION` en `trigal.env` (`estacion1`) | Los tópicos `trigal/estacion1/…` en `node-red/flows.json` |
| `CAM_CLAVE` | Atributo `data-cam` en los dos paneles HTML de la cámara en Grafana |
| Dominio de Grafana | `GF_SERVER_ROOT_URL` y `GF_SERVER_DOMAIN` del stack de Grafana y el dominio de la cámara en los paneles |
| Rutas del túnel | La de Node-RED (`^/(ciclo\|descarga)` → :1880) va **antes** que la de Grafana (:3000); `cam.` → :3333 |
| Pines de los LEDs | Blancos GPIO 6 (`PIN_LED_BLANCO`), UV GPIO 10 (`PIN_LED_UV`). Una versión vieja usaba 13 y 14 |
| Paquete de datos de la SIM | *Max* del panel "Datos 4G este mes" (hoy 5000 MB) |

Otras reglas del sistema:

- **Un solo programa usa cada recurso.** El puerto USB de la ESP32 lo abre solo `trigal-serial`; todo lo demás manda
  órdenes por MQTT (`trigal/estacion1/cmd`). La cámara la abre solo el servicio `camara`.
- **No hay RTC ni GPS.** El puente espera la hora por internet (`esperar-hora`) antes de publicar. El lote se registra
  a mano en `/ciclo`; mover la estación es un ciclo nuevo.
- **ModemManager debe estar desactivado**: si se activa, manda comandos AT a la ESP32 y al módulo 4G.
- **El WiFi nunca es la salida a internet** (`ipv4.never-default yes ipv6.never-default yes`): el WiFi de la
  universidad bloquea el puerto 7844 del túnel y el dashboard daría Error 1033.
- **Actualizaciones solo con WiFi o cable**, nunca por el 4G. Con el WiFi de la universidad usar
  `apt -o Acquire::ForceIPv4=true`.
- Las lecturas tomadas con los LEDs de la cámara encendidos no cuentan en el promedio de PAR y lux, para que el flash
  no altere el DLI ni el fotoperiodo.
- Los paneles HTML de la cámara necesitan `GF_PANELS_DISABLE_SANITIZE_HTML=true`; por eso solo `admin_trigal` y quien
  deba editar tienen un rol distinto de Viewer.

## Firmware (ESP32-S3)

- Placa D-ESP32-S3; en Arduino **ESP32S3 Dev Module**, *USB CDC On Boot: Disabled*. Se conecta a la Pi por el
  conector **UART/COM** (CP210x), no por el USB nativo.
- Librerías: SparkFun SCD30, Adafruit TSL2591 + Unified Sensor, modbus-esp8266 (`ModbusRTU`), DHT sensor library.
- Sensores: SCD30 (I²C `0x61`, 50 kHz), TSL2591 (`0x29`), PAR SEN0641 (RS485, ID 1, reg `0x0000`),
  3 sondas JXBS-3001 (RS485, IDs 4, 2, 3), DHT22 en GPIO 4 (temperatura de la **caja**, no del cultivo).
  I²C SDA 8 / SCL 9; RS485 RX 18 / TX 17; ventilador GPIO 5 (25 °C prende, 22 °C apaga).
- Tiempos: lectura 10 s, envío 60 s (PAR y lux promediados), suelo cada 15 min, primer envío a los 15 s.
- Órdenes: `{"cmd":"blanco"|"uv"|"apagar"|"ping"}`, con `"seg"` opcional para calibrar (máx. 300 s). Un LED se apaga
  solo a los 10 s (`T_MAX_LUZ`). Respuestas: `Estado: LUZ_…`, `#OK,luz lista`, `#OK,ping`, `#ERR,…`.
- Para cargar: `sudo systemctl stop trigal-serial` en la Pi, cargar desde un computador, volver a conectar y
  `sudo systemctl start trigal-serial`.

### Estilo del código Arduino (obligatorio)

- Mantener la estructura de los ejemplos del curso: **máquina de estados finitos (MEF) con `#define`** y, en cada
  estado, los bloques *1. Estado de las salidas físicas / 2. Cálculo de variables internas / 3. Preguntas de
  transición*.
- Respetar el código existente del equipo: cambios mínimos, sin reescribirlo.
- Sin líneas separadoras de relleno (`// ======`, `// ------`) ni comentarios decorativos que "se vean de IA".
- Comentarios cortos y en español.

## Índices agronómicos

| Índice | Dónde se calcula | Detalle |
| --- | --- | --- |
| DPV, punto y margen de rocío | Node-RED, función *Índices instantáneos* | Cada lectura; SVP de FAO-56 |
| Tmáx, Tmín, Tmedia, DLI, fotoperiodo | Tarea `indices_diarios` (CRON `10 5 * * *` = 00:10 Colombia) | Recalcula los últimos 3 días; `UMBRAL_LUZ` 2 µmol·m⁻²·s⁻¹ durante un minuto, `UMBRAL_LUX` 108, `DT_MAX` 150 s |
| GDD y GDD acumulado | Grafana, con la T-base del ciclo elegido | T-base por defecto 5 °C, editable por ciclo en `/ciclo`; Tmáx/Tmín de promedios de 5 min |

El aviso "¿sigue en el mismo lote?" sale tras más de 6 h sin datos (`const HORAS = 6;` en *Ciclos del cultivo*).
Los umbrales de color de los paneles son de referencia y El Trigal debe validarlos (sección 9 del manual).

## Cámara y fotos

- `main.py` (base `fastapi-cam` del docente, optimizada por el equipo), puerto 3333, 1280×720 MJPG; se apaga sola a
  los 10 s sin uso.
- Fotos automáticas a las 4:00, 12:00 y 20:00 (`HORAS_FOTO` en `trigal.env`, formato `HH:MM` separado por comas), con
  luz blanca y luego UV. Botones en Grafana: *Tomar foto ahora*, *Calibrar* (solo red local, `/video_feed`),
  *Ver en tiempo real* (`/video_lite`) y *Apagar*. Por decisión del equipo, los visitantes también ven los botones.
- Fotos en `/home/trigal/fotos/{automaticas,manuales}/<AAAA-MM mes>/`; `fotos-nube` las sube cada hora a
  `drive:EstacionTrigal/fotos` y borra de la Pi las de más de 30 días.
- Desde internet toda ruta empieza por `/<CAM_CLAVE>/` (sin ella responde 403).

## Cómo probar

```bash
revisar-estacion                     # revisión completa (~1 min); también corre sola 6 min tras arrancar → ~/ultimo-arranque.txt
prueba-final                         # revisión más profunda, cuenta lecturas por campo en InfluxDB
journalctl -u trigal-serial -n 30 --no-pager
curl -s localhost:3333/foto/estado | python3 -m json.tool
mosquitto_pub -h localhost -u nodered -P '<MQTT_PASS_NODERED>' -t trigal/estacion1/cmd -m '{"cmd":"ping"}'
```

Antes de una instalación: prueba de arranque en frío y prueba solo con 4G (sección 13 del manual).

## Decisiones ya tomadas (no reabrir sin que lo pida el equipo o El Trigal)

- Sin PCB: fuente de 12 V, Pi y módulo 4G alimentados por separado desde una multitoma; la fuente de 12 V no
  alimenta el 4G. La fuente (Mean Well LRS-35-12) es de entrada universal, 85 a 264 VAC, sin selector: sirve a 110 y 220 V.
- Todos los datos en un solo tópico MQTT, por sugerencia del profesor.
- Sin Cloudflare Access: pide registrar una tarjeta. Solo se menciona como opción de El Trigal, nunca como requisito.
- Un solo usuario de consulta (`trigal_visor`, Viewer); edición solo con `admin_trigal`. Kiosco solo para visitantes,
  que no necesitan la descarga de datos.
- Subdominio de `trigal-digital.com` (no de `floreseltrigal.com.co`), con la opción que se mantenga gratuita.
- Fotos en Google Drive de la cuenta del proyecto con rclone (permiso `drive.file`), separadas en automáticas y manuales.

## Pendientes conocidos

- Intervalos de lectura distintos por sensor en la ESP32 (las sondas en sustrato varían poco), sin perder la utilidad
  en otras condiciones. Cambio de firmware aplazado.
- Recalibrar el SCD30 al aire libre (marcó unos 320 ppm en laboratorio) y validar T-base y umbrales con El Trigal.
- Cambiar el *Max* del panel "Datos 4G este mes" al tamaño real del paquete.
- El manual dice que este repositorio es privado; confirmar su visibilidad en GitHub (Settings → General → Danger Zone).
- Recomendaciones para una siguiente versión: RTC DS3231, alertas por Telegram o correo, respaldo semanal programado.

## Cómo trabajar en este repositorio

- Idioma: español, en código, comentarios, documentación y mensajes de commit.
- Comandos para la Pi completos y uno por línea; el equipo y El Trigal no son expertos en Linux.
- Cada cambio que afecte la operación se refleja en `docs/manual-tecnico.md` (sección correspondiente y registro de
  cambios de la sección 15) y, si cambia un archivo de la sección 17, también ahí.
- No inventar valores agronómicos ni de hardware: si algo no está en el manual, el firmware o las fichas de
  `hardware/fichas/`, preguntar.
