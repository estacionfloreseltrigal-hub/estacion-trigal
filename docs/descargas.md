# Consulta y descarga de datos

Pestaña de Node-RED "Consulta y descarga" (incluida en `node-red/flows.json`).

Página: `http://<ip-de-la-pi>:1880/descarga` y `https://iot.trigal-digital.com/descarga` (pide usuario y clave).

## Criterios
| Criterio | Opciones |
|---|---|
| Qué datos | Lecturas de sensores, o resumen diario (Tmáx, Tmín, Tmedia, GDD y GDD acumulado del ciclo, DLI, inicio y fin de luz, fotoperiodo, horas con datos) |
| Cuándo | Un ciclo/lote de la lista, o un rango de fechas |
| Horario | Hora local de inicio y fin, por ejemplo 06:00 a 18:00 |
| Variables | Las que la estación haya enviado en los últimos 30 días (se cargan solas) |
| Agrupar | Sin agrupar (cada 5 s), 1 min, 5 min, 15 min, 1 h, 1 día (promedio) |
| Formato | Excel: `;` y coma decimal, fecha `2026-11-18 14:00:00`. R/Python: `,` y punto decimal, fecha ISO con `-05:00` |

Cada fila trae el lote y la ubicación según el ciclo de esa fecha. "Consultar" muestra las primeras 20 filas;
"Descargar CSV" baja el archivo. Máximo 100 000 filas por descarga (unos 5 días sin agrupar, o años con 15 min);
si se pasa, la página dice cuántas serían y pide agrupar más o acortar el rango.

## Desde R o Python
La página muestra el enlace exacto con los criterios elegidos. Con usuario y clave:

```r
library(httr)
r <- GET("https://iot.trigal-digital.com/descarga/csv?tipo=diario&ciclo=1234_2026-11-10&formato=codigo",
         authenticate("usuario", "clave"))
datos <- read.csv(text = content(r, "text", encoding = "UTF-8"))
```
```python
import io, requests, pandas as pd
r = requests.get("https://iot.trigal-digital.com/descarga/csv",
                 params={"tipo": "lecturas", "desde": "2026-11-10", "hasta": "2026-11-14",
                         "campos": "temperatura,humedad,par,dpv", "intervalo": "15m", "formato": "codigo"},
                 auth=("usuario", "clave"))
datos = pd.read_csv(io.StringIO(r.text), parse_dates=["fecha_hora"])
```

## Publicación en iot.trigal-digital.com
Solo se publican `/ciclo` y `/descarga`; el editor de Node-RED sigue siendo local.

1. **Clave de las páginas:** `httpNodeAuth` en `/opt/trigal/nodered/data/settings.js` (hash bcrypt de la clave estandarizada).
2. **Ruta del túnel de Cloudflare** (`rpi4trigal`), ANTES de la de Grafana: hostname `iot.trigal-digital.com`, ruta `^/(ciclo|descarga)`, servicio `http://localhost:1880`. La de Grafana (ruta vacía → `http://localhost:3000`) va de última.
3. No agregar ninguna otra ruta a `localhost:1880` (expondría el editor de Node-RED).

El token de Node-RED para InfluxDB debe tener permiso de **lectura y escritura** sobre el bucket `estacion`.

Probado con InfluxDB 2.7 y Node-RED 4: 84 960 filas sin agrupar en menos de 1 s, y los dos formatos leídos con pandas.
