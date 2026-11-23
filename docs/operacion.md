# Operación — Estación portátil Trigal (rpi4trigal)

## Qué arranca solo al encender la Pi
| Pieza | Cómo arranca |
| --- | --- |
| Módem 4G (`claro4g`, usb0) | NetworkManager, reintentos sin límite |
| Vigilante del 4G | `lte-watchdog.timer` (90 s tras arrancar y cada 5 min) |
| Mosquitto, Node-RED, InfluxDB, Grafana, cloudflared, Portainer | Docker con `restart: unless-stopped` |
| Puente ESP32 → MQTT | `trigal-serial.service` (espera la hora por internet con `esperar-hora`) |
| Cámara (fastapi-cam, puerto 3333) y fotos 4:00 / 12:00 / 20:00 | `camara.service` |
| Subida de fotos a Drive | `fotos-nube.timer` (10 min tras arrancar y cada hora) |
| Revisión automática | `revisar-estacion.timer` (6 min tras arrancar) → `~/ultimo-arranque.txt` |

## Instalar el comando de revisión
```bash
sudo cp revisar-estacion /usr/local/bin/ && sudo chmod +x /usr/local/bin/revisar-estacion
sudo cp revisar-estacion.service revisar-estacion.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable revisar-estacion.timer
revisar-estacion
```

## Wifi solo para la red local
El wifi de la universidad bloquea el puerto 7844 del túnel. Si la Pi sale a internet por wifi, el dashboard público da Error 1033. Con esto el wifi sirve para SSH y el internet sale siempre por el 4G:
```bash
WIFI=$(nmcli -t -f NAME,DEVICE connection show --active | grep ':wlan0$' | cut -d: -f1); echo "Wifi: $WIFI"
sudo nmcli connection modify "$WIFI" ipv4.never-default yes ipv6.never-default yes
sudo nmcli connection up "$WIFI"
```
Se aplica por cada red wifi (también al hotspot de un celular si se agrega).

## Prueba de arranque en frío
1. `sudo poweroff`, desconectar la corriente 10 s y volver a conectar (simula un corte en el invernadero).
2. Esperar 7 minutos sin tocar nada.
3. `cat ~/ultimo-arranque.txt` → debe terminar en "Todo lo esencial está funcionando".
4. Abrir `https://iot.trigal-digital.com` desde un celular con datos (no desde el wifi de la U).

## Si algo no carga en campo
Entrar por Raspberry Pi Connect (sale por el 4G) y ejecutar `revisar-estacion` o `cat ~/ultimo-arranque.txt`.
