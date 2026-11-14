# publish_release_v276.ps1
# Publica DMWoldVirtualP2P3Dv2.7.6.exe en GitHub Releases.
#
# Nota: la ruta del proyecto contiene '#' (VSC#) y gh.exe divide en el PRIMER '#',
# así que se copian los artefactos a una carpeta temporal limpia antes de subirlos.
$ErrorActionPreference = "Stop"
$VERSION      = "2.7.6"
$TAG          = "v$VERSION"
$EXE_NAME     = "DMWoldVirtualP2P3Dv$VERSION.exe"
$PUBLISH_DIR  = "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\bin\publish_v2.7.6"
$EXE_PATH     = Join-Path $PUBLISH_DIR $EXE_NAME
$REPO         = "Chicook/WoldVirtualP2P3D"
$GH           = "e:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $GH)) { $GH = "gh" }
if (-not (Test-Path $EXE_PATH)) { Write-Error "No se encontro: $EXE_PATH"; exit 1 }

# Carpeta temporal sin caracteres especiales para los assets.
$STAGE = Join-Path $env:TEMP "wvp3d_release_$VERSION"
if (Test-Path $STAGE) { Remove-Item $STAGE -Recurse -Force }
New-Item -ItemType Directory -Path $STAGE | Out-Null

$hash = (Get-FileHash -Path $EXE_PATH -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $EXE_PATH).Length
Write-Host "SHA-256: $hash  ($size bytes)"

$sha256sumsPath = Join-Path $STAGE "SHA256SUMS"
"$hash  $EXE_NAME" | Set-Content $sha256sumsPath -Encoding UTF8

$obj = [ordered]@{ tag_name=$TAG; name="Wold Virtual P2P 3D $TAG"; version=$VERSION; assets=@(@{ name=$EXE_NAME; size=$size; digest=$hash; url="https://github.com/$REPO/releases/download/$TAG/$EXE_NAME" }) }
$releaseJsonPath = Join-Path $STAGE "release.json"
($obj | ConvertTo-Json -Depth 4) | Set-Content $releaseJsonPath -Encoding UTF8

Copy-Item $EXE_PATH (Join-Path $STAGE $EXE_NAME)

$notes = "## Wold Virtual P2P 3D $TAG`n`nCambios del 2026-11-04:`n- **W-01 / DT-11 resuelto:** el WebNodo lee el release.json publicado con esquema {assets[]}, /descargar sirve el binario en ejecucion bajo el nombre anunciado (sin redirecciones 301), refresco de la release vigente cada 5 min y /api/info expone version y version_instalada.`n- Nueva autoprueba --webnodo-selftest.`n- Proyecto de pruebas unitarias xUnit Visor3DTests (34 superadas).`n- La pantalla de inicio de sesion detecta un nodo activo en el propio equipo.`n`nSHA-256: $hash"
& $GH release create $TAG --repo $REPO --title "Wold Virtual P2P 3D $TAG" --notes $notes "$STAGE\$EXE_NAME" "$sha256sumsPath" "$releaseJsonPath"
if ($LASTEXITCODE -ne 0) { Write-Error "gh release create fallo (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
Write-Host "Publicacion completada: https://github.com/$REPO/releases/tag/$TAG"
