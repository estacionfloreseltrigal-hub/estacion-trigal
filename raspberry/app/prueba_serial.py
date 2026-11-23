#!/usr/bin/env python3
"""
Prueba 1 - Estación Trigal: ¿llegan bien los datos de la ESP32 por USB?

Lee el puerto serial durante N segundos, valida cada línea como JSON y al final
muestra un resumen: líneas válidas, inválidas, tipos recibidos y paquetes perdidos
(según el contador "seq"). Con --ping también prueba el sentido Raspberry -> ESP32.

Uso:
    python3 prueba_serial.py                 # detecta el puerto solo, 30 s
    python3 prueba_serial.py --segundos 60 --ping
    python3 prueba_serial.py --puerto /dev/ttyUSB0
"""
import argparse
import glob
import json
import os
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("Falta pyserial. Instálalo con:  sudo apt install -y python3-serial")


# Puertos que NO son la ESP32: el SIM7600 crea varios /dev/ttyUSB* (AT, GPS, PPP...)
EXCLUIR = ("SimTech", "SIM7600", "Qualcomm", "Quectel")
# Nombres típicos de la ESP32-S3: USB nativo (Espressif) o chips CH340 / CP210x
PREFERIR = ("Espressif", "esp32", "1a86", "CH340", "CP210", "Silicon_Labs")


def abrir_serial(puerto, baudios):
    """Abre el puerto SIN mover DTR/RTS, para no dejar la ESP32 en modo de carga de programa."""
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = puerto, baudios, 1
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def reiniciar_esp(ser):
    """Reinicio normal de la ESP32 (EN abajo y arriba con IO0 en alto): arranca ejecutando el programa."""
    try:
        ser.dtr = False
        ser.rts = True
        time.sleep(0.2)
        ser.rts = False
    except (OSError, serial.SerialException):
        pass  # algunos puertos no tienen estas señales


def buscar_puerto_esp():
    """Busca la ESP32 sin confundirla con los puertos del módulo 4G."""
    if os.path.exists("/dev/esp32"):          # enlace creado por la regla udev 99-esp32.rules
        return "/dev/esp32"
    por_id = sorted(glob.glob("/dev/serial/by-id/*"))
    candidatos = [p for p in por_id if not any(x.lower() in p.lower() for x in EXCLUIR)]
    for p in candidatos:
        if any(x.lower() in p.lower() for x in PREFERIR):
            return p
    if candidatos:
        return candidatos[0]
    if not por_id:                             # sin /dev/serial/by-id: último recurso
        acm = sorted(glob.glob("/dev/ttyACM*"))
        if acm:
            return acm[0]
    return None


def main():
    ap = argparse.ArgumentParser(description="Prueba de lectura serial ESP32 -> Raspberry")
    ap.add_argument("--puerto", help="ej. /dev/ttyACM0 (si se omite, se detecta)")
    ap.add_argument("--baudios", type=int, default=115200)
    ap.add_argument("--segundos", type=int, default=30)
    ap.add_argument("--ping", action="store_true", help="envía {\"cmd\":\"ping\"} y espera respuesta")
    args = ap.parse_args()

    puerto = args.puerto or buscar_puerto_esp()
    if not puerto:
        sys.exit("No encontré ningún puerto. ¿Está conectada la ESP32? Revisa con:  ls /dev/ttyACM* /dev/ttyUSB*")

    print(f"Abriendo {puerto} a {args.baudios} baudios durante {args.segundos} s ...")
    try:
        ser = abrir_serial(puerto, args.baudios)
    except serial.SerialException as e:
        if "Permission denied" in str(e):
            sys.exit(f"Sin permiso para {puerto}. Corre:  sudo usermod -aG dialout $USER  y cierra/abre sesión.")
        sys.exit(f"No pude abrir {puerto}: {e}")

    # Reinicio limpio de la ESP32 y se descarta lo que imprime al arrancar.
    reiniciar_esp(ser)
    time.sleep(2.5)
    ser.reset_input_buffer()

    total = validas = invalidas = 0
    por_tipo = {}
    ultimo_seq = None
    perdidos = 0
    ping_enviado = ping_ok = False
    t_ping = 0.0
    inicio = time.time()

    while time.time() - inicio < args.segundos:
        if args.ping and not ping_enviado and time.time() - inicio > 8:
            ser.write(b'{"cmd":"ping"}\n')
            ping_enviado, t_ping = True, time.time()
            print(">> enviado a la ESP32: {\"cmd\":\"ping\"}")

        crudo = ser.readline()
        if not crudo:
            continue
        total += 1
        texto = crudo.decode("utf-8", errors="replace").strip()

        # Trama de la ESP32 y avisos (#OK, #ERR, Estado:)
        if texto.startswith("$EST") or texto.startswith("#") or texto.startswith("Estado:"):
            validas += 1
            tipo = "EST" if texto.startswith("$EST") else "aviso"
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
            if texto.startswith("#OK,ping"):
                ping_ok = True
                print(f"<< respuesta de la ESP32 en {(time.time() - t_ping) * 1000:.0f} ms: {texto}")
            else:
                print(f"   [{tipo:8}] {texto}")
            continue

        try:
            dato = json.loads(texto)
            if not isinstance(dato, dict):
                raise ValueError("no es un objeto JSON")
        except ValueError:
            invalidas += 1
            print(f"   [NO VALE] {texto!r}")
            continue

        validas += 1
        tipo = dato.get("t", "?")
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1

        seq = dato.get("seq")
        if isinstance(seq, int) and tipo == "ambiente":
            if ultimo_seq is not None and seq > ultimo_seq + 1:
                perdidos += seq - ultimo_seq - 1
                print(f"   [AVISO] se saltó de seq {ultimo_seq} a {seq}")
            ultimo_seq = seq

        if tipo == "resp" and dato.get("cmd") == "ping":
            ping_ok = True
            print(f"<< respuesta de la ESP32 en {(time.time() - t_ping) * 1000:.0f} ms: {texto}")
        else:
            print(f"   [{tipo:8}] {texto}")

    ser.close()

    print("\n========== RESUMEN ==========")
    print(f"Puerto:            {puerto}")
    print(f"Líneas recibidas:  {total}")
    print(f"Líneas válidas:    {validas}")
    print(f"Líneas inválidas:  {invalidas}")
    print(f"Por tipo:          {por_tipo}")
    print(f"Paquetes perdidos: {perdidos} (solo con el sketch de prueba JSON)")
    if args.ping:
        print(f"Ping Pi -> ESP32:  {'OK' if ping_ok else 'SIN RESPUESTA'}")

    bien = validas > 0 and invalidas == 0 and perdidos == 0 and (ping_ok or not args.ping)
    print("RESULTADO:", "✅ comunicación correcta" if bien else "⚠️  revisar (ver detalles arriba)")
    sys.exit(0 if bien else 1)


if __name__ == "__main__":
    main()
