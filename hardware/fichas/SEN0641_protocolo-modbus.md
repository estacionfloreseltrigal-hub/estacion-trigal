# Sensor PAR SEN0641 (DFRobot): protocolo Modbus-RTU

Resumen de la página de protocolo del fabricante (https://wiki.dfrobot.com/sen0641/docs/20337), consultada el
23-nov-2026. La ficha en PDF de esta carpeta no trae los registros; por eso están aquí.

## Comunicación

| Parámetro | Valor |
| --- | --- |
| Interfaz | RS485, 8 bits de datos, sin paridad, 1 bit de parada, CRC-16 |
| Velocidad | 2400, 4800 o 9600 baudios (de fábrica 4800; la estación usa 4800) |
| Dirección | 1 a 254 (de fábrica 1; la estación usa 1) |
| Funciones | 0x03 (leer) y 0x06 (escribir) |
| Alimentación | 5 a 30 V DC, menos de 10 mA (en la estación, 12 V) |
| Rango | 0 a 2500 µmol·m⁻²·s⁻¹, 400 a 700 nm |
| Cables | Café +V, negro GND, amarillo A (485-A), azul B (485-B) |

## Registros

| Registro | Contenido | Acceso | Valores |
| --- | --- | --- | --- |
| `0x0000` | PAR | Lectura | µmol·m⁻²·s⁻¹ (en el firmware: `REG_PAR`) |
| `0x0052` | Corrección del PAR | Lectura y escritura | Entero con signo, en µmol·m⁻²·s⁻¹ |
| `0x07D0` | Dirección del sensor | Lectura y escritura | 1 a 254 |
| `0x07D1` | Velocidad | Lectura y escritura | 0 = 2400, 1 = 4800, 2 = 9600 |

## Tramas de ejemplo (hexadecimal)

| Para qué | Petición | Respuesta |
| --- | --- | --- |
| Leer el PAR (dirección 1) | `01 03 00 00 00 01 84 0A` | `01 03 02 00 64 9B AF` → 0x0064 = 100 µmol·m⁻²·s⁻¹ |
| Cambiar la dirección a 2 | `01 06 07 D0 00 02 08 86` | Repite la petición |
| Cambiar la velocidad a 9600 | `01 06 07 D1 00 02 59 46` | Repite la petición |
| Preguntar dirección y velocidad (difusión 0xFF, sensor conectado solo) | `FF 03 07 D0 00 02 D1 58` | `01 03 04 00 01 00 01 6A 33` → dirección 1, velocidad 4800 |

Los cambios de dirección o velocidad se aplican al reiniciar el sensor. Configurarlo siempre conectado solo al bus
(sección 12 del manual técnico) y luego ajustar `ID_SENSOR_PAR_1` y `BAUDIOS_485` en el firmware si cambiaron.
