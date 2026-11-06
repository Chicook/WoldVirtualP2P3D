# publish_release_v275.ps1
# Publica DMWoldVirtualP2P3Dv2.7.5.exe en GitHub Releases
$ErrorActionPreference = "Stop"
$VERSION      = "2.7.5"
$TAG          = "v$VERSION"
$EXE_NAME     = "DMWoldVirtualP2P3Dv$VERSION.exe"
$PUBLISH_DIR  = "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\bin\publish_v2.7.5"
$EXE_PATH     = Join-Path $PUBLISH_DIR $EXE_NAME
$REPO         = "Chicook/WoldVirtualP2P3D"
if (-not (Test-Path $EXE_PATH)) { Write-Error "No se encontro: $EXE_PATH"; exit 1 }
$hash = (Get-FileHash -Path $EXE_PATH -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $EXE_PATH).Length
Write-Host "SHA-256: $hash  ($size bytes)"
$sha256sumsPath = Join-Path $PUBLISH_DIR "SHA256SUMS"
"$hash  $EXE_NAME" | Set-Content $sha256sumsPath -Encoding UTF8
$obj = [ordered]@{ tag_name=$TAG; name="Wold Virtual P2P 3D $TAG"; version=$VERSION; assets=@(@{ name=$EXE_NAME; size=$size; digest=$hash; url="https://github.com/$REPO/releases/download/$TAG/$EXE_NAME" }) }
$releaseJsonPath = Join-Path $PUBLISH_DIR "release.json"
($obj | ConvertTo-Json -Depth 4) | Set-Content $releaseJsonPath -Encoding UTF8
$notes = "## Wold Virtual P2P 3D $TAG`n`nCambios H0-H4: datos preservados, OTA fail-closed, endpoint LAN dinamico, extraccion segura, 97 pruebas Python OK, selftests C# exit 0.`n`nSHA-256: $hash"
gh release create $TAG --repo $REPO --title "Wold Virtual P2P 3D $TAG" --notes $notes "$EXE_PATH#$EXE_NAME" "$sha256sumsPath#SHA256SUMS" "$releaseJsonPath#release.json"
Write-Host "Publicacion completada: https://github.com/$REPO/releases/tag/$TAG"
