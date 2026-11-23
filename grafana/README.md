# Grafana

Tableros copiados de la Pi el 23-nov-2026 por la API de Grafana:

- `dashboards/estacion-trigal.json`: **Estación Trigal**, el principal (39 paneles; el de visitantes en modo kiosco)
- `dashboards/estacion-trigal-administracion.json`: **Estación Trigal - Administración** (4 paneles)

La clave de la cámara aparece como `<CAM_CLAVE>`. Al importar (Dashboards → New → Import) hay que
reemplazarla por la real y elegir la fuente de datos InfluxDB.

## Cómo actualizarlos

**Opción A (automática):** correr `recolectar-desde-la-pi.sh` en la Pi y dar la clave de `admin_trigal`
cuando la pida. Los baja todos a `grafana/dashboards/` y reemplaza la clave de la cámara por `<CAM_CLAVE>`.

**Opción B (a mano):** abrir cada tablero → *Share* (Compartir) → *Export* → *Save to file*, y guardar
el archivo en `grafana/dashboards/`. Antes de subirlo a GitHub, buscar en el archivo la clave de la cámara
(aparece en `data-cam` como `https://cam.trigal-digital.com/<clave>`) y reemplazarla por `<CAM_CLAVE>`.

## Configuración que no está en los tableros

- Fuente de datos InfluxDB (Flux): URL `http://localhost:8086`, org `trigal`, bucket `estacion`, token de solo lectura.
- `GF_PANELS_DISABLE_SANITIZE_HTML=true` (ver `docker/stacks/grafana.yml`): sin esto no funcionan los botones de la cámara.
- Usuarios: `admin_trigal` (administrador) y `trigal_visor` (Viewer, para El Trigal y visitantes).
