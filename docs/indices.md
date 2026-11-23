# Índices fisiológicos – Estación Trigal (snapdragon)

## Dónde se calcula cada índice

| Índice | Dónde | Cada cuánto | Fórmula |
|---|---|---|---|
| DPV | Node-RED (función "Índices instantáneos") | cada trama (60 s); Grafana promedia cada 15 min | SVP = 0,6108·exp(17,27·T/(T+237,3)); DPV = SVP·(1 − HR/100) |
| Tmáx, Tmín, Tmedia | Tarea de InfluxDB `indices_diarios` | 00:10 de cada día | máx. y mín. de los promedios de 5 min |
| GDD | Grafana, con la T-base del ciclo | al abrir el tablero | GDD = (Tmáx + Tmín)/2 − T-base; si < 0 → 0; acumulado = Σ desde el inicio del ciclo |
| DLI | Tarea de InfluxDB | 00:10 | Σ(PPFD × Δt)/1 000 000; Δt máximo 150 s (la ESP32 envía cada 60 s), para no inventar luz en los huecos |
| Fotoperiodo | Tarea de InfluxDB | 00:10 | hora fin luz − hora inicio luz; luz efectiva = PPFD ≥ 2 µmol/m²/s durante un minuto completo |

La tarea guarda un registro por día en la tabla `diario` del bucket `estacion` con los campos `tmax`, `tmin`, `tmedia`, `dli`, `fotoperiodo`, `inicio_luz`, `fin_luz` (en segundos) y `horas_datos`.

El GDD se calcula en Grafana para que, al cambiar la T-base o las fechas del ciclo, todo el histórico se recalcule sin tocar la base de datos.

## Instalación de la tarea

No usar **Import Task** (solo acepta plantillas JSON).

1. InfluxDB (`http://<ip-de-la-pi>:8086`) → **Tasks** → **+ Create Task** → **New Task**.
2. Name `indices_diarios`, Schedule **CRON** `10 5 * * *` (05:10 UTC = 00:10 en Colombia), Offset `0m`.
3. Pegar el contenido de `influxdb/indices_diarios.flux` en el editor → **Save** → **Run Task** → en **Runs** debe salir `success`.

**Llenar días anteriores (una sola vez):** Data Explorer → Script Editor, pegar el script y cambiar
`fin = date.truncate(...)` e `inicio = date.sub(...)` por fechas fijas, por ejemplo
`inicio = 2026-11-01T00:00:00-05:00` y `fin = 2026-11-19T00:00:00-05:00`. Ejecutar con **Submit**.

## Parámetros que se pueden cambiar

- `T-base` e inicio/fin del ciclo: en la página `/ciclo` de Node-RED (registro por lote).
- `UMBRAL_LUZ` (2 µmol/m²/s), `UMBRAL_LUX` (108 lux) y `DT_MAX` (150 s; era 60 s cuando la ESP32 enviaba cada 5 s): al inicio de `indices_diarios.flux`.

## Pruebas realizadas

Con 5 días de datos simulados (lectura cada 5 s, 2 h sin datos un día, flashes de LED a las 4:00 y 20:00) en InfluxDB 2.7 y Grafana 12.2:
DLI 24,76 mol/m²/d (19,26 el día del hueco, marcado con 22 h de datos), fotoperiodo 11:58:00 sin contar los flashes,
y GDD correcto con T-base 5 y 10 °C y con fecha de fin.
