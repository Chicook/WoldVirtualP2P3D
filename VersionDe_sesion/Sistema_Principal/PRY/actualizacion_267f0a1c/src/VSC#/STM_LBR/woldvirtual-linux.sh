#!/usr/bin/env bash
#
# STM_LBR · WoldVirtualP2P3D en Linux nativo (sin Wine, sin visor WPF).
#
# POR QUÉ EXISTE
# El visor publicado es WPF, y WPF sólo existe en Windows. Lo que sí es neutro
# de plataforma es el mundo: Godot 4.7.2 + wvp3d.pck. Este guión arranca ese
# mundo con un Godot de Linux, que es la vía que de verdad funciona aquí.
#
# QUÉ SE PIERDE RESPECTO AL VISOR DE WINDOWS
# Sin la capa C# no hay registro ni SMTPLC, ni túnel P2P automático, ni portal
# WebNodo, ni relay de chat, ni amigos. El mundo arranca en modo local; para
# entrar en la sesión de otro equipo hay que pasarle a mano los argumentos de
# red que en Windows inyecta el visor:
#
#   ./woldvirtual-linux.sh -- --client --ip=<host> --port=<puerto> --peer-url="<url>"
#   ./woldvirtual-linux.sh -- --peer-url="<url de invitación>"
#
# DE DÓNDE SALE CADA PIEZA
#   wvp3d.pck  (537.836.524 B, SHA-256 9d5c15e7…7a69ac94)
#     En el paquete de Linux: ./mundo/wvp3d.pck (o junto a este guión)
#     En un PC con el visor instalado: %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\wvp3d.pck
#     En el repositorio: VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c/src/VSC#/wvp3d.pck
#     Bajo Wine, si el visor llegó a arrancar: <prefix>/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/wvp3d.pck
#   Godot 4.7.2 para Linux
#     En el paquete de Linux: ./motor/ (o junto a este guión)
#     Si no está: godotengine.org/download/linux/ → Godot_v4.7.2-stable_linux.x86_64.zip
#
# USO
#   ./woldvirtual-linux.sh --dry-run            # qué ejecutaría, sin ejecutar
#   ./woldvirtual-linux.sh --pck /ruta/wvp3d.pck --godot /ruta/godot
#   ./woldvirtual-linux.sh --verificar          # comprueba la huella del pck
#   ./woldvirtual-linux.sh                      # busca motor y mundo por su cuenta

set -uo pipefail

VERSION_GODOT="4.7"
NOMBRE_MOTOR_LINUX="Godot_v4.7.2-stable_linux.x86_64"
PCK_BYTES=537836524
PCK_SHA256="9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94"

# El paquete de Linux lleva el motor y el mundo junto al guión: se buscan ahí
# primero para que funcione recién descomprimido, sin instalar nada.
AQUI="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

GODOT="${GODOT_BIN:-}"
PCK="${WOLD_PCK:-}"
DRY_RUN=0
VERIFICAR=0
EXTRA=()

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }
ayuda() { sed -n '3,34p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --godot)     GODOT="${2:-}"; shift 2 ;;
    --pck)       PCK="${2:-}"; shift 2 ;;
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

# ── Motor Godot de Linux ────────────────────────────────────────────────
buscar_motor() {
  local c
  for c in "$AQUI/$NOMBRE_MOTOR_LINUX" "$AQUI/motor/$NOMBRE_MOTOR_LINUX" \
           "$AQUI/../motor/$NOMBRE_MOTOR_LINUX" \
           "$NOMBRE_MOTOR_LINUX" godot4 godot /usr/bin/godot /usr/local/bin/godot \
           "$HOME/.local/bin/godot" "$HOME/Apps/$NOMBRE_MOTOR_LINUX" \
           "$XDG_DATA_HOME/woldvirtual-p2p3d/$NOMBRE_MOTOR_LINUX"; do
    command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return 0; }
    [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

[ -n "$GODOT" ] || GODOT="$(buscar_motor || true)"
[ -n "$GODOT" ] && { command -v "$GODOT" >/dev/null 2>&1 || [ -x "$GODOT" ]; } || die \
  "no encuentro Godot para Linux. Descarga Godot_v4.7.2-stable_linux.x86_64.zip en godotengine.org/download/linux/, descomprímelo y pásalo con --godot /ruta/Godot_v4.7.2-stable_linux.x86_64"

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
    info "huella OK: $REAL (mundo de la 2.6.1 a la 2.6.9)"
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
