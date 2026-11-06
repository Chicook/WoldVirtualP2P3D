# publicar_version.ps1
#
# Publica la version que dicta src/VERSION.json. Sustituye a publish_release_v275.ps1 y
# publish_release_v276.ps1, que cableaban el numero, la carpeta de salida y las notas: cada
# release era una copia con tres oportunidades de equivocarse (medida en el plan §1.6: el
# binario publicado como 2.7.6 salia de un arbol que declaraba 2.7.5).
#
#   .\publicar_version.ps1                # comprueba, compila y deja los artefactos listos
#   .\publicar_version.ps1 -Rebuild        # fuerza dotnet publish aunque exista el .exe
#   .\publicar_version.ps1 -Publicar -Notas notas.md
#   .\publicar_version.ps1 -Publicar -Notas notas.md -Objetivo DevQoderIA
#
# Sin -Publicar NO se sube nada: el arbol preparado se puede revisar antes. La publicacion es
# irreversible (regla R4: un tag publicado no se reescribe ni se borra), asi que el guion se
# niega si la etiqueta ya existe en Releases.
#
# -Objetivo existe porque gh pone el tag en la rama POR DEFECTO del repo (main). Si el binario
# se construyo desde otro arbol, ese tag por defecto anuncia un .exe cuyo fuente no esta en el
# commit: es el desfase binario/anuncio cerrado en DT-08, pero esta vez con tag irreversible.
# Sin -Objetivo el guion se niega a publicar y obliga a nombrar la rama o commit del fuente.
#
# La ruta del proyecto contiene '#' (VSC#) y gh.exe parte en el PRIMER '#', por eso los
# artefactos se copian a una carpeta temporal limpia antes de subirlos.
[CmdletBinding()]
param(
    [switch]$Publicar,
    [switch]$Rebuild,
    [string]$Notas = "",
    [string]$Objetivo = "",
    [string]$Repositorio = "Chicook/WoldVirtualP2P3D"
)
$ErrorActionPreference = "Stop"

$UTILS = $PSScriptRoot
$SRC   = (Resolve-Path (Join-Path $UTILS "..\..\..")).Path
$VSC   = Join-Path $SRC "VSC#"
$TABLA = Join-Path $SRC "STM_HRTS\utils\add_utils\version_unica.py"
$GH    = "e:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $GH)) { $GH = "gh" }

function Paso($mensaje) { Write-Host "==> $mensaje" }

# gh.exe escribe por stderr tambien cuando la operacion es una sonda («release not found» al
# comprobar si la etiqueta ya existe). Con ErrorActionPreference=Stop ese mensaje abortaba el
# guion ANTES de subir nada: medido el 2026-11-05 al publicar la 2.7.7, el paso 6 moria en su
# propia comprobacion previa. Toda llamada a gh pasa por aqui; devuelve verdadero solo si gh
# salio 0 y deja el codigo en GH_EXITO para los mensajes de fallo.
$script:GH_EXITO = 0
function Gh($argumentos) {
    $previa = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $salida = & $GH @argumentos 2>&1
    $script:GH_EXITO = $LASTEXITCODE
    $ErrorActionPreference = $previa
    if ($script:GH_EXITO -ne 0) {
        (($salida | Out-String).Trim()) | ForEach-Object { Write-Host "  gh: $_" }
    }
    return ($script:GH_EXITO -eq 0)
}

# Python no tiene por donde quejarse por stderr sin que Stop lo considere un error fatal.
function Tabla($argumento) {
    $salida = @(& python $TABLA $argumento 2>$null)
    if ($LASTEXITCODE -ne 0 -or $salida.Count -eq 0) {
        Write-Error "version_unica.py $argumento fallo (exit $LASTEXITCODE). Arbol: $SRC"
        exit 1
    }
    return ($salida[-1] -as [string]).Trim()
}

# 1. El numero no se escribe aqui: se lee de la tabla unica.
$VERSION = Tabla "--leer"
if ($VERSION -notmatch '^\d+\.\d+\.\d+$') { Write-Error "version leida sin formato x.y.z: '$VERSION'"; exit 1 }
$TAG = "v$VERSION"
Paso "version unica: $VERSION (motor y PCK anclados en VERSION.json)"

# 2. La puerta: si csproj/RutasLinux/PCK vuelven a cablear el numero, no se publica.
$null = Tabla "--comprobar"
Paso "version_unica --comprobar OK"

# 3. Compilar el distributable (single-file, autocontenido, con el PCK embebido).
$PUBLISH_DIR = Join-Path $VSC "bin\publish_v$VERSION"
$EXE_NAME    = "DMWoldVirtualP2P3Dv$VERSION.exe"
$EXE_PATH    = Join-Path $PUBLISH_DIR $EXE_NAME
if ($Rebuild -or -not (Test-Path $EXE_PATH)) {
    Paso "dotnet publish Visor3D.csproj -c Release -r win-x64 -> bin\publish_v$VERSION"
    & dotnet publish (Join-Path $VSC "Visor3D.csproj") -c Release -r win-x64 --self-contained true `
        -o $PUBLISH_DIR
    if ($LASTEXITCODE -ne 0) { Write-Error "dotnet publish fallo (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
}
if (-not (Test-Path $EXE_PATH)) { Write-Error "no se encontro $EXE_PATH tras compilar"; exit 1 }

# 4. Coherencia binario/tabla: el .exe se llama como dice la tabla o no se publica.
$INFO = (Get-Item $EXE_PATH).VersionInfo
if ($INFO.FileVersion -notlike "$VERSION*") {
    Write-Error "el .exe anuncia FileVersion '$($INFO.FileVersion)' y la tabla dicta $VERSION"
    exit 1
}
$HASH = (Get-FileHash -Path $EXE_PATH -Algorithm SHA256).Hash.ToLower()
$SIZE = (Get-Item $EXE_PATH).Length
Paso "$EXE_NAME · $SIZE bytes · sha256 $HASH"

# 5. Escaparate sin caracteres especiales: release.json + SHA256SUMS con el esquema que lee el WebNodo.
$STAGE = Join-Path $env:TEMP "wvp3d_release_$VERSION"
if (Test-Path $STAGE) { Remove-Item $STAGE -Recurse -Force }
New-Item -ItemType Directory -Path $STAGE | Out-Null
Copy-Item $EXE_PATH (Join-Path $STAGE $EXE_NAME)
"$HASH  $EXE_NAME" | Set-Content (Join-Path $STAGE "SHA256SUMS") -Encoding UTF8
$OBJ = [ordered]@{
    tag_name = $TAG
    name     = "Wold Virtual P2P 3D $TAG"
    version  = $VERSION
    assets   = @(@{
        name   = $EXE_NAME
        size   = $SIZE
        digest = $HASH
        url    = "https://github.com/$Repositorio/releases/download/$TAG/$EXE_NAME"
    })
}
($OBJ | ConvertTo-Json -Depth 4) | Set-Content (Join-Path $STAGE "release.json") -Encoding UTF8
Paso "artefactos preparados en $STAGE"

if (-not $Publicar) {
    Write-Host ""
    Write-Host "Sin publicar (falta -Publicar). Para repasar y subir:"
    Write-Host "  .\$([IO.Path]::GetFileName($PSCommandPath)) -Publicar -Notas notas.md"
    exit 0
}

# 6. Publicacion: exige notas escritas por una persona y rehuye reescribir un tag existente.
if (-not $Notas -or -not (Test-Path $Notas)) {
    Write-Error "-Publicar pide -Notas <fichero> con el texto de la release (no se inventan)."
    exit 1
}
$NOTAS = (Resolve-Path $Notas).Path
if (-not $Objetivo) {
    Write-Error "-Publicar pide -Objetivo <rama|commit>: sin el, gh anclaria $TAG en la rama por defecto."
    exit 1
}
if (Gh @("release", "view", $TAG, "--repo", $Repositorio)) {
    Write-Error "la release $TAG ya existe: un tag publicado no se reescribe (regla R4)."
    exit 1
}
# El fuente del binario tiene que existir en el remoto: un tag sobre un commit local no publicado
# dejaria la release apuntando a una nada.
if (-not (Gh @("api", "repos/$Repositorio/git/ref/heads/$Objetivo"))) {
    Write-Error "-Objetivo '$Objetivo' no es una rama existente en $Repositorio."
    exit 1
}
Paso "subiendo $TAG a $Repositorio (anclado en $Objetivo)"
$CREAR = Gh @("release", "create", $TAG, "--repo", $Repositorio, "--target", $Objetivo,
              "--title", "Wold Virtual P2P 3D $TAG", "--notes-file", $NOTAS,
              (Join-Path $STAGE $EXE_NAME), (Join-Path $STAGE "SHA256SUMS"), (Join-Path $STAGE "release.json"))
if (-not $CREAR) {
    Write-Error "gh release create fallo (exit $GH_EXITO). Comprueba con 'gh release view $TAG' antes de reintentar:"
    Write-Error "si la release ya existe, el fallo es posterior a la creacion y NO se repite (regla R4)."
    exit $GH_EXITO
}
Write-Host "Publicada: https://github.com/$Repositorio/releases/tag/$TAG"
