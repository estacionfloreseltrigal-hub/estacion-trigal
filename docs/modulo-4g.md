# Módulo 4G — SIM7600G-H-M2 en la Raspberry Pi 4 (Estación portátil Trigal)

Estado: funcionando desde el 5 de noviembre de 2026 en la Pi `rpi4trigal` (Raspberry Pi OS Trixie).

## Configuración que quedó en la Pi
- HAT Waveshare M.2 TO 4G/5G con módulo SIM7600G-H R2, conectado por USB a un puerto azul de la Pi.
- Switches del reverso: todas las posiciones "A" en ON; las "B" y "B/C" en OFF.
- DIP del frente PWR-D5 / RST-D6: OFF. Switch deslizante: EXT PWR (USB-C con fuente 5 V / 3 A).
- SIM Claro prepago (nano) en la ranura Nano SIM1. APN: internet.comcel.com.co
- Modo RNDIS (`AT+CUSBPIDSWITCH=9011,1,1`): la Pi ve el 4G como la interfaz `usb0`.
- Perfil de NetworkManager `claro4g` con métrica 700: el WiFi tiene prioridad para IPv4 cuando existe; en campo sale por Claro.
- ModemManager desactivado (`sudo systemctl disable --now ModemManager`).
- Reintentos sin límite para claro4g (10-nov-2026): `sudo nmcli connection modify claro4g connection.autoconnect-retries 0 ipv4.dhcp-timeout infinity`. Corrigió que al encender la Pi no conectara hasta presionar RESET del HAT (NetworkManager se rendía antes de que el módulo estuviera listo).
- Prueba: CSQ 30, LTE banda 7 (732-101), ping ~45 ms, navega con el WiFi apagado y reconecta tras reiniciar.

## Puertos serie del módulo en modo RNDIS (verificado 11-nov-2026)
| Puerto | Interfaz USB | Función |
| --- | --- | --- |
| ttyUSB1 | if02 | Diagnóstico |
| ttyUSB2 | if03 | GPS (salida NMEA: $GPRMC, $GPGGA...) |
| ttyUSB3 | if04 | **Comandos AT** |
| ttyUSB4 | if05 | Módem PPP (responde AT, no se usa) |
| ttyUSB5 | if06 | Audio |

La numeración ttyUSB cambia entre arranques (el 20-nov la ESP32 quedó en ttyUSB5). Usar siempre la ruta fija del puerto AT:
`/dev/serial/by-id/usb-SimTech__Incorporated_SimTech__Incorporated_0123456789ABCDEF-if04-port0`

## Hallazgos y correcciones
- 11-nov: el 4G funcionaba solo por IPv6. El perfil 1 del módem tenía el APN mal escrito (`"IP","internet.comcel.com"`, sin `.co`) y sin dirección.
- 20-nov: corregido con `AT+CGDCONT=1,"IPV4V6","internet.comcel.com.co"` y `AT+CRESET` por el puerto if04. Verificado con datos: `curl -4` y `curl -6` → 204, ping IPv4 a 8.8.8.8 ~41 ms.
- 20-nov: la SIM prepago se quedó sin datos. Síntoma: toda la navegación (IPv4 e IPv6) responde 302 hacia `compras.claro.com.co/orquestadordatos?user=PREPAGO`, HTTPS no conecta, Pi Connect y el túnel caen. Revisar saldo en Mi Claro.
- El vigilante v1 solo probaba ping IPv4 y enviaba `AT+CRESET` a ttyUSB2 (GPS). Al no ver IPv4, ejecutaba `nmcli connection up claro4g` cada 5 min, lo que cortaba usb0 y el túnel de Cloudflare (Error 1033). Se reemplazó por la v2.
- Todo lo que tenga IPv6 sale por el 4G aunque haya WiFi (el WiFi de la U solo da IPv4): Google Drive (rclone), apt, Docker, Pi Connect. Para instalar paquetes sin gastar datos: `sudo apt -o Acquire::ForceIPv4=true install ...`.
- Consumo: `vnstat` instalado (20-nov). `vnstat -i usb0 -d` muestra el consumo diario. Estimado: 3–5 GB/mes; paquete sugerido 8–10 GB hasta medir el real.

## Archivos (en `raspberry/` de este repositorio)
| Archivo | Ruta en la Pi | Qué hace |
| --- | --- | --- |
| lte-watchdog.sh | /usr/local/bin/lte-watchdog.sh | v2: prueba internet por IPv4 e IPv6 (ping y web). Si falla, reactiva claro4g; tras 3 revisiones seguidas sin red, reinicia el módulo (AT+CRESET por el puerto if04) |
| lte-watchdog.service | /etc/systemd/system/lte-watchdog.service | Servicio que ejecuta el script |
| lte-watchdog.timer | /etc/systemd/system/lte-watchdog.timer | Lo ejecuta 90 s después de arrancar y luego cada 5 min |

## Instalación del vigilante
```bash
sudo cp lte-watchdog.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/lte-watchdog.sh
sudo cp lte-watchdog.service lte-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lte-watchdog.timer
systemctl list-timers | grep lte      # comprobar que quedó programado
journalctl -t lte-watchdog            # ver qué ha hecho (vacío = nunca hubo fallas)
```
Antes de instalar, confirmar con `ls -l /dev/serial/by-id/` que existe la ruta `...-if04-port0` (puerto AT).

## Decisiones de arquitectura
- El vigilante corre en la Pi (systemd), separado del código de sensores y fuera de Docker: si la aplicación falla, la red y el acceso por Raspberry Pi Connect siguen vivos.
- Docker: `restart: unless-stopped`; los contenedores salen a internet por la Pi sin configuración extra.
- Descargar o actualizar imágenes Docker y el sistema solo con WiFi, para no gastar los datos del plan de Claro.
- La red WiFi de la universidad bloquea el puerto 7844 que usa el túnel de Cloudflare; el túnel solo conecta por el 4G.
- Registros del sistema persistentes (20-nov): `/etc/systemd/journald.conf.d/50-persistente.conf` con `Storage=persistent` y `SystemMaxUse=200M`.
- GPS del módulo: no se usa en el proyecto.
