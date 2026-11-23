# Node-RED

| Archivo | Estado |
| --- | --- |
| `flujo_estacion_trigal.json` | Pestaña "Estación Trigal" (datos → índices DPV y punto de rocío → InfluxDB, órdenes a los LEDs). Versión del 12-nov guardada en el Project. |
| Pestaña "Ciclos del cultivo" (`/ciclo`) | **Falta**: exportar desde la Pi |
| Pestaña "Consulta y descarga" (`/descarga`) | **Falta**: exportar desde la Pi |
| Pestañas de formularios de administración | **Falta**: exportar desde la Pi |

Los flujos de ciclos y descargas se generaron con scripts y se corrigieron varias veces; reconstruirlos
desde las conversaciones daría una versión vieja. Para tener los que funcionan:

- **Automático:** `recolectar-desde-la-pi.sh` copia `/opt/trigal/nodered/data/flows.json` (todas las pestañas)
  y `settings.js` con los hashes reemplazados.
- **A mano:** en `http://10.10.80.48:1880` → menú ☰ → *Exportar* → *Todos los flujos* → *Descargar*, y guardar
  el archivo aquí como `flows.json`.

Las credenciales de los nodos (token de InfluxDB, clave de Mosquitto) quedan en `flows_cred.json`, que **no** se sube.
Al importar en otra Node-RED hay que volver a ponerlas en los nodos de configuración `influxdb-local` y `mosquitto-local`.

Guía de uso de las páginas: `docs/descargas.md` y la sección 7 del manual técnico.
