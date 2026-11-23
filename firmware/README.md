# Firmware de la ESP32-S3

`PAYLOAD/PAYLOAD.ino` es el firmware cargado en la ESP32 (comparado el 22-nov-2026): intervalos por grupo de
sensores, ventilador a 25/22 °C, `Wire.setTimeOut(200)` y envío de la trama cada 60 s. Si se carga otra versión,
subirla aquí.

## Resumen

- Placa: ESP32-S3 Dev Module, conectada a la Pi por el puerto **UART/COM** (CP210x → `/dev/esp32`), *USB CDC On Boot: Disabled*.
- Envía cada `T_ENVIO` (60 s) la trama `$EST,co2=..,ta=..,hra=..,lux=..,par=..,tc=..,vent=..,luz=..,scd=..,tsl=..[,s1h=..,...]`.
  PAR y lux van promediados; los datos de suelo solo van en la trama siguiente a cada ronda (`T_SUELO`, 15 min).
- Órdenes por serial (las reenvía el puente desde `trigal/estacion1/cmd`): `{"cmd":"blanco"}`, `{"cmd":"uv"}`,
  `{"cmd":"apagar"}`, `{"cmd":"ping"}`, opcional `"seg"` para calibrar (máx. 300 s).
- MEF de luces `LUZ_APAGADA / LUZ_BLANCA / LUZ_UV`; responde `Estado: ...`, `#OK,luz lista`, `#ERR,...`.

## Pines

| Señal | GPIO |
| --- | --- |
| I²C (SCD30 0x61, TSL2591 0x29) | SDA 8, SCL 9 |
| RS485 (sondas de suelo y PAR) | RX 18, TX 17 |
| DHT22 de la caja | 4 |
| Ventilador | 5 |
| LEDs blancos (MOSFET) | **6** |
| LED UV (MOSFET) | **10** |

## Librerías (Arduino IDE)

SparkFun SCD30 Arduino Library, Adafruit TSL2591 Library, Adafruit Unified Sensor, modbus-esp8266
(`ModbusRTU.h`, de emelianov) y DHT sensor library (Adafruit).

## Si la ESP32 se traba

El puente de la Pi la reinicia sola (sin tramas completas en 3 min o sin suelo en 30 min).
