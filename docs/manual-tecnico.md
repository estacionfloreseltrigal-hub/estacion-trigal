# Manual técnico – Estación portátil de monitoreo Flores El Trigal

Nov 22, 2026 · @Jayder Andres Juagibioy

## 1. Cómo usar este manual y datos clave

Este documento reúne todo lo necesario para entender, operar, modificar y reparar la estación portátil de monitoreo para *Antirrhinum majus* (snapdragon) de Flores El Trigal. Cada procedimiento trae sus comandos completos y los archivos de configuración cortos están en el anexo (sección 17); solo los programas largos (firmware, puente, cámara, flujos y dashboards) están aparte, en el repositorio estacion-trigal. Proyecto del curso Plataformas de Agricultura Inteligente, Universidad EAFIT, 2026-2.

**Para quién es cada parte**

| Si usted quiere… | Lea |
| --- | --- |
| Entender cómo funciona todo | Secciones 2 a 5 |
| Entrar a alguna parte del sistema | Sección 6 |
| Usar el dashboard, crear ciclos o descargar datos | Sección 7 |
| Ver o cambiar algo de la cámara y las fotos | Sección 8 |
| Entender las variables, los índices y sus criterios, o adaptar la estación a otro cultivo | Sección 9 |
| Cambiar la SIM, el WiFi o el dominio | Secciones 10 y 12 |
| Cambiar un usuario o una contraseña | Sección 11 |
| Cambiar tiempos, horarios, umbrales, sensores o paneles | Sección 12 |
| Revisar que todo funciona o resolver una falla | Sección 13 |
| Respaldar o reinstalar desde cero | Sección 14 |
| Construir otra estación igual | Secciones 3 (materiales y conexiones), 4 (firmware), 14 (instalación) y 17 (archivos) |
| Saber qué significa una palabra técnica | Sección 16 (glosario) |
| Ver el contenido exacto de un servicio o script de la Pi | Sección 17 |

**Datos clave**

| Dato | Valor |
| --- | --- |
| Dashboard público | `https://iot.trigal-digital.com` |
| Dashboard en modo kiosco (visitantes) | `https://iot.trigal-digital.com/d/trigal-estacion?orgId=1&kiosk` |
| Dashboard de administración | `https://iot.trigal-digital.com/d/trigal-administracion` |
| Formulario de ciclos | `https://iot.trigal-digital.com/ciclo` |
| Consulta y descarga de datos | `https://iot.trigal-digital.com/descarga` |
| Cámara desde internet | `https://cam.trigal-digital.com/<CAM_CLAVE>/...` |
| Nombre de la Raspberry Pi | `rpi4trigal` (usuario Linux `trigal`) |
| IP local de la Pi (red de pruebas EAFIT) | `10.10.80.48`; cambia en otra red |
| Cuenta del proyecto | `estacionfloreseltrigal@gmail.com` (Google Drive, Cloudflare) |
| Dominio | `trigal-digital.com`, de El Trigal, registrado en Hostinger y con DNS en Cloudflare |
| Túnel de Cloudflare | `rpi4trigal` |
| Carpeta principal en la Pi | `/opt/trigal/` |
| Base de datos | InfluxDB 2, organización `trigal`, bucket `estacion` |
| Tópicos MQTT | `trigal/estacion1` |
| Fotos automáticas | 4:00, 12:00 y 20:00, con luz blanca y UV |
| Operador móvil | Claro, APN `internet.comcel.com.co` |
| Código fuente | github.com/estacionfloreseltrigal-hub/estacion-trigal (privado; sección 14) |

**Contraseñas:** este manual dice qué usuario usa cada servicio, pero no incluye ninguna clave. Las claves se entregan aparte en la bóveda de Bitwarden "Estación Trigal". En los comandos, todo lo que va entre `< >` o en mayúsculas (por ejemplo `NUEVA_CLAVE`) se reemplaza por el valor real.

**Convenciones:** "en la Pi" significa en una terminal de la Raspberry Pi (por SSH o por Raspberry Pi Connect, sección 6). Los comandos se pegan **uno a la vez**, sobre todo los que piden contraseña. En `nano`, se guarda con **Ctrl+O** y **Enter**, y se sale con **Ctrl+X**.

**Si es la primera vez que trabaja con estos temas:** lea primero las secciones 2 y 7, y tenga a mano el glosario (sección 16). Para cualquier cambio en la Pi necesita una terminal, que es una ventana donde se escriben órdenes de texto:

- **Desde Windows en la misma red de la Pi:** abrir PowerShell (tecla Windows → escribir `PowerShell` → Enter) y escribir `ssh trigal@<ip-de-la-pi>` (sección 6).
- **Desde cualquier lugar con internet:** entrar a connect.raspberrypi.com con la cuenta del proyecto → `rpi4trigal` → Remote shell.
- Se sabe que se está dentro de la Pi porque la línea empieza por `trigal@rpi4trigal:~ $`.
- Para pegar un comando en la terminal: clic derecho, o **Ctrl+Shift+V**. Para detener un comando que no termina: **Ctrl+C**.
- Si un comando pide contraseña, al escribirla no se ve nada en pantalla. Es normal: escribirla y dar Enter.

**Cuatro reglas antes de cambiar cualquier cosa**

1. Hacer una copia de lo que se va a modificar (sección 12, al inicio).
2. Cambiar una sola cosa a la vez y comprobar que funciona antes de seguir.
3. Al terminar, ejecutar `revisar-estacion` (sección 13): debe decir "Todo lo esencial está funcionando".
4. Anotar el cambio en el registro de cambios (sección 15) y, si cambió una clave, actualizarla en Bitwarden.

## 2. Cómo funciona: flujos de datos y fotos

La ESP32-S3 mide y envía una línea de texto por USB cada minuto. La Raspberry Pi la guarda, la procesa y la muestra; solo usa internet para publicar el dashboard y subir las fotos. Si se cae el 4G, la estación sigue midiendo y guardando.

```
Sensores ── ESP32-S3 ──USB (trama $EST)── Raspberry Pi 4
                                            │ trigal-serial → Mosquitto (MQTT) → Node-RED → InfluxDB → Grafana
                                            │ cámara USB (servicio camara) → fotos → Google Drive
                                            └ 4G SIM7600 ── túnel Cloudflare ── iot.trigal-digital.com / cam.trigal-digital.com
```

### Flujo A — Captura (ESP32-S3)

1. Cada **10 s** lee el SCD30 (CO₂, temperatura y humedad del aire), el TSL2591 (lux), el DHT22 de la caja y pide una lectura al sensor PAR. Con la temperatura de la caja controla el ventilador.
2. Cada **15 min** hace una ronda por las 3 sondas de suelo (humedad, temperatura, CE y pH).
3. Cada **60 s** arma la trama `$EST` y la envía por USB. El PAR y los lux van **promediados**; las lecturas tomadas con los LEDs de la cámara encendidos no se cuentan, para que el flash no altere el DLI ni el fotoperiodo.
4. El primer envío sale 15 s después de encender.

### Flujo B — Envío local (puente serie → MQTT)

1. El servicio `trigal-serial` (script `/opt/trigal/app/serial_mqtt.py`) lee el puerto `/dev/esp32` a 115200 baudios.
2. **Espera a que la Pi tenga la hora sincronizada por internet** antes de publicar (`esperar-hora`). Así ninguna lectura queda con fecha falsa, porque la Pi no tiene reloj propio.
3. Convierte la trama a JSON con nombres claros (`ta` → `temperatura`, `s1h` → `s1_humedad`…), descarta los valores `nan` y publica todo junto en `trigal/estacion1/datos` con el usuario MQTT `estacion`.
4. Si la ESP32 no manda nada durante 180 s (`SIN_DATOS_S`), el puente la reinicia.

### Flujo C — Procesamiento y almacenamiento (Node-RED → InfluxDB)

1. Node-RED se suscribe a `trigal/estacion1/datos` con el usuario MQTT `nodered`.
2. La función *Índices instantáneos* agrega `dpv`, `punto_rocio` y `margen_rocio` a cada lectura.
3. Guarda en InfluxDB: bucket `estacion`, medición `datos`, un campo por variable.
4. Cada noche a las 00:10 la tarea `indices_diarios` calcula Tmáx, Tmín, DLI y fotoperiodo y los guarda en la medición `diario`.
5. Los ciclos por lote se guardan en la medición `ciclos`, y el aviso de "¿sigue en el mismo lote?" en `estado_estacion`.
6. Cada 5 min, `metricas-sistema` guarda el consumo del 4G, el uso de la microSD, la temperatura de la CPU y el estado de la alimentación en la medición `sistema`.

### Flujo D — Visualización y descarga

1. Grafana consulta InfluxDB con un token de solo lectura y arma los dashboards.
2. `cloudflared` crea un túnel saliente hacia Cloudflare y publica Grafana y las páginas `/ciclo` y `/descarga` en `iot.trigal-digital.com`, sin abrir puertos ni necesitar IP pública.
3. Las páginas `/ciclo` y `/descarga` las sirve Node-RED y piden usuario y contraseña.

### Flujo E — Órdenes hacia la ESP32 (sentido inverso)

Node-RED o la cámara publican una orden en `trigal/estacion1/cmd` → el puente la escribe por USB → la ESP32 la ejecuta y responde por `trigal/estacion1/esp` (por ejemplo `Estado: LUZ_BLANCA` y `#OK,luz lista`). Solo un programa puede tener abierto el puerto USB, por eso todo pasa por MQTT.

### Flujo F — Fotos

1. A las 4:00, 12:00 y 20:00, o con el botón de Grafana, el servicio `camara` pide la luz blanca por MQTT, espera la confirmación de la ESP32, toma la foto, repite con la luz UV y apaga los LEDs.
2. Guarda las fotos en la microSD (`/home/trigal/fotos/automaticas/` o `/manuales/`) con fecha, hora y tipo de luz impresos.
3. Cada hora `fotos-nube` las copia a Google Drive (`EstacionTrigal/fotos`) y borra de la Pi las que tengan más de 30 días y ya estén en Drive.
4. Grafana muestra la última foto blanca y la última UV, que pide directamente al servidor de la cámara.

### Tiempos del sistema

| Qué | Cada cuánto | Dónde se cambia |
| --- | --- | --- |
| Lectura de aire, luz y caja | 10 s | `T_LECTURA` en el firmware |
| Envío de datos a la Pi | 60 s | `T_ENVIO` en el firmware |
| Ronda de sondas de suelo | 15 min | `T_SUELO` en el firmware |
| Índices diarios | 00:10 | Tarea `indices_diarios` en InfluxDB |
| Métricas del sistema | 5 min | `metricas-sistema.timer` |
| Fotos automáticas | 4:00, 12:00, 20:00 | `HORAS_FOTO` en `/opt/trigal/app/trigal.env` |
| Subida de fotos a Drive | Cada hora | `fotos-nube.timer` |
| Borrado local de fotos | Más de 30 días | `--min-age 30d` en `fotos-nube.sh` |
| Vigilante del 4G | 5 min | `lte-watchdog.timer` |
| Actualización del dashboard | 1 min (se recomienda 5 min) | Selector de refresco en Grafana |

## 3. Hardware, conexiones y energía

La estación es un trípode con mástil que lleva los sensores, la cámara y los LEDs, y una caja con la Raspberry Pi 4, la ESP32-S3 y el módulo 4G. La versión entregada **no usa PCB**: cada equipo se alimenta por separado desde una regleta.

**Componentes**

| Componente | Mide o hace | Conexión | Dirección o pin |
| --- | --- | --- | --- |
| Raspberry Pi 4 (4 GB) | Servidor local: puente, base de datos, dashboard, cámara | Fuente oficial de 27 W | — |
| ESP32-S3 (placa D-ESP32-S3; en Arduino, ESP32S3 Dev Module) | Lee sensores y maneja LEDs y ventilador | USB a la Pi por el conector marcado UART o COM (chip CP210x) | Aparece como `/dev/esp32` |
| SCD30 | CO₂ (ppm), temperatura (°C) y humedad relativa (%) del aire | I²C a 50 kHz | `0x61`; pin SEL a GND o al aire |
| TSL2591 | Iluminancia (lux) | I²C | `0x29` |
| Sensor PAR SEN0641 | PPFD (µmol·m⁻²·s⁻¹) | RS485 Modbus, 4800 baudios | ID 1, registro `0x0000` |
| 3 sondas JXBS-3001 | Humedad, temperatura, CE y pH del sustrato | RS485 Modbus, 4800 baudios | IDs 4, 2 y 3 (sondas 1, 2 y 3) |
| DHT22 | Temperatura dentro de la caja | Digital | GPIO 4 (`PIN_DHT`) |
| Ventilador 12 V | Enfría la caja: prende a 25 °C y apaga a 22 °C | MOSFET | GPIO 5 (`PIN_VENT`) |
| 2 LEDs blancos + 1 LED UV | Iluminación para las fotos, en canales separados | MOSFET DFR0457, con una resistencia de potencia de 10 W en serie por canal | Blancos GPIO 6 (`PIN_LED_BLANCO`), UV GPIO 10 (`PIN_LED_UV`) |
| Cámara USB con lente varifocal | Fotos y video, 1280×720 MJPG | USB a la Pi | `/dev/video0` |
| HAT Waveshare M.2 + SIM7600G-H | Internet 4G con Claro | USB a la Pi (modo RNDIS) | Interfaz `usb0` |

El bus I²C usa SDA en **GPIO 8** y SCL en **GPIO 9**. Los registros de las sondas de suelo son: pH `0x0006` (×0,01), humedad `0x0012` (×0,1 %), temperatura `0x0013` (×0,1 °C) y CE `0x0015` (µS/cm). Los pines que no aparecen en la tabla están en los `#define` al inicio del firmware (sección 4).

**Pines según el plano de Proteus:** módulo RS485 con TX en GPIO 17 y RX en GPIO 18 (si un sensor RS485 no responde, probar a intercambiarlos en el código); DHT22 con DATA en GPIO 4. Cables RS485 de las sondas y del PAR: café = 12 V, negro = GND, amarillo = A, azul = B. Si A y B quedan invertidos, el sensor no responde.

**Conexión de la ESP32-S3 a la Pi:** la placa tiene dos conectores USB-C. Se usa el marcado **UART** o **COM** (chip CP210x), que es el que reconoce la regla `99-esp32.rules` (sección 17). El otro conector (USB nativo) no funciona con el puente. No conectar a la Pi otro aparato con chip CP210x al mismo tiempo, porque la regla no podría distinguirlos.

**Registros adicionales del sensor PAR (SEN0641):** `0x0052` corrección frente a un medidor de referencia; `0x07D0` dirección Modbus; `0x07D1` velocidad (0 = 2400, 1 = 4800, 2 = 9600 baudios).

**Caja de control** (numeración de la foto del manual de usuario): resistencias de potencia de 10 W de los LEDs, Raspberry Pi 4 con el módulo 4G, ESP32-S3, conexiones del sensor de luz y del de CO₂, borneras de los MOSFET de potencia (ventiladores, LED UV y LEDs blancos), fuente de 12 V, módulo RS485, multitoma, ventilador de la caja, MOSFET, breaker de protección y bornera aérea.

> **Confirmado con el firmware cargado (`PAYLOAD.ino` del 21-nov-2026, el mismo del repositorio) y correcciones pendientes en el manual de usuario:**
>
> 1. **Bus RS485:** el firmware usa 4800 baudios, el PAR con dirección 1 y las sondas con 4, 2 y 3. El anexo del manual de usuario dice 9600 baudios y sondas 2, 3 y 4: hay que corregir el manual de usuario.
> 2. **DHT22:** mide la temperatura dentro de la caja (`temp_caja`) para controlar el ventilador; no mide el aire del cultivo. Corregir el manual de usuario.
> 3. **Pines:** LEDs blancos en GPIO 6, LED UV en GPIO 10, ventilador en GPIO 5 (prende a 25 °C y apaga a 22 °C) y DHT22 en GPIO 4. Una versión anterior del código usaba 13 y 14 para los LEDs.
> 4. **Tiempo de arranque:** el manual de usuario dice que en unos 2 minutos ya está midiendo. Es correcto para los datos; todos los servicios (túnel, cámara y revisión automática) quedan listos en unos 7 minutos.
> 5. **Fuente de 12 V a 110 V (pendiente):** revisar si la fuente tiene selector de 110/220 V antes de conectarla a una toma de 110 V.

**Energía**

La estación se conecta con un solo cable a 220 V (invernaderos de El Trigal) o a 110 V (toma normal). La energía pasa por un **switch** por fuera de la caja de control y un **breaker de protección**, y llega a una **multitoma** dentro de la caja, de la que se alimenta cada equipo por separado:

| Equipo | Fuente |
| --- | --- |
| Fuente de 12 V | Multitoma. Alimenta LEDs, ventiladores y sensores RS485 |
| Raspberry Pi 4 | Su cargador oficial, en la multitoma |
| Módulo 4G (HAT) | Su propio puerto USB-C con fuente de 5 V / 3 A, en la multitoma. La fuente de 12 V **no** lo alimenta |
| ESP32-S3 | Por el USB de la Pi |

**Encender:** conectar el cable al tomacorriente y subir el switch exterior. En unos 2 minutos ya está midiendo; todos los servicios quedan listos en unos 7 minutos. Si el breaker se baja de nuevo al subirlo, no insistir: hay un corto o una sobrecarga.

**Apagar:** lo más seguro para la microSD es apagar primero la Pi desde la terminal (`sudo poweroff`, esperar a que se apague el LED verde) y después bajar el switch. Bajar el switch directamente también funciona, pero hacerlo muchas veces puede dañar la memoria. Apagar siempre antes de mover la estación de cama o de invernadero.

**Reiniciar si no responde:** `sudo reboot` desde Pi Connect. Si no hay acceso, bajar el switch, esperar 30 segundos y subirlo.

**Cuidados físicos**

- El LED UV no debe mirarse de frente. El firmware lo apaga solo a los 10 s si no recibe la orden de apagar.
- No cubrir el SCD30 ni el sensor PAR. Limpiar el domo del PAR y el lente de la cámara con un paño seco cuando tengan polvo o condensación.
- Las sondas de suelo van en el sustrato, en la zona de raíces, sin tocar goteros ni paredes de la cama.
- El SCD30 reportó valores bajos de CO₂ en laboratorio (unos 320 ppm, cuando el aire exterior tiene más de 420 ppm). Antes de usar el CO₂ para decisiones, conviene recalibrarlo al aire libre.

**Lista de materiales** (para construir otra estación; tomada del presupuesto del equipo, noviembre de 2026)

| Componente | Cantidad | Para qué |
| --- | --- | --- |
| Raspberry Pi 4 Model B, 4 GB | 1 | Servidor local |
| Fuente oficial Raspberry Pi de 27 W (USB-C) | 1 | Alimentación de la Pi |
| MicroSD de 128 GB, clase 10 (SanDisk Extreme PRO o Kingston Canvas) | 1 | Sistema, base de datos y fotos |
| ESP32-S3 (D-ESP32-S3-1M) | 1 | Lectura de sensores y control de LEDs y ventilador |
| HAT Waveshare SIM7600G-H M.2 4G (WS-21707) con sus antenas | 1 | Internet 4G |
| Fuente de 5 V / 3 A con conector USB-C | 1 | Alimentación del HAT 4G |
| SIM nano de Claro, prepago, sin PIN | 1 | Línea de datos |
| SCD30 (CO₂, temperatura y humedad) | 1 | Aire |
| TSL2591 | 1 | Lux |
| Sensor PAR SEN0641 (RS485) | 1 | PPFD |
| Sonda de suelo JXBS-3001-TR-RS 4 en 1 (RS485, alimentación de 12 a 24 V) | 3 | Humedad, temperatura, CE y pH del sustrato |
| Módulo RS485 a TTL | 1 | Comunicación de la ESP32 con el PAR y las sondas |
| DHT22 | 1 | Temperatura de la caja |
| Controlador MOSFET DFR0457 | 6 (3 en uso) | LEDs blancos, LED UV y ventilador |
| LEDs de potencia: 2 blancos y 1 UV | 3 | Luz para las fotos |
| Resistencias de potencia de 10 W | 1 por canal de LED | Limitar la corriente de los LEDs (el presupuesto lista 6,8 Ω; verificar el valor marcado en la resistencia instalada) |
| Fuente conmutada Mean Well LRS-35-12 (12 V, 3 A) | 1 | LEDs, ventiladores y sensores RS485 |
| Ventilador de 12 V, 80 × 80 mm | 1 | Enfriar la caja |
| Cámara USB con lente varifocal (MJPG, 1280×720) | 1 | Fotos y video |
| Caja plástica IP65 de 400 × 300 × 148 mm (Kowet K4030-148) | 1 | Proteger la electrónica |
| Breaker de riel, switch exterior y multitoma | 1 de cada uno | Protección y distribución de la energía |
| Trípode y mástil | 1 | Estructura (fabricada por Multivallas Medellín) |
| Cables, borneras DC, amarres, tornillería y piezas impresas en PLA | Varios | Montaje |

La mayoría de los componentes electrónicos se compraron en Didácticas Electrónicas (Medellín). Guarde las fichas técnicas de los sensores junto con el repositorio: ahí están los registros Modbus y los rangos de medida.

## 4. Firmware de la ESP32-S3

El firmware es el archivo `PAYLOAD.ino`, escrito con la estructura de los códigos del curso: máquina de estados finitos (MEF) y bloques *1. Estado de las salidas físicas / 2. Cálculo de variables internas / 3. Preguntas de transición*. Guarden una copia del archivo cargado en el Drive del proyecto y en el repositorio (sección 14).

### Trama de datos `$EST`

Una línea por envío, con pares `nombre=valor` separados por comas. Un sensor que no responde envía `nan`, y la Pi descarta ese campo. Ejemplo:

```
$EST,co2=612,ta=19.4,hra=74.2,lux=1520.3,par=350.0,tc=30.0,vent=0,luz=0,s1h=38.5,s1t=17.2,s1ce=125,s1ph=6.31,s2h=...,s3ph=6.20
```

| En la trama | En InfluxDB y Grafana | Unidad |
| --- | --- | --- |
| `co2` | `co2` | ppm |
| `ta` | `temperatura` | °C |
| `hra` | `humedad` | % |
| `lux` | `lux` (promedio del minuto) | lx |
| `par` | `par` (promedio del minuto) | µmol·m⁻²·s⁻¹ |
| `tc` | `temp_caja` | °C |
| `vent` | `ventilador` | 0 apagado, 1 encendido |
| `luz` | `luz` | 0 apagada, 1 blanca, 2 UV |
| `s1h`, `s1t`, `s1ce`, `s1ph` | `s1_humedad`, `s1_temp`, `s1_ce`, `s1_ph` | %, °C, µS/cm, pH |
| `s2…`, `s3…` | `s2_…`, `s3_…` | Igual que la sonda 1 |
| `scd`, `tsl` | `scd`, `tsl` | Estado del sensor: 1 OK, 0 sin conexión |

Node-RED agrega `dpv` (kPa), `punto_rocio` (°C) y `margen_rocio` (°C). Un campo nuevo en la trama aparece solo en InfluxDB en cuanto llega.

### Otros mensajes de la ESP32

| Mensaje | Significado |
| --- | --- |
| `#OK,estacion lista` | La ESP32 arrancó |
| `Estado: LUZ_APAGADA` / `LUZ_BLANCA` / `LUZ_UV` | Cambio de estado de la MEF de luces |
| `#OK,luz lista` | La luz pedida ya está estable y se puede tomar la foto |
| `#OK,ping` | Respuesta a la orden `ping` |
| `#ERR,SCD30 sin datos nuevos` / `#ERR,TSL2591 desconectado` | Un sensor I²C dejó de responder: sus campos van como `nan` y se reintenta cada 30 s |
| `#ERR,luz apagada por tiempo maximo` | Un LED llegó a su tiempo máximo sin recibir la orden de apagar |
| `#ERR,orden desconocida` | Llegó una orden distinta de `blanco`, `uv`, `apagar` o `ping` |
| #OK,SCD30 detectado / #OK,TSL2591 detectado | El sensor I²C respondió al arrancar o al reintentar |
| #ERR,SCD30 no detectado / #ERR,TSL2591 no detectado | El sensor no respondió; la estación sigue con los demás y lo reintenta cada 30 s. Revisar cables I²C (GPIO 8 y 9) y alimentación |

El puente los publica en `trigal/estacion1/esp`, no en `datos`, para no mezclar texto con números.

### Órdenes que acepta (tópico `trigal/estacion1/cmd`)

| Orden | Efecto |
| --- | --- |
| `{"cmd":"blanco"}` | Enciende los LEDs blancos (máximo 10 s si no llega `apagar`) |
| `{"cmd":"uv"}` | Enciende el LED UV (máximo 10 s) |
| `{"cmd":"apagar"}` | Apaga todos los LEDs |
| `{"cmd":"blanco","seg":120}` | LEDs blancos por un tiempo dado, para calibrar la cámara (máximo 300 s) |
| `{"cmd":"ping"}` | La ESP32 responde `#OK,ping` |

Para probar una orden desde la Pi:

```bash
mosquitto_pub -h localhost -u nodered -P 'CLAVE_NODERED' -t trigal/estacion1/cmd -m '{"cmd":"ping"}'
```

### MEF de luces

Tres estados: `LUZ_APAGADA` → `LUZ_BLANCA` o `LUZ_UV` → `LUZ_APAGADA`. Al entrar a una luz, espera 500 ms (`T_ESTABILIZAR`) y avisa `#OK,luz lista`. Vuelve sola a `LUZ_APAGADA` cuando llega `apagar`, cuando vence `seg` o a los 10 s (`T_MAX_LUZ`), para proteger del calor y de la radiación UV.

### Constantes que se pueden ajustar

Todas están como `#define` al inicio de `PAYLOAD.ino`:

| Constante | Valor | Qué controla |
| --- | --- | --- |
| `PIN_SDA` / `PIN_SCL` | 8 / 9 | Bus I²C (SCD30 y TSL2591) |
| `PIN_RX` / `PIN_TX` | 18 / 17 | Módulo RS485 |
| `PIN_DHT` / `PIN_VENT` | 4 / 5 | DHT22 de la caja y MOSFET del ventilador |
| `PIN_LED_BLANCO` / `PIN_LED_UV` | 6 / 10 | MOSFET de los LEDs (ver la nota de la sección 3) |
| `T_LECTURA` | 10000 ms | Lectura de aire, luz y caja, y control del ventilador |
| `T_ENVIO` | 60000 ms | Envío de la trama a la Pi |
| `T_SUELO` | 900000 ms (15 min) | Ronda de las sondas de suelo. En suelo de campo se sugiere 300000 (5 min) |
| `T_PRIMER_ENVIO` | 15000 ms | Primer envío después de encender |
| `T_ON` / `T_OFF` | 25,0 / 22,0 °C | Temperatura de la caja para prender y apagar el ventilador |
| `T_ESTABILIZAR` | 500 ms | Espera con la luz encendida antes de avisar `#OK,luz lista` |
| `T_MAX_LUZ` | 10000 ms | Tiempo máximo de un LED encendido sin orden de apagar |
| `T_MAX_MANUAL` | 300000 ms | Máximo aceptado en `seg` |
| `VELOCIDAD_I2C` / `T_ESPERA_I2C` | 50000 Hz / 200 ms | El SCD30 necesita I²C lento y hasta 150 ms de espera |
| `T_REINTENTO_I2C` | 30000 ms | Cada cuánto se intenta reconectar un sensor I²C caído |
| `T_SIN_DATOS_SCD30` | 30000 ms | Tiempo sin datos nuevos del SCD30 para darlo por caído (`scd=0`) |
| `BAUDIOS_485` | 4800 | Velocidad del bus RS485 (igual en todos los sensores) |
| `BAUDIOS_RASPI` | 115200 | Velocidad del USB hacia la Pi; debe coincidir con `SERIAL_BAUD` de `trigal.env` |
| `ID_SENSOR_SUELO_1..3`, `ID_SENSOR_PAR_1` | 4, 2, 3 y 1 | Direcciones Modbus |
| `REG_PAR` / `PAR_USA_REG_ENTRADA` | `0x0000` / `false` | Registro del PAR y función Modbus que usa (`false` = 0x03, `true` = 0x04) |
| `INTERVALO_PETICION` | 100 ms | Pausa entre peticiones Modbus seguidas |

### Cómo cargar o actualizar el firmware

**Preparar el computador (solo la primera vez)**

1. Instalar Arduino IDE 2 desde arduino.cc.
2. Agregar las placas ESP32: File → Preferences → Additional boards manager URLs → pegar `https://espressif.github.io/arduino-esp32/package_esp32_index.json` → OK. Luego Tools → Board → Boards Manager → buscar `esp32` → instalar **esp32 by Espressif Systems**.
3. Instalar las librerías: Tools → Manage Libraries → buscar e instalar cada una: **SparkFun SCD30 Arduino Library**, **Adafruit TSL2591 Library**, **Adafruit Unified Sensor**, **modbus-esp8266** (de Alexander Emelianov; trae `ModbusRTU.h`) y **DHT sensor library** (de Adafruit).
4. Conectar la ESP32 al computador por el conector UART o COM. Si en Windows no aparece ningún puerto COM nuevo, instalar el controlador CP210x de Silicon Labs.
5. Tools → Board → esp32 → **ESP32S3 Dev Module**, y Tools → Port → el COM que apareció.

**Cargar el código**

1. En la Pi, detener el puente para liberar el puerto: `sudo systemctl stop trigal-serial`.
2. Desconectar el USB de la ESP32 de la Pi y conectarlo a un computador con Arduino IDE.
3. En el IDE: placa **ESP32S3 Dev Module** y las librerías que pide el archivo: *SparkFun SCD30 Arduino Library*, *Adafruit TSL2591* y *Adafruit Unified Sensor*, *modbus-esp8266* (clase `ModbusRTU`) y *DHT sensor library*.
4. Abrir `PAYLOAD.ino`, cambiar las constantes necesarias y **Subir**.
5. En el Monitor Serie (115200) debe salir `#OK,estacion lista` y, a los 15 s, la primera línea `$EST`. Cerrar el Monitor Serie.
6. Conectar otra vez la ESP32 a la Pi y arrancar el puente: `sudo systemctl start trigal-serial`.
7. Comprobar a los 2 minutos: `journalctl -u trigal-serial --since "-2 min" --no-pager | tail`. No debe aparecer "no manda nada".

Si se cambia `T_ENVIO`, el puente debe esperar al menos el triple antes de reiniciar la ESP32. Ajustar `SIN_DATOS_S` en `/opt/trigal/app/serial_mqtt.py` (hoy 180 s para envíos de 60 s; el mismo archivo tiene SIN\_SUELO\_S = 1800, que reinicia la ESP32 si pasan 30 min sin datos de suelo) y reiniciar con `sudo systemctl restart trigal-serial`.

## 5. Raspberry Pi: carpetas, servicios, contenedores y puertos

La Pi `rpi4trigal` usa Raspberry Pi OS de 64 bits (Debian Trixie) y arranca todo sola al recibir corriente. Lo que maneja la red, la ESP32 y la cámara corre directo en el sistema (systemd); la plataforma de datos corre en contenedores Docker administrados con Portainer.

### Qué arranca solo

| Pieza | Tipo | Cuándo |
| --- | --- | --- |
| Conexión 4G `claro4g` (`usb0`) | NetworkManager | Al arrancar, con reintentos sin límite |
| `lte-watchdog.timer` | systemd | 90 s después de arrancar y cada 5 min |
| Mosquitto, Node-RED, InfluxDB, Grafana, cloudflared, Portainer | Docker, `restart: unless-stopped` | Al arrancar Docker |
| `trigal-serial.service` (puente ESP32 → MQTT) | systemd | Al arrancar, después de sincronizar la hora |
| `camara.service` (cámara y fotos programadas) | systemd | Al arrancar |
| `fotos-nube.timer` | systemd | 10 min después de arrancar y cada hora |
| `metricas-sistema.timer` | systemd | 3 min después de arrancar y cada 5 min |
| `revisar-estacion.timer` | systemd | Una vez, 6 min después de arrancar |
| Raspberry Pi Connect | Servicio del usuario `trigal` | Al arrancar |

### Dónde está cada cosa

| Ruta | Contenido |
| --- | --- |
| `/opt/trigal/app/serial_mqtt.py` | Puente ESP32 → MQTT |
| `/opt/trigal/app/trigal.env` | Configuración del puente y de la cámara (con claves; permisos 600) |
| `/opt/trigal/app/influx-sistema.env` | Token de InfluxDB de `metricas-sistema` (permisos 600) |
| `/opt/trigal/mosquitto/config/` | `mosquitto.conf` y archivo de usuarios `passwd` |
| `/opt/trigal/nodered/data/` | Flujos y `settings.js` de Node-RED (respaldo `settings.js.respaldo`) |
| `/opt/trigal/influxdb/data/` y `/config/` | Base de datos InfluxDB |
| `/opt/trigal/grafana/data/` | Dashboards, usuarios y configuración de Grafana |
| `/opt/trigal/stacks/` | Copia de los archivos YML de cada contenedor |
| `/opt/trigal/backups/` | Carpeta para respaldos |
| `/home/trigal/fastapi-cam/main.py` | Servidor de la cámara y fotos (entorno Python en `.venv`) |
| `/home/trigal/fotos/` | Fotos: `automaticas/` y `manuales/`, una carpeta por mes |
| `/home/trigal/.config/rclone/rclone.conf` | Autorización de Google Drive |
| `/usr/local/bin/` | `revisar-estacion`, `lte-watchdog.sh`, `fotos-nube.sh`, `metricas-sistema`, `esperar-hora` |
| `/etc/systemd/system/` | Archivos `.service` y `.timer` de la tabla anterior |
| `/etc/udev/rules.d/99-esp32.rules` | Regla que crea el nombre fijo `/dev/esp32` |
| `/home/trigal/ultimo-arranque.txt` | Resultado de la revisión automática del último arranque |

### Contenido de `trigal.env` (sin claves)

```
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USER=estacion
MQTT_PASS=<clave del usuario estacion>
ESTACION=estacion1
SERIAL_PORT=            # vacío = usar /dev/esp32
SERIAL_BAUD=115200
HORAS_FOTO=...          # horas de las fotos automáticas (4, 12 y 20)
CAM_CLAVE=<clave de la cámara remota>
```

Para verlo: `sudo cat /opt/trigal/app/trigal.env`. Después de cambiarlo hay que reiniciar los servicios que lo usan: `sudo systemctl restart trigal-serial camara`.

### Puertos

| Servicio | Dirección local | Publicado en internet |
| --- | --- | --- |
| Grafana | `http://<ip-de-la-pi>:3000` | Sí: `iot.trigal-digital.com` |
| Node-RED editor | `http://<ip-de-la-pi>:1880` | **No**, nunca |
| Node-RED `/ciclo` y `/descarga` | `http://<ip-de-la-pi>:1880/ciclo` | Sí, con usuario y clave |
| InfluxDB | `http://<ip-de-la-pi>:8086` | No |
| Mosquitto (MQTT) | `<ip-de-la-pi>:1883` | No |
| Cámara | `http://<ip-de-la-pi>:3333` | Sí: `cam.trigal-digital.com`, con clave |
| Portainer | `https://<ip-de-la-pi>:9443` | No |

Node-RED, InfluxDB y Grafana usan `network_mode: host`, así que se encuentran entre sí en `localhost`.

### Comandos de uso frecuente

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"   # contenedores y su estado
docker logs --tail 30 <contenedor>                     # mensajes de un contenedor
docker restart <contenedor>                            # reiniciar un contenedor
systemctl status trigal-serial camara                  # estado de los servicios propios
systemctl list-timers --no-pager                       # próximas ejecuciones programadas
journalctl -u trigal-serial -n 30 --no-pager           # mensajes del puente
journalctl -u camara -n 30 --no-pager                  # mensajes de la cámara
df -h /                                                # espacio libre en la microSD
vnstat -i usb0 -d                                      # consumo diario del 4G
```

Los registros del sistema se conservan entre reinicios (`/etc/systemd/journald.conf.d/50-persistente.conf`, máximo 200 MB).

**Actualizaciones:** hacerlas solo con WiFi o cable, nunca en El Trigal por el 4G. Como el WiFi de la universidad solo da IPv4 y todo lo que tenga IPv6 sale por el 4G, instalar así: `sudo apt -o Acquire::ForceIPv4=true update` y `sudo apt -o Acquire::ForceIPv4=true install <paquete>`.

## 6. Cómo ingresar a cada parte

Hay dos tipos de acceso: los que funcionan desde cualquier lugar con internet (dashboard, formularios, cámara, cuentas en la nube y Raspberry Pi Connect) y los que solo funcionan desde la misma red que la Pi (SSH, editor de Node-RED, InfluxDB, Portainer). Cada servicio tiene su propio usuario y contraseña, guardados en Bitwarden.

### Accesos

| Qué | Dirección | Usuario | Desde dónde |
| --- | --- | --- | --- |
| Dashboard (consulta) | `https://iot.trigal-digital.com` | `trigal_visor` (solo lectura) | Internet |
| Dashboard en kiosco | `https://iot.trigal-digital.com/d/trigal-estacion?orgId=1&kiosk` | `trigal_visor` | Internet |
| Dashboard (administración y edición) | `https://iot.trigal-digital.com` y `/d/trigal-administracion` | `admin_trigal` | Internet |
| Formulario de ciclos | `https://iot.trigal-digital.com/ciclo` | Usuario de `httpNodeAuth` de Node-RED | Internet |
| Consulta y descarga | `https://iot.trigal-digital.com/descarga` | El mismo de `/ciclo` | Internet |
| Cámara remota | `https://cam.trigal-digital.com/<CAM_CLAVE>/video_lite` | La clave va en la dirección | Internet |
| Terminal de la Pi (remota) | [connect.raspberrypi.com](https://connect.raspberrypi.com) → `rpi4trigal` → *Remote shell* | Cuenta Raspberry Pi ID del proyecto | Internet (sale por el 4G) |
| Terminal de la Pi (local) | `ssh trigal@<ip-de-la-pi>` | `trigal` | Misma red |
| Editor de Node-RED | `http://<ip-de-la-pi>:1880` | `admin_trigal` | Misma red |
| InfluxDB | `http://<ip-de-la-pi>:8086` | `admin_trigal` | Misma red |
| Grafana local | `http://<ip-de-la-pi>:3000` | `admin_trigal` o `trigal_visor` | Misma red |
| Portainer | `https://<ip-de-la-pi>:9443` | `admin_trigal` | Misma red |
| Cámara local | `http://<ip-de-la-pi>:3333` | Sin clave | Misma red |
| Correo y Drive | [drive.google.com](https://drive.google.com) | `estacionfloreseltrigal@gmail.com` | Internet |
| Cloudflare | [dash.cloudflare.com](https://dash.cloudflare.com) y [one.dash.cloudflare.com](https://one.dash.cloudflare.com) | El Gmail del proyecto; Julián Guevara es administrador | Internet |
| Dominio (Hostinger) | Panel de Hostinger | Cuenta de El Trigal (la maneja Julián Guevara) | Internet |
| Saldo y paquete de la SIM | App o web Mi Claro | Número de la línea | Internet |

### Encontrar la IP de la Pi en otra red

La IP `10.10.80.48` es la de la red de pruebas. En otra red cambia. Para conocerla:

1. Entrar por Raspberry Pi Connect y ejecutar `hostname -I`. La primera dirección es la de la red local.
2. O probar `ssh trigal@rpi4trigal.local` desde un computador en la misma red.
3. O buscar `rpi4trigal` en la lista de dispositivos del router.

### Entrar por SSH desde Windows

Abrir PowerShell y escribir `ssh trigal@<ip-de-la-pi>`. La primera vez pregunta si confía en el equipo: responder `yes`. La contraseña no se ve mientras se escribe.

### Entrar sin red local (en El Trigal)

En campo la Pi solo tiene el 4G, así que SSH no funciona. Se usa Raspberry Pi Connect: entrar a connect.raspberrypi.com con la cuenta del proyecto → el dispositivo `rpi4trigal` debe aparecer *en línea* → *Remote shell*. Ahí se pueden ejecutar todos los comandos de este manual.

Para llegar al editor de Node-RED, InfluxDB o Portainer en campo, llevar un computador y conectarlo a la misma red WiFi que la Pi (sección 12, "Agregar una red WiFi").

## 7. Uso del dashboard, ciclos y descarga de datos

Hay dos dashboards en Grafana. **Estación Trigal** lo ve todo el mundo y tiene todos los datos, la cámara y los índices. **Estación Trigal - Administración** solo lo ve el equipo y tiene los formularios del ciclo y la descarga de datos.

### Paso a paso para quien usa la plataforma

Esta guía está escrita para el personal del cultivo y puede copiarse tal cual en la sección 7 ("Cómo usar la plataforma") del manual de usuario.

**1. Entrar**

1. En el celular o el computador, abrir **https://iot.trigal-digital.com**.
2. Escribir el usuario `trigal_visor` y su contraseña. Se abre directamente el tablero **Estación Trigal**.
3. Para tenerlo a mano en el celular: en el navegador, menú → *Agregar a la pantalla de inicio*.
4. Para una pantalla fija (por ejemplo un televisor en la oficina), usar el enlace de pantalla completa: `https://iot.trigal-digital.com/d/trigal-estacion?orgId=1&kiosk`. Para salir de la pantalla completa: tecla **Esc**.

**2. Revisar que la estación está funcionando**

En la primera fila, el último dato debe tener menos de 2 minutos. Si es más viejo, la estación está apagada o sin internet (ver "Qué hacer si algo falla" en el manual de usuario, o la sección 13 de este manual).

**3. Elegir qué ver**

- **Lote:** arriba a la izquierda, en *Ciclo / lote*, elegir el lote. El más reciente aparece primero.
- **Fechas:** arriba a la derecha, en el reloj, elegir *Últimas 24 horas*, *Últimos 7 días*, *Últimos 30 días* o unas fechas exactas.
- **Actualizar:** el tablero se actualiza solo cada minuto. El botón de flechas lo actualiza al instante.

**4. Leer el tablero, de arriba hacia abajo**

| Fila | Qué mirar |
| --- | --- |
| Estado | Último dato, lote actual y avisos en naranja |
| Cámara | Últimas fotos con luz blanca y con luz UV, con su fecha y hora |
| Ambiente | Temperatura, humedad, CO₂, luz y margen al rocío: el número grande es el valor actual y la gráfica muestra cómo ha cambiado. El color indica si está en un rango normal (verde) o de cuidado (naranja o rojo) |
| Índices del ciclo | Grados-día acumulados desde la siembra o el trasplante, luz del día (DLI) y duración del día (fotoperiodo). Se calculan cada noche a las 00:10 con el día anterior |
| DPV | Qué tan seco o húmedo está el aire para la planta |
| Suelo | Humedad, temperatura, sales (CE) y pH de las 3 sondas |
| Sistema (plegada) | Estado de la estación: datos de internet gastados, memoria y temperatura del equipo. Se abre con un clic en su título |

**5. Ver una gráfica en detalle**

- Pasar el mouse o el dedo sobre la línea muestra el valor exacto y la hora.
- Arrastrar sobre la gráfica hace zoom en ese periodo. Para volver: botón de lupa con menos (−) o volver a elegir el rango arriba.
- Para ver una gráfica en grande: menú del panel (tres puntos) → *View*. Se sale con **Esc**.

**6. Fotos y cámara**

- **Tomar una foto ahora:** botón *Tomar foto ahora*. La estación prende la luz blanca, toma la foto, repite con la luz UV y apaga. Tarda unos 10 segundos; al terminar aparecen las fotos nuevas y un mensaje.
- **Ver el cultivo en vivo:** *Ver en tiempo real*. Al terminar, presionar **Apagar**: el video gasta muchos datos del plan de internet.
- **Enfocar la cámara** (solo en la red local de la estación): *Calibrar*, y girar los anillos de zoom y foco del lente.
- **Ver todas las fotos anteriores:** en Google Drive de la cuenta del proyecto, carpeta *EstacionTrigal/fotos*: `automaticas` (4:00, 12:00 y 20:00) y `manuales` (las del botón), una carpeta por mes.

**7. Si aparece un aviso naranja de "¿sigue en el mismo lote?"**

Significa que la estación estuvo más de 6 horas sin datos. Avisar a la persona encargada del tablero de administración, para que confirme si la estación sigue en el mismo lote o si se movió.

**8. Tareas del encargado (usuario administrador)**

- **Cuando se mueve la estación de lote:** abrir `https://iot.trigal-digital.com/ciclo`, llenar el código del lote, la ubicación, la fecha de siembra o trasplante y la T-base, y presionar *Iniciar ciclo nuevo* (detalle más abajo).
- **Para descargar datos:** abrir `https://iot.trigal-digital.com/descarga`, elegir el lote o las fechas, las variables y la agrupación (por ejemplo cada hora), presionar *Consultar* para ver una muestra y luego *Descargar CSV*. Para Excel, elegir el formato Excel (detalle más abajo).
- **Para responder el aviso de lote:** en `/ciclo`, *Sí, sigue en el mismo lote* o *No, es un lote nuevo*.

### Dashboard principal "Estación Trigal" (`/d/trigal-estacion`)

| Fila | Contenido |
| --- | --- |
| Estado de la estación y ciclo | Último dato recibido, ciclo y lote actuales, aviso de "¿sigue en el mismo lote?" |
| Cámara | Botones *Tomar foto ahora*, *Calibrar*, *Ver en tiempo real* y *Apagar*; última foto blanca y última UV |
| Ambiente | Temperatura, humedad, CO₂, lux, PAR y margen al rocío: valor actual y gráfica |
| Índices del ciclo | GDD diario y acumulado, DLI, fotoperiodo, Tmáx y Tmín |
| DPV | DPV promediado cada 15 min |
| Suelo | Humedad, temperatura, CE y pH de las 3 sondas |
| Sistema (plegada) | Temperatura de la caja, ventilador, estado del SCD30 y del TSL2591, datos 4G de hoy y del mes, microSD usada y libre, temperatura de la CPU, alimentación de la Pi, consumo 4G por día |

**Controles de arriba**

- **Ciclo / lote:** lista de ciclos, el más reciente primero. Los índices se calculan con las fechas y la T-base del ciclo elegido.
- **Rango de tiempo:** por defecto las últimas 24 h. Se puede elegir 7 días, 30 días o fechas exactas.
- **Refresco automático:** por defecto cada 1 min. Para gastar menos datos del 4G se recomienda 5 min.
- **Enlace "Administración":** solo lo ve `admin_trigal`.

**Colores de referencia** (valores iniciales, ajustables con el criterio agronómico de El Trigal):

| Variable | Azul | Verde | Naranja | Rojo |
| --- | --- | --- | --- | --- |
| DPV (kPa) | < 0,4 (aire muy húmedo) | 0,4 – 1,2 | > 1,2 (aire seco) | — |
| Margen al rocío (°C) | — | > 3 | 1 – 3 | < 1 (riesgo de hoja mojada y botrytis) |

### Acceso de visitantes y modo kiosco

- El usuario `trigal_visor` tiene rol *Viewer*: puede mirar, cambiar el rango y el ciclo mientras mira, y usar los botones de la cámara, pero no puede guardar ni editar nada.
- No ve la carpeta **Administración** ni el enlace a ella.
- El enlace de kiosco `https://iot.trigal-digital.com/d/trigal-estacion?orgId=1&kiosk` abre el dashboard a pantalla completa, sin menús. En kiosco se ocultan los selectores de ciclo y de tiempo: se ve el ciclo más reciente y las últimas 24 h. La tecla **Esc** sale del kiosco.
- Los botones de la cámara quedaron visibles para los visitantes por decisión del equipo. El video en vivo es lo que más datos gasta: se recomienda cerrarlo después de usarlo.

### Dashboard de administración (`/d/trigal-administracion`)

Está en la carpeta **Administración**, a la que se le quitó el rol *Viewer*. Tiene:

- Botones **Ciclo del cultivo** y **Consulta y descarga de datos**.
- La fila **Configurar ciclo y T-base**, con el formulario del ciclo.
- Un enlace para volver al dashboard principal.

No se actualiza solo, para que no se borre lo que se está escribiendo en el formulario.

### Ciclos por lote (`/ciclo`)

Cada ciclo es un intervalo de fechas asociado a un lote. Las lecturas no llevan el lote pegado: si alguien se equivoca de fecha, se corrige después sin perder datos.

**Iniciar un ciclo nuevo** (por ejemplo, al mover la estación a otro lote):

1. Abrir `https://iot.trigal-digital.com/ciclo` (o el botón del dashboard de administración) e iniciar sesión.
2. Llenar el código numérico del lote, la ubicación (bloque, nave), la fecha de siembra o trasplante y la T-base (por defecto 5 °C).
3. **Iniciar ciclo nuevo** → revisar el resumen ("Se cerrará el ciclo del lote… Empieza el lote…") → **Aceptar**. El ciclo anterior se cierra solo el día antes del nuevo inicio.
4. Comprobar que aparece en "Ciclo actual" y en "Ciclos registrados", y en el selector *Ciclo / lote* del dashboard.

**Corregir o terminar el ciclo actual:** en el mismo formulario. Si se corrige la fecha de inicio, el fin del ciclo anterior se ajusta solo.

**Aviso después de un apagado:** si la estación pasa **más de 6 h sin enviar datos** (se apagó, se quedó sin energía o la movieron), al volver aparece en naranja: *"La estación estuvo sin datos desde… hasta… ¿Sigue en el mismo lote?"*. En el formulario hay dos botones:

- **Sí, sigue en el mismo lote:** el aviso desaparece.
- **No, es un lote nuevo:** lleva a iniciar el ciclo nuevo. Usar como fecha de inicio el día en que se movió la estación.

Mientras nadie responda, los datos se siguen guardando normalmente. Un corte de menos de 6 h no genera aviso.

### Consulta y descarga de datos (`/descarga`)

| Criterio | Opciones |
| --- | --- |
| Qué datos | Lecturas de sensores, o resumen diario (Tmáx, Tmín, Tmedia, GDD y GDD acumulado, DLI, inicio y fin de luz, fotoperiodo, horas con datos) |
| Cuándo | Un ciclo o lote de la lista, o un rango de fechas |
| Horario | Hora local de inicio y fin, por ejemplo 06:00 a 18:00 |
| Variables | Las que la estación haya enviado en los últimos 30 días |
| Agrupar | Sin agrupar, 1 min, 5 min, 15 min, 1 h o 1 día (promedio) |
| Formato | **Excel**: `;` y coma decimal, fecha `2026-11-18 14:00:00`. **R/Python**: `,`, punto decimal y fecha ISO con `-05:00` |

*Consultar* muestra las primeras 20 filas; *Descargar CSV* baja el archivo. Cada fila trae el lote y la ubicación del ciclo vigente en esa fecha. El máximo es 100 000 filas por descarga; si se pasa, la página pide agrupar más o acortar el rango.

**Desde R o Python**, la página muestra el enlace exacto para los criterios elegidos. Ejemplos:

```r
library(httr)
r <- GET("https://iot.trigal-digital.com/descarga/csv?tipo=diario&ciclo=1234_2026-11-10&formato=codigo",
         authenticate("USUARIO", "CLAVE"))
datos <- read.csv(text = content(r, "text", encoding = "UTF-8"))
```

```python
import io, requests, pandas as pd
r = requests.get("https://iot.trigal-digital.com/descarga/csv",
                 params={"tipo": "lecturas", "desde": "2026-11-10", "hasta": "2026-11-14",
                         "campos": "temperatura,humedad,par,dpv", "intervalo": "15m", "formato": "codigo"},
                 auth=("USUARIO", "CLAVE"))
datos = pd.read_csv(io.StringIO(r.text), parse_dates=["fecha_hora"])
```

**Descarga rápida de un solo panel:** en Grafana, menú del panel → *Inspect* → *Data* → *Download CSV*. Baja lo que muestra esa gráfica en el rango elegido.

## 8. Cámara y fotos

Un solo programa controla la cámara: el servidor `fastapi-cam` (base del docente, optimizada por el equipo), que corre como servicio `camara` en el puerto 3333. Da el video, toma las fotos programadas y las del botón, y le pide las luces a la ESP32 por MQTT. Linux solo deja que un programa use la cámara a la vez, por eso nada más debe abrirla.

### Servicio

| Dato | Valor |
| --- | --- |
| Código | `/home/trigal/fastapi-cam/main.py` |
| Servicio | `/etc/systemd/system/camara.service` (usuario `trigal`, `uvicorn main:app --host 0.0.0.0 --port 3333`, se reinicia solo si falla) |
| Configuración | `/opt/trigal/app/trigal.env`: `HORAS_FOTO`, `CAM_CLAVE` y los datos de MQTT |
| Resolución | 1280×720 MJPG (`CAM_WIDTH`, `CAM_HEIGHT`) |
| Encendido | La cámara se enciende cuando alguien pide video o foto, y se apaga sola a los 10 s sin uso (`CAM_IDLE`) |
| Aviso de cada foto | MQTT `trigal/estacion1/camara` |

### Direcciones del servidor

| Dirección | Qué da |
| --- | --- |
| `/` | Página de prueba con los dos videos |
| `/video_feed?fps=15` | Video completo, 1280×720: para **Calibrar** en la red local. Gasta 5 a 7 GB por hora: nunca por el 4G |
| `/video_lite?fps=5&q=60` | Video liviano, 640×360: para **Ver en tiempo real** desde internet. Gasta unos 0,3 a 0,7 GB por hora |
| `/snapshot.jpg` | Un cuadro suelto del video |
| `/status` | Si la cámara está encendida |
| `/foto` (POST) | Toma una tanda de fotos (blanca + UV) |
| `/foto/estado` | Estado de la toma: `mqtt`, `reloj_sincronizado`, `ultimo_resultado` y últimas fotos |
| `/foto/ultima/blanca.jpg` y `/foto/ultima/uv.jpg` | La última foto de cada tipo |

### Secuencia de cada foto (MEF)

`PREPARAR_CAMARA` → `PEDIR_LUZ` (blanco) → `ESPERAR_LUZ` → `AJUSTAR_EXPOSICION` → `CAPTURAR` → `PEDIR_LUZ` (UV) → … → `APAGAR_LUZ` → `REPOSO`

Si la ESP32 no confirma la luz en 4 s, o la cámara falla, pasa a `ERROR`, ordena apagar los LEDs y registra la causa. La tanda completa tarda unos 8 a 12 s.

### Archivos de las fotos

```
/home/trigal/fotos/
├── automaticas/                    ← 4:00, 12:00 y 20:00
│   └── 2026-11 noviembre/
│       ├── 2026-11-21_04h00_blanca.jpg
│       └── 2026-11-21_04h00_uv.jpg
└── manuales/                       ← botón "Tomar foto ahora"
    └── 2026-11 noviembre/
        └── 2026-11-21_15h32_blanca.jpg
```

Cada foto lleva impresa la etiqueta *Estación Trigal | fecha y hora | tipo de luz*. Si la Pi no ha sincronizado la hora, la foto se toma igual pero la etiqueta dice "hora sin verificar". Cada foto pesa entre 100 y 250 KB: con 6 fotos al día, la microSD de 128 GB no se llena.

Las fotos de las 4:00 y las 20:00 se toman a oscuras, solo con la luz de los LEDs, y son las más comparables entre días. En la de las 12:00 se mezcla la luz del sol. Según lo revisado, los destellos de pocos segundos no afectan la floración del snapdragon.

### Subida a Google Drive

- Herramienta: `rclone`, con la conexión llamada `drive` y la cuenta `estacionfloreseltrigal@gmail.com`. Usa el permiso `drive.file`: la Pi solo ve las carpetas que ella misma creó.
- Carpeta en Drive: **EstacionTrigal/fotos**, con las mismas subcarpetas `automaticas` y `manuales`.
- Se ejecuta cada hora con `fotos-nube.timer`. Si no hay internet, lo intenta la hora siguiente y sube todo lo pendiente.
- Script `/usr/local/bin/fotos-nube.sh`:

```bash
#!/bin/bash
# copy: sube solo lo que falte (nunca borra nada en Drive).
# move --min-age 30d: las fotos de más de 30 días se suben si faltaban y se borran de la Pi.
ORIGEN=/home/trigal/fotos
DESTINO=drive:EstacionTrigal/fotos
OPCIONES=(--exclude "*.tmp" --transfers 2 --retries 3 --low-level-retries 10 --log-level INFO)

rclone copy "$ORIGEN" "$DESTINO" "${OPCIONES[@]}" || exit 1
rclone move "$ORIGEN" "$DESTINO" "${OPCIONES[@]}" --min-age 30d --delete-empty-src-dirs
```

Borrar fotos de la Pi **no** las borra de Drive.

### Paneles de la cámara en Grafana

Son dos paneles de tipo *Text* en modo HTML (requiere `GF_PANELS_DISABLE_SANITIZE_HTML=true` en Grafana):

- **Cámara:** botones *Calibrar* (`/video_feed`), *Ver en tiempo real* (`/video_lite`) y *Apagar*.
- **Últimas fotos:** botón *Tomar foto ahora* y las últimas fotos blanca y UV lado a lado. Al presionar el botón, consulta `/foto/estado` cada 2 s (hasta 90 s) hasta que la cámara vuelve a `REPOSO`, y entonces recarga las fotos y muestra el resultado.

Los paneles detectan por dónde se entró: si es por `iot.trigal-digital.com` usan `https://cam.trigal-digital.com/<CAM_CLAVE>` (guardada en el atributo `data-cam` del HTML); si es por IP local usan `http://<esa-ip>:3333`. Las fotos se recargan solas cada cierto tiempo mientras alguien tenga el dashboard abierto (número en milisegundos en las etiquetas `<img>`: `300000` = 5 min; se recomienda `1800000` = 30 min para gastar menos datos).

### Acceso remoto protegido

El túnel publica la cámara en `cam.trigal-digital.com`. Desde internet, toda dirección debe empezar por la clave: `https://cam.trigal-digital.com/<CAM_CLAVE>/foto/estado`. Sin la clave responde **403 No autorizado**. Desde la red local no se pide clave. La clave está en `CAM_CLAVE` de `/opt/trigal/app/trigal.env`; para verla:

```bash
grep '^CAM_CLAVE=' /opt/trigal/app/trigal.env
```

### Cambiar el horario o la frecuencia de las fotos

1. En la Pi: `sudo nano /opt/trigal/app/trigal.env`.
2. Buscar la línea `HORAS_FOTO=` y escribir las horas nuevas **en el mismo formato que ya tiene** (horas de 0 a 23). Por ejemplo, para fotos cada 6 horas en lugar de cada 8: 0, 6, 12 y 18.
3. Guardar y reiniciar: `sudo systemctl restart camara`.
4. Comprobar: `journalctl -u camara -n 20 --no-pager` no debe mostrar errores, y a la hora siguiente programada debe aparecer la foto con `ls ~/fotos/automaticas/*/ | tail`.

Más fotos al día gastan más datos al subirlas (unos 0,3 a 0,6 GB al mes con 6 fotos diarias). Si la Pi está apagada a la hora programada, esa foto se pierde: no se toma después.

### Comprobar que las fotos funcionan

```bash
systemctl is-active camara                                      # debe decir active
curl -s localhost:3333/foto/estado | python3 -m json.tool       # mqtt conectado, reloj_sincronizado true, ultimo_resultado ok
journalctl -u camara --since today --no-pager | grep -i fotos   # cada toma: inicio y dos "guardada"
ls ~/fotos/automaticas/*/ | tail                                # últimas fotos automáticas
journalctl -u fotos-nube --since today --no-pager | grep -E "Copied|ERROR"
rclone check ~/fotos drive:EstacionTrigal/fotos --one-way       # 0 differences = todo está en Drive
```

## 9. Variables, índices y criterios agronómicos

La estación calcula cuatro índices para seguir la fenología del snapdragon. El DPV se calcula con cada lectura; el DLI y el fotoperiodo, una vez al día en InfluxDB; el GDD, en Grafana, con la T-base del ciclo elegido, para poder cambiarla sin tocar la base de datos.

| Índice | Dónde se calcula | Cuándo | Unidad |
| --- | --- | --- | --- |
| DPV (déficit de presión de vapor) | Node-RED, función *Índices instantáneos* | Cada lectura; Grafana promedia cada 15 min | kPa |
| Punto y margen de rocío | Node-RED, misma función | Cada lectura | °C |
| Tmáx, Tmín, Tmedia | Tarea `indices_diarios` de InfluxDB | 00:10 de cada día | °C |
| GDD y GDD acumulado | Grafana, con la T-base del ciclo | Al abrir el dashboard | °C·día |
| DLI (integral de luz diaria) | Tarea `indices_diarios` | 00:10 | mol·m⁻²·d⁻¹ |
| Fotoperiodo, inicio y fin de luz | Tarea `indices_diarios` | 00:10 | h:m:s |

**DPV**, con T en °C y HR en %:

```latex
SVP = 0.6108 \cdot e^{\frac{17.27\,T}{T + 237.3}} \qquad DPV = SVP \cdot \left(1 - \frac{HR}{100}\right)
```

Ejemplo de control: 20 °C y 80 % dan un DPV de 0,468 kPa y un punto de rocío de 16,44 °C.

**GDD** diario (si da negativo se toma 0); el acumulado es la suma desde el inicio del ciclo:

```latex
GDD = \frac{T_{máx} + T_{mín}}{2} - T_{base}
```

Tmáx y Tmín salen de los promedios de 5 min, para que un pico suelto no altere el resultado. La T-base por defecto es 5 °C y se define en cada ciclo desde el formulario `/ciclo`. Al cambiarla, todo el histórico del ciclo se recalcula solo.

**DLI** = Σ(PPFD × Δt) / 1 000 000. Entre dos lecturas se cuenta como máximo `DT_MAX` segundos, para no inventar luz en los huecos sin datos. Con envíos cada 60 s, `DT_MAX` debe ser **150** (con el envío anterior de 5 s era 60): revisar que la tarea tenga 150 (la versión de la sección 17 ya lo trae). El campo `horas_datos` dice cuántas horas del día tuvieron PAR; un día con menos de 24 h está incompleto y su DLI sale bajo.

**Fotoperiodo** = hora de fin de luz − hora de inicio de luz. Hay luz efectiva cuando el PPFD es ≥ 2 µmol·m⁻²·s⁻¹ durante un minuto completo (`UMBRAL_LUZ`). Si no hay PAR, se calcula con los lux del TSL2591 y un umbral de 108 lux (`UMBRAL_LUX`; aproximación para luz solar de 1 µmol·m⁻²·s⁻¹ ≈ 54 lux).

### La tarea `indices_diarios`

- Programación: CRON `10 5 * * *` (05:10 UTC = 00:10 en Colombia).
- Recalcula siempre los últimos 3 días: si la Pi estuvo apagada a las 00:10, esos días se llenan la noche siguiente.
- Guarda un registro por día en la medición `diario` del bucket `estacion`: `tmax`, `tmin`, `tmedia`, `dli`, `fotoperiodo`, `inicio_luz`, `fin_luz` (en segundos), `horas_datos`, y las versiones con lux `fotoperiodo_lux`, `inicio_luz_lux`, `fin_luz_lux`.
- Para verla o editarla: InfluxDB (`http://<ip-de-la-pi>:8086`) → *Tasks* → `indices_diarios`. Los parámetros `UMBRAL_LUZ`, `UMBRAL_LUX` y `DT_MAX` están al inicio del script.
- Para revisar que corrió: *Tasks* → `indices_diarios` → *Runs*: la última fila debe decir `success`.

**Validación:** con 5 días de datos simulados se obtuvo un DLI de 24,76 mol·m⁻²·d⁻¹ (19,26 el día con 2 h sin datos, marcado con 22 h), un fotoperiodo de 11:58:00 sin contar los destellos de la cámara, y el GDD correcto con T-base de 5 y 10 °C.

### Variables que mide la estación y cómo leerlas

| Variable | Campo en InfluxDB | Sensor | Unidad | Cómo leer el dato |
| --- | --- | --- | --- | --- |
| Temperatura del aire | `temperatura` | SCD30 | °C | Base del GDD y del DPV |
| Humedad relativa del aire | `humedad` | SCD30 | % | Por encima de 90 % de forma sostenida hay riesgo de hongos |
| CO₂ | `co2` | SCD30 | ppm | Cerca de 420 = igual al aire exterior. Menos de 400 de día = las plantas lo están consumiendo y conviene ventilar. Más alto de noche es normal (las plantas respiran) |
| Iluminancia | `lux` | TSL2591 | lx | Luz como la ve el ojo humano. Sirve para comparar y como respaldo del fotoperiodo. Se satura cerca de 88 000 lx a pleno sol |
| Luz fotosintética (PPFD) | `par` | SEN0641 | µmol·m⁻²·s⁻¹ | 0 = noche o tapa puesta; unos cientos = nublado o sombra; cerca de 2000 = sol fuerte. Base del DLI y del fotoperiodo |
| Humedad del sustrato (sondas 1 a 3) | `s1_humedad`… | JXBS-3001 | % | 0 % = seco |
| Temperatura del sustrato | `s1_temp`… | JXBS-3001 | °C | Temperatura en la zona de raíces |
| Conductividad eléctrica | `s1_ce`… | JXBS-3001 | µS/cm | Sales y fertilizante: entre más alto, más sales |
| pH del sustrato | `s1_ph`… | JXBS-3001 | — | Menos de 7 ácido, más de 7 alcalino |
| Temperatura de la caja | `temp_caja` | DHT22 | °C | Control del ventilador; no es un dato del cultivo |
| DPV | `dpv` | Calculado | kPa | Demanda de agua del aire |
| Punto y margen de rocío | `punto_rocio`, `margen_rocio` | Calculado | °C | Margen pequeño = riesgo de condensación en la hoja |
| Tmáx, Tmín, Tmedia | `tmax`, `tmin`, `tmedia` (medición `diario`) | Calculado | °C | Base del GDD |
| GDD | Se calcula en Grafana | Calculado | °C·día | Calor acumulado del ciclo |
| DLI | `dli` | Calculado | mol·m⁻²·d⁻¹ | Luz total del día |
| Fotoperiodo | `fotoperiodo`, `inicio_luz`, `fin_luz` | Calculado | h:m:s | Duración del día efectivo |

### Criterios usados y de dónde salen

Cada umbral es una decisión que se puede cambiar. Algunos vienen de la literatura y otros son decisiones de diseño del equipo; ambos se señalan. Los que dicen "referencia" deben validarse con el equipo agronómico de El Trigal.

| Criterio | Valor actual | De dónde sale | Dónde se cambia |
| --- | --- | --- | --- |
| Luz efectiva para el fotoperiodo | PPFD ≥ 2 µmol·m⁻²·s⁻¹ durante un minuto completo | Michigan State University (MSU): una intensidad de solo 1 a 2 µmol·m⁻²·s⁻¹ basta para que la planta perciba día largo; es la que se usa en iluminación fotoperiódica. Así el fotoperiodo mide el día **como lo percibe la planta**. El PDF de cálculos del equipo proponía 10 µmol·m⁻²·s⁻¹; con ese valor el día sale más corto, porque no cuenta el amanecer ni el atardecer. La regla del minuto completo es de diseño: deja por fuera los destellos de los LEDs de la cámara | `UMBRAL_LUZ` en la tarea `indices_diarios` |
| Luz efectiva con lux (si no hay PAR) | 108 lx | Mismo umbral convertido: para luz solar, 1 µmol·m⁻²·s⁻¹ ≈ 54 lx (MSU). Es solo un respaldo: bajo plásticos o luz artificial la conversión cambia | `UMBRAL_LUX` en la misma tarea |
| Hueco máximo entre lecturas para el DLI | 150 s | Diseño: 2,5 veces el intervalo de envío (60 s), para no inventar luz cuando faltan datos | `DT_MAX` en la misma tarea |
| T-base del GDD | 5 °C por defecto | Elegida por el equipo, editable por ciclo. Referencia: MSU estimó 36 °F (≈ 2 °C) para snapdragon 'Montego' de maceta; los cultivares de flor de corte pueden ser distintos | Formulario `/ciclo`, en cada ciclo |
| Método del GDD | (Tmáx + Tmín)/2 − T-base, mínimo 0 | Método clásico del promedio. Usar promedios de 5 min para Tmáx y Tmín es diseño: evita que un pico suelto altere el día | Tarea `indices_diarios` y paneles de GDD |
| Presión de saturación del DPV | 0,6108·e^(17,27·T/(T+237,3)) | Ecuación de la FAO-56 | Función *Índices instantáneos* de Node-RED |
| DLI de referencia | 11 mol·m⁻²·d⁻¹ | MSU clasifica el snapdragon como cultivo sensible al DLI: su floración se satura a 11 mol·m⁻²·d⁻¹ o más. Es el mínimo para florecer rápido, no un valor ideal | Umbrales (*Thresholds*) del panel de DLI en Grafana |
| Colores del DPV | Azul < 0,4 kPa; verde en el rango intermedio; naranja por encima de 1,2 a 1,5 kPa | MSU recomienda mantener el DPV por encima de 0,5 kPa en la etapa final, para que la planta transpire y se eviten enfermedades foliares. Por encima de 1,5 kPa la pérdida de agua es alta y la fotosíntesis puede bajar. El rango verde exacto es referencia | Umbrales del panel de DPV |
| Margen al rocío | Rojo < 1 °C; naranja 1 a 3 °C; verde > 3 °C | Diseño: cuando la temperatura del aire se acerca al punto de rocío, el agua se condensa en las hojas (hoja mojada, riesgo de botrytis). Referencia | Umbrales del panel de margen al rocío |
| Humedad relativa alta | 90 % | Referencia de partida para riesgo de hongos | Umbrales del panel de humedad |
| Día incompleto | Menos de 23 h con datos de PAR | Diseño: con huecos, el DLI sale más bajo de lo real | Tabla de resumen diario en Grafana |
| Aviso de "¿mismo lote?" | Más de 6 h sin datos | Diseño: un corte corto no implica que la estación se haya movido | `const HORAS = 6;` en la pestaña *Ciclos del cultivo* de Node-RED |
| CO₂ del aire exterior | Unos 420 ppm | Concentración actual del aire libre; se usa para calibrar el SCD30 | Calibración del SCD30 (sección 12) |

### Luz natural de referencia en la zona

El Trigal compartió los valores de luz natural de Medellín, tomados de una presentación técnica sobre cantidad de luz. Sirven para comprobar que lo que mide la estación es razonable; no cambian ningún umbral.

| Dato | Valor de referencia | Cómo usarlo con la estación |
| --- | --- | --- |
| Fotoperiodo natural | Unas 12 h todo el año: 11 h 46 min en diciembre (día más corto) y 12 h 29 min en junio (día más largo) | El `fotoperiodo` diario debe quedar cerca de ese rango. Puede variar unos minutos, porque el umbral de 2 µmol·m⁻²·s⁻¹ cuenta parte del amanecer y del atardecer, y las montañas tapan el sol temprano o tarde. Muy por encima de 12 h 30 min indica luz artificial (iluminación nocturna, LEDs) o un error; muy por debajo, sombra sobre el sensor o datos faltantes |
| DLI exterior | Unos 31 mol·m⁻²·d⁻¹ | Techo de referencia: el DLI dentro del invernadero no debería superarlo de forma habitual |
| DLI estimado dentro del invernadero | 19 a 22 mol·m⁻²·d⁻¹, suponiendo que la cubierta deja pasar del 60 al 70 % de la luz | Rango esperado del `dli` en un día típico; se puede marcar como franja en el panel de DLI de Grafana. Días muy por debajo indican cielo muy nublado, plástico sucio o sensor sombreado. El promedio del DLI de varias semanas dividido entre 31 da una estimación aproximada de cuánta luz deja pasar la cubierta |

Como el día natural casi no cambia en el año, la luz que recibe el cultivo varía sobre todo por el clima y el estado del invernadero. Por eso, en esta zona el DLI es el índice más útil para seguir la luz; el fotoperiodo sirve más para detectar luz artificial o fallas. La validación con datos simulados (11 h 58 min) cae dentro del rango esperado.

En crisantemo, que es de día corto, un día natural de unas 12 h ya favorece la floración. Si el cultivo usa iluminación nocturna en la etapa vegetativa y esa luz supera el umbral en el sensor, aparecerá como PAR de noche o como un fotoperiodo más largo.

Antes de usar los colores de los paneles para decisiones, revisar en cada panel (*Edit* → *Thresholds*) qué valores tiene hoy, porque se ajustaron durante las pruebas.

### Adaptar la estación a otro cultivo

La estación mide variables generales del ambiente, así que sirve para cualquier cultivo bajo invernadero, por ejemplo crisantemo. Lo que depende del cultivo son los umbrales con que se interpretan los datos y algunos horarios. Los sensores y el firmware no cambian.

| Qué depende del cultivo | Valor para snapdragon | Qué revisar para otro cultivo | Dónde y cómo se cambia |
| --- | --- | --- | --- |
| T-base del GDD | 5 °C | La T-base del cultivo o cultivar, según la literatura o los registros de El Trigal | En `/ciclo`, al iniciar el ciclo del lote. Cada lote puede tener su propia T-base, así que varios cultivos conviven sin cambiar código |
| GDD acumulado para el corte | No definido | Los grados-día que el cultivar necesita hasta el corte, sacados de ciclos anteriores | Panel de GDD acumulado → *Edit* → *Thresholds* → agregar un umbral con ese valor y activar *Show thresholds* como línea |
| Respuesta al fotoperiodo | Snapdragon: día largo facultativo | Si el cultivo es de día corto, lo que importa es la duración de la noche (24 h − fotoperiodo). El umbral de 2 µmol·m⁻²·s⁻¹ sigue siendo válido, porque mide lo que la planta percibe | `UMBRAL_LUZ` solo si se quiere otro criterio |
| Horario de las fotos | 4:00, 12:00 y 20:00 | **Crisantemo:** es una planta de día corto cualitativa; una interrupción de la noche con luz puede inhibir su floración. Con crisantemo, las fotos deben tomarse solo con luz de día (por ejemplo 8:00, 12:00 y 16:00) | `HORAS_FOTO` en `/opt/trigal/app/trigal.env` (sección 8) |
| DLI de referencia | 11 mol·m⁻²·d⁻¹ | El DLI de saturación o el recomendado para el cultivo | Panel de DLI → *Thresholds* |
| Rangos de DPV, humedad y margen al rocío | Ver tabla anterior | Los rangos del cultivo y de su etapa (propagación, vegetativa, floración) | Paneles correspondientes → *Thresholds* |
| Ronda de las sondas de suelo | 15 min (sustrato) | En suelo de campo, que cambia más rápido, 5 min | `T_SUELO` en el firmware (sección 4) |
| Altitud del sitio | Rionegro, unos 2100 m | Si la estación se usa a otra altitud, el SCD30 debe compensarla | `setAltitudeCompensation()` en el programa de calibración del SCD30 (sección 12). El sensor guarda el valor en su memoria y PAYLOAD.ino no lo cambia |
| Nombre del cultivo | Lote y ubicación en `/ciclo` | El formulario no tiene un campo "cultivo" | Escribir el cultivo en la ubicación del ciclo, o agregar el campo al formulario en la pestaña *Ciclos del cultivo* de Node-RED |

**Paso a paso para cambiar un umbral de color en Grafana:** entrar como `admin_trigal` → en el panel, menú → *Edit* → panel derecho → *Thresholds* → cambiar los números o agregar uno con *+ Add threshold* → *Save dashboard*. Para que el umbral se vea como línea en la gráfica: *Thresholds* → *Show thresholds* → *As lines*.

**Paso a paso para cambiar un umbral de cálculo** (`UMBRAL_LUZ`, `UMBRAL_LUX`, `DT_MAX`): sección 12, "Cambiar los umbrales de luz", y luego recalcular los días anteriores.

### Fuentes de los criterios

- [MSU — Long-day lighting (1 a 2 µmol·m⁻²·s⁻¹ para iluminación fotoperiódica)](https://www.canr.msu.edu/floriculture/uploads/files/long%20day%20lighting.pdf)
- [MSU — Lighting applications](https://www.canr.msu.edu/floriculture/uploads/files/lightingapplications.pdf)
- [MSU — Light units and sensors (1 µmol·m⁻²·s⁻¹ = 54 lux para luz solar)](https://www.canr.msu.edu/uploads/resources/pdfs/light-units-and-sensors.pdf)
- [MSU — Fundamentals of temperature (T-base del snapdragon: 36 °F)](https://www.canr.msu.edu/uploads/resources/pdfs/fundamentalsoftemperature.pdf)
- [MSU — Light and temperature responses of bedding plants (snapdragon sensible al DLI, ≥ 11 mol·m⁻²·d⁻¹)](https://www.canr.msu.edu/floriculture/uploads/files/Light%20and%20temp%20on%20bedding.pdf)
- [MSU Extension — DPV frente a humedad relativa (> 0,5 kPa)](https://www.canr.msu.edu/news/why_should_greenhouse_growers_pay_attention_to_vapor_pressure_deficit_and_n)
- [MSU — Water vapor-pressure deficit (> 1,5 kPa alto)](https://bluedynamo.msu.edu/floriculture/uploads/files/Water%20VPD.pdf)
- [Journal of Plant Growth Regulation (2020) — Crisantemo, planta de día corto cualitativa, e interrupción nocturna](https://link.springer.com/content/pdf/10.1007/s00344-019-10002-5.pdf)
- FAO-56, *Crop evapotranspiration*, ecuación de la presión de vapor de saturación.
- Flores El Trigal: diapositiva "Natural light conditions in Medellín" (fotoperiodo, DLI exterior y DLI estimado en invernadero), compartida con el equipo en noviembre de 2026.

## 10. Conectividad: SIM, 4G, WiFi, túnel y dominio

En campo la estación sale a internet solo por el 4G de Claro. Un túnel de Cloudflare publica el dashboard, las páginas y la cámara en `trigal-digital.com` sin abrir puertos. El WiFi se usa solo para entrar a la Pi desde la red local.

### SIM y plan de datos

| Dato | Valor |
| --- | --- |
| Operador | Claro, línea prepago |
| Número de la línea | 311 620 1272 (también en el empaque de la SIM; guardarlo) |
| Tamaño y ranura | Nano SIM, en la ranura **Nano SIM1** del HAT |
| APN | `internet.comcel.com.co` (guardado en el perfil 1 del módulo como `IPV4V6`) |
| Activación (solo la primera vez, ya hecha) | Marcar \*611#, registrar los datos y comprar un paquete |
| Recarga | **Cada mes**: comprar un paquete de datos para el 311 620 1272 en cualquier punto de recarga o en Mi Claro |
| Cancelación | Si la línea pasa más de 2 meses sin recarga, Claro cancela el plan |
| Vencimiento del empaque | 4/02/2027 |
| PIN y PUK | En Bitwarden |
| Consumo estimado | 3 a 5 GB al mes; **paquete recomendado de 8 a 10 GB** hasta medir el real |

| Qué gasta datos | Estimado al mes |
| --- | --- |
| Túnel de Cloudflare y Pi Connect, aunque nadie mire | 0,5 – 1 GB |
| Subida de fotos a Drive | 0,3 – 0,6 GB |
| Ver el dashboard (2 o 3 personas, 15–20 min al día) | 1 – 2 GB |
| Video en vivo (unas 2 h al mes) | 1 – 1,5 GB |

El consumo real se ve en la fila **Sistema** del dashboard ("Datos 4G hoy", "Datos 4G este mes" y "Consumo 4G por día") o con `vnstat -i usb0 -d`. En el panel "Datos 4G este mes" hay que poner como máximo el tamaño del paquete en MB (sección 12).

**Síntoma de la SIM sin datos:** el dashboard da Error 1033, Pi Connect se cae y en la Pi toda página responde `302` hacia `compras.claro.com.co`. Solución: recargar o comprar un paquete en Mi Claro. No hay que tocar la Pi: el vigilante reconecta solo.

### Módulo 4G (SIM7600G-H en HAT Waveshare M.2)

| Elemento | Configuración |
| --- | --- |
| Conexión a la Pi | USB a un puerto azul |
| Switches del reverso | Todas las posiciones "A" en ON; "B" y "B/C" en OFF |
| Frente | DIP PWR-D5 / RST-D6 en OFF; switch deslizante en EXT PWR (USB-C, 5 V / 3 A) |
| Modo | RNDIS (`AT+CUSBPIDSWITCH=9011,1,1`): la Pi ve el 4G como la interfaz `usb0` |
| Perfil de red | `claro4g` en NetworkManager, métrica 700, reintentos sin límite |
| ModemManager | Desactivado (si se activa, interfiere con la ESP32 y el módulo) |
| Puerto de comandos AT | `/dev/serial/by-id/usb-SimTech__Incorporated_SimTech__Incorporated_0123456789ABCDEF-if04-port0` |
| GPS del módulo | No se usa |

Los nombres `ttyUSB0`, `ttyUSB1`… cambian en cada arranque; por eso siempre se usa la ruta fija del puerto AT (interfaz if04). Las otras interfaces del módulo son diagnóstico (if02), GPS (if03), PPP (if05) y audio (if06).

**Vigilante del 4G** (`/usr/local/bin/lte-watchdog.sh`, cada 5 min): prueba internet por IPv4 e IPv6 (ping y web). Si falla, reactiva `claro4g`; después de 3 revisiones seguidas sin red, reinicia el módulo con `AT+CRESET` por el puerto AT. Su historial: `journalctl -t lte-watchdog` (vacío = nunca hubo fallas).

**Comprobar el 4G:**

```bash
curl -4 --interface usb0 -s -o /dev/null -m 10 -w "IPv4 -> %{http_code}\n" http://connectivitycheck.gstatic.com/generate_204
curl -6 --interface usb0 -s -o /dev/null -m 10 -w "IPv6 -> %{http_code}\n" http://connectivitycheck.gstatic.com/generate_204
ping -I usb0 -c 3 -W 5 8.8.8.8
```

Lo correcto es `204` en las dos líneas y respuesta al ping (unos 40 ms). `302` significa que la SIM no tiene datos.

### WiFi: solo para la red local

Cada red WiFi se configura para que **no** sea la salida a internet. Así el WiFi sirve para SSH y el internet siempre sale por el 4G. Esto es obligatorio en la universidad: su WiFi bloquea el puerto 7844 que usa el túnel, y el dashboard público daría Error 1033. El procedimiento para agregar una red está en la sección 12.

Todo lo que use IPv6 (Drive, Pi Connect, apt, Docker) sale por el 4G aunque haya WiFi, porque el WiFi de la universidad solo da IPv4.

### Dominio y túnel de Cloudflare

| Elemento | Valor |
| --- | --- |
| Dominio | `trigal-digital.com`, registrado en Hostinger a nombre de El Trigal |
| DNS | En Cloudflare, plan gratuito. Nameservers `john.ns.cloudflare.com` y `kinsley.ns.cloudflare.com`. Los registros anteriores quedaron en modo "DNS only" |
| Cuenta Cloudflare | `estacionfloreseltrigal@gmail.com`; Julián Guevara (El Trigal) es administrador |
| Túnel | `rpi4trigal`, con el conector `cloudflared` en un contenedor Docker de la Pi |
| Equipo Zero Trust | `trigal` |

**Rutas del túnel** (one.dash.cloudflare.com → *Networks* → *Tunnels* → `rpi4trigal` → *Rutas*). Cloudflare las revisa en orden: la de Node-RED tiene que ir **antes** que la de Grafana.

| Orden | Subdominio | Ruta | Servicio |
| --- | --- | --- | --- |
| 1 | `iot.trigal-digital.com` | `^/(ciclo\|descarga)` | `http://localhost:1880` (Node-RED, solo esas dos páginas) |
| 2 | `iot.trigal-digital.com` | Vacía | `http://localhost:3000` (Grafana) |
| 3 | `cam.trigal-digital.com` | Vacía | `http://localhost:3333` (cámara, protegida con `CAM_CLAVE`) |

Nunca se publica el editor de Node-RED, InfluxDB ni Portainer.

**Cloudflare Access** (inicio de sesión extra solo para ciertos correos) no se activó, porque Cloudflare pide registrar una tarjeta aunque sea gratuito. Es opcional y solo lo debería activar El Trigal si lo decide. Hoy la seguridad la dan los usuarios de Grafana y de Node-RED y la clave de la cámara.

**Error 1033** en el navegador = Cloudflare no encuentra el túnel: la Pi está apagada, sin 4G, sin saldo, o saliendo por un WiFi que bloquea el túnel (sección 13).

## 11. Cómo cambiar usuarios y contraseñas

Cada servicio tiene su propia clave. Al recibir la estación, El Trigal debería cambiarlas todas. Después de cada cambio hay que actualizar la entrada en Bitwarden y, cuando la tabla lo indique, cambiar la clave también en el programa que la usa.

| Usuario | Dónde se usa | Si se cambia, actualizar también en… |
| --- | --- | --- |
| `trigal` (Linux) | SSH y `sudo` | Nada más |
| `admin_trigal` (Grafana) | Administración del dashboard | Variable `GRAFANA_PASSWORD` del stack en Portainer (solo como registro) |
| `trigal_visor` (Grafana) | Visitantes | Avisar a quienes lo usan |
| `admin_trigal` (Node-RED) | Editor de flujos | Nada más |
| Usuario de `/ciclo` y `/descarga` | Formularios y scripts de R/Python | Scripts que descarguen datos |
| `estacion` (Mosquitto) | Puente y cámara | `MQTT_PASS` en `trigal.env` |
| `nodered` (Mosquitto) | Node-RED | Nodo de configuración del broker en Node-RED |
| Tokens de InfluxDB | Node-RED, Grafana, `metricas-sistema` | Cada programa que usa ese token |
| `CAM_CLAVE` | Cámara desde internet | Paneles de cámara de Grafana |

### Contraseña del usuario `trigal` de la Raspberry Pi

En la Pi, escribir `passwd`. Pide la clave actual y dos veces la nueva (no se ven al escribir).

### Grafana: administrador `admin_trigal`

```bash
docker exec -it grafana grafana cli admin reset-admin-password 'NUEVA_CLAVE'
```

Debe responder `Admin password changed successfully`. Después, en Portainer → *Stacks* → `grafana` → *Environment variables*, poner la misma clave en `GRAFANA_PASSWORD` y *Update the stack*. Esa variable solo se usa al crear Grafana, pero así lo documentado coincide con lo real. También se puede cambiar desde Grafana: avatar (arriba a la derecha) → *Profile* → *Change password*.

### Grafana: usuario de visitantes y usuarios nuevos

- **Cambiar la clave de `trigal_visor`:** entrar como `admin_trigal` → *Administration* → *Users and access* → *Users* → `trigal_visor` → *Change password*.
- **Crear un usuario por persona:** *Users* → *New user* → nombre, correo como *Username*, clave temporal → *Create*. Revisar que en *Organizations* tenga el rol **Viewer** (o **Editor** / **Admin** si va a modificar paneles). Grafana no tiene configurado el envío de correos, así que las invitaciones se crean a mano.
- **Quitar el acceso a alguien:** *Users* → la persona → *Delete user*.
- Solo `admin_trigal` y quienes deban editar pueden tener rol distinto de *Viewer*, porque los paneles HTML de la cámara ejecutan código en el navegador.

### Node-RED: editor (`admin_trigal`)

1. Generar el hash de la clave nueva en la Pi (pide la clave dos veces):

   ```bash
   sudo apt install -y apache2-utils     # solo la primera vez
   htpasswd -nBC 8 "" | tr -d ':\n' ; echo
   ```

   Sale una línea que empieza por `$2y$08$`. Copiarla completa.
2. `sudo nano /opt/trigal/nodered/data/settings.js` → **Ctrl+W** → `adminAuth` → en la línea `password: "..."` reemplazar el hash viejo por el nuevo, entre comillas y con la coma al final.
3. Reiniciar y revisar: `docker restart node-red` y `docker logs --tail 15 node-red`. Debe terminar en `Started flows`. Si sale un error de `settings.js`, casi siempre falta una coma o una comilla.

### Node-RED: páginas `/ciclo` y `/descarga`

1. Generar el hash (el espacio al inicio evita que la clave quede en el historial):

   ```bash
    docker exec node-red node -e "console.log(require('bcryptjs').hashSync(process.argv[1], 8))" 'NUEVA_CLAVE'
   ```
2. `sudo nano /opt/trigal/nodered/data/settings.js` → **Ctrl+W** → `httpNodeAuth` → la línea debe quedar `httpNodeAuth: {user:"USUARIO",pass:"$2b$08$..."},` con el usuario deseado y el hash nuevo.
3. `docker restart node-red` y comprobar que `/descarga` pide la clave nueva.
4. Cambiar la clave en los scripts de R o Python que descarguen datos.

### Mosquitto: usuarios `estacion` y `nodered`

1. Cambiar la clave (sin `-c`, que borraría a los demás usuarios). Pide la clave dos veces:

   ```bash
   docker run --rm -it -v /opt/trigal/mosquitto/config:/mosquitto/config eclipse-mosquitto:2 mosquitto_passwd /mosquitto/config/passwd estacion
   sudo chown 1883:1883 /opt/trigal/mosquitto/config/passwd && sudo chmod 0700 /opt/trigal/mosquitto/config/passwd
   docker restart mosquitto
   ```

   Para `nodered`, el mismo comando cambiando el último `estacion` por `nodered`.
2. **Si se cambió `estacion`:** `sudo nano /opt/trigal/app/trigal.env` → `MQTT_PASS=` con la clave nueva → `sudo systemctl restart trigal-serial camara`. En `journalctl -u trigal-serial -n 10` debe salir `Conectado a Mosquitto`.
3. **Si se cambió `nodered`:** en el editor de Node-RED, doble clic en cualquier nodo MQTT → lápiz junto al servidor `mosquitto-local` → pestaña *Security* → nueva clave → *Update* → *Implementar*. Los nodos MQTT deben quedar en verde (*connected*).
4. Para crear un usuario nuevo, el mismo comando con otro nombre.

### InfluxDB: administrador

En la interfaz de InfluxDB, menú del usuario → cambiar contraseña, o por terminal:

```bash
docker exec -it influxdb influx user password -n admin_trigal
```

### InfluxDB: tokens (Node-RED, Grafana y métricas)

Un token no se cambia: se crea uno nuevo, se reemplaza donde se usa y se borra el viejo.

1. InfluxDB → *Load Data* → *API Tokens* → *Generate API Token* → *Custom API Token*.
2. Permisos sobre el bucket `estacion`: **Read + Write** para Node-RED; **Read** para Grafana; **Write** para `metricas-sistema`. *Generate* y copiar el token (solo se muestra una vez).
3. Reemplazarlo:
   - **Node-RED:** doble clic en el nodo *Guardar en InfluxDB* → lápiz de `influxdb-local` → *Token* → *Update* → *Implementar*.
   - **Grafana:** *Connections* → *Data sources* → la fuente de InfluxDB → *Token* → *Save & test* (debe decir que funciona).
   - **Métricas del sistema:** `sudo nano /opt/trigal/app/influx-sistema.env` → `INFLUX_TOKEN=` con el token nuevo → probar con `sudo /usr/local/bin/metricas-sistema`.
4. Comprobar que los datos siguen llegando y borrar el token viejo en *API Tokens*.

### Portainer

`https://<ip-de-la-pi>:9443` → menú del usuario (arriba a la derecha) → *My account* → *Change user password*.

### Clave de la cámara (`CAM_CLAVE`)

1. Generar una clave nueva: `openssl rand -hex 16`.
2. `sudo nano /opt/trigal/app/trigal.env` → `CAM_CLAVE=` con la clave nueva → `sudo systemctl restart camara`.
3. Comprobar: `journalctl -u camara -n 30 --no-pager | grep -i protecci` debe decir `Protección remota: ACTIVA`.
4. En Grafana, editar los dos paneles de la cámara (*Edit*) y reemplazar la clave vieja por la nueva en el atributo `data-cam` → *Save dashboard*.
5. Los enlaces guardados con la clave vieja dejan de funcionar.

### Cuenta de Google del proyecto

`estacionfloreseltrigal@gmail.com` es la llave de Drive y de Cloudflare. En [myaccount.google.com](https://myaccount.google.com) → *Seguridad*: cambiar la contraseña, la verificación en dos pasos y el correo y teléfono de recuperación (deben ser de El Trigal, no de un estudiante). Guardar los códigos de respaldo en Bitwarden.

Si después la subida de fotos falla con un error de autorización, hay que reautorizar rclone (sección 12, "Reautorizar Google Drive").

### Cloudflare

Se entra con la cuenta de Google del proyecto. Para dar o quitar acceso a otra persona: [dash.cloudflare.com](https://dash.cloudflare.com) → *Manage account* → *Members* → *Invite* (o quitar). Julián Guevara ya es administrador.

### Raspberry Pi Connect

Se administra en [id.raspberrypi.com](https://id.raspberrypi.com) con la cuenta Raspberry Pi ID del proyecto. Si se cambia la cuenta, en la Pi: `rpi-connect signout` y luego `rpi-connect signin`, y abrir el enlace que muestra.

### PIN de la SIM

La SIM debe quedar **sin PIN**, porque la Pi no lo puede escribir al arrancar. Para cambiar o quitar el PIN, poner la SIM en un celular y hacerlo desde los ajustes de seguridad de la SIM.

## 12. Cómo cambiar configuraciones y funciones

Antes de cualquier cambio, guardar una copia de lo que se va a modificar (exportar el flujo, el dashboard o la tarea, o copiar el archivo con `sudo cp archivo archivo.respaldo`). Así se puede volver atrás.

| Quiero cambiar… | Dónde |
| --- | --- |
| Horario o frecuencia de las fotos | Sección 8, "Cambiar el horario o la frecuencia de las fotos" |
| Cada cuánto lee o envía la ESP32, el ventilador o las direcciones Modbus | Sección 4, "Constantes que se pueden ajustar" y "Cómo cargar el firmware" |
| Usuarios y contraseñas | Sección 11 |
| La SIM o el operador | Abajo |
| Una red WiFi | Abajo |
| Ciclo, lote o T-base | Sección 7, "Ciclos por lote" |
| Todo lo demás | Abajo |

### Cambiar la SIM o el operador móvil

1. Apagar la Pi (`sudo poweroff`) y desconectar el módulo 4G.
2. Cambiar la SIM en la ranura **Nano SIM1**. La SIM nueva debe tener plan de datos y **no tener PIN**.
3. Encender. Si la SIM es de Claro, no hay que hacer nada más.
4. **Si es de otro operador,** cambiar el APN en el módulo (preguntar el APN al operador):

   ```bash
   P=/dev/serial/by-id/usb-SimTech__Incorporated_SimTech__Incorporated_0123456789ABCDEF-if04-port0
   sudo timeout 6 bash -c "stty -F $P 115200 raw -echo 2>/dev/null; exec 3<>$P; printf 'AT+CGDCONT=1,\"IPV4V6\",\"NUEVO_APN\"\r' >&3; sleep 1; printf 'AT+CGDCONT?\r' >&3; sleep 1; timeout 2 cat <&3"
   ```

   La respuesta debe mostrar `1,"IPV4V6","NUEVO_APN"`. Luego reiniciar el módulo y esperar 2 minutos:

   ```bash
   sudo timeout 4 bash -c "stty -F $P 115200 raw -echo 2>/dev/null; exec 3<>$P; printf 'AT+CRESET\r' >&3"
   ```
5. Comprobar con los `curl` de la sección 10: deben dar `204`.
6. Actualizar en Bitwarden el número de la línea y en este manual el operador y el APN.

### Agregar una red WiFi (solo para acceso local)

Con la Pi encendida, desde Pi Connect o con teclado y pantalla:

```bash
sudo nmcli dev wifi connect "NOMBRE_RED" password "CLAVE_WIFI"
sudo nmcli connection modify "NOMBRE_RED" ipv4.never-default yes ipv6.never-default yes
sudo nmcli connection up "NOMBRE_RED"
ip route get 1.1.1.1
```

La última línea debe decir `dev usb0`: el internet sigue saliendo por el 4G. Si la red ya estaba guardada y la Pi está conectada a ella, basta con:

```bash
WIFI=$(nmcli -t -f NAME,DEVICE connection show --active | grep ':wlan0$' | cut -d: -f1); echo "Wifi: $WIFI"
sudo nmcli connection modify "$WIFI" ipv4.never-default yes ipv6.never-default yes
sudo nmcli connection up "$WIFI"
```

Para olvidar una red: `sudo nmcli connection delete "NOMBRE_RED"`.

### Agregar un sensor o una variable nueva

1. En el firmware, leer el sensor y agregar el campo a la trama `$EST` con un nombre corto en minúsculas, sin tildes ni espacios (por ejemplo `hs=...`).
2. En `/opt/trigal/app/serial_mqtt.py`, solo si el campo nuevo no aparece en InfluxDB unos minutos después de cargar el firmware, agregar el nombre corto y el nombre largo que tendrá en InfluxDB en el diccionario de nombres que corresponda (`CAMPOS_AMBIENTE`, `CAMPOS_SISTEMA` o `CAMPOS_SUELO`) y reiniciar: `sudo systemctl restart trigal-serial`.
3. El campo aparece solo en InfluxDB (medición `datos`) y en la lista de variables de `/descarga`.
4. Agregar un panel en Grafana (abajo).
5. Si sirve para un índice, agregar el cálculo en la función *Índices instantáneos* de Node-RED (instantáneo) o en la tarea `indices_diarios` (diario).

### Agregar o modificar un panel en Grafana

Como `admin_trigal`: *Edit* → *Add* → *Visualization* → fuente InfluxDB → editor de código (Flux). Consulta base, cambiando el nombre del campo:

```
from(bucket: "estacion")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "datos" and r._field == "temperatura")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

Para un valor actual (*Stat*), cambiar la última línea por `|> last()`. Para las métricas del sistema, la medición es `sistema`; para los resúmenes diarios, `diario`. Las gráficas de semanas o meses deben llevar `aggregateWindow`, porque llega un dato por minuto. Unidad, decimales y colores se cambian en el panel derecho (*Standard options* y *Thresholds*). Terminar con *Save dashboard*.

En los paneles de suelo, *Connect null values* debe estar en **Always**, porque las sondas solo envían cada 15 min.

### Cambiar el máximo del panel "Datos 4G este mes"

*Edit* en el panel → *Standard options* → *Max* = tamaño del paquete en MB (por ejemplo 10000 para 10 GB) → *Save dashboard*. Los colores cambian solos al 80 % y al 95 %.

### Cambiar la actualización automática

- **Dashboard completo:** selector de refresco arriba a la derecha (por ejemplo `5m`) → *Save dashboard*.
- **Fotos del panel de la cámara:** *Edit* en el panel "Últimas fotos" y cambiar en las dos etiquetas `<img>` el número `300000` (5 min) por `1800000` (30 min) → *Save dashboard*.

### Cambiar qué ven los visitantes

- **Ocultar un dashboard:** moverlo a la carpeta **Administración** (*Dashboard settings* → *Folder*).
- **Ocultar un panel:** como los visitantes ven el mismo dashboard principal, el panel se debe mover al dashboard de administración: copiarlo (*More* → *Copy*), pegarlo en el de administración y borrarlo del principal.
- **Que todos entren directo al dashboard:** *Administration* → *General* → *Default preferences* → *Home Dashboard* = Estación Trigal.
- **Permitir mirar sin iniciar sesión (opcional, no activado):** en Portainer → *Stacks* → `grafana` → *Editor*, cambiar `GF_AUTH_ANONYMOUS_ENABLED=false` por `true` y agregar debajo `- GF_AUTH_ANONYMOUS_ORG_NAME=Main Org.`, `- GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` y `- GF_AUTH_ANONYMOUS_HIDE_VERSION=true` → *Update the stack*. Desde ahí cualquiera con el enlace ve el dashboard.

### Cambiar los umbrales de luz del DLI y el fotoperiodo

InfluxDB → *Tasks* → `indices_diarios` → *Edit Task* → al inicio del script cambiar `UMBRAL_LUZ` (2,0), `UMBRAL_LUX` (108,0) o `DT_MAX` (debe ser 150,0 con envíos cada 60 s) → *Save*. Los días anteriores no cambian solos: recalcularlos (abajo).

### Recalcular días anteriores

1. InfluxDB → *Data Explorer* → *Script Editor*.
2. Abrir la tarea `indices_diarios` y copiar todo su script.
3. Pegarlo en el *Script Editor*, borrar la línea que empieza por `option task` y cambiar estas dos líneas por fechas fijas:

   ```
   fin = 2026-11-30T00:00:00-05:00
   inicio = 2026-11-01T00:00:00-05:00
   ```
4. *Submit*. Los días de ese rango se sobrescriben. Puede no mostrar gráfica; lo importante es que no salga un error en rojo.

### Cambiar el tiempo del aviso "¿sigue en el mismo lote?"

En el editor de Node-RED, pestaña **Ciclos del cultivo** → la función que contiene `const HORAS = 6;` → cambiar el número de horas → *Implementar*.

### Modificar un flujo de Node-RED

1. Exportar la pestaña actual: menú ☰ → *Exportar* → *Descargar*. Guardarla en el repositorio con la fecha.
2. Hacer el cambio en `http://<ip-de-la-pi>:1880`. Para probar sin ensuciar la base de datos, usar los nodos de inyección de la rama "Prueba de índices", que no guardan en InfluxDB.
3. *Implementar* y revisar la pestaña de depuración (🐞): no deben salir errores en rojo.
4. **Importar un flujo:** menú ☰ → *Importar* → elegir el archivo. Si avisa que hay nodos repetidos, *Importar copia*. Después revisar en cada nodo MQTT que el servidor sea `mosquitto-local` y en cada nodo de InfluxDB que sea `influxdb-local` (los que tienen la clave y el token). No borrar esos nodos de configuración.

### Cambiar o reemplazar la cámara

- **Enfocar o encuadrar:** en la red local, botón *Calibrar* del dashboard y ajustar los anillos de zoom y foco del lente varifocal. Para tener luz mientras se ajusta, enviar `{"cmd":"blanco","seg":120}` (sección 4). Volver a *Apagar* al terminar.
- **Otra cámara USB:** conectarla y revisar que aparece: `v4l2-ctl --list-devices` y `v4l2-ctl -d /dev/video0 --list-formats-ext`. Debe ofrecer MJPG. Si no da 1280×720, cambiar `CAM_WIDTH` y `CAM_HEIGHT` en `main.py` por un tamaño que ofrezca y `sudo systemctl restart camara`. Una resolución con muchos cuadros por segundo puede saturar el USB de la Pi.
- **Probar:** abrir `http://<ip-de-la-pi>:3333` y luego tomar una foto con el botón.

### Reautorizar Google Drive o cambiar la cuenta

1. Desde un computador en la misma red: `ssh -L 53682:localhost:53682 trigal@<ip-de-la-pi>`.
2. En esa sesión: `rclone config reconnect drive:` y responder `y` cuando pregunte si usar el navegador.
3. Copiar el enlace completo `http://127.0.0.1:53682/auth?state=...`, abrirlo en una ventana privada del computador, entrar con la cuenta del proyecto y *Permitir*. Debe salir *Success!*.
4. Si sale "state did not match": **Ctrl+C**, `pkill rclone` y repetir con un enlace nuevo en otra ventana privada.
5. Probar: `sudo systemctl start fotos-nube` y `journalctl -u fotos-nube -n 20`.

Para usar otra cuenta de Google se hace lo mismo con `rclone config` → borrar `drive` (`d`) y crearlo de nuevo (`n`, tipo `drive`, scope `3`). Para cambiar la carpeta de destino, editar `DESTINO=` en `/usr/local/bin/fotos-nube.sh`.

### Cambiar cuántos días se guardan las fotos en la Pi

`sudo nano /usr/local/bin/fotos-nube.sh` → cambiar `--min-age 30d` (por ejemplo `90d`). Las fotos siempre quedan en Drive.

### Borrar fotos de prueba

```bash
find ~/fotos -type f -name '*.jpg' -delete            # en la Pi; deja las carpetas
rclone delete drive:EstacionTrigal/fotos               # en Drive (van a la papelera 30 días)
rclone rmdirs drive:EstacionTrigal/fotos --leave-root
```

Antes de borrar en la Pi, comprobar que todo está en Drive con `rclone check ~/fotos drive:EstacionTrigal/fotos --one-way`.

### Cambiar el dominio o agregar una ruta pública

En one.dash.cloudflare.com → *Networks* → *Tunnels* → `rpi4trigal` → *Rutas* → *Agregar ruta* → *Aplicación publicada*: subdominio, dominio, ruta y servicio (`http://localhost:<puerto>`). Las rutas con camino específico van antes que la de Grafana. Toda ruta que permita cambiar datos o encender luces necesita usuario y clave. El cambio aplica en un minuto, sin reiniciar nada.

Si se cambia el dominio de Grafana, actualizar también `GF_SERVER_ROOT_URL` y `GF_SERVER_DOMAIN` en el stack de Grafana (Portainer) y el dominio de la cámara en los paneles HTML.

### Calibrar el sensor de CO₂ (SCD30)

Es el único sensor que se calibra en campo: al instalar la estación y cada 6 a 12 meses. Se calibra al aire libre, con el valor del aire exterior (420 ppm). La autocalibración del sensor se deja apagada, porque en un invernadero el CO₂ nunca baja de forma regular al valor exterior.

1. Sacar la estación al aire libre, lejos de personas, motores y escapes. No respirar cerca del sensor.
2. En la Pi: `sudo systemctl stop trigal-serial`. Conectar la ESP32 a un computador con Arduino IDE.
3. Cargar este programa (placa *ESP32S3 Dev Module*). Mide 3 minutos y luego fija la referencia en 420 ppm; el sensor la guarda en su memoria:

   ```cpp
   #include <Wire.h>
   #include "SparkFun_SCD30_Arduino_Library.h"
   SCD30 co2;
   void setup() {
     Serial.begin(115200);
     Wire.begin(8, 9);          // SDA = 8, SCL = 9
     Wire.setClock(50000);
     Wire.setTimeOut(200);
     if (!co2.begin(Wire)) { Serial.println("No se encontro el SCD30"); while (1); }
     co2.setAutoSelfCalibration(false);
     co2.setAltitudeCompensation(2100);   // altitud del sitio en metros
     Serial.println("Midiendo 3 min al aire libre...");
     delay(180000);
     co2.setForcedRecalibrationFactor(420);
     Serial.println("Calibrado a 420 ppm");
   }
   void loop() {
     if (co2.dataAvailable()) { Serial.print("CO2: "); Serial.println(co2.getCO2()); }
     delay(2000);
   }
   ```
4. En el Monitor Serie (115200) debe salir "Calibrado a 420 ppm" y después lecturas cercanas a 420.
5. Volver a cargar `PAYLOAD.ino`, conectar la ESP32 a la Pi y `sudo systemctl start trigal-serial`.
6. Anotar la fecha de la calibración.

Si la estación se usa a otra altitud, cambiar `2100` por la altitud del sitio y volver a correr la calibración. El sensor guarda la altitud en su memoria; el firmware de la estación no la modifica.

### Configurar la dirección Modbus de un sensor nuevo o de reemplazo

De fábrica, el sensor PAR y las sondas de suelo vienen con la misma dirección (1) y el PAR a otra velocidad, así que no funcionan juntos en el mismo bus. Cada sensor nuevo se configura **conectado solo**:

- **Sondas JXBS-3001:** con el programa de JXCT y un convertidor USB-RS485 desde un computador.
- **Sensor PAR SEN0641:** escribiendo su registro `0x07D0` (dirección) y `0x07D1` (velocidad: 0 = 2400, 1 = 4800, 2 = 9600) con un programa de prueba, y reiniciando el sensor.

La dirección y la velocidad elegidas deben coincidir con los `#define` `ID_SENSOR_SUELO_1..3`, `ID_SENSOR_PAR_1` y `BAUDIOS_485` del firmware (sección 4). Marcar cada sonda con su número para no confundirlas en campo.

## 13. Verificación y solución de problemas

La primera herramienta ante cualquier duda es `revisar-estacion`. Revisa la Pi, el 4G y el WiFi, los servicios, los contenedores, la cadena ESP32 → MQTT → Node-RED → InfluxDB → Grafana, la cámara, las fotos y el dashboard público. Termina con "Todo lo esencial está funcionando" o con la lista de lo que falla. La prueba de datos espera hasta 75 s una trama, porque la ESP32 envía cada 60 s; por eso la revisión tarda alrededor de un minuto. Se ejecuta sola 6 min después de cada arranque y deja el resultado en `~/ultimo-arranque.txt`.

```bash
revisar-estacion              # revisión completa ahora
cat ~/ultimo-arranque.txt     # resultado del último arranque
```

Si está instalado `prueba-final` (carpeta `raspberry/bin` del repositorio), hace una revisión más profunda: además cuenta, campo por campo, las lecturas que llegaron a InfluxDB en los últimos minutos.

### Diagnóstico en seis preguntas (para quien no conoce el sistema)

Responder en orden. La primera respuesta "no" indica dónde está la falla.

| Pregunta | Cómo saberlo | Si la respuesta es no |
| --- | --- | --- |
| 1. ¿Carga `https://iot.trigal-digital.com` desde un celular con datos móviles? | Abrir la página | Error 1033: Pi apagada, sin 4G o sin saldo. Revisar que la estación tenga energía, el saldo en Mi Claro y luego entrar por Pi Connect y ejecutar `revisar-estacion` |
| 2. ¿El último dato tiene menos de 2 minutos? | Primera fila del dashboard | El puente o la ESP32: `journalctl -u trigal-serial -n 30` y revisar el cable USB de la ESP32 |
| 3. ¿Todos los paneles muestran datos? | Paneles con "No data", o SCD30 y TSL2591 en "Sin conexión" en la fila Sistema | Revisar los cables del sensor que falta (tabla de fallas, abajo) |
| 4. ¿Hay fotos de la última hora programada? | Fila Cámara | `systemctl status camara` y `curl -s localhost:3333/foto/estado` (sección 8) |
| 5. ¿Aparecen los índices de ayer, después de las 00:10? | Fila Índices del ciclo | InfluxDB → Tasks → `indices_diarios` → Runs (sección 9) |
| 6. ¿Las fotos están llegando a Drive? | Drive del proyecto → EstacionTrigal/fotos | `journalctl -u fotos-nube -n 30` (sección 8) |

### Revisión rápida desde el celular

1. Abrir `https://iot.trigal-digital.com` con datos móviles.
2. En la fila de estado, el último dato debe tener menos de 2 minutos.
3. En la fila **Sistema**: SCD30 y TSL2591 en "OK", alimentación "OK", microSD por debajo de 80 % y consumo de datos dentro del paquete.
4. En la fila **Cámara**, la última foto automática debe ser de la última hora programada.
5. Después de las 00:10, los índices del día anterior deben aparecer.

### Puesta en marcha en campo

1. Conectar el cable a la toma y subir el switch exterior. Esperar unos 7 minutos sin tocar nada.
2. Desde un celular con datos móviles, abrir `https://iot.trigal-digital.com` y comprobar que llegan datos.
3. Si la estación se instaló en un lote distinto, iniciar el ciclo nuevo en `/ciclo` (sección 7).
4. Enfocar la cámara si hace falta (sección 12, "Cambiar o reemplazar la cámara").
5. Si algo no carga: entrar por Raspberry Pi Connect y ejecutar `revisar-estacion`.

### Prueba de arranque en frío

Simula un corte de energía. Hacerla antes de cada instalación:

1. `sudo poweroff`, desconectar la corriente 10 s y volver a conectar.
2. Esperar 7 minutos sin tocar nada.
3. `cat ~/ultimo-arranque.txt` debe terminar en "Todo lo esencial está funcionando".
4. Abrir `https://iot.trigal-digital.com` desde un celular con datos (no desde el WiFi de la universidad).

### Prueba solo con 4G (sin WiFi)

Apaga el WiFi 3 minutos y lo vuelve a encender solo, para no perder el acceso:

```bash
sudo -v
nohup sudo bash -c 'nmcli radio wifi off; sleep 180; nmcli radio wifi on' >/dev/null 2>&1 &
```

Durante esos 3 minutos: en connect.raspberrypi.com, `rpi4trigal` debe aparecer *en línea*, y en su terminal `ip route get 1.1.1.1` debe decir `dev usb0`; y el dashboard debe cargar desde un celular con datos.

### Mantenimiento periódico

| Cada cuánto | Qué hacer |
| --- | --- |
| Cada mes | Recargar la SIM (311 620 1272). Limpiar con un paño seco el domo del sensor PAR, la ventanita del sensor de luz y el lente de la cámara. Revisar que el ventilador de la caja gire y que los cables estén bien conectados y sin daños. Revisar en la fila **Sistema** el consumo de datos y el espacio de la microSD |
| Cada mes | Revisar en Google Drive que las fotos se estén subiendo, y en el dashboard que los índices diarios aparezcan |
| Cada 6 a 12 meses | Calibrar el SCD30 (sección 12) |
| Después de cada cambio importante | Imagen de la microSD y respaldo (sección 14) |
| Siempre | Dejar la caja de control cerrada. Mantener la electrónica lejos del agua y del riego; solo las sondas de suelo toleran el agua. Apagar antes de mover la estación. Dejar las agujas de las sondas completamente enterradas, sin piedras alrededor. No dejar objetos que hagan sombra sobre los sensores de luz. No desarmar los sensores: vienen calibrados de fábrica |

### Fallas frecuentes

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| El dashboard da **Error 1033** | El túnel no conecta: Pi apagada, sin 4G, SIM sin saldo o Pi saliendo por un WiFi que bloquea el túnel | Revisar saldo en Mi Claro; `revisar-estacion`; `journalctl -t lte-watchdog`; aplicar `never-default` a esa red WiFi (sección 12) |
| Toda web responde `302` a `compras.claro.com.co` | SIM sin datos | Recargar o comprar paquete |
| No llegan datos nuevos | Puente detenido, ESP32 desconectada o sin hora | `journalctl -u trigal-serial -n 30`; revisar el cable USB; `ls -l /dev/esp32` |
| El puente dice "Esperando hora por internet" | Sin internet al arrancar, y la Pi no tiene reloj propio | Revisar el 4G; los datos empiezan a guardarse al sincronizar la hora |
| El puente dice "Mosquitto rechazó la conexión (código 5)" | Clave de `estacion` mal escrita en `trigal.env` | Corregir `MQTT_PASS` y `sudo systemctl restart trigal-serial` |
| El puente dice "Se perdió el puerto serial" | Otro programa tiene abierta la ESP32 (por ejemplo el Monitor Serie) | Cerrarlo y `sudo systemctl restart trigal-serial` |
| CO₂, temperatura y humedad en 0 o sin datos, y SCD30 "Sin conexión" | Bus I²C: cable suelto, SDA/SCL cruzados, sin 3,3 V o pin SEL del SCD30 en alto | Revisar cableado (SDA GPIO 8, SCL GPIO 9, GND común); el SCD30 y el TSL2591 deben responder en `0x61` y `0x29` |
| PAR en 0 con luz | Registro o función Modbus del sensor PAR | Revisar con la ficha técnica el registro (`REG_PAR`) y `PAR_USA_REG_ENTRADA` |
| Una sonda de suelo sin datos | Cable RS485 (A/B) o dirección Modbus | Revisar cables (café +V, negro GND, amarillo A, azul B) y que el ID coincida con el firmware |
| Sondas de suelo con humedad 0 %, CE 0 y pH 7 exacto | La sonda está al aire o en sustrato seco: sin humedad no mide CE y el pH queda en 7 por defecto. La comunicación sí funciona (la temperatura es real) | Normal si la estación está guardada. En campo: enterrar las agujas completas en sustrato regado, sin aire alrededor |
| *Tomar foto* da "la ESP32 no confirmó la luz" | La ESP32 no recibe la orden o no responde | Revisar que `trigal-serial` está activo; probar `{"cmd":"ping"}` (sección 4) |
| Las fotos no se actualizan en el dashboard | Cámara detenida o clave remota incorrecta en el panel | `systemctl status camara`; `curl -s localhost:3333/foto/estado`; revisar `data-cam` |
| El video no abre por internet | Ruta `cam.` del túnel o `CAM_CLAVE` | Probar `https://cam.trigal-digital.com/<CAM_CLAVE>/foto/estado` |
| Las fotos no llegan a Drive | Sin internet o rclone sin autorización | `journalctl -u fotos-nube -n 30`; si dice token o autorización, reautorizar (sección 12) |
| No aparecen DLI ni fotoperiodo de ayer | Tarea fallida o Pi apagada a las 00:10 | InfluxDB → *Tasks* → `indices_diarios` → *Runs*; se recupera sola en los 3 días siguientes |
| Un panel dice "No data" | Ese sensor no envía, o el rango de tiempo no tiene datos | Ampliar el rango; revisar el sensor en la fila Sistema |
| `/ciclo` o `/descarga` no cargan después de un cambio | Error de sintaxis en `settings.js` | `docker logs --tail 15 node-red`; corregir o restaurar con `sudo cp /opt/trigal/nodered/data/settings.js.respaldo /opt/trigal/nodered/data/settings.js` |
| InfluxDB no responde (`NetworkError`) | Contenedor detenido | `docker ps`; `docker logs --tail 20 influxdb`; `docker restart influxdb` |
| "Alimentación de la Pi" en rojo | El cargador no da suficiente corriente | Usar el cargador oficial; no alimentar otros equipos desde la Pi |
| MicroSD por encima de 90 % | Fotos o registros acumulados | Revisar `du -sh ~/fotos` y que `fotos-nube` esté moviendo las fotos viejas |
| El 4G no conecta al encender | El módulo tarda en estar listo | El vigilante reintenta solo; si no, presionar RESET en el HAT |
| La ESP32 se reinicia sola o envía líneas raras | ModemManager reactivado, que le envía comandos AT | `sudo systemctl disable --now ModemManager` |
| El puente dice "Sin datos de suelo hace ... reinicio la ESP32" | Las sondas no responden: cable RS485, alimentación de 12 V o direcciones Modbus | Revisar cables y fuente de 12 V. Mientras falle, el puente reinicia la ESP32 cada 30 min (SIN\_SUELO\_S) |
| Los LEDs no prenden al tomar la foto | Pin distinto en el firmware, MOSFET o resistencia dañados, o fuente de 12 V apagada | Enviar {"cmd":"blanco","seg":20} (sección 4) y mirar el LED; revisar PIN\_LED\_BLANCO, PIN\_LED\_UV y la bornera del MOSFET |
| El ventilador de la caja no prende | La caja está por debajo de 25 °C (normal), el DHT22 no lee o falla el MOSFET del ventilador | En la fila Sistema, con temp\_caja por encima de 25 °C el campo ventilador debe estar en 1; si no, revisar el DHT22 (GPIO 4) y el MOSFET (GPIO 5) |
| Arduino IDE no encuentra el puerto de la ESP32 | Conector USB equivocado, cable que solo carga o falta el controlador CP210x | Usar el conector UART o COM y otro cable; instalar el controlador (sección 4) |

Si nada de lo anterior funciona: `sudo reboot`, esperar 7 minutos y revisar `~/ultimo-arranque.txt`.

## 14. Respaldo, recuperación y reinstalación

La forma más rápida de recuperar la estación es una **imagen completa de la microSD**: si la tarjeta se daña, se graba la imagen en otra y todo vuelve a funcionar igual. El respaldo de configuración y datos sirve para recuperar partes o para reinstalar desde cero.

### Imagen de la microSD (después de cada cambio importante)

1. `sudo poweroff` y sacar la microSD.
2. En un computador con Windows, abrir Win32 Disk Imager, elegir la unidad de la tarjeta, un nombre de archivo (por ejemplo `rpi4trigal_2026-11-21.img`) y **Read**. En Linux o Mac: `sudo dd if=/dev/<tarjeta> of=rpi4trigal_2026-11-21.img bs=4M status=progress`.
3. Guardar la imagen en un disco de El Trigal y en un lugar privado (contiene claves).
4. **Restaurar:** grabar la imagen en una microSD de 128 GB o más con Raspberry Pi Imager (*Use custom*) o balenaEtcher, ponerla en la Pi y encender.

### Respaldo de configuración y datos (sin apagar)

```bash
FECHA=$(date +%F); D=/opt/trigal/backups/$FECHA; sudo mkdir -p $D
docker exec influxdb influx backup /var/lib/influxdb2/respaldo_$FECHA
sudo mv /opt/trigal/influxdb/data/respaldo_$FECHA $D/influxdb
sudo tar czf $D/configuracion.tgz /opt/trigal/app /opt/trigal/mosquitto/config /opt/trigal/nodered/data /opt/trigal/grafana/data /opt/trigal/stacks /home/trigal/fastapi-cam/main.py /usr/local/bin /etc/systemd/system/*.service /etc/systemd/system/*.timer /etc/udev/rules.d/99-esp32.rules /home/trigal/.config/rclone
sudo chown -R trigal:trigal $D
rclone copy $D drive:EstacionTrigal/respaldos/$FECHA
```

El archivo `configuracion.tgz` contiene claves y tokens: guardarlo solo en lugares privados. Además, exportar los dos dashboards de Grafana (*Export* → *Export as JSON*) y los flujos de Node-RED (☰ → *Exportar* → todos los flujos), y guardar una copia de `PAYLOAD.ino`.

**Restaurar solo los datos de InfluxDB:** copiar la carpeta del respaldo a `/opt/trigal/influxdb/data/` y ejecutar `docker exec influxdb influx restore /var/lib/influxdb2/<carpeta> --full`. Un CSV de `/descarga` sirve para analizar, pero no se vuelve a cargar solo.

### Código fuente: repositorio `estacion-trigal`

Todo el código del proyecto está en el repositorio privado de GitHub **[estacionfloreseltrigal-hub/estacion-trigal](https://github.com/estacionfloreseltrigal-hub/estacion-trigal)**, de la cuenta del proyecto. Este manual es su documentación. Para descargarlo completo: en la página del repositorio, Code → Download ZIP (con una cuenta que tenga acceso), o `git clone https://github.com/estacionfloreseltrigal-hub/estacion-trigal`.

| Carpeta | Qué contiene | Dónde va en la Pi |
| --- | --- | --- |
| `firmware/PAYLOAD/` | `PAYLOAD.ino`, firmware de la ESP32-S3 | Se carga con Arduino IDE (sección 4) |
| `raspberry/app/` | `serial_mqtt.py` y ejemplos de `trigal.env` e `influx-sistema.env` sin claves | `/opt/trigal/app/` |
| `raspberry/camara/` | `main.py` y `requirements.txt` del servidor de la cámara | `/home/trigal/fastapi-cam/` |
| `raspberry/bin/` | `revisar-estacion`, `prueba-final`, `esperar-hora`, `lte-watchdog.sh`, `fotos-nube.sh`, `metricas-sistema` | `/usr/local/bin/` |
| `raspberry/systemd/` | Servicios y temporizadores (sección 17) | `/etc/systemd/system/` |
| `raspberry/udev/` | `99-esp32.rules` | `/etc/udev/rules.d/` |
| `raspberry/sistema/` | `50-persistente.conf` (registros persistentes) | `/etc/systemd/journald.conf.d/` |
| `docker/` | YML de cada contenedor y `mosquitto.conf` | `/opt/trigal/stacks/` y `/opt/trigal/mosquitto/config/` |
| `node-red/` | `flows.json`, `settings.js` (sin hashes) y `package.json` | `/opt/trigal/nodered/data/` |
| `influxdb/` | `indices_diarios.flux` | InfluxDB → Tasks |
| `grafana/dashboards/` | Dashboards exportados | Grafana → Dashboards → Import |

- **La versión que vale es la de la Pi.** El repositorio se comparó archivo por archivo con la Pi el 23 de noviembre de 2026.
- El `PAYLOAD.ino` del repositorio es el mismo que está cargado en la ESP32 (comparados el 22 de noviembre de 2026). Los archivos de la sección 17 son copia de la carpeta `raspberry/` del repositorio.
- Después de cambiar algo en la Pi, actualizar el repositorio con `bash ~/estacion-trigal/recolectar-desde-la-pi.sh`: copia flujos, dashboards, scripts y servicios, quita las claves y deja `~/estacion-trigal.tar.gz` para subir (por Pi Connect: `rclone copy ~/estacion-trigal.tar.gz drive:EstacionTrigal/repositorio`).
- Nunca subir `trigal.env`, `influx-sistema.env`, `passwd`, `rclone.conf`, `flows_cred.json` ni tokens. El `.gitignore` del repositorio ya los bloquea, y el script reemplaza los hashes de `settings.js`.
- Después de cada cambio en la Pi o en el firmware, subir los archivos nuevos con un mensaje que diga qué cambió y anotarlo en el registro de cambios (sección 15).

### Reinstalación desde cero (sin imagen)

Hacerlo con WiFi o cable, no por el 4G.

**1. Sistema.** Grabar Raspberry Pi OS de 64 bits con Raspberry Pi Imager: nombre `rpi4trigal`, usuario `trigal`, SSH activado, zona horaria `America/Bogota`. Después:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-serial python3-paho-mqtt mosquitto-clients rclone vnstat apache2-utils v4l-utils
sudo systemctl disable --now ModemManager
sudo mkdir -p /opt/trigal/{app,backups,fotos,stacks,nodered/data,influxdb/data,influxdb/config,grafana/data,mosquitto/config,mosquitto/data}
sudo chown -R trigal:trigal /opt/trigal
sudo chown -R 472:0 /opt/trigal/grafana
sudo usermod -aG dialout,docker trigal
```

**2. Módulo 4G.** Con la SIM puesta y los switches como en la sección 10: poner el módulo en modo RNDIS (`AT+CUSBPIDSWITCH=9011,1,1` por el puerto AT), corregir el APN (sección 12), crear el perfil y dejarlo con reintentos sin límite:

```bash
sudo nmcli connection add type ethernet ifname usb0 con-name claro4g ipv4.route-metric 700 ipv6.route-metric 700
sudo nmcli connection modify claro4g connection.autoconnect-retries 0 ipv4.dhcp-timeout infinity
```

Instalar `lte-watchdog.sh`, `.service` y `.timer` (su contenido está en la sección 17) y activar: `sudo systemctl enable --now lte-watchdog.timer`.

**3. Docker y Portainer.** Instalar Docker desde el repositorio oficial (docs.docker.com, Debian). Luego:

```bash
docker run -d -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
```

Abrir `https://<ip-de-la-pi>:9443` y crear `admin_trigal` (si pide *setup token*: `docker logs portainer | grep setup_token`).

**4. Contenedores.** En Portainer → *Stacks* → *Add stack*, uno por servicio, con los YML guardados en `/opt/trigal/stacks/`. Como referencia:

```yaml
# mosquitto
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    restart: unless-stopped
    ports: ["1883:1883"]
    volumes:
      - /opt/trigal/mosquitto/config:/mosquitto/config
      - /opt/trigal/mosquitto/data:/mosquitto/data
```

`/opt/trigal/mosquitto/config/mosquitto.conf`:

```
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
persistence true
persistence_location /mosquitto/data/
log_dest stdout
```

Crear los usuarios `estacion` (con `-c` solo la primera vez) y `nodered` como en la sección 11, y luego `sudo chown -R 1883:1883 /opt/trigal/mosquitto`.

```yaml
# nodered
services:
  node-red:
    image: nodered/node-red:latest
    container_name: node-red
    restart: unless-stopped
    network_mode: host
    environment: [TZ=America/Bogota]
    volumes:
      - /opt/trigal/nodered/data:/data
      - /opt/trigal/fotos:/fotos:ro
```

```yaml
# influxdb (variable INFLUX_PASSWORD en Portainer)
services:
  influxdb:
    image: influxdb:2
    container_name: influxdb
    restart: unless-stopped
    network_mode: host
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin_trigal
      - DOCKER_INFLUXDB_INIT_PASSWORD=${INFLUX_PASSWORD}
      - DOCKER_INFLUXDB_INIT_ORG=trigal
      - DOCKER_INFLUXDB_INIT_BUCKET=estacion
    volumes:
      - /opt/trigal/influxdb/data:/var/lib/influxdb2
      - /opt/trigal/influxdb/config:/etc/influxdb2
```

```yaml
# grafana (variable GRAFANA_PASSWORD en Portainer)
services:
  grafana:
    image: grafana/grafana-enterprise
    container_name: grafana
    restart: unless-stopped
    network_mode: host
    environment:
      - TZ=America/Bogota
      - GF_SECURITY_ADMIN_USER=admin_trigal
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_PANELS_DISABLE_SANITIZE_HTML=true
      - GF_SERVER_ROOT_URL=https://iot.trigal-digital.com
      - GF_SERVER_DOMAIN=iot.trigal-digital.com
      - GF_AUTH_ANONYMOUS_ENABLED=false
    volumes:
      - /opt/trigal/grafana/data:/var/lib/grafana
```

```yaml
# cloudflared (variable TUNNEL_TOKEN en Portainer, del panel de Cloudflare)
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    network_mode: host
    command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
```

El token del túnel está en one.dash.cloudflare.com → *Tunnels* → `rpi4trigal` → instalar conector. Las rutas del túnel quedan guardadas en Cloudflare: no hay que crearlas de nuevo.

**5. InfluxDB.** Crear los tokens (sección 11) y la tarea `indices_diarios` (*Tasks* → *Create Task* → *New Task*, nombre `indices_diarios`, CRON `10 5 * * *`, pegar el script guardado). Si hay respaldo de datos, restaurarlo.

**6. Node-RED.** Instalar desde *Manage palette* el nodo `node-red-contrib-influxdb`. Importar los flujos guardados, poner las claves en los nodos `mosquitto-local` e `influxdb-local`, configurar `adminAuth` y `httpNodeAuth` en `settings.js` (sección 11) e *Implementar*.

**7. Grafana.** Crear la fuente de datos InfluxDB (lenguaje Flux, URL `http://localhost:8086`, organización `trigal`, token de lectura), importar los dos dashboards, crear la carpeta **Administración** sin el rol *Viewer*, crear `trigal_visor` y fijar el dashboard de inicio (sección 12).

**8. Puente ESP32.** Copiar `serial_mqtt.py` y `trigal.env` a `/opt/trigal/app/` (`chmod 600 trigal.env`), la regla `99-esp32.rules` a `/etc/udev/rules.d/` (`sudo udevadm control --reload && sudo udevadm trigger`), y `esperar-hora` a `/usr/local/bin/` con su `esperar-hora.conf` en `/etc/systemd/system/trigal-serial.service.d/`. Instalar `trigal-serial.service` y `sudo systemctl enable --now trigal-serial`.

**9. Cámara.** Copiar `main.py` y `requirements.txt` de `raspberry/camara/` del repositorio a `/home/trigal/fastapi-cam`, crear el entorno (`python3 -m venv .venv` y `.venv/bin/pip install -r requirements.txt`), instalar `camara.service` y `sudo systemctl enable --now camara`. Si falta `libGL`: `sudo apt install -y libgl1`.

**10. Fotos a Drive.** `rclone config` → `n` → nombre `drive` → tipo `drive` → `client_id` y `client_secret` vacíos → scope `3` → autorizar con la cuenta del proyecto (sección 12). Instalar `fotos-nube.sh`, `.service` y `.timer` y `sudo systemctl enable --now fotos-nube.timer`.

**11. Métricas y revisión.** Instalar `metricas-sistema` (con su token en `/opt/trigal/app/influx-sistema.env`) y `revisar-estacion` con sus timers, y activar los registros persistentes (`Storage=persistent`, `SystemMaxUse=200M` en `/etc/systemd/journald.conf.d/50-persistente.conf`).

**12. Raspberry Pi Connect.** `sudo apt install -y rpi-connect-lite`, `rpi-connect signin` y abrir el enlace con la cuenta del proyecto.

Los servicios, temporizadores, reglas y scripts cortos de los pasos 2, 8, 10 y 11 están completos en la sección 17. Los programas largos (`serial_mqtt.py`, `main.py`, `metricas-sistema`, `revisar-estacion`, flujos y dashboards) están en el repositorio.

**13. Comprobar** con la prueba de arranque en frío y la prueba solo con 4G (sección 13).

## 15. Entrega a El Trigal, limitaciones y recomendaciones

Todo queda a nombre de El Trigal: el equipo de estudiantes no conserva ninguna cuenta ni acceso. Nada debe quedar atado al celular o al correo personal de un estudiante.

### Lista de entrega

- [ ] Entregar la cuenta `estacionfloreseltrigal@gmail.com` con correo y teléfono de recuperación de El Trigal, verificación en dos pasos a nombre de El Trigal y códigos de respaldo.
- [ ] Entregar la bóveda de Bitwarden "Estación Trigal" (idealmente como organización compartida) con todas las claves, tokens, `CAM_CLAVE` y los datos de la SIM.
- [ ] Confirmar que Julián Guevara es administrador en Cloudflare y quitar a los estudiantes que hayan quedado como miembros.
- [ ] Pasar la cuenta de Raspberry Pi Connect a El Trigal (o crear una suya y volver a vincular la Pi).
- [ ] Definir quién recarga la SIM de Claro y el tamaño del paquete (8 a 10 GB al mes recomendados).
- [ ] Cambiar todas las contraseñas después de recibir (sección 11).
- [ ] Entregar `trigal_visor` y su clave a quienes vayan a consultar, y el enlace de kiosco.
- [ ] Iniciar el ciclo del lote donde se instala la estación (sección 7).
- [ ] Hacer y guardar una imagen de la microSD ya entregada (sección 14).
- [ ] Guardar una copia de este manual, del firmware `PAYLOAD.ino` y de los dashboards exportados.
- [ ] Entregar a El Trigal el acceso al repositorio estacionfloreseltrigal-hub/estacion-trigal y completarlo con los flujos de Node-RED y los dashboards de Grafana usando recolectar-desde-la-pi.sh (sección 14).

### Limitaciones conocidas

- **Sin reloj propio (RTC):** la Pi toma la hora de internet. Si arranca sin 4G, el puente no guarda lecturas hasta sincronizar la hora, para no guardar fechas falsas. Si la Pi está apagada a la hora de una foto, esa foto se pierde.
- **Sin GPS:** el lote y la ubicación se registran a mano en `/ciclo`. Si la estación se mueve y no se inicia un ciclo nuevo, los datos quedan asociados al lote anterior.
- **Depende de la cobertura y el saldo de Claro:** sin 4G no hay acceso remoto ni subida de fotos, pero la estación sigue midiendo y guardando en la Pi.
- **WiFi de la universidad:** bloquea el túnel; el acceso público solo funciona por el 4G.
- **Días incompletos:** si faltan horas de PAR, el DLI de ese día sale bajo. Revisar `horas_datos` antes de usarlo.
- **Calibración:** el SCD30 mostró valores bajos de CO₂ en laboratorio y el sensor PAR debe verificarse con su ficha técnica. Los umbrales de color (DPV, margen al rocío, DLI, HR 90 %) y la T-base de 5 °C son valores de referencia que El Trigal debe validar; hay literatura que usa cerca de 2 °C para algunos cultivares de snapdragon.
- **Visitantes:** pueden usar los botones de la cámara, y el video en vivo es lo que más datos gasta. En kiosco no se pueden cambiar el ciclo ni el rango de tiempo.
- **Sin Cloudflare Access:** la seguridad depende de las claves de Grafana, de Node-RED y de la cámara. Activarlo es opcional y requiere registrar una tarjeta en Cloudflare.

### Recomendaciones para una siguiente versión

- Agregar un módulo de reloj DS3231 a la Pi, para guardar datos y tomar fotos con hora aunque no haya internet al arrancar.
- Alertas automáticas por Telegram o correo cuando la estación deje de enviar datos, el paquete de datos se acerque al límite o un índice salga de rango.
- Programar el respaldo de la sección 14 una vez por semana.
- Recalibrar el SCD30 al aire libre y validar la T-base y los umbrales con el equipo agronómico de El Trigal.
- Ajustar `T_SUELO` a 5 min si la estación se usa en suelo de campo en lugar de sustrato.

### Registro de cambios

Cada cambio en la estación se anota aquí, una línea por cambio, para que quien venga después sepa qué se tocó y dónde quedó la copia.

| Fecha | Qué se cambió | Quién | Dónde quedó la copia |
| --- | --- | --- | --- |
| 2026-11-22 | Entrega a El Trigal: la versión que describe este manual | Equipo del curso | Repositorio `estacion-trigal` e imagen de la microSD |
|  |  |  |  |

## 16. Glosario

Palabras técnicas que aparecen en el manual, explicadas para quien no trabaja con estos temas.

| Término | Qué es, en esta estación |
| --- | --- |
| APN | Nombre que el operador móvil exige para dar internet a una SIM. El de Claro es `internet.comcel.com.co` |
| Baudios | Velocidad de una comunicación serial. Los dos extremos deben usar la misma |
| Bitwarden | Gestor de contraseñas donde se guardan todas las claves de la estación |
| Bucket, medición y campo | Organización de InfluxDB: el bucket `estacion` es la base de datos; las mediciones (`datos`, `diario`, `sistema`…) son como tablas, y cada campo es una variable (`temperatura`, `par`…) |
| CE | Conductividad eléctrica del sustrato, en µS/cm. Indica cuántas sales y fertilizante hay |
| Cloudflare y túnel | Servicio que publica el dashboard en `trigal-digital.com`. La Pi abre una conexión de salida (el túnel) y Cloudflare entrega por ella las visitas, sin abrir puertos |
| Contenedor y Docker | Docker ejecuta programas en contenedores, cajas aisladas que traen todo lo que necesitan. Mosquitto, Node-RED, InfluxDB, Grafana y cloudflared corren así |
| CSV | Archivo de texto con datos en filas y columnas que abre Excel, R o Python |
| Dashboard y panel | El dashboard es la página de Grafana con las gráficas; cada gráfica o número es un panel |
| DLI | Integral de luz diaria: toda la luz fotosintética que recibió el cultivo en un día, en mol·m⁻²·d⁻¹ |
| DPV | Déficit de presión de vapor, en kPa: qué tan seco está el aire para la planta. Bajo = aire saturado; alto = la planta pierde mucha agua |
| Firmware | Programa que corre dentro de la ESP32 (`PAYLOAD.ino`) |
| Flux | Lenguaje de consultas de InfluxDB, usado en la tarea `indices_diarios` y en los paneles |
| Fotoperiodo | Horas de luz efectiva del día, medidas con el sensor PAR |
| GDD y T-base | Grados-día: calor acumulado por encima de una temperatura base (T-base) por debajo de la cual el cultivo casi no avanza |
| GPIO | Pin de la ESP32 que se usa como entrada o salida |
| I²C | Bus de dos cables (SDA y SCL) por el que la ESP32 habla con el SCD30 y el TSL2591 |
| InfluxDB | Base de datos donde se guardan todas las lecturas con su fecha y hora |
| IP | Dirección de un equipo en una red, por ejemplo `10.10.80.48` |
| Kiosco | Modo de Grafana a pantalla completa, sin menús, para un televisor o una pantalla fija |
| MEF | Máquina de estados finitos: forma de programar en la que el sistema está en un estado (por ejemplo luz apagada, blanca o UV) y pasa a otro cuando se cumple una condición |
| Modbus y dirección | Idioma con el que la ESP32 pregunta a los sensores RS485. Cada sensor tiene una dirección (ID) distinta |
| MOSFET | Interruptor electrónico con el que la ESP32 prende los LEDs y el ventilador de 12 V |
| MQTT, broker y tópico | Sistema de mensajes entre programas. El broker (Mosquitto) recibe y reparte los mensajes; cada mensaje va a un tópico, como `trigal/estacion1/datos` |
| Node-RED y flujo | Programa visual que recibe los datos por MQTT, calcula índices, los guarda en InfluxDB y sirve las páginas `/ciclo` y `/descarga`. Cada pestaña de nodos conectados es un flujo |
| PAR y PPFD | PAR es la luz que usan las plantas (400 a 700 nm). PPFD es su intensidad en un instante, en µmol·m⁻²·s⁻¹ |
| Portainer | Página para administrar los contenedores de Docker sin usar la terminal |
| Punto y margen de rocío | Temperatura a la que el agua del aire se condensa. El margen es cuántos grados falta para llegar a ella |
| rclone | Programa que copia las fotos a Google Drive |
| RNDIS | Modo en que el módulo 4G se presenta a la Pi como una tarjeta de red (`usb0`) |
| RS485 | Bus de dos cables (A y B) para sensores a varios metros de distancia: el PAR y las sondas de suelo |
| Servicio y temporizador (systemd) | Un servicio es un programa que la Pi arranca sola; un temporizador lo ejecuta cada cierto tiempo. Se manejan con `systemctl` |
| SSH y terminal | La terminal es la ventana donde se escriben órdenes; SSH permite abrir la terminal de la Pi desde otro computador |
| `sudo` | Antepuesto a un comando, lo ejecuta con permisos de administrador. Pide la clave del usuario `trigal` |
| Token | Clave larga que un programa usa para entrar a InfluxDB sin usuario ni contraseña |
| Trama `$EST` | Línea de texto con todas las lecturas que la ESP32 envía cada minuto |
| udev | Parte de Linux que reconoce los aparatos USB; con una regla le da a la ESP32 el nombre fijo `/dev/esp32` |

## 17. Anexo: archivos de configuración de la Pi

Estos son los archivos cortos que hacen que todo arranque solo. Con ellos y el repositorio se puede reconstruir la Pi sin la imagen de la microSD. Ninguno tiene claves. Son copia exacta de la carpeta raspberry/ del repositorio (sección 14).

**Cómo crear o reemplazar uno de estos archivos en la Pi**

1. `sudo nano <ruta del archivo>` (la ruta está en el título de cada archivo).
2. Borrar lo que tenga, pegar el contenido y guardar: **Ctrl+O**, **Enter**, **Ctrl+X**.
3. Si es un script de `/usr/local/bin/`, darle permiso de ejecución: `sudo chmod +x <ruta>`.
4. Si es un `.service`, `.timer` o `.conf` de systemd: `sudo systemctl daemon-reload` y luego `sudo systemctl enable --now <nombre>` (para los que tienen temporizador, el `.timer`).
5. Si es la regla udev: `sudo udevadm control --reload-rules && sudo udevadm trigger`, y desconectar y conectar la ESP32.

Cuando un bloque trae dos archivos (por ejemplo un `.service` y su `.timer`), cada uno empieza con un comentario con su nombre: se crean por separado, cada uno con su parte.

### Puente ESP32 → MQTT

`/etc/udev/rules.d/99-esp32.rules` (le da a la ESP32 el nombre fijo `/dev/esp32` y le dice a ModemManager que no la toque):

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="esp32", GROUP="dialout", MODE="0660", ENV{ID_MM_DEVICE_IGNORE}="1"
```

`/etc/systemd/system/trigal-serial.service`:

```ini
[Unit]
Description=Estacion Trigal - puente serial ESP32 -> MQTT
After=network-online.target docker.service
Wants=network-online.target

[Service]
User=trigal
Group=dialout
Environment=TRIGAL_ENV=/opt/trigal/app/trigal.env
ExecStart=/usr/bin/python3 /opt/trigal/app/serial_mqtt.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/trigal-serial.service.d/esperar-hora.conf` (hace que el puente espere la hora antes de arrancar):

```ini
[Service]
ExecStartPre=/usr/local/bin/esperar-hora
TimeoutStartSec=infinity
```

`/usr/local/bin/esperar-hora`:

```bash
#!/bin/bash
# Espera a que la Raspberry tenga la hora sincronizada por internet (4G) antes de
# arrancar el puente serial. La Pi no tiene reloj propio: al prender sin red arranca
# con la hora del último apagado y las lecturas quedarían con fechas equivocadas.
minutos=0
until [ "$(timedatectl show -p NTPSynchronized --value)" = "yes" ]; do
    if [ $((minutos % 5)) -eq 0 ]; then
        echo "Esperando hora por internet ($minutos min). Hora actual de la Pi: $(date '+%F %T')"
    fi
    sleep 60
    minutos=$((minutos + 1))
done
echo "Hora sincronizada: $(date '+%F %T')"
```

### Cámara y fotos

`/etc/systemd/system/camara.service`:

```ini
[Unit]
Description=Estacion Trigal - camara (video, fotos con LEDs)
After=network-online.target docker.service trigal-serial.service
Wants=network-online.target

[Service]
User=trigal
WorkingDirectory=/home/trigal/fastapi-cam
Environment=TRIGAL_ENV=/opt/trigal/app/trigal.env
ExecStart=/home/trigal/fastapi-cam/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3333
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/fotos-nube.service` y `fotos-nube.timer` (el script `fotos-nube.sh` está en la sección 8):

```ini
# fotos-nube.service
[Unit]
Description=Estacion Trigal - subir fotos a Google Drive
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=trigal
ExecStart=/usr/local/bin/fotos-nube.sh

# fotos-nube.timer
[Unit]
Description=Estacion Trigal - subir fotos cada hora

[Timer]
OnBootSec=10min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
```

### Métricas, revisión automática y registros

`/etc/systemd/system/metricas-sistema.service` y `metricas-sistema.timer` (el script está en el repositorio):

```ini
# metricas-sistema.service
[Unit]
Description=Estacion Trigal - metricas del sistema (4G, disco, temperatura) a InfluxDB
After=docker.service vnstat.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/metricas-sistema

# metricas-sistema.timer
[Unit]
Description=Ejecuta las metricas del sistema cada 5 minutos

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

`/etc/systemd/system/revisar-estacion.service` y `revisar-estacion.timer` (el script está en el repositorio):

```ini
# revisar-estacion.service
[Unit]
Description=Estacion Trigal - revision automatica despues de arrancar
After=network-online.target docker.service

[Service]
Type=oneshot
User=trigal
ExecStart=/usr/local/bin/revisar-estacion
StandardOutput=truncate:/home/trigal/ultimo-arranque.txt
StandardError=inherit
SuccessExitStatus=0-255

# revisar-estacion.timer
[Unit]
Description=Estacion Trigal - revisar 6 minutos despues de encender

[Timer]
OnBootSec=6min
Unit=revisar-estacion.service

[Install]
WantedBy=timers.target
```

`/etc/systemd/journald.conf.d/50-persistente.conf` (conserva los registros entre reinicios; después de crearlo, `sudo systemctl restart systemd-journald`):

```ini
[Journal]
Storage=persistent
SystemMaxUse=200M
```

### Vigilante del 4G

`/usr/local/bin/lte-watchdog.sh` (versión 2, 11-nov-2026):

```bash
#!/bin/bash
# Vigilante 4G v2: revisa internet por IPv4 e IPv6 y solo actúa tras 3 revisiones seguidas sin red.
IF=usb0
STATE=/run/lte-watchdog.fails
PORT=/dev/serial/by-id/usb-SimTech__Incorporated_SimTech__Incorporated_0123456789ABCDEF-if04-port0

hay_red() {
  ping -I "$IF" -c 2 -W 5 1.1.1.1 >/dev/null 2>&1 && return 0
  ping -6 -I "$IF" -c 2 -W 5 2606:4700:4700::1111 >/dev/null 2>&1 && return 0
  curl --interface "$IF" -s -o /dev/null -m 10 http://connectivitycheck.gstatic.com/generate_204 && return 0
  curl --interface "$IF" -s -o /dev/null -m 10 https://www.cloudflare.com/cdn-cgi/trace && return 0
  return 1
}

if hay_red; then
  rm -f "$STATE"
  exit 0
fi

FAILS=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 ))
echo "$FAILS" > "$STATE"
logger -t lte-watchdog "Sin internet por $IF (fallo $FAILS de 3)"

if [ "$FAILS" -lt 3 ]; then
  nmcli connection up claro4g >/dev/null 2>&1
  exit 0
fi

if [ -e "$PORT" ]; then
  logger -t lte-watchdog "3 revisiones seguidas sin red, reiniciando modulo"
  stty -F "$PORT" 115200 raw -echo 2>/dev/null
  printf 'AT+CRESET\r' > "$PORT"
else
  logger -t lte-watchdog "No se encontro el puerto AT del modulo"
fi
rm -f "$STATE"
```

`/etc/systemd/system/lte-watchdog.service` y `lte-watchdog.timer`:

```ini
# lte-watchdog.service
[Unit]
Description=Vigilante conexion 4G Claro

[Service]
Type=oneshot
ExecStart=/usr/local/bin/lte-watchdog.sh

# lte-watchdog.timer
[Unit]
Description=Ejecuta el vigilante 4G cada 5 minutos

[Timer]
OnBootSec=90s
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

Antes de activarlo, comprobar con `ls -l /dev/serial/by-id/` que existe la ruta terminada en `-if04-port0`. Si se cambia el módulo 4G por otro, esa ruta cambia y hay que corregir `PORT=`.

### Tarea `indices_diarios` de InfluxDB

Se crea en InfluxDB → Tasks → + Create Task → **New Task** (no Import Task): nombre `indices_diarios`, Schedule **CRON** `10 5 * * *`, Offset `0m`, y se pega este script completo. Esta versión ya trae `DT_MAX = 150.0`, el valor correcto con envíos cada 60 s.

```
// Tarea de InfluxDB: índices diarios de la estación Trigal
// Corre a las 00:10 de Colombia y guarda el resumen de los últimos 3 días en la medición "diario".
// Para llenar días anteriores: pegar en Data Explorer (Script Editor), borrar la línea "option task",
// cambiar "inicio" y "fin" por fechas fijas y ejecutar una vez.

import "date"
import "timezone"

option location = timezone.location(name: "America/Bogota")
option task = {name: "indices_diarios", cron: "10 5 * * *"}   // 05:10 UTC = 00:10 en Colombia

// Parámetros
UMBRAL_LUZ = 2.0      // PPFD (µmol/m²/s) a partir del cual hay "luz efectiva"
UMBRAL_LUX = 108.0    // el mismo umbral en lux (luz solar: 1 µmol/m²/s ≈ 54 lux)
DT_MAX = 150.0        // segundos máximos entre dos lecturas (2,5 veces el envío de 60 s); en un hueco no se inventa luz

fin = date.truncate(t: now(), unit: 1d)
inicio = date.sub(d: 3d, from: fin)

campo = (f) => from(bucket: "estacion")
    |> range(start: inicio, stop: fin)
    |> filter(fn: (r) => r._measurement == "datos" and r._field == f)
    |> keep(columns: ["_time", "_value", "_field", "_measurement"])

guardar = (tables=<-, nombre) => tables
    |> map(fn: (r) => ({_time: r._time, _measurement: "diario", _field: nombre, _value: float(v: r._value)}))
    |> to(bucket: "estacion")

// 1. Temperatura: máxima y mínima de los promedios de 5 min
temp5 = campo(f: "temperatura")
    |> aggregateWindow(every: 5m, fn: mean, createEmpty: false, timeSrc: "_start")

tmax = temp5 |> aggregateWindow(every: 1d, fn: max, createEmpty: false, timeSrc: "_start")
tmin = temp5 |> aggregateWindow(every: 1d, fn: min, createEmpty: false, timeSrc: "_start")
tmax |> guardar(nombre: "tmax")
tmin |> guardar(nombre: "tmin")
join(tables: {a: tmax, b: tmin}, on: ["_time"])
    |> map(fn: (r) => ({_time: r._time, _value: (r._value_a + r._value_b) / 2.0}))
    |> guardar(nombre: "tmedia")

// 2. DLI = Σ (PPFD × Δt) / 1 000 000
par = campo(f: "par")
    |> elapsed(unit: 1s)
    |> map(fn: (r) => ({r with
        dt: if float(v: r.elapsed) > DT_MAX then DT_MAX else float(v: r.elapsed),
        ppfd: if r._value > 0.0 then r._value else 0.0}))

par
    |> map(fn: (r) => ({r with _value: r.ppfd * r.dt / 1000000.0}))
    |> aggregateWindow(every: 1d, fn: sum, createEmpty: false, timeSrc: "_start")
    |> guardar(nombre: "dli")

par
    |> map(fn: (r) => ({r with _value: r.dt / 3600.0}))
    |> aggregateWindow(every: 1d, fn: sum, createEmpty: false, timeSrc: "_start")
    |> guardar(nombre: "horas_datos")

// 3. Fotoperiodo = hora fin de luz − hora inicio de luz (solo cuenta un minuto completo sobre el umbral)
minutos_luz = campo(f: "par")
    |> aggregateWindow(every: 1m, fn: min, createEmpty: false, timeSrc: "_start")
    |> filter(fn: (r) => r._value >= UMBRAL_LUZ)
    |> map(fn: (r) => ({r with _value: float(v: uint(v: r._time)) / 1000000000.0}))

ini = minutos_luz |> aggregateWindow(every: 1d, fn: min, createEmpty: false, timeSrc: "_start")
fil = minutos_luz |> aggregateWindow(every: 1d, fn: max, createEmpty: false, timeSrc: "_start")

ini
    |> map(fn: (r) => ({r with _value: r._value - float(v: uint(v: r._time)) / 1000000000.0}))
    |> guardar(nombre: "inicio_luz")
fil
    |> map(fn: (r) => ({r with _value: r._value + 60.0 - float(v: uint(v: r._time)) / 1000000000.0}))
    |> guardar(nombre: "fin_luz")
join(tables: {a: ini, b: fil}, on: ["_time"])
    |> map(fn: (r) => ({_time: r._time, _value: r._value_b + 60.0 - r._value_a}))
    |> guardar(nombre: "fotoperiodo")

// 4. Fotoperiodo con los lux (mismo método), para los días sin PAR
minutos_lux = campo(f: "lux")
    |> aggregateWindow(every: 1m, fn: min, createEmpty: false, timeSrc: "_start")
    |> filter(fn: (r) => r._value >= UMBRAL_LUX)
    |> map(fn: (r) => ({r with _value: float(v: uint(v: r._time)) / 1000000000.0}))

ini_lux = minutos_lux |> aggregateWindow(every: 1d, fn: min, createEmpty: false, timeSrc: "_start")
fin_lux = minutos_lux |> aggregateWindow(every: 1d, fn: max, createEmpty: false, timeSrc: "_start")

ini_lux
    |> map(fn: (r) => ({r with _value: r._value - float(v: uint(v: r._time)) / 1000000000.0}))
    |> guardar(nombre: "inicio_luz_lux")
fin_lux
    |> map(fn: (r) => ({r with _value: r._value + 60.0 - float(v: uint(v: r._time)) / 1000000000.0}))
    |> guardar(nombre: "fin_luz_lux")
join(tables: {a: ini_lux, b: fin_lux}, on: ["_time"])
    |> map(fn: (r) => ({_time: r._time, _value: r._value_b + 60.0 - r._value_a}))
    |> guardar(nombre: "fotoperiodo_lux")
```

Después de guardarla: clic en la tarea → Run Task → en Runs debe salir `success`.
