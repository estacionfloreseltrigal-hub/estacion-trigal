// Tarea de InfluxDB: índices diarios de la estación Trigal
// Corre a las 00:10 de Colombia y guarda el resumen de los últimos 3 días
// en la tabla "diario" del mismo bucket. Recalcular 3 días llena los que se
// perdieron si la Pi estaba apagada a esa hora; los días ya guardados se sobrescriben igual.
//
// Campos que guarda (uno por día, con la hora 00:00 de ese día):
//   tmax, tmin, tmedia   °C   (para GDD; la T-base se aplica en Grafana)
//   dli                  mol/m²/d
//   fotoperiodo          segundos (Grafana lo muestra como hh:mm:ss)
//   inicio_luz, fin_luz  segundos desde la medianoche (hh:mm:ss en Grafana)
//   fotoperiodo_lux, inicio_luz_lux, fin_luz_lux
//                        lo mismo, calculado con los lux del TSL2591 (respaldo si no hay PAR)
//   horas_datos          horas del día con lecturas de PAR (para ver si el día está completo)
//
// Para llenar días anteriores: copiar el script en Data Explorer (Script Editor),
// cambiar "inicio" y "fin" por las fechas deseadas y ejecutarlo una vez.

import "date"
import "timezone"

option location = timezone.location(name: "America/Bogota")
option task = {name: "indices_diarios", cron: "10 5 * * *"}   // 05:10 UTC = 00:10 en Colombia

// Parámetros
UMBRAL_LUZ = 2.0      // PPFD (µmol/m²/s) a partir del cual hay "luz efectiva"
UMBRAL_LUX = 108.0    // el mismo umbral en lux (luz solar: 1 µmol/m²/s ≈ 54 lux)
DT_MAX = 150.0        // segundos máximos entre dos lecturas que se cuentan (si hay un hueco, no se inventa luz). 150 porque la ESP32 envía cada 60 s

fin = date.truncate(t: now(), unit: 1d)
inicio = date.sub(d: 3d, from: fin)

campo = (f) => from(bucket: "estacion")
    |> range(start: inicio, stop: fin)
    |> filter(fn: (r) => r._measurement == "datos" and r._field == f)
    |> keep(columns: ["_time", "_value", "_field", "_measurement"])

guardar = (tables=<-, nombre) => tables
    |> map(fn: (r) => ({_time: r._time, _measurement: "diario", _field: nombre, _value: float(v: r._value)}))
    |> to(bucket: "estacion")

// 1. Temperatura: máxima y mínima de los promedios de 5 min (así un pico suelto del sensor no cuenta)
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

// 3. Fotoperiodo = hora fin de luz − hora inicio de luz
// Se toma el mínimo de cada minuto: el flash de los LED al tomar la foto (segundos)
// no alcanza a contar como luz, solo cuenta un minuto completo sobre el umbral.
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
