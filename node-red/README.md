# Node-RED

| Archivo | Qué es |
| --- | --- |
| `flows.json` | Todos los flujos, copiados de la Pi el 23-nov-2026. Pestañas: **Estación Trigal** (datos → DPV y punto de rocío → InfluxDB, órdenes a los LEDs), **Ciclos del cultivo** (`/ciclo`) y **Consulta y descarga** (`/descarga`). |
| `settings.js` | Configuración de Node-RED. Los hashes de las claves (`adminAuth` y `httpNodeAuth` de `admin_trigal`) van como `<HASH_BCRYPT>`. |
| `package.json` | Nodos instalados: `node-red-contrib-influxdb` y `@flowfuse/node-red-dashboard`. |

Todo va en `/opt/trigal/nodered/data/` en la Pi.

Para reinstalar: copiar los tres archivos, generar los hashes con `docker exec -it node-red node-red admin hash-pw`
y ponerlos en `settings.js`. Luego reiniciar el contenedor e instalar los nodos (*Manage palette*), o correr `npm install` en `/data`.

Las credenciales de los nodos (token de InfluxDB, clave de Mosquitto) quedan en `flows_cred.json`, que **no** se sube.
Al importar en otra Node-RED hay que volver a ponerlas en los nodos de configuración `influxdb-local` y `mosquitto-local`.

Para actualizar este archivo: correr `recolectar-desde-la-pi.sh` en la Pi, o en Node-RED ☰ → *Exportar* → *Todos los flujos*.

Guía de uso de las páginas: `docs/descargas.md` y la sección 7 del manual técnico.
