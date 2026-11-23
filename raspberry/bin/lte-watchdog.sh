#!/bin/bash
# Vigilante 4G v2: revisa internet por IPv4 e IPv6 y solo actua tras 3 revisiones seguidas sin red.
IF=usb0
STATE=/run/lte-watchdog.fails
PORT=/dev/serial/by-id/usb-SimTech__Incorporated_SimTech__Incorporated_0123456789ABCDEF-if04-port0

hay_red() {
  ping -I "$IF" -c 2 -W 5 1.1.1.1 >/dev/null 2>&1 && return 0
  ping -6 -I "$IF" -c 2 -W 5 2606:4700:4700::1111 >/dev/null 2>&1 && return 0
  curl --interface "$IF" -s -o /dev/null -m 10 http://connectivitycheck.gstatic.com/generate_204 && return 0
  curl --interface "$IF" -s -o /dev/null -m 10 https://www.cloudflare.com/cdn-cgi/trace && return 0
  return 1
}

if hay_red; then
  rm -f "$STATE"
  exit 0
fi

FAILS=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 ))
echo "$FAILS" > "$STATE"
logger -t lte-watchdog "Sin internet por $IF (fallo $FAILS de 3)"

if [ "$FAILS" -lt 3 ]; then
  nmcli connection up claro4g >/dev/null 2>&1
  exit 0
fi

if [ -e "$PORT" ]; then
  logger -t lte-watchdog "3 revisiones seguidas sin red, reiniciando modulo"
  stty -F "$PORT" 115200 raw -echo 2>/dev/null
  printf 'AT+CRESET\r' > "$PORT"
else
  logger -t lte-watchdog "No se encontro el puerto AT del modulo"
fi
rm -f "$STATE"
