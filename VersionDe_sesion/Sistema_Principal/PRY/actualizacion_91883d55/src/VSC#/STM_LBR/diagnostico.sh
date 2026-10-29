#!/usr/bin/env bash
#
# STM_LBR · Diagnóstico de WoldVirtualP2P3D en Linux.
#
# Recoge lo que hace falta para saber por qué el visor no arranca en este
# equipo: entorno, Wine, estado del ICU, visor Linux completo y su
# autocomprobación, y una prueba real del runtime .NET con cada estrategia de
# globalización. Escribe un informe para pegar tal cual.
#
# USO
#   ./diagnostico.sh                    # informe + sondeos
#   ./diagnostico.sh --sin-sondeo       # sólo el entorno, no lanza nada
#   ./diagnostico.sh --exe /ruta/DMWoldVirtualP2P3Dv2.6.9.exe
#   ./diagnostico.sh --hash             # incluye SHA-256 del exe y del visor (tarda)
#
# El sondeo del visor Linux usa «woldvirtual-linux --comprobar» (sin ventana) y
# el del .exe usa --chat-selftest, que sale del proceso en cuanto el runtime
# arranca: si devuelve 0, .NET funciona bajo este Wine y lo que falle después
# será la ventana WPF, no ICU.

set -uo pipefail

XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="${WOLD_WINEPREFIX:-$XDG_DATA_HOME/woldvirtual-p2p3d/wineprefix}"
PATRON_EXE='DMWoldVirtualP2P3Dv*.exe'
MARCADORES_ICU='icuuc|Cannot get symbol|find_forwarded_export|libicuuc'
TIEMPO_SONDEO="${WOLD_SONDEO_SEG:-120}"

EXE=""
SONDEAR=1
HASH=0
INFORME="$XDG_STATE_HOME/woldvirtual/diagnostico-$(date +%Y%m%d-%H%M%S).log"

while [ $# -gt 0 ]; do
  case "$1" in
    --exe)        EXE="${2:-}"; shift 2 ;;
    --prefix)     PREFIX="${2:-}"; shift 2 ;;
    --sin-sondeo) SONDEAR=0; shift ;;
    --hash)       HASH=1; shift ;;
    -h|--ayuda)   sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            printf 'ERROR: opción desconocida: %s\n' "$1" >&2; exit 1 ;;
  esac
done

mkdir -p "$(dirname "$INFORME")"

decir() { printf '%s\n' "$*" | tee -a "$INFORME"; }
titulo() { decir ""; decir "== $* =="; }
tener() { command -v "$1" >/dev/null 2>&1; }

titulo "INFORME STM_LBR"
decir "fecha   : $(date -Is 2>/dev/null || date)"
decir "informe : $INFORME"

titulo "ENTORNO"
if [ -r /etc/os-release ]; then
  decir "distro  : $(. /etc/os-release && printf '%s %s' "${NAME:-?}" "${VERSION:-${VERSION_ID:-?}}")"
fi
decir "kernel  : $(uname -srm)"
decir "sesión  : ${XDG_SESSION_TYPE:-?} / ${XDG_CURRENT_DESKTOP:-?}"
decir "HOME    : $HOME"

titulo "WINE"
WINE="$(command -v wine || command -v wine64 || true)"
if [ -z "$WINE" ]; then
  decir "wine    : NO instalado (Arch/CachyOS: sudo pacman -S wine wine-gecko wine-mono)"
else
  decir "wine    : $WINE"
  decir "versión : $("$WINE" --version 2>/dev/null || echo 'no responde')"
  decir "prefix  : $PREFIX ($([ -d "$PREFIX/drive_c" ] && echo 'inicializado' || echo 'vacío o ausente'))"

  ICU_PREF="$(find "$PREFIX" -iname 'icu*.dll' 2>/dev/null | head -5)"
  decir "icu en el prefix: ${ICU_PREF:-ninguna (Wine usa la del sistema)}"
  if tener ldconfig; then
    ICU_SYS="$(ldconfig -p 2>/dev/null | grep -i 'libicuuc' | head -3)"
    decir "libicuuc del sistema: ${ICU_SYS:-no encontrada}"
  fi
  decir "El icu.dll de Wine reenvía a icuuc68; si esa librería no existe, .NET muere con 127 antes de llegar al visor."
fi

titulo "VISOR"
if [ -z "$EXE" ]; then
  for c in "$PWD"/*.exe "$HOME"/Descargas/$PATRON_EXE "$HOME"/Downloads/$PATRON_EXE "$HOME"/$PATRON_EXE; do
    [ -f "$c" ] && { EXE="$c"; break; }
  done
fi
if [ -n "$EXE" ] && [ -f "$EXE" ]; then
  decir "exe     : $EXE"
  decir "tamaño  : $(stat -c %s "$EXE" 2>/dev/null || stat -f %z "$EXE" 2>/dev/null || echo '?') B"
  if [ "$HASH" -eq 1 ] && tener sha256sum; then
    decir "sha256  : $(sha256sum "$EXE" | cut -d' ' -f1)"
  fi
else
  decir "exe     : no encontrado (pásalo con --exe)"
fi

titulo "VISOR COMPLETO LINUX (woldvirtual-linux)"
AQUI="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VISOR=""
VISOR_SIN_X=""
for c in "$AQUI/woldvirtual-linux" "$PWD/woldvirtual-linux" \
         "$AQUI/../woldvirtual-linux" "$HOME/.local/bin/woldvirtual-linux"; do
  [ -f "$c" ] || continue
  VISOR_SIN_X="$c"
  [ -x "$c" ] && { VISOR="$c"; break; }
done
if [ -z "$VISOR" ] && tener woldvirtual-linux; then
  VISOR="$(command -v woldvirtual-linux)"
  VISOR_SIN_X=""
fi
if [ -z "$VISOR" ] && [ -n "$VISOR_SIN_X" ]; then
  decir "visor   : $VISOR_SIN_X (sin permiso de ejecución: chmod +x)"
elif [ -z "$VISOR" ]; then
  decir "visor   : no encontrado (viene en el paquete WoldVirtualP2P3Dv2.7.1-linux.tar.gz)"
else
  decir "visor   : $VISOR"
  decir "tamaño  : $(stat -c %s "$VISOR" 2>/dev/null || stat -f %z "$VISOR" 2>/dev/null || echo '?') B"
  if [ "$HASH" -eq 1 ] && tener sha256sum; then
    decir "sha256  : $(sha256sum "$VISOR" | cut -d' ' -f1)"
  fi
  if [ "$SONDEAR" -eq 1 ]; then
    log="$XDG_STATE_HOME/woldvirtual/comprobar-$(date +%Y%m%d-%H%M%S).log"
    printf '%s' "  --comprobar … " | tee -a "$INFORME"
    timeout "$TIEMPO_SONDEO" "$VISOR" --comprobar >"$log" 2>&1
    codigo=$?
    if [ "$codigo" -eq 0 ]; then
      decir "OK — ver $log"
    else
      decir "sale con $codigo — ver $log"
    fi
    tail -12 "$log" | sed 's/^/      /' | tee -a "$INFORME"
  fi
fi

titulo "RUTA NATIVA (Godot de Linux + wvp3d.pck)"
NOMBRE_MOTOR="Godot_v4.7.2-stable_linux.x86_64"
GODOT=""
GODOT_SIN_X=""
# Primero el runtime extraído por el visor (motor y mundo van dentro de él).
for c in "${WOLD_RUNTIME_DIR:-}/Servidor3D/$NOMBRE_MOTOR" \
         "$XDG_DATA_HOME"/WoldVirtualP2P3D/runtime/*/Servidor3D/"$NOMBRE_MOTOR" \
         "$AQUI/motor/$NOMBRE_MOTOR" "$AQUI/$NOMBRE_MOTOR" "$AQUI/../motor/$NOMBRE_MOTOR"; do
  [ -f "$c" ] || continue
  GODOT_SIN_X="$c"
  [ -x "$c" ] && { GODOT="$c"; break; }
done
[ -n "$GODOT" ] || GODOT="$(command -v godot || command -v godot4 || true)"
if [ -z "$GODOT" ] && [ -n "$GODOT_SIN_X" ]; then
  decir "godot   : $GODOT_SIN_X (sin permiso de ejecución: chmod +x)"
else
  decir "godot   : ${GODOT:-no encontrado}$( [ -n "$GODOT" ] && echo " ($("$GODOT" --version 2>/dev/null | head -1))")"
fi

PCK=""
for ruta in \
  "${WOLD_RUNTIME_DIR:-}/wvp3d.pck" \
  "$XDG_DATA_HOME"/WoldVirtualP2P3D/runtime/*/wvp3d.pck \
  "$AQUI/mundo/wvp3d.pck" "$AQUI/wvp3d.pck" "$AQUI/../mundo/wvp3d.pck" \
  "$PWD/wvp3d.pck" "$HOME"/Descargas/wvp3d.pck "$HOME"/Downloads/wvp3d.pck \
  "$XDG_DATA_HOME"/woldvirtual-p2p3d/runtime/*/wvp3d.pck \
  "$PREFIX"/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/wvp3d.pck \
  "$HOME"/.wine/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/wvp3d.pck \
  /mnt/c/Users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/wvp3d.pck; do
  [ -f "$ruta" ] && { PCK="$ruta"; break; }
done
decir "pck     : ${PCK:-no encontrado}"
decir "El mundo (wvp3d.pck) es neutro de plataforma: con Godot 4.7.2 de Linux funciona sin el visor."

if [ "$SONDEAR" -eq 1 ] && [ -n "$WINE" ] && [ -n "$EXE" ] && [ -f "$EXE" ]; then
  titulo "SONDEO DEL RUNTIME .NET BAJO WINE"
  for par in "nls|DOTNET_SYSTEM_GLOBALIZATION_USENLS=1" \
             "invariant|DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1" \
             "nls+invariant|DOTNET_SYSTEM_GLOBALIZATION_USENLS=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1"; do
    nombre="${par%%|*}"; vars="${par#*|}"
    log="$XDG_STATE_HOME/woldvirtual/sondeo-$nombre.log"
    printf '%s' "  $nombre … " | tee -a "$INFORME"
    env WINEPREFIX="$PREFIX" WINEDEBUG=-all $vars timeout "$TIEMPO_SONDEO" \
      "$WINE" "$EXE" --chat-selftest >"$log" 2>&1
    codigo=$?
    if grep -Eq "$MARCADORES_ICU" "$log"; then
      decir "FALLO ICU (código $codigo) — ver $log"
    elif [ "$codigo" -eq 0 ]; then
      decir "OK, el runtime arranca y la autoprueba del chat pasa — ver $log"
    elif [ "$codigo" -eq 124 ]; then
      decir "sin respuesta en ${TIEMPO_SONDEO}s (probablemente la ventana WPF) — ver $log"
    else
      decir "sale con $codigo sin fallo de ICU — ver $log"
      tail -5 "$log" | sed 's/^/      /' | tee -a "$INFORME"
    fi
  done
  decir ""
  decir "Lectura: si alguna estrategia da OK, ICU ya no es el problema y el visor puede"
  decir "usarse con ./woldvirtual-wine.sh --estrategia <esa>. Si todas fallan por ICU,"
  decir "el paquete de Wine tiene el reenvío roto: prueba wine-staging o la vía nativa."
elif [ "$SONDEAR" -eq 1 ]; then
  titulo "SONDEO DEL RUNTIME .NET BAJO WINE"
  decir "omitido: falta wine o el exe."
fi

decir ""
decir "Informe completo: $INFORME"
