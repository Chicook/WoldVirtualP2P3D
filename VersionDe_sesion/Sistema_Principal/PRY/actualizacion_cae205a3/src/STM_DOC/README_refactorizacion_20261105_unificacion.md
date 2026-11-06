# Plan de refactorización — versión nueva y unificada en `CONTRRF/TLLDCD/src`

**Fecha de medición:** 2026-11-05 · **Rama local:** `DevQoderIA` @ `294a72a` · **`origin/main`:** `490817d` (PRs #57–#62 fusionadas el mismo 2026-11-05)
**Versión declarada en el código de la zona:** `2.7.4` · **Declarada en `main`:** `2.7.5` · **Declarada en `DevAntigravityIDEIA`:** `2.7.6` · **Release publicada vigente:** `v2.7.6` (*Latest*, 2026-11-04T12:47:37Z) · **Versión del issue contenedor de deuda:** v2.7.5 ([#48](https://github.com/Chicook/WoldVirtualP2P3D/issues/48))

Todo el trabajo de este plan se ejecuta **dentro de `E:\WoldVirtualP2P3D`**, y el árbol de destino es
`VersionDe_sesion/CONTRRF/TLLDCD/src/` (en adelante **`src/`** o *zona de trabajo*).

> Las siglas `CONTRRF`, `TLLDCD`, `RFC`, `PRY`, `STM_*`, `MTBGT`, `SBSTM`, `LC_STM`, `VSC#` y `RFPRMN`
> **no están expandidas en el repositorio** (lo dice el propio `README.md:296`, `:632` y `:662`).
> Este documento no les inventa significado: se refiere a ellas por la ruta literal.

---

## 1. Diagnóstico medido

### 1.1 Hay cuatro copias del mismo proyecto y **ninguna es superconjunto**

| # | Copia | Ficheros | Estado |
|---|---|---|---|
| A | `src/` en **disco** (zona de trabajo, rellenada hoy 16:36 por RFPRMN) | 6.637 (1,5 GiB) | no rastreada por Git en esta rama |
| B | `PRY/actualizacion_2f040968/src` en disco (instantánea creada hoy por `actualizar`) | 6.637 | no rastreada |
| C | `PRY/actualizacion_aeef1149/src` en **`origin/main`** | 659 rastreados | **el tronco: lleva las PRs `stage1/*` y el arte S8** |
| D | `CONTRRF/TLLDCD/src` en **`origin/DevAntigravityIDEIA`** | 504 rastreados | utillaje, autopruebas del portal, tests xUnit **y la fuente del `.exe` publicado v2.7.6** (§1.6) |

**Parentesco real de las ramas** (medido con `git merge-base`): el punto de bifuración de C y D es
`e8295fc` («addev», 2026-10-31). Desde ese punto, **`origin/main` acumula 47 commits privativos y
`origin/DevAntigravityIDEIA` sólo 5** (`d510acd` CI + suites H1/H2/H3, `8bbf920` reordena `STM_HRTS` y añade
`STM_PY`, `c8854d8` merge de `DevTraeIA`, `f95c60e`, `a43202b`). `origin/DevAntigravityIDEIA` **no es ancestro
de `main`**: son dos líneas separadas desde el 31-10, pero con papeles distintos — C es el tronco funcional y
D es una rama de utillaje. La rama checkout local (`DevQoderIA` @ `294a72a`) está **47 commits por detrás de
`main`**, anterior incluso al punto de bifurcación.

Mediciones sobre Git (blob por blob, no por fecha de fichero):

- Comunes C∩D: **436 rutas → 407 idénticas, 29 con contenido distinto**.
- **Sólo en C (223):** 107 en `MTBGT/.../gltfimport`, 46 en `STM_HRTS/utils`, 32 en `MTBGT/.../AreaDeTrabajo`,
  17 en `MTBGT/.../SLCAV`, 7 en `tests`, 1 en `VSC#/Chat`, 1 en `MTBGT/.../gdscrip`. Aquí están los
  **25 `.glb`/`.gltf` (5.048.684 B) de la PR #63** y el trabajo de seguridad `stage1`.
- **Sólo en D (68):** `STM_HRTS/utils/STM_UTILS/` (39 arneses `probar_*.gd`, `retarget_animaciones.py`,
  `purgar_repositorio.ps1`…), `STM_HRTS/STM_PY/__main__.py`, `VSC#/Services/WebNodoSelfTest.cs`.
- Disco (A) frente a C: de las 659 rutas rastreadas por `main`, **192 no existen en el disco**.
- La misma pieza, tres grosores **y tres contenidos distintos**: `VSC#/Services/WebNodoService.cs` mide
  **896 líneas en el disco (A), 1.011 en C y 1.018 en D** (§1.7). `MTBGT/.../Construccion.gd`: 1.761 en el
  disco, y C integra las ramas de #60 y #61 con
  aritmética limpia de unión (1.761 + 68 + 15 = **1.844**).

**Consecuencia:** hoy no existe un único árbol desde el que compilar la última versión. El tronco (C) es el
más avanzado en funcionalidad y el punto de partida correcto; pero las autopruebas del portal y el utillaje
de Godot **sólo existen en D**, y la zona de trabajo (A) no coincide exactamente con ninguna de las dos.

### 1.2 Los 29 ficheros que divergen son toda la superficie de conflicto

`VSC#`: `App.xaml.cs` · `MainWindow.xaml.cs` · `Visor3D.csproj` · `Services/WebNodoService.cs` ·
`Services/RateLimiter.cs` · `Chat/ChatClient.cs` · `Chat/ChatRelayServer.cs` · `RedP2P/P2PNodo.cs` ·
`RedP2P/RedP2PServicio.cs` · `VisorLinux/VisorLinux.csproj` · `VisorLinux/Vistas/VentanaPrincipal.Chat.cs` ·
`VisorLinux/Vistas/VentanaPrincipal.Red.cs`
`MTBGT`: `gdscrip/Red.gd` · `ChunkManager.gd` · `Construccion.gd` · `PlayerSync.gd` · `Identidad.gd`
Otros: `README_DESARROLLO.md` · `STM_CH/rutas.py` · `LC_STM/red_neuronal/ENRN/EN10_RN.py` ·
`SBSTM/accesores.py` · `STM_HRTS/.github/workflows/ci.yml` · 4 tests · 3 ficheros de `STM_HRTS/opencode`

### 1.3 Peso: el 92 % de la zona de trabajo no es código del proyecto

| Elemento | Medida | Naturaleza |
|---|---|---|
| `STM_HRTS/opencode/` | **881 MiB, 5.259 ficheros** (5.256 bajo `node_modules`; `opencode-ai 1.19.5`; 454 `.js.map`, 955 `.d.ts`) | herramienta vendoreada. **Ningún fichero del proyecto la importa.** Cuatro copias idénticas de `opencode.exe` de 211.564.424 B |
| `VSC#/bin/` + `obj/` | **≈350 MiB** (incluye `bin/publish_v2.7.6/DMWoldVirtualP2P3Dv2.7.6.exe`, 365.088.633 B) | salida de compilación |
| `STM_CH/pycache/` | 855 `.pyc` en 23 MiB | bytecode, incluido `scipy`/`numpy`/`site-packages` de intérpretes ajenos (`STM_CH/rutas.py:37-48` fija `sys.pycache_prefix`) |
| `VSC#/wvp3d.pck` | 114.591.724 B | binario legítimo embebido en el exe |
| `VSC#/godot_exe.zip` / `godot_linux.zip` | 86.155.888 / 79.135.021 B | binarios legítimos embebidos |
| Código real | ≈1.400 ficheros: 88 `.cs`, 65 `.gd`, 124 `.py`, 38 `.tscn`, 126 `.md` | lo que hay que unificar |

### 1.4 El árbol de trabajo está en un estado de índice anómalo

`git status --short`: **463 borrados**, 18 sin rastrear, **2 `MD`**, **1 `UU`**, **1 `DU`**
(`src/STM_CH/PSNRL/cierre_sesion_blockchain.json` y `PRY/actualizacion_91883d55/src/STMGNRL/mainLCSTM.py`)
**sin `MERGE_HEAD`, `CHERRY_PICK_HEAD` ni `REBASE_HEAD`**: es un índice con entradas en conflicto huérfanas,
no un merge en curso. Cualquier `git commit` imprudente registraría la **desaparición del instantáneo
`actualizacion_91883d55`** (463 ficheros) y dejaría entradas sin etapa. Esto hay que resolver **antes**
de tocar una sola línea de código (fase U0).

Además `.gitignore` lista `cierre_sesion_blockchain.json` **dos veces**, y ese fichero es de los pocos
`src/` que Git rastrea en esta rama.

### 1.5 Duplicación Windows/Linux: no hay núcleo común, hay `Include` improvisado

Hay **2 `.csproj` y ningún `.sln`**. `VisorLinux/VisorLinux.csproj:28-43` enlaza **17 ficheros** concretos
del árbol WPF (`WebNodoService`, `DescubrimientoP2P`, `RateLimiter`, `VisorLog`, `RedP2P/*`, 4 de `Chat`,
3 de `STM_actualizar`, 4 de `Seguridad`). Todo lo que no está en esa lista se **re-implementa** para Linux:

| Clase | Windows | Linux | Mismo namespace |
|---|---|---|---|
| `InstanciaUnica` | `Services/InstanciaUnica.cs` | `VisorLinux/Linux/InstanciaUnica.cs` | sí (`Visor3D.Services`) |
| `RegistroPcUnico` | `Seguridad/Seguridad_sesion_unica/RegistroPcUnico.cs:32` (190 ln) | `VisorLinux/Linux/RegistroPcUnico.cs:17` | sí |
| `ReinicioCuenta` | `…/ReinicioCuenta.cs:18` (326 ln) | `VisorLinux/Linux/ReinicioCuenta.cs:15` (258 ln) | sí |
| OTA | `STM_actualizar/UpdateChecker` + `UpdateDownloader` + `UpdateApplier` | `Linux/ActualizadorLinux.cs` (300 ln), que re-declara `GhRelease`/`GhAsset` (`:284,:292`) y reimplementa la comparación de versiones | — |

**62 nombres de método idénticos** entre ambos visores (`ConectarChatAsync`, `ResolverEndpointChat`,
`EnlaceInvitacion`, `BuscarEnLanAsync`, `SendDirectAsync`, `MarcarArranqueCorrecto`…). Es la razón mecánica
por la que cada PR `stage1` toca dos o tres ficheros gemelos y por la que las 29 divergencias existan.

El subsistema `Seguridad/SMTPLC/` (8 ficheros: `LocationAccountLedger` 271 ln, `LocationFingerprinter` 312,
`VmDetector` 399, `VpnDetector` 351, `SmtplcSecurityService` 221…) **no está enlazado a Linux**: hoy el
visor de Linux no ejecuta ninguna de las comprobaciones que describe la issue #26.

### 1.6 La versión tiene cinco fuentes de verdad y se desmienten entre sí

| Fuente | Valor |
|---|---|
| `Visor3D.csproj:24,27-29` | `2.7.4` |
| `VisorLinux.csproj:10` | `2.7.4` |
| `RutasLinux.cs:15` | `2.7.4` (y motor `4.7.2` en `:16`) |
| `VSC#/obj/.../VisorLinux.AssemblyInfo.cs` (generado, rancio) | `2.7.5` |
| `VSC#/bin/publish_v2.7.6/` | `2.7.6` |
| `SBSTM/__init__.py` `__version__` | `2026.3.1` |

Y hay **tres parseadores de versión paralelos**: `AppExtractor.cs:20-32` (reflejos del ensamblado),
`STM_actualizar/UpdateChecker.cs:234` y `:258` (desde el tag y desde el nombre del asset) y
`MainWindow.xaml.cs:232`/`:250` (tercera copia, con `"0.0.0"`).

**La correspondencia binario ↔ fuente está rota (medido).** La release vigente es **v2.7.6** (*Latest*,
publicada el 2026-11-04T12:47:37Z): su `DMWoldVirtualP2P3Dv2.7.6.exe` pesa 365.088.633 B con SHA-256
`26fb446e45a937af2a6c8866efb9601ef0ec0b192d105f33aba2e01d973b150f`, **idéntico byte a byte** al exe que hay en
`VSC#/bin/publish_v2.7.6/` de la zona, y su `release.json` (531 B, `3465bbc7…66ad28`) coincide igual con el local.
Pero el tag `v2.7.6` (`3caf0e7`, merge de #47) está sobre `main` y **el árbol que `main` rastrea declara 2.7.5**
(`Visor3D.csproj:24,27-29` de `PRY/actualizacion_aeef1149/src`), mientras que `origin/DevAntigravityIDEIA` declara
2.7.6 y su `Description` enumera exactamente el trabajo del 2026-11-04. Es decir: **el binario que se descarga
hoy no tiene fuente en el tronco**; esa fuente es privativa de D. Por eso U1 no puede reducirse a «quedarse
con `main`».

### 1.7 Defecto raíz comprobado: `release.json` tiene otro esquema y el fallo es silencioso

`VSC#/Services/WebNodoService.cs:171-183` (copia en disco) lee `release.json` buscando las claves **`exe`, `url`,
`size_mb`** y, si algo falla, cae en `catch { }` (línea 183) sin avisar. El `release.json` real que se genera al publicar
tiene **`tag_name`, `name`, `version`, `assets[].{url,name,digest,size}`** (verificado en
`VSC#/bin/publish_v2.7.6/release.json`). Por tanto `TryGetProperty("exe")` nunca acierta, la lectura local
**no aporta nunca nada** y el valor de arranque del portal son los literales cableados en `:70` y `:72`
(`DMWoldVirtualP2P3Dv2.7.4.exe`). Este es el mecanismo que subyace a W-01/DT-11 y a DT-14, y sigue vivo en
la zona de trabajo: no existe `--webnodo-selftest` en esta copia (sólo `App.xaml.cs:16,23,30,38` despachan
`--cuenta-selftest`, `--chat-selftest`, `--startup-selftest`, `--red-selftest`).

**Qué se rompe exactamente, según sus propias reglas.** El sondeo a GitHub sí existe en las tres copias
(`RefrescarReleaseVigente()` → `RefrescarReleaseAsync()`, A `:98-128`), así que a los pocos segundos el portal
anuncia la *Latest* real y R11 se cumple. Lo que no funciona nunca es el **valor de arranque**: como la lectura
local falla por esquema, `ReleaseActiva` nace siendo la constante, no el `release.json` empaquetado que R14 obliga
a regenerar junto al binario. Mientras no hay red, o antes del primer refresco, A anuncia `DMWoldVirtualP2P3Dv2.7.4.exe`
(literal fijo, y por tanto **un binario que no es el que está corriendo**, contra R12/R13) y C anuncia el suyo
derivado del ensamblado — que es la conducta razonable que R13 describe para los builds antiguos. Sólo D convierte
el `release.json` empaquetado en fuente útil.

**El arreglo ya existe, pero sólo en D — y las tres copias están en puntos distintos del mismo fichero:**

| Copia | Claves que lee | *Fallback* del nombre anunciado | Qué trae de propio |
|---|---|---|---|
| A disco (896 ln, csproj **2.7.4**) | `exe`/`url`/`size_mb` (`:176-178`) → nunca acierta | `const` con `v2.7.4` cableado (`:70,:72`) | nada |
| C `main` (1.011 ln, csproj **2.7.5**) | `exe`/`url`/`size_mb` (`:222-224`) → **sigue sin acertar** | derivado de `ObtenerVersionEnsamblado()` (`:82-84`) | delegación a `TokenSesionChat` (`:197-206`), el trabajo `stage1` |
| D `DevAntigravityIDEIA` (1.018 ln, csproj **2.7.6**) | **`assets[]` con `tag_name`/`name`/`version`** (`:264-294`) | derivado del ensamblado | costura de prueba (`:124-126`), `version_instalada` en `/api/info` (`:881`), `--webnodo-selftest` |

Consecuencia directa para U1: `WebNodoService.cs` es un **divergente bidireccional**. D trae la corrección de
W-01/DT-11 y la autoprueba que la verifica; C trae la credencial de sesión de `stage1`. Resolver este fichero
«a favor del tronco» **reintroduciría el defecto de esquema** que describe esta sección, así que es el único de
la lista de §1.2 que exige fusión a tres manos y no elección.

### 1.8 `WebNodoService.cs` es un punto único de fallo funcional

> **Resuelto en U3.4 (2026-11-05), con dos correcciones de medida.** Eran **1.116 líneas**, no 896; las ocho
> responsabilidades están ahora en cinco ficheros (`WebNodoService.cs` raíz de ciclo de vida, `.PortalHttp.cs`,
> `.ProxyTcp.cs`, `.ProxyWebSocket.cs` y `AnuncioRelease.cs`) y el HTML del portal salió de la cadena. Las
> referencias `:NNN` de los párrafos siguientes apuntan al fichero **previo** al troceo y se conservan como
> evidencia de la lectura original. «Tres propietarios» resultó ser duplicidad de tipo entre caminos de arranque
> distintos, no tres instancias conviviendo (§U3.2 del registro).

896 líneas y ocho responsabilidades en un solo `IDisposable`: servidor `HttpListener` (`:293`, `:529`),
proxy TCP con reescritura de `Host` (`:412`, `:434`, regex `:479`/`:483`), proxy WebSocket (`:841`),
portal HTML embebido de ~105 líneas en una cadena (`:188`), extracción de assets, sondeo de release de
GitHub (`:98`, `:109`), límite por IP (`:163`, `:164`, `:827`) y un router de 197 líneas (`:605-801`).
Suma estáticas compartidas por el proceso entero (`ReleaseLocal:77`, `ReleaseActiva:78`, `_releaseLock:79`,
`_refresheoLanzado:80`) y **tres propietarios** del seudosingleton:
`App.xaml.cs:12` (`public static WebNodoService WebNodo { get; } = new WebNodoService()`),
`VisorLinux/Vistas/VentanaPrincipal.cs:23` (`private readonly WebNodoService _portal = new()`) y
`VisorLinux/Linux/ComprobacionLocal.cs:71` (`using (var portal = new WebNodoService())`).
DT-13 (miembros `internal …ParaPrueba`) **no aplica a esta copia**: esos miembros sólo existen en la
ramificación de `DevAntigravityIDEIA`, lo que confirma que el issue #48 describe un árbol distinto del que hay en disco.

### 1.9 Godot: referencias colgantes y singleton muerto

- `project.godot:65` registra el autoload `OptimizadorAvatares`; grep de `OptimizadorAvatares` en `.gd`/`.tscn`/`.godot`
  sólo devuelve coincidencias **dentro del propio fichero** → singleton huérfano que se instancia en cada arranque.
- `gdscrip/AnimacionesCompartidas.gd:13` exige `res://gltfimport/avatares/AVH1.gltf`, y en la zona de trabajo
  **no hay ni un `.glb`/`.gltf`** (`.gitignore:59,68`); sí existen en `main` (PR #63). La zona de trabajo tal cual
  **no puede reexportar el PCK**.
- La issue #1 sigue sin cumplir su criterio «el cliente puede introducir el puerto»: `Red.gd:43-50` parsea
  `--port=` y `:79`/`:115`/`:140` lo propagan, pero `resolver_url_ws(host, _port, …)` (`:153`) **ignora el
  argumento** y construye siempre `"ws://%s:%d" % [h, PUERTO_WS]` (`:161`), con `PUERTO_WS := 8911` en `:6`.
  El anfitrión tampoco lo acata (`:201`, `:208`). En C# los literales gemelos están en
  `DescubrimientoP2P.cs:22-23` (8911/8912), `WebNodoService.cs:58` (8920) y `ChatRelayServer.cs:40,62` (8920-8929).

**Corregido al medir (U4, 2026-11-05).** Dos de los tres puntos arriba no se reprodujeron:

- `OptimizadorAvatares` **no está huérfano**: se instancia y su `_ready()` fija `root.mesh_lod_threshold = 4.0` (se ve en
  el arranque headless), con `_process()` recorriendo cada frame un registro siempre vacío. Lo que tiene 0 llamadas
  externas es su API de texturas/VRAM/LOD. Detalle en §U4.5 del registro.
- La zona **sí tiene assets**: 16 `.glb`, 9 `.gltf` y `MTBGT/WoldVirtualP2P3D/gltfimport/avatares` presentes, incluido
  `AVH1.gltf`. El «no puede reexportar el PCK» por falta de assets era falso; lo que lo impide es RU5 (falta el árbol
  externo `E:/areadetrabajo/wvp270/godot` y la autorización), no el `.gitignore`.
- El tercer punto **sí era cierto y ya está corregido**: el puerto se acata ahora en las dos ramas de
  `resolver_url_ws` (con `lleva_puerto_explicito`) y los literales gemelos de C# viven en `ConfigRed`.

### 1.10 Pruebas y CI: lo que se afirma no es ejecutable desde la zona

- **El proyecto xUnit sí existe, pero no en la zona ni en `main`.** En disco, `VSC#/Tests/` sólo tiene artefactos
  `obj/Debug/net8.0-windows/Visor3DTests.*`: ningún `.csproj` ni un `[Fact]`. Las cuatro rutas reales
  (`Visor3DTests.csproj`, `UpdateCheckerTests.cs`, `PasswordHasherTests.cs`, `WebNodoReleaseTests.cs`) están
  **sólo en el árbol de `origin/DevAntigravityIDEIA`**, y `git ls-tree origin/main` no lista ese directorio en
  absoluto. La aritmética del «34/34 verde» de #48 cuadra con esa copia: 12 `[Fact]` + 6 `[Theory]` con 22
  `[InlineData]` = **34 casos**. DT-15 por tanto **no es «no hay tests» sino «los tests existen en una rama que
  nadie compila»**; se recuperan en U1.4 y U6 queda reducido a hacerlos correr en CI.
- `STM_HRTS/pytest.ini:2` y `STM_HRTS/pyproject.toml:33-34` dicen `testpaths = tests`, pero **`STM_HRTS/tests/`
  no existe**: las pruebas reales están en `src/tests/` (12 ficheros). Sin `conftest.py`. DT-10 se confirma.
- El workflow vive en `STM_HRTS/.github/workflows/ci.yml` → GitHub nunca lo descubre (DT-01 se confirma).
  **Ojo:** sacarlo a la raíz del repo es una acción **fuera de `src/`** (ver §5).
- Los selftests son de proceso completo y se invocan desde el exe publicado (`STM_LBR/diagnostico.sh:179`,
  `woldvirtual-wine.sh:28,77`), no desde `dotnet test`. Su superficie **depende de la copia**: 4 banderas en A,
  5 en C (añade `--update-selftest`) y 6 en D (añade además `--webnodo-selftest`).

### 1.11 RFPRMN: seis defectos medidos en la herramienta (`CONTRRF/STM_RFC/`)

Flujo real: `TLLDCD/src` → (`enviar`) → `RFC/src` → (`actualizar`) → `PRY/actualizacion_<id>` → `RFC` vacío.

1. **El identificador del instantáneo no deriva del contenido**: `stm_gestion.py:381`
   `numero = uuid.uuid4().hex[:8]`. `actualizacion_aeef1149`, `91883d55` y `2f040968` no son hash: dos envíos
   del mismo árbol producen ids distintos, así que el nombre no acredita nada.
2. **`actualizar` purga los demás instantáneos** (`stm_gestion.py:396-402`): es la razón de que en disco sólo
   quede `2f040968` y `91883d55`/`aeef1149` vivan sólo en Git. Destruye el punto de retorno local en cada ciclo.
3. **La elección del instantáneo vigente es por `mtime`** (`stm_gestion.py:115` `_ultima_actualizacion_pry`),
   no por el registro: un `git checkout` o una copia manual cambian silenciosamente qué árbol devuelve `refactorizar`.
4. **La verificación del envío es por número de ficheros** (`:384-385`), sin manifest ni hash por ruta.
5. **Rutas absolutas de otro equipo cableadas**: `stm_base.py:274-275` apunta a
   `C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\…` (inexistente aquí); funciona sólo por el *fallback* de `:277-278`.
6. **Dos `envios.json`**: el vivo (`TLLDCD/STM_RFC/envios.json`, 4 entradas, última 2026-11-05T16:36:10) y uno
   rancio dentro de la propia herramienta (`STM_RFC/STM_RFPRMN/stm_registro_json/STM_RFC/envios.json`, que aún
   cita `52bf0d80`). Mi memoria de sesión apuntaba a `52bf0d80` como vigente: **queda corregida**.

### 1.12 Documentación que el propio flujo destruye

`README.md` enlaza su hoja de ruta y su deuda a `VersionDe_sesion/Sistema_Principal/PRY/**actualizacion_91883d55**/src/STM_DOC/...`
(`:689`, `:728`, `:748`, `:765`, `:778`). Ese instantáneo **ya no existe en disco** (purgado el 2026-11-05) y no es
el que rastrea `main` (`aeef1149`). Lo mismo hace el análisis externo recién fusionado: `docs/STACK.md` y
`docs/IMPLEMENTATION_PLAN.md` fijan `SRC = …/PRY/actualizacion_aeef1149/src`, una ruta que el próximo
`actualizar` borrará. Sus 82 hallazgos con número de línea caducan por diseño.

Raíz de `main` contaminada por los merges: `answer.md`, `applecat88.md`, `read.md`, `readme.md`, `reads.md`
(PR #51, #52, #53, #55, #56) y el commit ajeno `2fbdd39 "Update fmt.Println message from 'Hello' to 'Goodbye'`
(traído por PR #47 desde `CesarChaMal/development`, código Go que no existe en el proyecto).

### 1.13 Ledger de las PRs cerradas: la unificación **sí** ocurrió, pero sólo dentro de `main`

Inventario de las fusiones recientes (todas con `merged_at`, ninguna cerrada sin fusionar):

| PR | Base ← Head | Fusión (UTC) | Qué aportó |
|---|---|---|---|
| #44 | `main` ← `DevAntigravityIDEIA` | 2026-10-31T23:21 | «addev» → `e8295fc`, el punto de bifurcación actual |
| #46 | `main` ← `DevAntigravityIDEIA` | 2026-11-01T01:27 | workflow de CI, suites H1/H2/H3, scripts de actualización, comprobaciones de red y OTA |
| #47 | `main` ← `development` (fork `CesarChaMal`) | 2026-11-02T22:20 | `docs/STACK.md`, `docs/IMPLEMENTATION_PLAN.md` (+EN), `AGENTS.md`, `CLAUDE.md`, `.editorconfig`, `.env.example`, `.vscode` y el commit Go espurio |
| #50, #53 | `main` ← `applecat88-patch-1` | 2026-11-04T15:58 / 17:38 | basura de prueba en la raíz |
| #51, #52 | `applecat88-patch-1` ← `…-patch-2`/`-3` | 2026-11-04 | `readme.md`, `reads.md` — **fusionadas dentro de una rama de parche, no en `main`** |
| #55, #56 | `main` ← `applecat88-patch-4`/`-4-1` | 2026-11-04T19:54 | «A la espera de su respuesta» |
| **#63** | `main` ← `arte/s8-activos-faltantes` | 2026-11-05T15:41 | **134 ficheros**: los 16 avatares `.glb` que faltaban (AVmj1–7 en `AVHM`, avhm1–9 en `AVMJ`), generados como humanoides procedurales autocontenidos con el esqueleto Mixamo de 65 huesos de AVH1 y los clips parado/caminar/correr/strafe, más `gltfimport/**` |
| **#62** | `main` ← `stage1/s6-peer-registration-auth` | 2026-11-05T15:42 | registro de pares autenticado en `POST /peer` |
| **#61** | `main` ← `stage1/s1-peer-identity-v2` | 2026-11-05T15:42 | identidad de pares con prueba de posesión (`Identidad.gd`, `Red.gd`, `ChunkManager.gd`, `Construccion.gd`) |
| **#60** | `main` ← `stage1/s4-any-peer-validation-h6m21` | 2026-11-05T15:43 | `ValidacionRed.gd` y validación de entradas `any_peer` |
| **#59** | `main` ← `stage1/s3-client-ip-h2` | 2026-11-05T15:43 | IP de cliente fiable + `RateLimiter` LRU |
| **#58** | `main` ← `stage1/s2-chat-relay-auth-g1` | 2026-11-05T15:44 | `TokenSesionChat.cs`, autenticación del relé de chat |
| **#57** | `main` ← `stage1/s5-ip-privacy-g4` | 2026-11-05T15:44 | privacidad de la IP en roster y sesión |

**Comprobación de integridad del resultado** (las siete últimas entraron en 3 minutos sobre las mismas
rutas, que es donde un merge en paralelo suele destruir trabajo): para cada PR, todas las líneas que añadieron
están presentes en la punta de `main` — `#58` 13/13, `#59` 84/84, `#60` 67/67, `#61` 16/16 y 220/220,
`#57`/`#62`/`#63` sin desajustes. El hecho de que los blobs de `main` difieran del `head` de cada PR es
**la unión correcta**, no una pérdida: `main:WebNodoService.cs` (1.011 ln) = el trabajo de `#58` sobre el de
`#59`; `main:Construccion.gd` (1.844 ln) = base + `#60` + `#61`.

**Lectura correcta del estado:** la «unificación reciente» es real y está bien hecha **en `main`**. Lo que no
existe es el puente hacia la zona de trabajo: `actualizar` generó el instantáneo `2f040968` a las 15:33:49Z
(y 16:33 local, UTC+1), **ocho minutos antes** de que se fusionara la primera PR `stage1` (15:41:56Z). Por eso
`src/` no contiene nada de eso, y por eso la fase U1 consiste en cruzar el tronco a la zona, no en resolver
un conflicto entre iguales.

---

## 2. Reglas de trabajo de este plan (numeradas)

| Regla | Contenido |
|---|---|
| **RU1** | Ninguna fase toca `E:` fuera de `E:\WoldVirtualP2P3D`. Lo que exija salir se declara en §5 y espera decisión. |
| **RU2** | **No se commitean los 463 borrados** ni se purga ningún instantáneo: son el efecto normal del flujo RFPRMN (`STM_DOC/REGLAS_DE_ACTUALIZACION.md:12-16`). Primero U0. |
| **RU3** | Prohibido `--force`, reescribir ramas ajenas o borrar `respaldo/*` (contienen el trabajo pre-limpieza del 2026-10-22). |
| **RU4** | El árbol canónico es `src/`. Cualquier otra copia es entrada de fusión, no destino. |
| **RU5** | Orden de versión obligatorio: Godot → PCK → `.csproj` → `publish` → `release` → OTA (`REGLAS_DE_ACTUALIZACION.md` §1) y su checklist §7. |
| **RU6** | Ningún paso se da por hecho sin evidencia: cada fase cierra con el mando ejecutado y su resultado (prohibido afirmar sin medida). |
| **RU7** | El agente no publica releases, no fusiona a `main` y no cierra issues sin confirmación expresa del dueño (R16). |
| **RU8** | Los 29 ficheros divergentes se resuelven **uno a uno con decisión escrita**; no se acepta «gana la copia más nueva». Los que tienen aportación en ambos lados (`WebNodoService.cs`, §1.7) **se fusionan**, no se eligen. |

---

## 3. Objetivos: qué cuenta como «versión nueva y unificada»

| # | Criterio de cierre | Cómo se mide |
|---|---|---|
| U-C1 | Existe **un** árbol (`src/`) que contiene el 100 % de las 436 rutas comunes + las 223 de C + las 68 de D, y `git ls-tree` de ese árbol no pierde ninguna | `comm` de listas de rutas, como en §1.1 |
| U-C2 | Peso de `src/` **≤ 300 MiB** con el PCK y los dos zips dentro | `du -sm src/` |
| U-C3 | Un único punto para el número de versión; ningún literal `2.7.x` en código | `grep -nE "2\.7\.[0-9]" src/VSC#` → sólo el fichero de versión y los tests |
| U-C4 | Windows y Linux compilan contra el **mismo núcleo**: 0 clases duplicadas con el mismo nombre y namespace | lista de solapes de símbolos vacía |
| U-C5 | `release.json` se parsea por su esquema real y el portal anuncia la release correcta sin literales cableados | selftest del portal en verde + test unitario del parseo |
| U-C6 | `dotnet test` ejecuta la suite xUnit (34 casos restaurados de D) y **los seis selftests** corren en CI | trabajo de CI con los seis resultados |
| U-C7 | `pytest` funciona desde la raíz de `src/` sin tocar el CWD | `pytest -q` |
| U-C8 | El puerto LAN configurable se cumple también en Godot (issue #1) | test que pase un puerto distinto de 8911 y lo vea en la URL |

---

## 4. Fases

### U0 — Blindaje del repositorio *(sin tocar código; prerrequisito absoluto)*

1. Congelar el estado actual con referencias locales de seguridad, sin push:
   `git tag -m "rescate U0" rescate/20261105/<n>` sobre `HEAD`, `origin/main` y `origin/DevAntigravityIDEIA`.
2. Sanear el índice huérfano: inspeccionar los 4 conflictos (`UU`/`DU`/`MD`) con `git ls-files -u`,
   decidir **por fichero** y resolver con `git checkout --conflict=merge` + `git add` de la versión correcta.
   Prohibido `git reset --hard` (destruiría el trabajo de otras sesiones concurrentes).
3. Decidir el destino de los 463 borrados antes de cualquier commit: **se mantienen sin commitear** (RU2),
   y se documenta en el commit de U1 que el árbol activo lo gobierna RFPRMN.
4. Respaldo del árbol A **sin crear carpetas nuevas dentro del sistema de control** (no se inventan rutas en
   `Sistema_Principal/`): las referencias de rescate del punto 1 ya preservan D y C en Git, y el inventario de
   rutas+hashes de los 6.637 ficheros en disco se escribe como `STM_DOC/inventario_zona_20261105.tsv` generado
   con `git hash-object --stdin-paths`. Ese fichero es la prueba de con qué se partió.
5. Fijar el registro RFPRMN: copiar `TLLDCD/STM_RFC/envios.json` a `STM_DOC/registro_envios_20261105.json` como evidencia.

**Salida:** `git status --short` sin entradas `UU`/`DU`/`MD`; referencias de rescate existentes; cero push.

### U1 — Convergencia a un árbol canónico *(la fase que da la «versión nueva»)*

Orden recomendado, con evidencia en `STM_DOC/registro_refactor.md` (ya existe, ampliarlo):

> **Sentido de la fusión (corregido tras el ledger de §1.13):** el tronco es **C** (`origin/main`, 47 commits
> desde `e8295fc`, con el trabajo `stage1` y el arte S8 ya integrados y verificados). D porta **5 commits de
> utillaje**. Se parte de C y se le añaden las piezas de D, no al revés. La nota anterior de este documento
> proponía D como punto de partida: queda sustituida por esta.
> **Matiz medido (§1.6):** C es el tronco *de fuente*, pero el binario publicado vigente (v2.7.6, *Latest*) se
> compiló desde la línea de D. Las piezas de D no son ornamentales: son la única fuente del producto que hoy se
> descarga, y en `WebNodoService.cs` contienen la corrección que `main` aún no tiene.

1. **Sincronizar la rama de trabajo con el tronco.** La rama checkout (`DevQoderIA` @ `294a72a`) está 47 commits
   por detrás de `main`. Antes de mover un solo fichero: traer `origin/main` a la rama de trabajo por fusión
   normal (sin `--force`, respetando RU3) y dejar constancia de que los 463 borrados del flujo RFPRMN **no se
   commitean** en ese merge (RU2).
2. **Punto de partida del árbol canónico = C** (`origin/main` → `PRY/actualizacion_aeef1149/src`), materializado
   en `src/` **sin checkout en masa**: `git checkout <ref> -- <ruta>` sólo para las **192 rutas que faltan en el
   disco**. Las 29 divergentes se dejan intactas aquí y se resuelven una a una en el paso 5, no en bloque.
3. **Incorporar de C los 223 ficheros privativos**, en dos
   lotes: (a) seguridad `stage1` (`ValidacionRed.gd`, `TokenSesionChat.cs`, 7 tests `test_stage1_*` y
   `test_g4_privacidad_ip.py`) y (b) arte (`gltfimport/**` 107, `AreaDeTrabajo/**` 32, `SLCAV/**` 17,
   25 `.glb`/`.gltf`). El lote (b) es el que repara la referencia colgante de `AnimacionesCompartidas.gd:13`.
   **Trampa medida:** esos recursos son invisibles para Git. `git check-ignore -v` confirma que
   `…/AVHM/AVmj1.glb` casa con `.gitignore:59` (`*.glb`) y aun así está en el árbol de `main`: se añadió a la
   fuerza. En la zona de trabajo hay **0 `.glb`/`.gltf` en disco**; lo que trae `main` son 16 `.glb`, 9 `.gltf`,
   9 `.bin` y 66 `.import`. Al copiarlos a `src/` hace falta `git add -f` explícito o una regla de negación
   (`!**/gltfimport/**`, `!**/AreaDeTrabajo/**`) en `.gitignore`; sin eso, RFPRMN los moverá por conteo de
   ficheros pero el commit los olvidará y el árbol volverá a quedar incompleto.
4. **Superponer la capa de utillaje de D (68 rutas que NO están en el disco).** Medido con `[ -f ]` ruta a ruta:
   las 68 privativas de `origin/DevAntigravityIDEIA` dan **0 presencia en `src/`** — su única copia viva es el
   árbol de esa rama, así que recuperarlas es un `git checkout DevAntigravityIDEIA -- <ruta>`, no una copia de
   disco. Tres bloques: (a) utillaje Godot, `STM_HRTS/utils/STM_UTILS/` (43: 39 arneses `probar_*.gd`,
   `retarget_animaciones.py`, `purgar_repositorio.ps1`), `add_utils/` (10), `json/` (7), `.vscode/` (2) y
   `STM_HRTS/STM_PY/__main__.py`; (b) autoprueba del portal `VSC#/Services/WebNodoSelfTest.cs`;
   (c) **la única copia existente de `VSC#/Tests/`** — 4 rutas (`Visor3DTests.csproj`, `UpdateCheckerTests.cs`,
   `PasswordHasherTests.cs`, `WebNodoReleaseTests.cs`): `git ls-tree origin/main` no lista ese directorio y en el
   disco de la zona sólo quedan `bin/` y `obj/` sin fuentes. El bloque (c) es el que convierte U5.3
   («recrear los tests») en «restaurar los tests que ya existían».
5. **Resolver los 29 divergentes** con la tabla de §1.2, anotando en cada uno qué se toma de C, qué de D y qué de A.
   Prioridad por riesgo: `WebNodoService.cs` → `MainWindow.xaml.cs` y `VentanaPrincipal.{Chat,Red}.cs` →
   `App.xaml.cs` → `Red.gd`/`ChunkManager.gd` → los `.csproj` → `rutas.py`. Dos de ellos **no admiten elegir bando**:
   `WebNodoService.cs` es bidireccional (C aporta la delegación a `TokenSesionChat`; D aporta el parseo correcto de
   `release.json`, `version_instalada` y la costura de prueba — tabla de §1.7), y en `App.xaml.cs` la unión es
   literal: C ya despacha cinco de las seis banderas `--*-selftest` y le falta el bloque `--webnodo-selftest`
   (`:46-48` de D), la única pieza de D que hay que re-inyectar a mano después del paso 4.
6. **Reconciliar `README_DESARROLLO.md`** (divergente y ausente en `src/`): unificar en `src/STM_DOC/README_DESARROLLO.md`
   y dejar un enlace en la raíz de `src/`, para que el fichero sobreviva a la purga de instantáneos.
7. **Regenerar el inventario** con el mismo método de §1.1 y exigir 0 rutas perdidas (U-C1).

**Decisión de layout (ejecutada en U1.5, registrar en el README de U1.6):** el utillaje canónico es el
**empaquetado de D** (`STM_HRTS/utils/STM_UTILS/` para los arneses y `STM_HRTS/utils/add_utils/` para el paquete
con `pyproject.toml`, `pytest.ini` y la consola). No es una preferencia estética: en D la raíz de `STM_HRTS/` es
`.github, STM_PY, opencode, utils` **sin** `rutas.py`/`herramientas.py`/`pytest.ini` planos, las copias
empaquetadas son superconjunto de las planas y `tests/test_hrts_rutas.py`, `tests/test_h1_contencion.py`,
`tests/test_regresion.py`, `STM_CH/rutas.py` y `SBSTM/accesores.py` ya sólo importan la ruta empaquetada. Las 53
copias planas que la superposición dejaba duplicadas se **aislan** (no se borran) con manifiesto, y el catálogo
de herramientas vuelve a ser único.

**Salida:** un árbol, compilable, con las tres funciones: seguridad `stage1` y arte (C), utillaje y autopruebas
del portal (D), y el historial de `main` intacto bajo la rama de trabajo. Conteo medido de la unión con
`git ls-tree -r`: 436 rutas comunes C∩D + 223 privativas de C + 68 privativas de D = **727**, y **1** más que
sólo existe en la base (`pytest.ini` en la raíz de `src/`, que la regla de configuración única deja ausente a
propósito) → **728 rutas** para U-C1.

### U2 — Purga de contaminación y peso

| Acción | Objetivo | Ganancia esperada | **Ejecutado (medida)** |
|---|---|---|---|
| Sacar `STM_HRTS/opencode/` de la zona y dejar sólo un lanzador externo | sin uso real en el proyecto | −881 MiB, −5.259 ficheros | **No ejecutado** — está cableado a `STM_HRTS/utils/STM_UTILS/lanzar_opencode.bat:5`, sus configs sí están rastreadas en D y su restauración exige red (`npm ci`). En espera del dueño (§U2.3 del registro) |
| Borrar `VSC#/bin/` y `VSC#/obj/` (salida reproducible) | el `.exe` publicado no va a Git | −350 MiB | **−901 MiB** (706 + 195; el plan subestimaba `bin/` porque contaba sólo el publish) |
| Borrar `STM_CH/pycache/` (855 `.pyc`) y desactivar `sys.pycache_prefix` dentro de la zona | bytecode regenerable | −23 MiB | **−23 MiB / 861 `.pyc`**. La segunda mitad no hace falta: es caché redirigida por `WOLD_RUNTIME_DIR`, no `sys.pycache_prefix` del árbol |
| Excluir de la zona `VSC#/bin/publish_v2.7.6/*` (exe de 365.088.633 B) | RU de no commitear ejecutables | −348 MiB | **dentro del bloque `bin/`**, y probado sin pérdida: el sha-256 local `26fb446e…3b150f` es idéntico al `digest` del asset publicado (§U2.2) |
| Borrar `VSC#/VisorLinux/{bin,obj}` y `VSC#/Tests/{bin,obj}` | idem | — | **−2 MiB / 10 ficheros** (el plan no los listaba) |
| Borrar el log de efectos `tests/test_voces/voz_audit.log` | scratch de la suite | — | **−1 MiB** |
| Depurar `.gitignore`: quitar la regla duplicada de `cierre_sesion_blockchain.json` y acotar `**/bin/`/`**/obj/` (líneas 17-18) para que no se coman carpetas fuente llamadas `bin` | higiene de rastreo | — | **Ambas premisas son falsas.** `sort` + `uniq -d` sobre las reglas no comentadas devuelve 0 duplicados y la cadena `cierre_sesion_blockchain.json` no existe en `.gitignore` (sólo `**/blockchain_ledger.json`:229). Y `git ls-tree -r` en HEAD, C y D da **0 rutas** bajo `bin/` u `obj/`, ni hay ninguna carpeta fuente con ese nombre en el disco: acotar las reglas sería un cambio sin efecto. Sí aparece un hueco real no previsto: `*.orig` no está ignorado (§U2.5) |

**Salida (reescrita con la medida):** el objetivo `du -sm src/ ≤ 300 MiB` es **inalcanzable** respetando la lista
de no-tocar. Tras purgar lo regenerable, `du -sm src` = **1420 MiB** (desde 2342); su composición es 881 MiB de
`opencode` (§U2.3), 269 MiB de `wvp3d.pck` + `godot_exe.zip` + `godot_linux.zip` con SHA-256 en el manifiesto H0,
248 MiB de texturas `gltfimport/{avatares,terrenoblok}` (ignoradas por diseño, únicas fuentes para reexportar el
PCK) y ~13 MiB de código + documentación. **U-C2 pasa a ser: 0 MiB de contaminación regenerable dentro de `src`**,
con las tres compilaciones y las dos suites volviendo a pasar desde el árbol limpio, y techo estructural de
**537 MiB** si el dueño autoriza soltar `opencode`.

### U3 — Unificación C#: crear el núcleo común

1. Añadir `VSC#/Nucleo/Nucleo.csproj` (`net8.0`, sin UI) y **migrar** los 17 ficheros hoy enlazados más
   `InstanciaUnica`, `RegistroPcUnico`, `ReinicioCuenta` y el OTA (`ReleaseInfo`/`UpdateChecker`/`UpdateDownloader`/`UpdateApplier`)
   a interfaces de plataforma (`IPlataforma`, `IEjecutableExterno`). `VisorLinux/Linux/*` pasa a ser la
   implementación, no un duplicado. `Visor3D.csproj` y `VisorLinux.csproj` referencian `Nucleo` con `ProjectReference`.
2. Añadir el `.sln` que falta y una sola lista de proyectos.
3. **Decisión del dueño (§5):** SMTPLC entra en `Nucleo` (Linux pasa a validar registro) o se declara
   explícitamente exclusivo de Windows. Hoy no está en la lista de enlaces de `VisorLinux.csproj`.
4. Trocear `WebNodoService.cs` (896 ln) en cuatro piezas testeables: `PortalHttp` (router `:605-801`),
   `ProxyTcp` (`:412-483`), `ProxyWebSocket` (`:841`) y `AnuncioRelease` (parseo + refresco, DT-13 y DT-14),
   con el HTML del portal fuera de la cadena (`:188`) como recurso. Eliminar las estáticas mutables y los
   tres propietarios (§1.8): un único dueño con inyección explícita.
5. Reducir `MainWindow.xaml.cs` (3.389 ln, 165 miembros) llevando su lógica de negocio a `Nucleo` y dejando
   la vista como adaptador WPF, espejo del patrón ya usado en Linux con `VentanaPrincipal.*`.

**Salida:** ~~los 62 métodos solapados desaparecen~~ (la cifra no se reprodujo al medir) y el mismo código de
red/chat/OTA compila para ambos objetivos — esto último **sí cumplido**.

**Ejecutado (medida, 2026-11-05):** ver §U3 de `registro_unificacion_20261105.md`.

| Paso | Estado | Medida |
|---|---|---|
| 1 · `Nucleo.csproj` + migrar los 17 enlazados | **hecho**, sin interfaces de plataforma | 25 `.cs` en el núcleo; 17 `<Compile Include="../">` eliminados por 1 `ProjectReference`; `<Compile Remove="Nucleo\**">` en el WPF para no compilar dos veces. `IPlataforma`/`IEjecutableExterno` **no** se crearon: la única dependencia real de plataforma era el sello de cuenta única, y se resolvió con un parámetro (`PerfilUsuario.TieneIdentidad(bool)`, 5 call sites). `InstanciaUnica`, `RegistroPcUnico`, `ReinicioCuenta` y `UpdateApplier` se quedan por plataforma. |
| 2 · `.sln` único | **hecho** | `VSC#/Visor3D.sln` clásico (no `slnx`, que el SDK preview 11 genera por defecto y CI estable no lee) con Nucleo, Visor3D, VisorLinux, Tests |
| 3 · SMTPLC | **en espera del dueño (§5)** | 8 ficheros y 1.918 ln en `VSC#/Seguridad/SMTPLC/`, con 6 `DllImport` de `iphlpapi`; sólo lo consumen `FormularioUsuarioWindow.xaml.cs` y `StartupSelfTest.cs` (WPF). Declararlo exclusivo de Windows es coherente con la medida; llevarlo a Linux es un port del nativo, no un move |
| 4 · Trocear `WebNodoService.cs` | **hecho** | 5 ficheros (234 + 374 + 203 + 61 + 246 ln) con `AnuncioRelease.cs` como dueño del estado mutable de anuncio; las **105 ln** de HTML del portal fuera de la cadena, servidas desde `webnodo/public/index.html` |
| 4 · «eliminar las estáticas mutables y los tres propietarios» | **matizado** | Los 3 propietarios están en 3 caminos de arranque distintos (el `--comprobar` de Linux retorna antes de crear la ventana), así que nunca convivían. Las estáticas que quedan son inmutables por diseño (token de sesión, marcador de proxy, cubetas del limitador); el estado mutable del anuncio quedó en un único dueño nombrado |
| 5 · Reducir `MainWindow.xaml.cs` | **no ejecutado** | 3.428 ln medidas (el plan citaba 3.389). Es una fase en sí misma; se mantiene como trabajo abierto de U3 |

### U4 — Unificación Godot y recursos 3D

1. Retirar o conectar el autoload `OptimizadorAvatares` (`project.godot:65`), hoy sin uso.
2. Consolidar `MTBGT/…/gltfimport/` y `AreaDeTrabajo/` dentro de `src/` (aprovecha el lote b de U1) y anclar
   la ruta que espera `AnimacionesCompartidas.gd:13`; verificar que el árbol Godot abre sin rutas externas.
3. Centralizar dirección y puerto: un único `ConfigRed` leído por `Red.gd` y por el C#. Corregir `Red.gd:153`/`:161`
   para respetar `port` (U-C8, issue #1) y sustituir los literales de `WebNodoService.cs:58`,
   `DescubrimientoP2P.cs:22-23` y `ChatRelayServer.cs:40,62` por esa fuente.
4. **El PCK de la zona está desfasado respecto al código unificado.** Medido: `VSC#/wvp3d.pck` en disco pesa
   114.591.724 B con SHA-256 `ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14` — el de la 2.7.4.
   Cualquier cambio de U4 en `gdscrip/` viaja al binario **sólo tras reexportar el PCK** (regla RU5). Anotar el
   digest nuevo y verificar en el bytecode embebido que el arreglo viaja, como se hizo en la 2.7.3.

**Salida:** lista de puertos/IP en un solo sitio; el visor arranca con un puerto no-8911 probado.

**Ejecutado (medida, 2026-11-05):** ver §U4 de `registro_unificacion_20261105.md`.

| Paso | Estado | Medida |
|---|---|---|
| 1 · Retirar o conectar el autoload `OptimizadorAvatares`, «hoy sin uso» | **no ejecutado — premisa falsa** | Sí está en uso: `project.godot:65` con `*`, `_ready()` fija `root.mesh_lod_threshold = 4.0` (impreso en el arranque headless) y `_process()` corre cada frame sobre un registro vacío. Lo que tiene **0 llamadas externas** es la API de texturas/VRAM/LOD (`optimizar_nodo`, `aplicar_configuracion_global`, `limpiar_cache`, `avatar_optimizado`). Tocar esto cambia el binario → decisión del dueño (§5) + RU5. |
| 2 · Consolidar `gltfimport/` y `AreaDeTrabajo/` en `src/` e anclar `AnimacionesCompartidas.gd:13` | **no ejecutado** | La zona ya abre sin esas rutas (12 pruebas headless exit 0), pero el ancla sigue apuntando fuera. Queda para U6 con el inventario de assets. |
| 3 · «un único `ConfigRed` leído por `Red.gd` y por el C#» | **hecho, con una variante documentada** | Dos tablas y un gate que las obliga a coincidir: `Nucleo/RedP2P/ConfigRed.cs` (112 ln, 8 constantes, 5 métodos) + 5 constantes en `Red.gd` + `tests/test_config_red.py` (186 ln, 6 pruebas, 12 consumidores sin literales). Un JSON en runtime se descartó por medido: el C# no lee `res://` y un fichero ausente o un PCK sin reexport serían un modo de fallo nuevo. |
| 3 · «corregir `Red.gd:153`/`:161` para respetar `port`» | **matizado** | El número ya viajaba en `parsear_url_host_puerto`; lo roto era `resolver_url_ws` (tiraba el puerto explícito) y la ausencia de la regla de reescritura en los visores C#. Defectos concretos corregidos: `ws://ip:puerto` → host `"ws"`, `https://host` en el roster → `wss://https://host`, off-by-one de `woldvirtual://` y la regla 3030-3040/7890/80/443 copiada tres veces. |
| 4 · Reexportar el PCK | **en espera del dueño (RU5)** | `VSC#/wvp3d.pck` en disco sigue siendo el de la 2.7.4: 114.591.724 B, SHA-256 `ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14`. Necesita `E:/areadetrabajo/wvp270/godot`. Sin eso, nada de este paso viaja al binario publicado. |
| — · Parser de destino | **hecho (fuera del plan)** | Tres copias → una: WPF (`MainWindow.xaml.cs:1163`) y Avalonia (`LanzadorMundo.cs:225`) delegan en `ConfigRed.ProbarDestino`. |
| — · Prueba de red | **hecha (fuera del plan)** | `STM_HRTS/utils/STM_UTILS/probar_red_puerto.gd` (175 ln): 41 comprobaciones / 0 fallos. Banderas de `Red.gd` extraídas a `analizar_args()` pura para poder probarlas. |

### U5 — Versión única, pruebas y CI

1. **Un número:** `src/VERSION.json` (`version`, `motor`, `pck_sha256`, `fecha`) generado por un script en
   `STM_HRTS/utils/`; los `.csproj` lo consumen vía `Directory.Build.props`; `RutasLinux.Version`,
   `ExeNameFallback` y `ExeUrlFallback` se derivan en tiempo de compilación. Probar `GetEntryAssembly()`
   en todos los contextos (DT-08).
2. **Arreglar el parseo de `release.json` (§1.7):** no hay que escribirlo — la versión corregida ya existe en D
   (`WebNodoService.cs:264-294`, esquema `tag_name`/`name`/`version`/`assets[]` más costura de prueba `:124-126`).
   El trabajo es que sobreviva a la fusión del divergente bidireccional de U1.5 y **eliminar el `catch { }`
   silencioso** (en A `:183`, en C `:229`) con al menos un aviso al log.
3. **Restaurar y ampliar `VSC#/Tests`:** el `.csproj` y los tres ficheros de prueba existen **sólo en D**
   (U1.4c, 34 casos) y nunca llegaron a `main`; a esa base hay que añadir xUnit para Nucleo, `EstadoGlobal`,
   `PerfilUsuario`, `ReinicioCuenta`, `LocationAccountLedger` (HMAC/corrupción/merge), `VmDetector`/`VpnDetector` (F1).
4. **Selftests dentro del runner:** convertir las seis banderas `--*-selftest` en pruebas de CI que lancen el exe con
   `APPDATA`/`LOCALAPPDATA`/`WOLD_RUNTIME_DIR` temporales (DT-15), y restaurar las dos banderas que faltan en A:
   `--update-selftest` (existe en C **y** en D) y `--webnodo-selftest` (sólo en D, con su `WebNodoSelfTest.cs`).
5. **`pytest` arreglado:** `pytest.ini`/`pyproject.toml` junto a `src/tests/` con `testpaths = tests` y `conftest.py`
   que fije la raíz (DT-10).
6. **CI real:** un workflow en la **raíz del repo** que ejecute `dotnet test`, los selftests y `pytest`
   (esto exige salir de `src/`; véase §5 y DT-01).

**Salida:** U-C3, U-C5, U-C6, U-C7.

**Ejecutado (medida, 2026-11-05):** ver §U5 de `registro_unificacion_20261105.md`.

| Paso del plan | Estado | Medida |
|---|---|---|
| 1 · Un número en `src/VERSION.json` | **hecho, con otro mecanismo** | No lo genera un script: lo lee MSBuild. `Directory.Build.props` extrae `$(WoldVersion)`/`$(WoldMotor)` con property functions y `Directory.Build.targets` materializa `WoldInfoVersion.g.cs` en `obj/`. Diez literales en cinco ficheros sustituidos. El plan no esperaba la contradicción real: D llevaba `2.7.6` en el csproj y `2.7.5` en `RutasLinux` en el mismo árbol. |
| 2 · Parseo de `release.json` + fin del `catch { }` | **hecho** | Adoptado el parser de D en `AnuncioRelease.cs`; el fallo silencioso (DT-13) ahora deja línea en el log y la prueba `Sin_release_cae_al_nombre_del_ensamblado` lo cubre. |
| 3 · xUnit sobre Nucleo/EstadoGlobal/PerfilUsuario/ReinicioCuenta/Ledger/detectores | **hecho en parte** | 34 → **67 casos** (4 ficheros nuevos). De los detectores se fijan los umbrales y los defaults de la política, **no** `Analyze()`/`AnalyzeLocal()`: leen WMI, registro y procesos, y el resultado depende del equipo. Seguir cubre el comportamiento de máquina → queda como prueba manual (`--startup-selftest`). |
| 4 · Seis selftests en el runner con entorno temporal | **hecho** | Exit 0 los seis sobre `DMWoldVirtualP2P3Dv2.7.7.exe` con `WOLD_RUNTIME_DIR` **y** `WOLD_LOG_DIR`. Hallazgo: las pruebas escribían avisos falsos de «cuenta reiniciada» en el log que el usuario copia para soporte (10 líneas contadas); `VisorLog` honra ahora `WOLD_LOG_DIR` y el log real quedó en 472 → 472 líneas. |
| 5 · `pytest.ini` junto a `src/tests/` | **no hecho — contradice una regla testada** | `test_regresion.py:99-115` exige `PYTEST_INI.parent == ADD_UTILS_DIR` y la ausencia del de la raíz, y `test_hrts_rutas.py:124` fija el `-c`; U1 ya contó esa ausencia como justificada. Ejecutado y deshecho: sin `-c` la suite pasa pero deja `.pytest_cache` en `src/`. Lo que se ha cogido del paso es `tests/conftest.py` (185 casos funcionan sin `-c`). DT-10 queda **medio cerrado**, con el motivo escrito. |
| 6 · CI en la raíz del repo | **en espera del dueño** | `ci.yml` reescrito dentro del taller (resuelve `src/` buscando `VERSION.json`, suite Python estricta, `dotnet test`, comprobación del nombre del `.exe`, seis banderas). Copiarlo a `.github/workflows/` está fuera de `src/` → #65 P0-2. |


### U6 — Deuda funcional por issue

| Issue | Trabajo en este plan | Fase |
|---|---|---|
| **#48** DT-12 | decidir renombrar el `.exe` tras el OTA (`UpdateApplier`) o documentar como aceptado | U5 |
| #48 DT-13 / DT-16 | extraer el parseo de release a tipo puro; eliminar el acoplamiento por estado estático | U3.4, U5.2 |
| #48 DT-14 | invalidar el anuncio de release al aplicar un OTA | U3.4 |
| #48 DT-01 | workflow a la raíz | U5.6 (**fuera de `src/`**) |
| #48 DT-04 | prueba física LAN con dos equipos (criterio de cierre de #1) | U4.3 + prueba externa |
| #48 DT-05 | versionar la suite headless de Godot (201/201) en `src/tests/godot/` | U5.5 |
| #48 DT-06 / DT-07 | corte de red/timeout en `--update-selftest`; validar SHA del PCK también en el primer arranque | U5.4, U5.1 |
| #48 DT-09 | IPv6 literal con corchetes en el parseo de `DescubrimientoP2P.cs` | U4.3 |
| #48 F7 | manifiesto de `avtrnCRS/` con SHA-256 y firma de código | U2, decisión §5 |
| **#26** SMTPLC | (1) `LocationAccountLedger` propagado por P2P con hash sin datos personales; (2) distinguir raíz/huésped en WSL2-Hyper-V (la corrección actual bajó `HypervisorPresent` a 0,25 — parche, no criterio); (3) sustituir `api.ipify.org`/`ipinfo.io` por reflexión STUN entre nodos + lista local de ASN de centro de datos; (4) sondeo ARP para equipos sin Wi-Fi | U3.3, U6 |
| **#15** Peso | ya reducido a la mitad en la 2.7.2 (PCK 114.591.724 B); falta la **Fase 3** del issue: `.exe` base + `patch.pck`, y publicar comprimido. La purga de U2 recorta 1,2 GiB de ruido de la zona pero no el binario | U2, decisión §5 |
| **#1** LAN | hacer efectivo el puerto configurable en Godot (§1.9) y documentar el firewall | U4.3 |
| **#16** LucIA | `LC_STM`/`SBSTM`/`STM_IA` siguen siendo un segundo producto sin integración (D14). Decidir: empaquetar como servicio con contrato, o sacarlo de la zona de trabajo | decisión §5 |

---

## 5. Lo que exige decisión del dueño antes de ejecutar

1. **`git commit` de los 463 borrados: sí o no.** Afecta a todas las ramas alineadas por árbol; es la
   discrepancia más delicada del repo hoy.
2. **SMTPLC en Linux** (entrar en `Nucleo` o declararlo exclusivo de Windows).
3. **Sacar el workflow de CI a la raíz** (`DT-01`): rompe el encierro en `src/` — es el único punto del plan
   que **no se puede hacer dentro de la zona de trabajo**.
4. **Reexportar el PCK** requiere el árbol de assets del motor. Los `.glb`/`.gltf` ya existen en `main` (PR #63)
   pero están ignorados por `.gitignore` y sostenidos sólo por un `git add -f`, y las fuentes `.blend` siguen
   fuera de Git: hay que decidir si se blinda la regla de negación (y el repo pasa a versionar recursos) o si
   el reexporte sigue haciéndose con el árbol externo. Sin reexporte, U1+U2+U3+U5 dan un árbol unificado
   **con el PCK de la 2.7.4** (medido en la zona: 114.591.724 B, SHA-256 `ebeff90c…7ae5e14`).
5. **Firma de código** (F7) y **número de versión resultante** de la unificación. No puede ser 2.7.4, 2.7.5 ni
   2.7.6: los tres están ya publicados (2.7.6 es la *Latest* vigente) y R2 prohíbe reetiquetar. La opción limpia
   es **2.7.7** (unificación sin cambios funcionales) o **2.8.0** si el árbol canónico se declara hito. R2 pide
   `<Version>` nueva para binario nuevo (y en los cuatro sitios a la vez) y R4 prohíbe renombrar un tag publicado.
6. **Destino de `applecat88.md`, `answer.md`, `read.md`, `readme.md`, `reads.md`** en la raíz y de `docs/*`
   con rutas a instantáneas que se purgan.

---

## 6. Orden y esfuerzo

| Fase | Esfuerzo | Dependencia |
|---|---|---|
| U0 blindaje | medio (crítico, poco código) | ninguna — **empieza por aquí** |
| U1 convergencia | alto (29 ficheros a mano) | U0 |
| U2 purga | bajo | U0 (y antes de U1 conviene tener el inventario de U1) |
| U3 núcleo C# | alto | U1 |
| U4 Godot/red | medio | U1, U3 |
| U5 versión/tests/CI | medio-alto | U3 |
| U6 deuda funcional | alto | U3, U4, U5 |

Cierre del ciclo: cuando `src/` esté unificado, el flujo propio hace `enviar` → `actualizar`, que versiona a
`PRY/actualizacion_<uuid>` y **vacía la zona** (`stm_gestion.py:381-406`). Antes de pulsar `actualizar`,
asegurar que el árbol está commiteado o respaldado, porque la purga de instantáneos (`:396-402`) no perdona.

---

*Documento generado por análisis del árbol en disco, de `origin/main` `490817d`, de `origin/DevAntigravityIDEIA`
y de las issues #48/#26/#15/#1/#16 y PRs #46/#47/#51–#63. Cada cifra de §1 es medida, no estimada.
Ninguna fase de este plan se ha ejecutado todavía.*
