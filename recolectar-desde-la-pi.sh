#!/bin/bash
# Recolecta de la Raspberry (rpi4trigal) las versiones ACTUALES de todo el código y la
# configuración de la estación, y las copia en esta carpeta del repositorio.
# Las claves, tokens y hashes se reemplazan por marcadores como <CAM_CLAVE>.
#
# Uso, en la Pi, dentro de la carpeta del repositorio:
#     bash recolectar-desde-la-pi.sh
# Pide la clave de sudo y, si se quiere, la del usuario admin_trigal de Grafana
# (para bajar los tableros). No cambia nada en la Pi: solo lee y copia.

set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAIZ:-}"                     # solo para pruebas fuera de la Pi
ENV="$RAIZ/opt/trigal/app/trigal.env"
NR="$RAIZ/opt/trigal/nodered/data"
CAM="$RAIZ/home/trigal/fastapi-cam"
SUDO="sudo"; [ -n "$RAIZ" ] && SUDO=""

COPIADOS=0; FALTAN=()
copiar() {   # copiar <origen> <destino>
  if $SUDO test -f "$1"; then
    mkdir -p "$(dirname "$2")"; $SUDO cat "$1" > "$2"; COPIADOS=$((COPIADOS+1))
  else
    FALTAN+=("$1")
  fi
}

echo "Recolectando en $REPO"
$SUDO true || { echo "Se necesita sudo"; exit 1; }

# 1. Servicios systemd (.service, .timer y carpetas .d) de la estación
echo "1. Servicios systemd"
UNIDADES=$( { ls "$RAIZ"/etc/systemd/system/{trigal-serial,camara,fotos-nube,lte-watchdog,revisar-estacion,metricas-sistema}.{service,timer} 2>/dev/null
              grep -lis trigal "$RAIZ"/etc/systemd/system/*.service "$RAIZ"/etc/systemd/system/*.timer 2>/dev/null; } | sort -u)
for u in $UNIDADES; do copiar "$u" "$REPO/raspberry/systemd/$(basename "$u")"; done
for d in "$RAIZ"/etc/systemd/system/{trigal-serial,camara,fotos-nube}.service.d; do
  [ -d "$d" ] && for f in "$d"/*.conf; do copiar "$f" "$REPO/raspberry/systemd/$(basename "$d")/$(basename "$f")"; done
done

# 2. Scripts de /usr/local/bin
echo "2. Scripts de /usr/local/bin"
for f in revisar-estacion prueba-final esperar-hora lte-watchdog.sh fotos-nube.sh metricas-sistema; do
  copiar "$RAIZ/usr/local/bin/$f" "$REPO/raspberry/bin/$f"
done
chmod +x "$REPO"/raspberry/bin/* 2>/dev/null

# 3. Puente ESP32 -> MQTT (/opt/trigal/app). Los .env no se copian: el repositorio tiene sus ejemplos.
echo "3. Puente serial"
for f in serial_mqtt.py prueba_serial.py; do copiar "$RAIZ/opt/trigal/app/$f" "$REPO/raspberry/app/$f"; done
if $SUDO test -r "$ENV"; then   # avisa si trigal.env tiene variables que el ejemplo no menciona
  for k in $($SUDO grep -oE '^[A-Za-z_]+=' "$ENV" | tr -d =); do
    grep -q "$k" "$REPO/raspberry/app/trigal.env.ejemplo" || echo "   ⚠️  $k está en trigal.env y falta en trigal.env.ejemplo"
  done
fi

# 4. Cámara: solo main.py (requirements.txt se mantiene en el repositorio)
echo "4. Cámara"
copiar "$CAM/main.py" "$REPO/raspberry/camara/main.py"

# 5. Regla udev de la ESP32 y registros persistentes
echo "5. udev y journald"
for f in $(grep -lis esp32 "$RAIZ"/etc/udev/rules.d/*.rules 2>/dev/null); do copiar "$f" "$REPO/raspberry/udev/$(basename "$f")"; done
for f in "$RAIZ"/etc/systemd/journald.conf.d/*.conf; do [ -f "$f" ] && copiar "$f" "$REPO/raspberry/sistema/journald.conf.d/$(basename "$f")"; done

# 6. Docker: archivos YML de cada contenedor y mosquitto.conf (nunca el archivo passwd)
echo "6. Docker"
for f in "$RAIZ"/opt/trigal/stacks/*.yml "$RAIZ"/opt/trigal/stacks/*.yaml; do   # los vacíos no se copian
  $SUDO test -s "$f" && copiar "$f" "$REPO/docker/stacks/$(basename "$f")"
done
copiar "$RAIZ/opt/trigal/mosquitto/config/mosquitto.conf" "$REPO/docker/mosquitto/mosquitto.conf"

# 7. Node-RED: flujos, paquetes instalados y settings.js (sin flows_cred.json)
echo "7. Node-RED"
copiar "$NR/flows.json" "$REPO/node-red/flows.json"
copiar "$NR/package.json" "$REPO/node-red/package.json"
if $SUDO test -f "$NR/settings.js"; then   # sin los comentarios de la plantilla de Node-RED
  $SUDO cat "$NR/settings.js" | python3 -c '
import re, sys
s = re.sub(r"/\*.*?\*/", "", sys.stdin.read(), flags=re.S)
print("\n".join(l.rstrip() for l in s.split("\n") if l.strip() and not l.lstrip().startswith("//")))
' > "$REPO/node-red/settings.js" && COPIADOS=$((COPIADOS+1))
else FALTAN+=("$NR/settings.js"); fi

# 8. InfluxDB: la tarea indices_diarios tal como está guardada
echo "8. InfluxDB"
if [ -z "$RAIZ" ] && docker exec influxdb influx task list --json > /tmp/tareas.json 2>/dev/null; then
  TAREAS=/tmp/tareas.json python3 - "$REPO/influxdb" <<'PY' && echo "   tareas de InfluxDB copiadas"
import sys, json, os
for t in json.load(open(os.environ["TAREAS"])):
    if t.get("flux"):
        open(os.path.join(sys.argv[1], t["name"] + ".flux"), "w").write(t["flux"])
PY
  rm -f /tmp/tareas.json
else
  echo "   No se pudo leer de InfluxDB; queda la copia del repositorio (influxdb/indices_diarios.flux)"
fi

# 9. Grafana: tableros por la API (opcional)
echo "9. Grafana"
GPASS=""
[ -z "$RAIZ" ] && read -rsp "   Clave de admin_trigal en Grafana (Enter para omitir): " GPASS && echo
if [ -n "$GPASS" ]; then
  mkdir -p "$REPO/grafana/dashboards"
  GUSER="admin_trigal" GPASS="$GPASS" python3 - "$REPO/grafana/dashboards" <<'PY'
import sys, os, json, base64, re, urllib.request
aut = "Basic " + base64.b64encode(f"{os.environ['GUSER']}:{os.environ['GPASS']}".encode()).decode()
def get(p):
    r = urllib.request.Request("http://localhost:3000" + p, headers={"Authorization": aut})
    return json.load(urllib.request.urlopen(r, timeout=10))
try:
    for d in get("/api/search?type=dash-db"):
        tab = get("/api/dashboards/uid/" + d["uid"])["dashboard"]
        tab["id"] = None
        nombre = re.sub(r"[^a-z0-9]+", "-", d["title"].lower()).strip("-") or d["uid"]
        json.dump(tab, open(os.path.join(sys.argv[1], nombre + ".json"), "w"), indent=2, ensure_ascii=False)
        print("   tablero:", d["title"])
except Exception as e:
    print("   No se pudieron bajar los tableros:", e)
PY
else
  echo "   Omitido. Se pueden exportar a mano: tablero → Share → Export → Save to file → grafana/dashboards/"
fi
unset GPASS

# 10. Quitar claves de todo lo copiado
echo "10. Quitando claves"
SECRETOS=$(mktemp); chmod 600 "$SECRETOS"
for e in "$ENV" "$RAIZ/opt/trigal/app/influx-sistema.env"; do
  $SUDO test -r "$e" && $SUDO grep -E '^[A-Za-z_]*(PASS|CLAVE|TOKEN|SECRET|KEY)[A-Za-z_]*=' "$e" >> "$SECRETOS"
done
python3 - "$REPO" "$SECRETOS" <<'PY'
import sys, os, re
repo, archivo = sys.argv[1], sys.argv[2]
pares = []
for l in open(archivo):
    k, _, v = l.strip().partition("=")
    v = v.strip().strip('"').strip("'")
    if len(v) >= 4:
        pares.append((v, "<" + k + ">"))
pares.sort(key=lambda p: -len(p[0]))
hash_re = re.compile(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}")
cambios = 0
for raiz, dirs, archivos in os.walk(repo):
    dirs[:] = [d for d in dirs if d != ".git"]
    for a in archivos:
        p = os.path.join(raiz, a)
        try:
            s = open(p, encoding="utf-8").read()
        except Exception:
            continue
        n = s
        for v, marca in pares:
            n = n.replace(v, marca)
        n = hash_re.sub("<HASH_BCRYPT>", n)
        if n != s:
            open(p, "w", encoding="utf-8").write(n)
            cambios += 1
            print("   limpiado:", os.path.relpath(p, repo))
print(f"   {cambios} archivo(s) con claves reemplazadas")
PY
rm -f "$SECRETOS"

# 11. Revisión final: cosas que parecen claves y no se reconocieron
echo "11. Revisión final"
SOSPECHAS=$(grep -rnIE --exclude-dir=.git --exclude=recolectar-desde-la-pi.sh \
  'eyJ[A-Za-z0-9_-]{30,}|-----BEGIN|(token|password|passwd|secret)["'"'"' ]*[:=] *["'"'"']?[A-Za-z0-9_+/=-]{16,}' "$REPO" | grep -v '<[A-Z_]*>' | head -20)
if [ -n "$SOSPECHAS" ]; then
  echo "   ⚠️  Revisar estas líneas antes de subir (podrían ser claves):"; echo "$SOSPECHAS" | sed 's/^/     /'
else
  echo "   ✅ No se encontraron claves a la vista"
fi

echo
echo "Listo: $COPIADOS archivos o carpetas copiados."
if [ ${#FALTAN[@]} -gt 0 ]; then echo "No se encontraron (puede ser normal):"; printf '   %s\n' "${FALTAN[@]}"; fi
cd "$REPO/.." && tar --exclude=.git -czf "$REPO.tar.gz" "$(basename "$REPO")" && echo "Comprimido en: $REPO.tar.gz"
