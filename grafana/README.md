# Grafana

Aquí van los tableros exportados en JSON:

- `trigal-estacion` (principal, el de visitantes en modo kiosco)
- `trigal-administracion`

No se pudieron rescatar de las conversaciones con seguridad: se generaron con scripts y después se
cambiaron a mano en Grafana (clave de la cámara, paneles de sistema, umbrales del plan de datos).
La versión buena es la que está en la Pi.

## Cómo exportarlos

**Opción A (automática):** correr `recolectar-desde-la-pi.sh` en la Pi y dar la clave de `admin_trigal`
cuando la pida. Los baja todos a `grafana/dashboards/` y reemplaza la clave de la cámara por `<CAM_CLAVE>`.

**Opción B (a mano):** abrir cada tablero → *Share* (Compartir) → *Export* → *Save to file*, y guardar
el archivo en `grafana/dashboards/`. Antes de subirlo a GitHub, buscar en el archivo la clave de la cámara
(aparece en `data-cam` como `https://cam.trigal-digital.com/<clave>`) y reemplazarla por `<CAM_CLAVE>`.

## Configuración que no está en los tableros

- Fuente de datos InfluxDB (Flux): URL `http://localhost:8086`, org `trigal`, bucket `estacion`, token de solo lectura.
- `GF_PANELS_DISABLE_SANITIZE_HTML=true` (ver `docker/stacks/grafana.yml`): sin esto no funcionan los botones de la cámara.
- Usuarios: `admin_trigal` (administrador) y `trigal_visor` (Viewer, para El Trigal y visitantes).
