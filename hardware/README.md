# Hardware

Fichas técnicas de los componentes de la estación y el proyecto de Proteus del circuito. Los documentos son de cada
fabricante y se guardan aquí para que no dependan de enlaces que pueden cambiar.

## Fichas técnicas (`fichas/`)

| Componente | Archivo | Qué consultar |
| --- | --- | --- |
| Sondas de suelo JXBS-3001 (humedad, temperatura, CE, pH) | `JXBS-3001_sonda-suelo-RS485.pdf` | Registros Modbus, rangos, cableado |
| Sensor PAR SEN0641 (DFRobot) | `SEN0641_sensor-PAR_DFRobot.pdf`, `SEN0641_sensor-PAR_dimensiones.jpg` | Características y medidas |
| Sensor PAR SEN0641: registros | `SEN0641_protocolo-modbus.md` | Dirección, velocidad, registros y tramas de ejemplo |
| SCD30 (CO₂, temperatura, humedad, Sensirion) | `SCD30_datasheet_Sensirion.pdf` | Precisión, alimentación, pines (SEL) |
| SCD30: comandos | `SCD30_descripcion-interfaz_Sensirion.pdf` | I²C (máx. 100 kHz, *clock stretching*), calibración forzada, autocalibración, altitud |
| TSL2591 (lux, ams) | `TSL2591_datasheet_ams.pdf` | Ganancia, tiempo de integración, saturación |
| DHT22 / AM2302 (temperatura de la caja) | `DHT22_AM2302_datasheet_Aosong.pdf` | Alimentación 3,3 a 6 V, lectura cada 2 s como mínimo |
| Controlador MOSFET DFR0457 (LEDs y ventilador) | `DFR0457_controlador-MOSFET_DFRobot.pdf`, `DFR0457_esquematico.pdf` | VIN 5 a 36 V, lógica 3,3 a 10 V, hasta 20 A |
| Fuente Mean Well LRS-35-12 (12 V, 3 A) | `LRS-35-12_fuente-12V_MeanWell.pdf` | Entrada universal 85 a 264 VAC (sin selector) |
| ESP32-S3 (Espressif) | `ESP32-S3_datasheet_Espressif.pdf`, `ESP32-S3-WROOM-1_modulo_Espressif.pdf` | GPIO, pines de arranque, características eléctricas |
| Módulo 4G SIM7600G-H M.2 (SIMCom) | `SIM7600X-M2_diseno-hardware_SIMCom.pdf`, `SIM7600G-H_diseno-hardware_SIMCom.pdf` | Alimentación, interfaces USB, bandas |

No están aquí (se consultan en línea):

- Manual de comandos AT del SIM7600 (*SIM7500_SIM7600 Series AT Command Manual V3.00*, en simcom.com y en la wiki de
  Waveshare): ahí están `AT+CUSBPIDSWITCH`, `AT+CGDCONT` y `AT+CRESET`, que usa la estación.
- Wiki del HAT Waveshare M.2 (switches A/B/C, alimentación USB-C): https://www.waveshare.com/wiki/SIM7600G-H-M2_4G_HAT
- Módulo RS485 a TTL: es un módulo genérico, sin ficha del fabricante.

## Proyecto de Proteus (`proteus/`)

`Estacion_movil.pdsprj.zip` (septiembre de 2026). Se descomprime y se abre `Estacion_movil.pdsprj`.

La versión entregada **no usa PCB**: cada equipo se alimenta por separado desde una multitoma. El plano de Proteus
sirve como referencia de pines (RS485 TX en GPIO 17 y RX en GPIO 18, DHT22 en GPIO 4). Si no coincide con el firmware,
vale lo que dice `firmware/PAYLOAD/PAYLOAD.ino` (sección 3 del manual técnico).

La lista de materiales, el cableado y la energía están en la sección 3 de `docs/manual-tecnico.md`.
