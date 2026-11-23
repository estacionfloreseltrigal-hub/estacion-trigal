# Hardware

| Archivo | Qué es |
| --- | --- |
| `fichas/JXBS-3001_sonda-suelo-RS485.pdf` | Ficha técnica de las sondas de suelo JXBS-3001 (humedad, temperatura, CE y pH por RS485 Modbus): registros, rangos y cableado |
| `proteus/Estacion_movil.pdsprj.zip` | Proyecto de Proteus del circuito (septiembre de 2026). Se descomprime y se abre `Estacion_movil.pdsprj` |

La versión entregada **no usa PCB**: cada equipo se alimenta por separado desde una multitoma. El plano de Proteus
sirve como referencia de pines (RS485 TX en GPIO 17 y RX en GPIO 18, DHT22 en GPIO 4). Si no coincide con el firmware,
vale lo que dice `firmware/PAYLOAD/PAYLOAD.ino` (sección 3 del manual técnico).

La lista de materiales, el cableado y la energía están en la sección 3 de `docs/manual-tecnico.md`.

Faltan las fichas del sensor PAR SEN0641 (DFRobot), del SCD30, del TSL2591, del DFR0457 y del HAT SIM7600G-H.
Si se consiguen, agregarlas en `fichas/`.
