# ⛔ Reglas estrictas de actualización — el flujo de Godot se respeta

**Alcance:** todo cambio que acabe en un binario publicado del visor (mundo Godot, motor,
`wvp3d.pck`, `godot_exe.zip`, C#, portal WebNodo o metadatos de release). Si una actualización
no pasa el checklist de §7, **no se publica**.

**Fuente de verdad:** el código, no los README. Cada regla cita el fichero y la línea que la
sustentan. Si el código cambia y esta página no, gana el código y esta página es un defecto.

Rutas relativas a la raíz del repositorio. El proyecto que se compila y exporta está bajo
`VersionDe_sesion/CONTRRF/TLLDCD/src/`; en lo que sigue, `<src/>` = esa carpeta `src/`. La copia
`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_f7bfd9ba/src/` es la última instantánea
RFPRMN y está congelada en la 2.5.5: no es el árbol del que sale un binario nuevo.

---

## 1. El flujo, en orden obligatorio

Ningún paso se salta ni se reordena. Cada flecha es una dependencia real, no una convención.

```
1  proyecto Godot            <src/>MTBGT/WoldVirtualP2P3D/   (project.godot: features "4.7", "Forward Plus")
   ↓  export                 godot --headless --export-pack "Windows Desktop" …  → wvp3d.pck
2  copiar el PCK             <src/>VSC#/wvp3d.pck            ← el .csproj lo embebe desde AQUÍ
3  versionar                 <src/>VSC#/Visor3D.csproj       ← Version / AssemblyVersion / FileVersion / AssemblyName
4  compilar                  dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
   ↓                         el .exe resultante CONTIENE el motor y el mundo
5  publicar release          exe + release.json + SHA256SUMS  (los tres en el mismo gesto)
6  OTA en el equipo cliente  UpdateChecker → UpdateDownloader (SHA-256) → UpdateApplier → relanzar
7  primer arranque           AppExtractor re-extrae motor + PCK a %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\
```

**Por qué el orden importa:** el PCK y el motor se incrustan en el `.exe` en el paso 4
(`<src/>VSC#/Visor3D.csproj:85-86`, `EmbeddedResource Include="godot_exe.zip"` / `"wvp3d.pck"`).
Exportar el mundo *después* de compilar produce un binario con el mundo viejo.

---

## 2. Reglas de versión y del mundo Godot

**R1 — El número de versión es la única señal de que el mundo cambió.**
El marcador de re-extracción es la versión del ensamblado
(`<src/>VSC#/AppExtractor.cs:20`, `AppVersion = ObtenerVersionEnsamblado()`), que fija la carpeta
`runtime\<versión>\` (`AppExtractor.cs:42,52`). Si cambias `wvp3d.pck` o `godot_exe.zip` y publicas
con la **misma** versión, los equipos ya actualizados seguirán arrancando el mundo extraído antes:
el `.exe` nuevo estará en disco pero el mundo visible será el viejo.

**R2 — Un binario nuevo exige `<Version>` nueva, y en los cuatro sitios a la vez.**
`<Version>`, `<AssemblyVersion>`, `<FileVersion>` y `<AssemblyName>`
(`<src/>VSC#/Visor3D.csproj:24,27-29`). `<AssemblyName>` debe ser exactamente el nombre del exe sin
extensión: hoy `DMWoldVirtualp2pCNXv2.5.8`, que corresponde al exe
`DMWoldVirtualp2pCNXv2.5.8.exe`.

**R3 — La versión debe coincidir en los cuatro planos:** csproj ↔ tag de GitHub (`v2.5.8`) ↔
nombre del fichero del asset (`DMWoldVirtualp2pCNXv2.5.8.exe`) ↔ `release.json` (`version`, `tag`,
`exe`, `url`). El actualizador lee
la versión del tag **y** del nombre del asset y toma la mayor
(`<src/>VSC#/STM_actualizar/UpdateChecker.cs`, `SeleccionarMejorRelease`); cualquier desalineación
hace que un visor se crea "al día" teniendo binario nuevo por instalar.

**R4 — Nunca se renombra un tag publicado.**
Renombrar `v2.5.2` → `v2.5.3` invalidó todas las URLs `…/download/v2.5.2/…`, que hoy responden 404,
y dejó obsoletos los metadatos que las referenciaban. Si una release sale mal: se sube el asset
corregido bajo un tag **nuevo**, no se toca el existente.

**R5 — La re-extracción cuesta ~686 MiB y segundos.** Es comportamiento esperado tras un OTA, no un
fallo. No se "arregla" volviendo el marcador a una constante fija: eso fue el defecto que existía
antes (constante `"0.1.0"`) y quedó documentado en el comentario de `AppExtractor.cs:16-19`.

---

## 3. Reglas del motor Godot

**R6 — El ejecutable del motor se llama y se coloca exactamente:**
`runtime\<versión>\Servidor3D\Godot_v4.7.2-stable_win64.exe` (`AppExtractor.cs:58`). Cambiar la
versión del engine obliga a actualizar esa ruta y el `godot_exe.zip`; el fallo de nombre se
autocorrige buscando el exe en subcarpetas, pero no se debe contar con ello.

**R7 — El mundo se lanza con `--main-pack`, nunca con `--path` en distribución.**
`<src/>VSC#/GodotHwndHost.cs:230`. Godot 4 **no** tiene flag `--scene`: la escena es argumento
posicional y un `--scene` desconocido puede abortar el arranque antes de leer los argumentos de red
y caer en modo local (comentario en `GodotHwndHost.cs:108-112`). Escena principal:
`res://WoldVirtual3DP2P.tscn` (`<src/>VSC#/GodotConfig.cs:79`).

**R8 — Los argumentos de red van siempre después de `--`.**
`GodotHwndHost.cs:239` (`args += $" -- {_userArgs}"`). El contrato entre el visor y el motor es:
`--client --ip=<host> --port=<puerto> --peer-url="<url>"`, emitido en
`<src/>VSC#/MainWindow.xaml.cs:717` y parseado en
`<src/>MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd:6-130` (precargado por `ChunkManager.gd:14` y
`Sonda.gd:9`, que lo usan en `ChunkManager.gd:1103-1107` y `Sonda.gd:24-31`). La sonda previa al
carrusel usa el mismo descubrimiento y la misma URL que el mundo: si tocas el parseo de túneles
(`Red.gd`), el cambio vale para ambos lados.
**Cambiar una bandera exige tocar los dos lados en el mismo commit.** Sin `--userArgs`, Godot arranca
como `SERVIDOR_LOCAL` por defecto (`GodotHwndHost.cs:252`): no es un error, pero un binario que deba
conectar y no conecta se manifiesta así.

**R9 — El proyecto Godot y el PCK no conviven en Git.** `*.pck` y `*.zip` están excluidos
(`.gitignore:59-60`). Lo que se versiona es el **proyecto** (`<src/>MTBGT/WoldVirtualP2P3D/`) y el
código GDScript; el PCK se regenera. Por tanto, un commit que toque `.gd`/escenas **debe** ir
acompañado, en la publicación, de un PCK exportado desde ese mismo árbol — nunca de un PCK heredado
de una build anterior.

---

## 4. Reglas de red y del portal WebNodo

**R10 — Puertos fijados en código, no en documentación:** portal `3030`, con rango de reserva
`3030…3040` y proxy interno `puerto + 100`
(`<src/>VSC#/Services/WebNodoService.cs:63,275-276,286`); WebSocket del motor **TCP 8911**
(`WebNodoService.cs:575`, `MainWindow.xaml.cs:726`). **No hay ENet**: cualquier doc que mencione
ENet/8910 está obsoleto.

**R11 — El portal anuncia la release vigente real, nunca una etiqueta fija.**
Al arrancar, `RefrescarReleaseVigente()` (`WebNodoService.cs:86,266`) consulta GitHub con el **mismo**
criterio que el botón de actualizar y sustituye el valor empaquetado. Está prohibido volver a:
leer sólo `release.json` del disco (ningún OTA lo regenera → el portal queda congelado), o escribir
un nombre de exe a mano en `webnodo/public/index.html`. El `ExeNameFallback`
(`WebNodoService.cs:64`) es último recurso ante fallo de red, no el valor anunciado.

**R12 — `/descargar` sirve el `.exe` en ejecución si su nombre coincide con la release vigente**, y
sólo si no, busca en `webnodo/descargas/`, y si tampoco lo encuentra redirige a GitHub
(`WebNodoService.cs:670-707`, bloque `/descargar`). Prohibido servir un binario obsoleto del disco: es mejor
redirigir.

**R13 — Un visor ya instalado no se arregla cambiando GitHub.** Las correcciones de R11/R12 llegan a
un equipo cuando ese equipo hace OTA a la versión que las contiene. Documentar lo contrario es
mentir: los builds antiguos anuncian la constante empotrada en su propio binario.

---

## 5. Reglas de publicación

**R14 — El triple `exe` + `release.json` + `SHA256SUMS` se sube junto, y se regenera junto.**
`release.json` con `version`, `tag`, `exe`, `url`, `size_mb`; `SHA256SUMS` con el digest del exe y el
del propio `release.json`. Subir sólo el binario deja el portal y cualquier consumidor externo
apuntando al anterior.

**R15 — Verifica por API, no por `curl`.** GitHub cachea assets por CDN: tras un `--clobber`, la URL
de descarga puede servir contenido viejo durante decenas de segundos. El `digest` que devuelve
`gh api repos/…/releases/tags/<tag> --jq '.assets[]'` es la autoridad.

**R16 — Antes de tocar GitHub, confirmar con el responsable.** Subir assets, marcar *Latest* o
abrir PRs son acciones sobre estado compartido y no son reversibles para quien ya descargó.

**R17 — El `.exe` no se comitea.** `.gitignore:55-56,59-60` (`*.exe`, `*.dll`, `*.zip`, `*.pck`) y
AGENTS.md §2. El binario vive únicamente en la release.

---

## 6. Regla de documentación

**R18 — Actualizar docs en el mismo commit que el cambio.** Toda afirmación rastreable a un fichero,
cada capacidad con una etiqueta exacta (*Implementado* / *Implementado, sin prueba real* / *Parcial* /
*Planificado* / *Fuera del repo*), cifras recalculadas y nunca copiadas de un doc viejo, y siglas que
el repo no expande marcadas "sin documentar".

---

## 7. Checklist obligatorio antes de dar por buena una actualización

Con evidencia en el log, no "me parece que va". El visor escribe en
`%LOCALAPPDATA%\WoldVirtualP2P3D\logs\visor-<fecha>.log` y `update_debug.log`.

- [ ] **PCK fresco:** `wvp3d.pck` exportado del árbol Godot de este commit (comprobar fecha/horas y
      tamaño real, no el tamaño recordado).
- [ ] **Versión sincronizada** en csproj, tag, nombre del asset y `release.json` (R2, R3).
- [ ] **Compila** con el .NET de `E:\Program Files\dotnet\dotnet.exe` (`DOTNET_ROOT` en E:), publish
      self-contained single-file.
- [ ] **Cero binarios en el commit:** `git status` sin `.exe`/`.dll`/`.zip`/`.pck` (R17).
- [ ] **Arranque limpio:** aparece carpeta `runtime\<versión nueva>\` y su `.extracted` contiene esa
      versión (esto demuestra R1). Sin líneas `ERROR`/`EXCEPTION` en el log.
- [ ] **El motor arranca desde el PCK:** la ventana muestra el mundo (no el modo local vacío).
- [ ] **Portal:** el log contiene `WebNodo: release vigente → <exe esperado>`; `/api/info` devuelve
      ese nombre y tamaño; `/descargar` responde `200` con `Content-Length` igual al número de bytes
      del asset publicado.
- [ ] **OTA de punta a punta en un equipo con la versión anterior:** actualizar → relanzar →
      re-extracción → el mundo y el portal muestran la nueva versión (R13: es la única prueba que
      vale).
- [ ] **Metadatos:** `digest` del asset publicado según `gh api` coincide con el SHA-256 local (R15).
- [ ] **Docs:** README y esta página actualizadas en el mismo commit (R18).

---

## 8. Prohibiciones duras

1. Publicar con la misma versión un mundo o motor distintos (R1).
2. Renombrar o borrar un tag ya publicado con assets descargados (R4).
3. Poner un nombre de exe, una URL o un tamaño a mano en el portal o en `release.json` (R3, R11).
4. Servir desde `webnodo/descargas/` un binario más antiguo que el que se está ejecutando (R12).
5. Cambiar una bandera de la línea de órdenes de Godot sin tocar `MainWindow.xaml.cs` **y**
   `ChunkManager.gd` en el mismo commit (R8).
6. Mencionar ENet/8910 como si existiera (R10).
7. Comitear binarios o el PCK (R9, R17).
8. Afirmar que una corrección alcanzó a los clientes sin la prueba OTA de §7 (R13).
9. Recompilar para un detalle cosmético una vez publicado el digest: invalida `SHA256SUMS` y el
   `release.json` (R14).

---

## 9. Huecos conocidos (no ocultarlos detrás de estas reglas)

- **Preset de exportación (resuelto el 2026-10-23).** `export_presets.cfg` está versionado en
  `<src/>MTBGT/WoldVirtualP2P3D/` con `export_filter="all_resources"` y un `exclude_filter` que
  descarta las copias de avatares que ningún catálogo usa (`avtrnCRS/Texturas/` y los `.glb` sin
  animación). Las texturas usadas llevan `process/size_limit=2048` en sus `.import` (los 24 avatares
  a 2K; el terreno 4K a 2K). Comando exacto, reproducible desde un clon con los assets locales:
  `godot --headless --path . --import` y
  `godot --headless --path . --export-pack "Windows Desktop" wvp3d.pck`.
  *Estado: Implementado.*
- **Formato de `tamano_mb`:** `/api/info` emite coma decimal (`"536,0"`) por heredar la cultura del
  sistema. Corrección aplazada a propósito: recompilar invalidaría el digest publicado (§8.9).
  *Estado: Implementado, sin prueba real de consumo externo estricto.*
- **Sesión persistida (resuelto el 2026-10-23).** `user://session_host.txt` sólo lo escribe el
  anfitrión local (`ChunkManager.gd:1035`): nunca identifica a un anfitrión
  remoto. Hasta v2.5.4 el visor lo leía en `MainWindow.ComprobarHostMigrado()` y lo asignaba a
  `_urlAmigoPendiente`, que decide el rol con el que arranca Godot; tras reiniciar o actualizar, el
  visor arrancaba como **cliente de su propio túnel ya cerrado** y la carga no terminaba (el cliente
  explícito no degrada a anfitrión). Desde v2.5.5 ese fichero sólo actualiza el enlace de invitación
  y se ignoran los archivos anteriores al arranque. *Estado: Implementado, sin prueba real.*
- **`WOLD_RUNTIME_DIR` con barras `/` (resuelto el 2026-10-23).** `AppExtractor.ExtractResource`
  comparaba la ruta extraída con `destDir` sin normalizar; con barras normales (`E:/tmp/...`)
  descartaba las entradas del zip del motor y dejaba `Servidor3D` vacío. Ahora ambas rutas pasan por
  `Path.GetFullPath`. Con la ruta por defecto (barras invertidas de Windows) nunca ocurrió.
  *Estado: Implementado.*
- **El PCK embebido no se valida por hash** en tiempo de ejecución: `AppExtractor` se guía por la
  versión del ensamblado, no por el contenido. Un PCK corrupto en el `.exe` sólo se detecta al
  arrancar Godot. *Estado: Planificado.*
