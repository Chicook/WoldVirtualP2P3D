#!/usr/bin/env bash
#
# STM_LBR · Arranque del visor WoldVirtualP2P3D bajo Wine (Linux).
#
# PROBLEMA QUE RESUELVE
# El .exe publicado es un WPF de .NET 8 autocontenido para win-x64. Antes de
# ejecutar una sola línea nuestra, .NET inicializa la globalización cargando el
# ICU de Windows; el icu.dll de Wine reenvía a icuuc68, que no está, y el
# proceso muere con 127:
#
#   err:module:find_forwarded_export module not found for forward
#       'icuuc68.u_charsToUChars_68' used by L"C:\windows\system32\icu.dll"
#   Cannot get symbol u_charsToUChars from libicuuc
#   Error: 127
#
# SOLUCIÓN
# Decirle a .NET que no cargue ICU. Hay dos vías y cuál funciona depende de la
# compilación de Wine: NLS (usa las API de locale de kernel32) e invariante
# (sin datos de cultura). Este guión las prueba en orden, guarda la ganadora y
# la reutiliza en los siguientes arranques.
#
# USO
#   ./woldvirtual-wine.sh                       # busca el exe en Descargas/Downloads
#   ./woldvirtual-wine.sh --exe /ruta/DMWoldVirtualP2P3Dv2.6.9.exe
#   ./woldvirtual-wine.sh --estrategia invariant
#   ./woldvirtual-wine.sh --motor               # mundo 3D bajo Wine, sin la UI WPF
#   ./woldvirtual-wine.sh --dry-run             # sólo muestra qué ejecutaría
#   ./woldvirtual-wine.sh --chat-selftest       # argumentos extra pasan al exe
#
# LÍMITE HONESTO: arreglar ICU hace que el runtime .NET arranque. La interfaz
# es WPF, que sólo existe en Windows; bajo Wine puede no pintar o cerrarse. Si
# eso pasa, la vía que sí sostiene el mundo 3D es woldvirtual-linux.sh (Godot
# nativo + wvp3d.pck, que es neutro de plataforma).

set -uo pipefail

GODOT_WIN64="Godot_v4.7.2-stable_win64.exe"
PATRON_EXE='DMWoldVirtualP2P3Dv*.exe'
MARCADORES_ICU='icuuc|Cannot get symbol|find_forwarded_export|libicuuc'

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

PREFIX="${WOLD_WINEPREFIX:-$XDG_DATA_HOME/woldvirtual-p2p3d/wineprefix}"
ESTADO_DIR="$XDG_STATE_HOME/woldvirtual"
GUARDADO="$ESTADO_DIR/wine-estrategia"
EXE=""
ESTRATEGIA=""
DRY_RUN=0
MODO_MOTOR=0
EXTRA=()

# nombre|variables de entorno
ESTRATEGIAS=(
  "nls|DOTNET_SYSTEM_GLOBALIZATION_USENLS=1"
  "invariant|DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1"
  "nls+invariant|DOTNET_SYSTEM_GLOBALIZATION_USENLS=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1"
)

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

ayuda() {
  sed -n '3,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --exe)         EXE="${2:-}"; shift 2 ;;
    --prefix)      PREFIX="${2:-}"; shift 2 ;;
    --estrategia)  ESTRATEGIA="${2:-}"; shift 2 ;;
    --motor)       MODO_MOTOR=1; shift ;;
    --dry-run)     DRY_RUN=1; shift ;;
    -h|--ayuda)    ayuda ;;
    --)            shift; while [ $# -gt 0 ]; do EXTRA+=("$1"); shift; done ;;
    # Las opciones del exe también empiezan por -- (p. ej. --chat-selftest):
    # lo que no sea una opción de este guión se le pasa tal cual.
    --*)           EXTRA+=("$1"); shift ;;
    -*)            die "opción desconocida: $1 (usa --ayuda)" ;;
    *)             EXTRA+=("$1"); shift ;;
  esac
done

# ── Wine ────────────────────────────────────────────────────────────────
WINE="$(command -v wine || command -v wine64 || true)"
[ -n "$WINE" ] || die "no hay wine en el PATH. En CachyOS/Arch: sudo pacman -S wine wine-gecko wine-mono (o wine-staging)."
info "wine   : $WINE ($("$WINE" --version 2>/dev/null || echo 'versión desconocida'))"
info "prefix : $PREFIX"

mkdir -p "$ESTADO_DIR" "$PREFIX" || die "no se pudo crear $PREFIX"

if [ ! -d "$PREFIX/drive_c" ]; then
  info "El prefix está vacío: se inicializa (puede tardar un minuto)."
  if [ "$DRY_RUN" -eq 0 ]; then
    # Un wineboot que falla no siempre es definitivo: el prefix puede quedar
    # utilizable, así que se avisa y se sigue en vez de abortar.
    WINEPREFIX="$PREFIX" WINEARCH=win64 timeout 600 "$WINE" wineboot --init \
      >"$ESTADO_DIR/wineboot.log" 2>&1 \
      || info "AVISO: wineboot salió con error; detalle en $ESTADO_DIR/wineboot.log. Se intenta arrancar igualmente."
  fi
fi

# ── Localizar el exe ────────────────────────────────────────────────────
buscar_exe() {
  local c
  for c in \
    "$PWD"/*.exe \
    "$HOME"/Descargas/$PATRON_EXE \
    "$HOME"/Downloads/$PATRON_EXE \
    "$HOME"/$PATRON_EXE \
    "$XDG_DATA_HOME"/woldvirtual-p2p3d/$PATRON_EXE; do
    [ -f "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

if [ "$MODO_MOTOR" -eq 0 ]; then
  [ -n "$EXE" ] || EXE="$(buscar_exe || true)"
  [ -n "$EXE" ] && [ -f "$EXE" ] || die \
    "no encuentro el visor. Pásalo con --exe /ruta/$PATRON_EXE"
  info "visor  : $EXE"
fi

# ── Modo motor: mundo 3D bajo Wine sin pasar por WPF ────────────────────
if [ "$MODO_MOTOR" -eq 1 ]; then
  RUNTIME="$(ls -d "$PREFIX"/drive_c/users/*/AppData/Local/WoldVirtualP2P3D/runtime/*/ 2>/dev/null | tail -1)"
  [ -n "$RUNTIME" ] || RUNTIME="${WOLD_RUNTIME_DIR:-}"
  [ -n "$RUNTIME" ] && [ -f "$RUNTIME/wvp3d.pck" ] || die \
    "no hay runtime extraído en el prefix. Ejecuta primero el visor completo una vez, o usa woldvirtual-linux.sh, que extrae motor y mundo del propio visor Linux."
  MOTOR="$RUNTIME/Servidor3D/$GODOT_WIN64"
  [ -f "$MOTOR" ] || die "falta el motor: $MOTOR"
  COMANDO=("$WINE" "$MOTOR" --main-pack "$RUNTIME/wvp3d.pck")
  [ ${#EXTRA[@]} -gt 0 ] && COMANDO+=(-- "${EXTRA[@]}")
  if [ "$DRY_RUN" -eq 1 ]; then printf '%q ' "${COMANDO[@]}"; printf '\n'; exit 0; fi
  WINEPREFIX="$PREFIX" WINEDEBUG="${WINEDEBUG:--all}" "${COMANDO[@]}"
  exit $?
fi

# ── Estrategias de globalización ────────────────────────────────────────
variables_de() {
  local nombre="$1" entrada
  for entrada in "${ESTRATEGIAS[@]}"; do
    [ "${entrada%%|*}" = "$nombre" ] && { printf '%s' "${entrada#*|}"; return 0; }
  done
  return 1
}

orden() {
  if [ -n "$ESTRATEGIA" ] && [ "$ESTRATEGIA" != "todas" ]; then
    variables_de "$ESTRATEGIA" >/dev/null || die "estrategia inválida: $ESTRATEGIA (nls|invariant|nls+invariant|todas)"
    printf '%s\n' "$ESTRATEGIA"
    return
  fi
  # La que ya funcionó antes va primero.
  if [ -f "$GUARDADO" ]; then
    local previa; previa="$(head -1 "$GUARDADO" 2>/dev/null)"
    [ -n "$previa" ] && printf '%s\n' "$previa"
  fi
  local entrada nombre
  for entrada in "${ESTRATEGIAS[@]}"; do
    nombre="${entrada%%|*}"
    [ "$nombre" = "$( [ -f "$GUARDADO" ] && head -1 "$GUARDADO" )" ] && continue
    printf '%s\n' "$nombre"
  done
}

ejecutar() { # $1=nombre  -> código de salida del exe
  local nombre="$1" vars log codigo
  vars="$(variables_de "$nombre")"
  log="$ESTADO_DIR/wine-$nombre-$(date +%Y%m%d-%H%M%S).log"

  if [ "$DRY_RUN" -eq 1 ]; then
    info "[dry-run] env WINEPREFIX=$PREFIX WINEDEBUG=-all $vars $WINE $EXE ${EXTRA[*]+"${EXTRA[*]}"}"
    return 0
  fi

  info "Probando estrategia '$nombre' → $log"
  env WINEPREFIX="$PREFIX" WINEDEBUG="${WINEDEBUG:--all}" $vars "$WINE" "$EXE" \
    ${EXTRA[@]+"${EXTRA[@]}"} 2>&1 | tee "$log"
  codigo="${PIPESTATUS[0]}"

  if grep -Eq "$MARCADORES_ICU" "$log" || [ "$codigo" -eq 127 ]; then
    info "  ↳ sigue el fallo de ICU (código $codigo)."
    return 127
  fi
  info "  ↳ sin fallo de ICU (código $codigo)."
  printf '%s\n' "$nombre" > "$GUARDADO"
  printf '%s\n' "$log"    >> "$GUARDADO"
  return "$codigo"
}

if [ "$DRY_RUN" -eq 1 ]; then
  while read -r nombre; do ejecutar "$nombre"; done < <(orden)
  exit 0
fi

SALIDA=127
while read -r nombre; do
  ejecutar "$nombre"; SALIDA=$?
  [ "$SALIDA" -ne 127 ] && break
done < <(orden)

if [ "$SALIDA" -eq 127 ]; then
  cat >&2 <<EOF

Ninguna estrategia de globalización arrancó el runtime: el fallo de ICU sigue.
Prueba, en este orden:
  1) ./diagnostico.sh            → informe completo para pegar al desarrollador
  2) wine-staging o un wine más reciente (el reenvío roto a icuuc68 es del paquete)
  3) woldvirtual-linux.sh        → mundo 3D con Godot nativo + wvp3d.pck
Recuerda que la interfaz del visor es WPF y sólo existe en Windows: aunque ICU
se resuelva, la ventana puede no pintar bajo Wine.
EOF
  exit 127
fi

info "Estrategia guardada en $GUARDADO (se usará primero la próxima vez)."
exit "$SALIDA"
