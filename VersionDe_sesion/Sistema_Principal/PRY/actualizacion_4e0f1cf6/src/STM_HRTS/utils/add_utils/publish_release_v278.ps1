# publish_release_v278.ps1
# Publica la release v2.7.8 en GitHub Releases (visor Windows + paquete Linux),
# con las novedades de seguridad del subsistema defensivo STM_DEF.
#
# Nota: la ruta del proyecto contiene '#' (VSC#) y gh.exe divide en el PRIMER '#',
# así que los artefactos se copian a una carpeta temporal limpia antes de subirlos.
$ErrorActionPreference = "Stop"

$VERSION     = "2.7.8"
$TAG         = "v$VERSION"
$EXE_NAME    = "DMWoldVirtualP2P3Dv$VERSION.exe"
$LINUX_NAME  = "WoldVirtualP2P3Dv$VERSION-linux.tar.gz"

# Artefactos compilados fuera del árbol (los binarios no se comitean, R17).
$BUILD_DIR   = "E:\areadetrabajo\wvp278"
$EXE_PATH    = Join-Path $BUILD_DIR "win\$EXE_NAME"
$LINUX_PATH  = Join-Path $BUILD_DIR $LINUX_NAME

$REPO        = "Chicook/WoldVirtualP2P3D"
$GH          = "e:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $GH)) { $GH = "gh" }

foreach ($p in @($EXE_PATH, $LINUX_PATH)) {
  if (-not (Test-Path $p)) { Write-Error "No se encontro: $p"; exit 1 }
}

# Carpeta temporal sin caracteres especiales para los assets.
$STAGE = Join-Path $env:TEMP "wvp3d_release_$VERSION"
if (Test-Path $STAGE) { Remove-Item $STAGE -Recurse -Force }
New-Item -ItemType Directory -Path $STAGE | Out-Null

function Get-Digest([string]$ruta) { (Get-FileHash -Path $ruta -Algorithm SHA256).Hash.ToLower() }

$exeHash   = Get-Digest $EXE_PATH
$exeSize   = (Get-Item $EXE_PATH).Length
$linuxHash = Get-Digest $LINUX_PATH
$linuxSize = (Get-Item $LINUX_PATH).Length

Write-Host "$EXE_NAME  -> $exeHash  ($exeSize bytes)"
Write-Host "$LINUX_NAME -> $linuxHash  ($linuxSize bytes)"

# R14: el digest de cada asset va tambien en SHA256SUMS, en el mismo gesto.
$sha256sumsPath = Join-Path $STAGE "SHA256SUMS"
@("$exeHash  $EXE_NAME", "$linuxHash  $LINUX_NAME") | Set-Content $sha256sumsPath -Encoding UTF8

# Esquema publicado por el pipeline: { tag_name, name, version, assets[] }.
$obj = [ordered]@{
  tag_name = $TAG
  name     = "Wold Virtual P2P 3D $TAG"
  version  = $VERSION
  assets   = @(
    @{ name = $EXE_NAME;   size = $exeSize;   digest = $exeHash;   url = "https://github.com/$REPO/releases/download/$TAG/$EXE_NAME" },
    @{ name = $LINUX_NAME; size = $linuxSize; digest = $linuxHash; url = "https://github.com/$REPO/releases/download/$TAG/$LINUX_NAME" }
  )
}
$releaseJsonPath = Join-Path $STAGE "release.json"
($obj | ConvertTo-Json -Depth 5) | Set-Content $releaseJsonPath -Encoding UTF8

Copy-Item $EXE_PATH   (Join-Path $STAGE $EXE_NAME)
Copy-Item $LINUX_PATH (Join-Path $STAGE $LINUX_NAME)

$notes = @"
## Wold Virtual P2P 3D $TAG

Release con las novedades de seguridad: subsistema defensivo ``STM_DEF`` y retirada del vector R-01.b.

| fichero | bytes | SHA-256 |
|---|---|---|
| ``$EXE_NAME`` (Windows, single-file, motor y mundo embebidos) | $exeSize | ``$exeHash`` |
| ``$LINUX_NAME`` (visor Linux Avalonia, motor y mundo embebidos) | $linuxSize | ``$linuxHash`` |

### Novedades de seguridad

- **Escaneo estatico del arbol** (``STM_DEF escanear``) con allowlist ``rutas_ignoradas.txt``: 0 hallazgos / LIMPIO.
- **Escaneo del historial de Git** (``STM_DEF historial``): detecta el commit malicioso del dropper EtherHiding.
- **Heuristica de entropia de Shannon** (umbral >= 6.0) para payloads ofuscados.
- **Integridad HMAC** de ficheros sellados y **cuarentena firmada** (nunca borra: conserva evidencia).
- **Arranque fail-closed**: ``ArranqueSeguro.cs`` invoca ``python -m STM_HRTS.STM_DEF arranque`` antes de abrir la ventana; fail-open solo si no existe el interprete Python o el arbol de fuentes.
- **Servicio de vigilancia** continuo (hilos daemon) y **firma Ed25519** autocontenida con respaldo puro RFC 8032.
- **Retirada del vector R-01.b**: el ``.vscode/settings.json`` de la raiz con ``task.allowAutomaticTasks`` y una tarea ``runOn: folderOpen`` queda eliminado; la configuracion vive en ``STM_HRTS/utils/.vscode``.

Deuda tecnica del desarrollo y fases pendientes (blindaje de red y gobernanza): issue de seguimiento.

### Linux

``$LINUX_NAME`` trae el visor completo (Avalonia 11): cuenta local, portal WebNodo, tunel P2P, invitacion, chat de texto, amigos, motor Godot y comprobacion de actualizaciones. El motor ``Godot_v4.7.2-stable_linux.x86_64`` y ``wvp3d.pck`` van embebidos en ``woldvirtual-linux`` y se extraen en el primer arranque. No lleva chat de voz ni webcam (dependen de DirectShow).

SHA-256 (Windows): ``$exeHash``
SHA-256 (Linux): ``$linuxHash``
"@

& $GH release create $TAG --repo $REPO --title "Wold Virtual P2P 3D $TAG" --notes $notes `
    "$STAGE\$EXE_NAME" "$STAGE\$LINUX_NAME" "$sha256sumsPath" "$releaseJsonPath"
if ($LASTEXITCODE -ne 0) { Write-Error "gh release create fallo (exit $LASTEXITCODE)"; exit $LASTEXITCODE }

Write-Host "Publicacion completada: https://github.com/$REPO/releases/tag/$TAG"
