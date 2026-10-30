#!/usr/bin/env bash
#
# STM_LBR · WoldVirtualP2P3D en Linux nativo.
#
# QUÉ ES
# Desde la 2.7.1 el paquete de Linux trae el visor completo: «woldvirtual-linux»
# (Avalonia, .NET 8) con cuenta local, portal WebNodo, túnel P2P, invitación,
# chat de texto, amigos, lanzamiento del motor y actualizaciones. El motor Godot
# 4.7.2 de Linux y el mundo (wvp3d.pck) van EMBEBIDOS dentro del visor, igual
# que en el exe de Windows, y se extraen en el primer arranque. Este guión
# arranca el visor si está junto a él; el resto de opciones queda para quien
# sólo tenga motor + mundo sueltos.
#
# MODO MUNDO DIRECTO (sin visor)
# Arranca Godot 4.7.2 + wvp3d.pck por sí solo. Si no hay motor o mundo sueltos
# pero sí está el visor, primero le pide que los extraiga (--extraer). En ese
# modo el mundo es local y los argumentos de red se pasan a mano, como los
# inyecta el visor:
#
#   ./woldvirtual-linux.sh -- --client --ip=<host> --port=<puerto> --peer-url="<url>"
#   ./woldvirtual-linux.sh -- --peer-url="<url de invitación>"
#
# DE DÓNDE SALE CADA PIEZA
#   wvp3d.pck  (114.591.756 B, SHA-256 3e010b5e…c1e5c5e)
#     Dentro del visor: se extrae a ~/.local/share/WoldVirtualP2P3D/runtime/<versión>/wvp3d.pck
#     Suelto junto al guión: ./mundo/wvp3d.pck (o ./wvp3d.pck)
#     En un PC con el visor de Windows: %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\wvp3d.pck
#     En el árbol de compilación: VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/wvp3d.pck (no versionado)
#     Bajo Wine, si el visor llegó a arrancar: <prefix>/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/wvp3d.pck
#   Godot 4.7.2 para Linux
#     Dentro del visor: se extrae a ~/.local/share/WoldVirtualP2P3D/runtime/<versión>/Servidor3D/
#     Suelto junto al guión: ./motor/ (o ./Godot_v4.7.2-stable_linux.x86_64)
#     Si no está: godotengine.org/download/linux/ → Godot_v4.7.2-stable_linux.x86_64.zip
#
# USO
#   ./woldvirtual-linux.sh                      # visor completo si está; si no, mundo directo
#   ./woldvirtual-linux.sh --comprobar          # autocomprobación sin ventana del visor
#   ./woldvirtual-linux.sh --extraer            # extrae motor y mundo del visor y da sus rutas
#   ./woldvirtual-linux.sh --motor              # fuerza el modo mundo directo
#   ./woldvirtual-linux.sh --dry-run            # qué ejecutaría, sin ejecutar
#   ./woldvirtual-linux.sh --pck /ruta/wvp3d.pck --godot /ruta/godot
#   ./woldvirtual-linux.sh --verificar          # comprueba la huella del pck

set -uo pipefail

VERSION_GODOT="4.7"
NOMBRE_MOTOR_LINUX="Godot_v4.7.2-stable_linux.x86_64"
PCK_BYTES=114591724
PCK_SHA256="ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14"

# El paquete de Linux lleva el motor y el mundo junto al guión: se buscan ahí
# primero para que funcione recién descomprimido, sin instalar nada.
AQUI="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

GODOT="${GODOT_BIN:-}"
PCK="${WOLD_PCK:-}"
DRY_RUN=0
VERIFICAR=0
MODO_MOTOR=0
EXTRA=()

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }
ayuda() { awk 'NR>2 && /^set -uo pipefail/ {exit} NR>2 {sub(/^# ?/,""); print}' "$0"; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --godot)     GODOT="${2:-}"; MODO_MOTOR=1; shift 2 ;;
    --pck)       PCK="${2:-}"; MODO_MOTOR=1; shift 2 ;;
    --motor)     MODO_MOTOR=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --verificar) VERIFICAR=1; shift ;;
    -h|--ayuda)  ayuda ;;
    --)          shift; while [ $# -gt 0 ]; do EXTRA+=("$1"); shift; done ;;
    # Los argumentos del mundo (--client, --peer-url=…) pueden ir sin el --
    # separador: acaban igualmente detrás de él.
    --*)         EXTRA+=("$1"); shift ;;
    -*)          die "opción desconocida: $1 (usa --ayuda)" ;;
    *)           EXTRA+=("$1"); shift ;;
  esac
done

# ── Visor completo ──────────────────────────────────────────────────────
# El paquete de la 2.7.3 trae «woldvirtual-linux» junto a este guión. Si está,
# se arranca él: es el visor completo (cuenta, portal, túnel, chat, motor).
VISOR="$AQUI/woldvirtual-linux"
if [ "$MODO_MOTOR" -eq 0 ] && [ -x "$VISOR" ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '%q ' "$VISOR" ${EXTRA[@]+"${EXTRA[@]}"}; printf '\n'
    exit 0
  fi
  info "visor  : $VISOR (visor completo: cuenta, portal, túnel P2P, chat)"
  exec "$VISOR" ${EXTRA[@]+"${EXTRA[@]}"}
fi

if [ "$MODO_MOTOR" -eq 0 ] && [ -f "$VISOR" ]; then
  die "«$VISOR» existe pero no es ejecutable. Prueba: chmod +x \"$VISOR\""
fi

# Sin visor sólo queda el modo mundo directo: las órdenes que dependen del
# visor no deben acabar como argumentos de Godot.
if [ "$MODO_MOTOR" -eq 0 ]; then
  for a in ${EXTRA[@]+"${EXTRA[@]}"}; do
    case "$a" in
      --comprobar|--extraer)
        die "«$a» lo ejecuta el visor (woldvirtual-linux), que no está en $AQUI" ;;
    esac
  done
fi

# ── Motor Godot de Linux ────────────────────────────────────────────────
# La búsqueda escribe en variables y no imprime por stdout: en una sustitución
# de comandos correría en un subshell y el aviso de «sin permiso» se perdería.
MOTOR_ENCONTRADO=""
MOTOR_SIN_X=""
buscar_motor() {
  local c
  MOTOR_ENCONTRADO=""
  for c in "$AQUI/$NOMBRE_MOTOR_LINUX" "$AQUI/motor/$NOMBRE_MOTOR_LINUX" \
           "$AQUI/../motor/$NOMBRE_MOTOR_LINUX" \
           "$NOMBRE_MOTOR_LINUX" godot4 godot /usr/bin/godot /usr/local/bin/godot \
           "$HOME/.local/bin/godot" "$HOME/Apps/$NOMBRE_MOTOR_LINUX" \
           "$XDG_DATA_HOME/woldvirtual-p2p3d/$NOMBRE_MOTOR_LINUX"; do
    command -v "$c" >/dev/null 2>&1 && { MOTOR_ENCONTRADO="$(command -v "$c")"; return 0; }
    [ -f "$c" ] && MOTOR_SIN_X="${MOTOR_SIN_X:-$c}"
    [ -x "$c" ] && { MOTOR_ENCONTRADO="$c"; return 0; }
  done
  return 1
}

if [ -z "$GODOT" ]; then
  buscar_motor || true
  GODOT="$MOTOR_ENCONTRADO"
fi

# El motor y el mundo viajan dentro del visor: si no los hay sueltos, se le
# pide al visor que los extraiga (sólo la primera vez; después es instantáneo).
if [ -z "$GODOT" ] && [ -x "$VISOR" ]; then
  info "motor   : no hay motor suelto; extrayéndolo del visor (sólo la primera vez)…"
  if salida="$("$VISOR" --extraer 2>&1)"; then
    extraido_motor="$(printf '%s\n' "$salida" | sed -n 's/^MOTOR=//p' | tail -1)"
    extraido_pck="$(printf '%s\n' "$salida" | sed -n 's/^PCK=//p' | tail -1)"
    [ -n "$extraido_motor" ] && GODOT="$extraido_motor"
    [ -n "$PCK" ] || PCK="$extraido_pck"
    MOTOR_SIN_X=""
  else
    printf '%s\n' "$salida" | tail -3 >&2
  fi
fi

if [ -z "$GODOT" ]; then
  if [ -n "$MOTOR_SIN_X" ]; then
    die "«$MOTOR_SIN_X» existe pero no es ejecutable. Prueba: chmod +x \"$MOTOR_SIN_X\""
  fi
  die "no encuentro Godot para Linux. Viene dentro de «woldvirtual-linux» (--extraer) o se descarga de godotengine.org/download/linux/ (Godot_v4.7.2-stable_linux.x86_64.zip) y se pasa con --godot /ruta/Godot_v4.7.2-stable_linux.x86_64"
fi
command -v "$GODOT" >/dev/null 2>&1 || [ -x "$GODOT" ] || die \
  "«$GODOT» no es ejecutable. Prueba: chmod +x \"$GODOT\""

if [ "$DRY_RUN" -eq 0 ]; then
  VERSION_MOTOR="$("$GODOT" --version 2>/dev/null | head -1)"
  info "motor  : $GODOT"
  info "versión: ${VERSION_MOTOR:-desconocida}"
  case "$VERSION_MOTOR" in
    "$VERSION_GODOT"*) ;;
    *) info "AVISO: el mundo se exportó con Godot $VERSION_GODOT.x; con otra rama el pck puede no cargar." ;;
  esac
fi

# ── Mundo empaquetado ───────────────────────────────────────────────────
buscar_pck() {
  local c d
  for c in "$AQUI/wvp3d.pck" "$AQUI/mundo/wvp3d.pck" "$AQUI/../mundo/wvp3d.pck" \
           "$AQUI/../wvp3d.pck" "$PWD/wvp3d.pck" \
           "$HOME"/Descargas/wvp3d.pck "$HOME"/Downloads/wvp3d.pck; do
    [ -f "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  for d in \
    "$XDG_DATA_HOME"/woldvirtual-p2p3d/wineprefix/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/* \
    "$HOME"/.wine/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/* \
    /mnt/c/Users/*/AppData/Local/WoldVirtualP2P3D/runtime/* \
    "$XDG_DATA_HOME"/woldvirtual-p2p3d/runtime/*; do
    [ -f "$d/wvp3d.pck" ] && { printf '%s\n' "$d/wvp3d.pck"; return 0; }
  done
  return 1
}

[ -n "$PCK" ] || PCK="$(buscar_pck || true)"
[ -n "$PCK" ] && [ -f "$PCK" ] || die \
  "no encuentro wvp3d.pck. Cópialo de un PC con el visor instalado (%LOCALAPPDATA%\\WoldVirtualP2P3D\\runtime\\<versión>\\wvp3d.pck) y pásalo con --pck /ruta/wvp3d.pck"

info "mundo  : $PCK"
BYTES="$(stat -c %s "$PCK" 2>/dev/null || stat -f %z "$PCK" 2>/dev/null || echo 0)"
if [ "$BYTES" != "$PCK_BYTES" ]; then
  info "AVISO: tamaño $BYTES B, el mundo publicado pesa $PCK_BYTES B. Puede ser otra versión."
fi

if [ "$VERIFICAR" -eq 1 ]; then
  command -v sha256sum >/dev/null 2>&1 || die "--verificar necesita sha256sum"
  info "Calculando SHA-256 de $BYTES B (unos segundos)…"
  REAL="$(sha256sum "$PCK" | cut -d' ' -f1)"
  if [ "$REAL" = "$PCK_SHA256" ]; then
    info "huella OK: $REAL (mundo de la 2.7.3)"
  else
    info "huella distinta: $REAL"
    info "esperada         : $PCK_SHA256"
    info "Es otro build del mundo: funcionará si se exportó con Godot $VERSION_GODOT.x."
  fi
fi

# ── Arranque ────────────────────────────────────────────────────────────
COMANDO=("$GODOT" --main-pack "$PCK")
[ ${#EXTRA[@]} -gt 0 ] && COMANDO+=(-- "${EXTRA[@]}")

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%q ' "${COMANDO[@]}"; printf '\n'
  exit 0
fi

mkdir -p "$XDG_STATE_HOME/woldvirtual"
LOG="$XDG_STATE_HOME/woldvirtual/linux-$(date +%Y%m%d-%H%M%S).log"
info "registro: $LOG"
info "Los datos del jugador quedarán en ~/.local/share/godot/app_userdata/WoldVirtualP2P3D"
"${COMANDO[@]}" 2>&1 | tee "$LOG"
exit "${PIPESTATUS[0]}"
