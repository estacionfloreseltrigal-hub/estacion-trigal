# Firmware de la ESP32-S3

`PAYLOAD/PAYLOAD.ino` es la última versión que se preparó en las conversaciones del proyecto (20-nov-2026):
intervalos por grupo de sensores, ventilador a 25/22 °C, `Wire.setTimeOut(200)` y SCD30 sin la consulta
de presencia. Con esta versión la estación quedó enviando CO₂, temperatura, HR y lux cada 60 s.

**Antes de darlo por definitivo, compárenlo con el que está cargado en la ESP32** (el del computador con el que
lo subieron). Si el equipo hizo cambios a mano después (pines, direcciones Modbus, registro del PAR), el suyo manda.

## Resumen

- Placa: ESP32-S3 Dev Module, conectada a la Pi por el puerto **UART/COM** (CP210x → `/dev/esp32`), *USB CDC On Boot: Disabled*.
- Envía cada `T_ENVIO` (60 s) la trama `$EST,co2=..,ta=..,hra=..,lux=..,par=..,tc=..,vent=..,luz=..,scd=..,tsl=..[,s1h=..,...]`.
  PAR y lux van promediados; los datos de suelo solo van en la trama siguiente a cada ronda (`T_SUELO`, 15 min).
- Órdenes por serial (las reenvía el puente desde `trigal/estacion1/cmd`): `{"cmd":"blanco"}`, `{"cmd":"uv"}`,
  `{"cmd":"apagar"}`, `{"cmd":"ping"}`, opcional `"seg"` para calibrar (máx. 300 s).
- MEF de luces `LUZ_APAGADA / LUZ_BLANCA / LUZ_UV`; responde `Estado: ...`, `#OK,luz lista`, `#ERR,...`.

## Pines en esta versión

| Señal | GPIO |
| --- | --- |
| I²C (SCD30 0x61, TSL2591 0x29) | SDA 8, SCL 9 |
| RS485 (sondas de suelo y PAR) | RX 18, TX 17 |
| DHT22 de la caja | 4 |
| Ventilador | 5 |
| LEDs blancos (MOSFET) | **6** |
| LED UV (MOSFET) | **10** |

El equipo confirmó los pines 6 y 10 (22-nov-2026); la primera propuesta era 13 y 14 y ya se corrigió en el manual.

## Librerías (Arduino IDE)

SparkFun SCD30 Arduino Library, Adafruit TSL2591 Library, Adafruit Unified Sensor, modbus-esp8266
(`ModbusRTU.h`, de emelianov) y DHT sensor library (Adafruit).

## Pendiente conocido

- PAR en 0.0: falta revisar el registro del sensor con su hoja de datos.
- Si la ESP32 se traba, el puente de la Pi la reinicia sola (sin tramas completas en 3 min o sin suelo en 30 min).
