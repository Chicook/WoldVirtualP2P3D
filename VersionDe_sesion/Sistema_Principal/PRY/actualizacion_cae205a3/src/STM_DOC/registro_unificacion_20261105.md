# Registro de la unificación 2026-11-05 — evidencia por fase

Bitácora del plan [`README_refactorizacion_20261105_unificacion.md`](README_refactorizacion_20261105_unificacion.md).
Cada entrada lleva el mando ejecutado y su resultado medido (RU6: prohibido afirmar sin medida). Los números de
`origin/main` y `origin/DevAntigravityIDEIA` son los de las referencias de rescate, no los de una apuesta.

---

## U0 — Blindaje (2026-11-05)

**Punto de partida medido:** rama `DevQoderIA` @ `294a72a` (2026-10-30T17:07:08+01:00), `origin/main` @ `490817d`
(2026-11-05T16:44:39+01:00), `origin/DevAntigravityIDEIA` @ `a43202b` (2026-11-04T15:44:56+01:00).

### U0.1 Referencias de seguridad (locales, cero push)

```
git tag -f -m "rescate U0 plan de refactorizacion 20261105" rescate/20261105/DevQoderIA-HEAD HEAD
git tag -f -m "…" rescate/20261105/main                 origin/main
git tag -f -m "…" rescate/20261105/DevAntigravityIDEIA  origin/DevAntigravityIDEIA
```

→ `git tag -l 'rescate/20261105/*'` devuelve las tres. Los tres árboles del diagnóstico (§1.1) quedan alcanzables
aunque RFPRMN purgue instantáneos o avance una rama.

### U0.2 Índice huérfano saneado

`git status --porcelain` arrancaba con **4 entradas anómalas sin `MERGE_HEAD`** (no había merge en curso):
`1 UU`, `1 DU`, `2 MD`. Se resolvieron por fichero, preservando antes cada blob staged en
[`rescate_indice_20261105/`](rescate_indice_20261105/README.md) (6 blobs + README, hashes verificados 3/3):

| Ruta | Estado | Resolución |
|---|---|---|
| `…/actualizacion_91883d55/src/SBSTM/IAFREE.py` | `MD` | `git reset -- <ruta>` (índice vuelve a HEAD; disco intacto) |
| `…/actualizacion_91883d55/src/STM_IA/…/uso_ialocal.md` | `MD` | ídem |
| `…/actualizacion_91883d55/src/STMGNRL/mainLCSTM.py` | `UU` (3 stages) | `git reset -- <ruta>`; los tres stages copiados al rescate |
| `TLLDCD/src/STM_CH/PSNRL/cierre_sesion_blockchain.json` | `DU` | `git rm --cached -f` → **sale del índice, sigue en disco**. Marcador de sesión, no código: ni `HEAD` ni `main` lo tienen |

**Prohibido y no usado:** `git reset --hard` (RU0.2 del plan) — habría destruido staged de otras sesiones.

Salida medida: `git status --porcelain | grep -E '^(UU|DU|MD|AA|AU|UA)'` → **0 líneas**. Quedan `466` borrados sin
confirmar (efecto normal de RFPRMN, RU2: **no se commitean**) y `2` rutas sin rastrear (`CONTRRF/TLLDCD/` y
`PRY/actualizacion_2f040968/`).

### U0.4 Inventario con hash de la zona (prueba del punto de partida)

`STM_DOC/inventario_zona_20261105.tsv` — 6.645 líneas `ruta<TAB>blob-sha1`, generado con
`git hash-object --stdin-paths` sobre la lista de `find . -type f`.

- Peso medido de la zona: **1.593.687.326 B (1.519,9 MiB)** de fichero; `du -sm` = 1.534 MiB.
- **Trampa encontrada:** con rutas *relativas*, `git hash-object --stdin-paths` aborta
  (`could not open 'LC_STM/…/EN10_RN.py' for reading`, exit 128, 0 hashes) porque no resuelve contra el `cwd` de
  la shell. Con rutas absolutas (`pwd -W` + prefijo) sale exit 0, 6.645 hashes, 0 errores.
- Autoverificación del método: 3 rutas dan el mismo hash en disco y en `main`
  (`project.godot` `25e5a487…`, `EN1_RN.py` `4057f2c8…`, `Boot.gd` `2b75d8f4…`) y una distinta
  (`VSC#/STM_actualizar/UpdateDownloader.cs`: disco `f6de430a…` vs main `de184745…`) — divergencia real, no fallo de medida.
- Las 6.645 frente a las 6.637 del diagnóstico: +8 ficheros escritos por este plan (documento, registro,
  inventario, dos copias de `envios.json` y los 6 blobs del rescate).

### U0.5 Registro RFPRMN congelado

`registro_envios_20261105.json` (1.159 B, copia del vivo `TLLDCD/STM_RFC/envios.json`) y
`registro_envios_herramienta_20261105.json` (4.081 B, copia del de la propia herramienta en
`CONTRRF/STM_RFC/STM_RFPRMN/stm_registro_json/STM_RFC/envios.json`).

El vivo documenta el ciclo de hoy, cuatro movimientos de **6.637 ficheros** cada uno:
`src → RFC` 16:32:02 · `RFC → PRY/actualizacion_2f040968` 16:33:49 (`OK actualizar`) ·
`snapshot → RFC` 16:35:21 (`OK refactorizar`) · `RFC → TLLDCD/src` 16:36:10 (`OK`).
**Confirmación de §1.13:** el instantáneo se cerró a las 16:33:49 local (15:33:49Z) y la primera PR `stage1` se
fusionó en `main` a las 15:41:56Z — **ocho minutos después**. La zona no perdió un conflicto: llegó tarde.

El histórico de la herramienta termina en `actualizacion_52bf0d80` (2026-10-27, 3.627 ficheros), lo que confirma
que la nota de memoria que daba ese instantáneo como vigente está obsoleta: el vigente es `2f040968`.

### Corrección a §1.3 del plan

`.gitignore` (raíz) **no** contiene ninguna regla para `cierre_sesion_blockchain.json`:
`grep -n cierre_sesion .gitignore` → 0 coincidencias. La afirmación de la sección 1.3 sobre esa duplicada es
falsa y queda retirada; la duplicada real sigue siendo objeto de revisión en U2.

### U0 · verificación de salida

`git status --short` sin `UU`/`DU`/`MD` · 3 referencias `rescate/20261105/*` creadas · 0 push · 0 ficheros de
código modificados.

---

## U1 — Convergencia a un árbol canónico (2026-11-05)

Copias usadas durante toda la fase: **A** = zona en disco `CONTRRF/TLLDCD/src`; **B** =
`PRY/actualizacion_2f040968/src` en disco; **C** = `origin/main:VersionDe_sesion/Sistema_Principal/PRY/
actualizacion_aeef1149/src`; **D** = `origin/DevAntigravityIDEIA:VersionDe_sesion/CONTRRF/TLLDCD/src`;
base = `e8295fc:VersionDe_sesion/CONTRRF/TLLDCD/src`.

### U1.1–U1.4 Superposición por rutas (sin `checkout` masivo)

`git ls-tree -r` sobre cada referencia → **C = 659 rutas, D = 504, base = 480; unión = 728**. Se extrajeron a la
zona las rutas ausentes (192 de C y 68 de D) con `git show "<ref>/<ruta>" > <ruta>`, y los 29 divergentes se
fusionaron con `git merge-file --diff3` (base = blob de `e8295fc`). **22 fusiones salieron limpias y se
aplicaron; 7 quedaron en conflicto** (los 6 de §1.2 más `README_DESARROLLO.md`, aplazado a U1.6).

### U1.5 Los 6 conflictos y su resolución

| Ruta | Conflicto | Decisión | Prueba |
| --- | --- | --- | --- |
| `VSC#/App.xaml.cs` | 1 hunk (44–71) | **D íntegro** | `diff base→C` añade sólo `--update-selftest`; `base→D` añade además `--webnodo-selftest`: D es superconjunto estricto (190 ln ⊃ 182) |
| `VSC#/Visor3D.csproj` | 3 hunks (AssemblyName, Version trío, Description) | **D + versión 2.7.7 + Description acumulada** | C declara 2.7.5 y D 2.7.6; `git ls-remote --tags` y `gh release list` confirman que **2.7.4/2.7.5/2.7.6 ya están publicados** y `v2.7.6` es *Latest* → R2 obliga a 2.7.7 y R4 prohíbe reetiquetar |
| `VSC#/Services/WebNodoService.cs` | 2 hunks | **D en ambos, y el literal `"2.7.6"` sustituido por derivación del ensamblado** | Fusionado = 1.110 ln; contiene `TokenSesionChat` (3 apariciones, aportación de C), `TryGetProperty("assets"` y `TryGetProperty("tag_name"` (1 c/u, de D) y `HostInterno` (3, de A/base) |
| `STM_HRTS/.github/workflows/ci.yml` | 1 hunk | **D íntegro** | `diff C↔D` = sólo rutas del utillaje (10 cambios) y el `--rootdir`; 113 ln |
| `tests/test_h1_contencion.py` | fichero completo (sin base) | **D íntegro** | `diff C↔D` = 4 líneas, todas la ruta de importación (`STM_HRTS.herramientas` → `STM_HRTS.utils.add_utils.herramientas`); 297 ln en ambos |
| `tests/test_regresion.py` | 1 hunk | **D íntegro** | `diff C↔D` = 2 hunks y ninguno aporta asserts ajenos al empaquetado; D añade la lista de módulos empaquetados y `PYTEST_CACHE` |

**Decisión de fondo que arrastran estas cuatro últimas filas:** el utillaje canónico es el **layout empaquetado
de D** (`STM_HRTS/utils/add_utils/`), no el plano de C. Es medible, no una preferencia: en D no existe
`STM_HRTS/rutas.py` ni `STM_HRTS/utils/*.gd` sueltos (su raíz es `.github, STM_PY, opencode, utils`), y las
versiones empaquetadas son superconjunto de las planas (`rutas.py` 183 ln vs 170; `herramientas.py` 248 vs 245,
más el `--rootdir`; `pytest.ini` con `pythonpath = .`). Tras adoptar D en tests y CI, **ningún módulo de la zona
importa ya el layout plano** (`grep -E '(from|import) STM_HRTS\.(rutas|herramientas|registro_hrts)'` → 0
coincidencias fuera del propio plano).

`ObtenerVersionEnsamblado()` queda así: `InformationalVersion` → si falta, `Assembly.GetName().Version`
formateada `Major.Minor.Build` → si también falta, `"0.0.0"`. Con esto el portal anuncia la versión con la que
se compiló el `.exe` y en el código **no queda ningún literal de versión** (U-C3), que era el mecanismo por el
que `WebNodoService.cs:70` de A anunciaba `v2.7.4` aunque el binario fuera otro.

### U1.5.b Defecto nuevo encontrado: 16 rutas obsoletas que los 29 divergentes no cubrían

El criterio «29 divergentes» comparaba ficheros con trabajo en ambos lados, pero dejó **rutas cuya copia en
disco era exactamente la de `e8295fc` mientras C y D habían avanzado**. Medido con
`git hash-object --stdin-paths` sobre las 728 rutas de la unión:

- **11 rutas `IGUAL_BASE` con C == D** → se adoptó C sin ambigüedad: `SBSTM/RPLC.py`, `SBSTM/selector_modelos.py`,
  `STM_BKCH/BKSVCB.py`, `STM_BKCH/compat_local.py`, `VSC#/AppExtractor.cs`,
  `VSC#/STM_actualizar/UpdateChecker.cs`, `VSC#/STM_actualizar/UpdateDownloader.cs`,
  `VSC#/Services/CuentaSelfTest.cs`, `VSC#/Services/DescubrimientoP2P.cs`, `VSC#/Services/StartupSelfTest.cs`,
  `VSC#/VisorLinux/Linux/RutasLinux.cs`.
- **5 rutas `PROPIA_ZONA_CD_IGUAL`** → se **conserva la zona**, porque su copia es trabajo que no está en ninguna
  rama: `STMGNRL/mainLCSTM.py` (1.075 ln; C/D tienen 456), `SBSTM/IAFREE.py` (524 vs 432),
  `STM_IA/modelosIAlocal/IALOCAL/uso_ialocal.md` (226 vs 195), `MTBGT/…/ctr_tscn_userBS/gdscrip/entornodeprueba.gd`
  (sólo la primera cámara del subtree pasa a `current`, corrigiendo el cielo torcido) y
  `MTBGT/WoldVirtualP2P3D/gdscrip/AnimacionesCompartidas.gd` (`RegEx ^mixamorig\d*[:_]` en lugar del
  `begins_with("mixamorig")` + `find("_")`, que no emparejaba `mixamorig12:Hips`). Estas 5 son candidatas a PR
  propio (U6): hoy **no existen más que en esta zona**.

Consecuencia directa y verificada: antes de adoptar C, `tests/test_h1_contencion.py` fallaba **5** asserts
(`ImportError: cannot import name 'IPFS_DISPONIBLE' from 'STM_BKCH.compat_local'`, y
`UpdateDownloader.cs:154` era `if (!string.IsNullOrWhiteSpace(release.Digest) && hash != null)` — es decir,
**fail-open**: sin digest no se comparaba nada). `compat_local.py` de A devolvía
`{"ok": True, …, "recuperado": True}` en `recuperar_pesos`, justo lo que H1 prohíbe. Tras la adopción: 0 fallos.

### U1.5.c `STMGNRL/mainLCSTM.py` llegaba con un conflicto de `git stash pop` sin resolver

No venía de esta fusión: el fichero en disco llevaba los rótulos
`<<<<<<< Updated upstream:…PRY/actualizacion_91883d55/…` / `>>>>>>> Stashed changes:…TLLDCD/src/…` y **no
compilaba** (`py_compile` → `SyntaxError`). Las tres etapas estaban ya en
`STM_DOC/rescate_indice_20261105/` (`97ea0f1c` = base, `79f41e02` = ours/HEAD, `f67df05e` = stash, 1.081 ln).
Se resolvió el único hunk conservando el lado del stash —el `print` de `limpiar_rutas_stmch()` más el checkpoint
`self.conciencia.detener()` / `xi()`— porque `detener()` (:243) y `xi()` (:389) sí existen en el cuerpo fusionado
y la rama de ours era la redacción vieja del mismo `print`. Resultado: `py_compile` OK y barrido
`grep -rl '^<<<<<<< '` sobre toda la zona (excluyendo `STM_DOC`) → **0 ficheros**.

### U1.5.d Duplicados del utillaje: aislados, no borrados

Superponer C y D dejó en `STM_HRTS/` y `STM_HRTS/utils/` dos generaciones del mismo utillaje. El catálogo de
`add_utils/herramientas.py` recorre `STM_HRTS/utils` **en recursivo**, así que la duplicación reventaba
`test_catalogo_integro` (`86 == 47`, herramientas repetidas). Se aislaron **53 ficheros** en
`STM_DOC/rescate_zona_20261105/duplicados_utils_flat/` (44) y `duplicados_utillaje_flat/` (9), con
`manifest_duplicados.tsv` que anota para cada uno su SHA-1, si era la blob de C y si su sustituto canónico es
idéntico. Desglose medido: **40 `canonico_igual`**, **11 `canonico_DISTINTO`** y **2 `sin_canonico`**.

De los 11 «distintos», ninguno pierde contenido: `Godot_abrir_y_limpiar_al_cerrar.bat`, `borrar_packs_viejos.ps1`,
`limpiar_cache_godot.ps1` y `purgar_repositorio.ps1` son **idénticos tras quitar `\r`**
(`diff <(tr -d '\r' a) <(tr -d '\r' b)` → 0 líneas), `manifiesto_h0.json` sólo difiere en la marca de tiempo de
generación, y `rutas.py` / `herramientas.py` / `__main__.py` / `pytest.ini` / `pyproject.toml` / `__init__.py`
son la generación plana que el paquete sustituye. Los 2 `sin_canonico` son inertes y se queda así:
`session.py` (**0 B**) y `transport.py` (1.585 B, cliente JSON-RPC con `0x3b1574…` cableado, **0 importadores**
en la zona).

### U1.5.e Alineación de `tests/test_sistema.py` con el reflejo interno de la zona

`test_orquestador_contexto_y_memoria` pedía el literal `Estimulo cognitivo`, que sólo existe en el
`_generar_reflejo_interno` viejo (C/D/base). La copia de la zona —la única— devuelve respuestas por rama
(registro de cambios, estado de conciencia, saludo, genérica), así que la aserción se reescribió para el contrato
actual: saludo con `Soy LucIA` + `PSNRL` + mención del tono, y una segunda comprobación de que un prompt sin
palabra clave devuelve `He recibido tu mensaje` + `reflejo interno`. No se ha tocado el código para que el test
pase; se ha ajustado el test a un código que es estrictamente más capaz.

### U1.6 Versión unificada

`VSC#/Visor3D.csproj` y `VSC#/VisorLinux/VisorLinux.csproj` declaran los dos **2.7.7** (`AssemblyName`, `Version`,
`AssemblyVersion`, `FileVersion`). Dejaba de cumplirse R2 tener el visor Windows en 2.7.7 y el de Linux en 2.7.5,
porque `VersionInstalada` se deriva ahora del ensamblado de cada binario. El literal 2.7.7 desaparece en U5 con
`src/VERSION.json` + `Directory.Build.props`.

### U1.7 Control de integridad del árbol (medida final)

`git hash-object --stdin-paths` sobre las 728 rutas de la unión, clasificado contra base/C/D
(`STM_DOC/clasificacion_arbol_20261105.tsv`):

| Clase | Rutas |
| --- | --- |
| `IGUAL_C` (tronco) | 572 |
| `IGUAL_D` (capa de utillaje) | 77 |
| `FUSIONADA` (difiere de C, D y base por construcción) | 20 |
| `PROPIA_ZONA_CD_IGUAL` (trabajo sólo en la zona) | 5 |
| `AISLADA` (duplicados con sustituto canónico) | 53 |
| `AUSENTE` no justificado | **1** |

La ausencia sin justificación es `pytest.ini` en la raíz de `src/`, que **debe** estar ausente: es la regla que
verifica `test_config_pytest_unica_en_raiz`. **0 rutas de código perdidas.** El plan anticipaba 727 rutas fuente;
la unión medida es **728**.

Prueba de salida de la fase:

```
python -m pytest tests/test_h1_contencion.py tests/test_hrts_rutas.py \
  tests/test_regresion.py tests/test_sistema.py -q --rootdir . \
  -c STM_HRTS/utils/add_utils/pytest.ini -p no:cacheprovider
  → 55 passed
python -m pytest tests/ -q … --timeout=60 -k "not ipfs_deteccion_resiliente"
  → 168 passed, 1 deselected      (la nota de la release 2.7.5 afirmaba 97)
```

Queda abierto y anotado: `README_DESARROLLO.md` (32 hunks, U1.6 del plan → siguiente entrada), el
`PytestConfigWarning: Unknown config option: cache_dir` —que aparece sólo con `-p no:cacheprovider`, porque es el
`cacheprovider` quien registra esa opción— (**cerrado en U5.5**, quitando la bandera del `ci.yml`) y que
`STM_HRTS/.github/workflows/ci.yml` **nunca se ha ejecutado**:
un `.github/workflows` anidado no lo lee GitHub Actions, y sus `working-directory` apuntan a
`VersionDe_sesion/CONTRRF/TLLDCD/src`, que en `main` no existe (el tronco guarda `VersionDe_sesion/
Sistema_Principal/…`). Los dos puntos son decisión §5.3 + U5.


### U1 · verificación de salida (cierre de fase)

La salida del plan exige «un árbol, **compilable**, con las tres funciones». Medido:

```
grep -rl '^<<<<<<< ' . --exclude-dir=STM_DOC   → 0 ficheros (0 marcas de conflicto)
dotnet build VSC#/Visor3D.csproj               → Compilación correcta. 0 Advertencia(s) 0 Errores
                                                 (build completo 00:00:11.37; re-build incremental 00:00:00.45, 11.0.100-preview.7.26381.103)
python -m pytest tests/ -q …                   → 168 passed, 1 deselected
git hash-object --stdin-paths (728 rutas)      → 0 rutas de código perdidas (§U1.7)
```

| Función del plan | Dónde quedó | Evidencia |
| --- | --- | --- |
| Seguridad `stage1` + arte (C) | tronco: 572 rutas `IGUAL_C` | tabla §U1.7 |
| Utillaje empaquetado + autopruebas del portal (D) | capa: 77 rutas `IGUAL_D` + `VSC#/Tests/` restaurado | §U1.5.b, §U1.6 |
| Historial de `main` intacto bajo la rama de trabajo | `DevQoderIA` + refs `rescate/20261105/*` (locales, 0 push) | §U0.1 |

**U1 cerrada.** El conteo real de la unión es 728 (no 727): el plan no contaba `pytest.ini`.

---

## U2 — Purga de contaminación y peso (2026-11-05)

### U2.1 Medida de entrada

`du -sm src` = **2342 MiB**. Todos los bloques candidatos están **fuera del índice**: `git ls-files` sobre cada
ruta devuelve 0 ficheros rastreados en `HEAD`, y `git check-ignore -v` confirma que la raíz `.gitignore` ya los
cubre (`**/bin/`:17, `**/obj/`:18, `node_modules/`:190, `__pycache__/`:181, `*.exe`:10, `*.dll`:11, `*.pdb`:25,
`*.pck`:35, `*.zip`:37).
Por tanto la purga **no genera ningún borrado rastreado**: `git status --porcelain` de la zona sigue marcando
`0` rutas `D` de más.

### U2.2 Purgado (regenerable por los mandos del propio árbol)

| Bloque | MiB | Ficheros | Cómo se regenera |
| --- | --- | --- | --- |
| `VSC#/bin` (incl. `publish_v2.7.6/`) | 706 | 484 | `dotnet build VSC#/Visor3D.csproj` |
| `VSC#/obj` | 195 | 39 | ídem |
| `VSC#/VisorLinux/{bin,obj}` | 1 | 5 | `dotnet build VSC#/VisorLinux/VisorLinux.csproj` |
| `VSC#/Tests/{bin,obj}` | 1 | 5 | `dotnet build VSC#/Tests/Visor3DTests.csproj` |
| `STM_CH/pycache` | 23 | 861 (`.pyc`) | se re-emite solo; es caché de bytecode redirigida (`WOLD_RUNTIME_DIR`), con scipy/numpy/comtypes |
| `tests/test_voces/voz_audit.log` | 1 | 1 | efecto colateral de la suite Python |
| **Suma de bloques** | **927** | **1395** | delta medido `du -sm`: **922 MiB** (2342 → 1420; la diferencia es redondeo por bloque) |

**Prueba de que no se perdió nada** (ejecutada después de purgar y antes del estado final):

```
dotnet build VSC#/Visor3D.csproj                    → Compilación correcta. 0 Advertencia(s) 0 Errores (00:00:04.88)
dotnet build VSC#/VisorLinux/VisorLinux.csproj      → Compilación correcta. 0/0 (00:00:07.63)
dotnet build VSC#/Tests/Visor3DTests.csproj         → Compilación correcta. 0/0 (00:00:02.90)
dotnet test  VSC#/Tests/Visor3DTests.csproj         → Correctas! 0 fallos, 34 superados, 0 omitidos (142 ms)
python -m pytest tests/ -q (caché fría)             → 168 passed, 1 deselected (7.56 s)
```

La línea de xUnit es la evidencia que faltaba: los **34 casos** que la nota de la release 2.7.5 afirmaba vuelven
a ejecutarse de verdad tras restaurar `VSC#/Tests/` en U1. Con esa medida queda justificada la redacción de la
futura nota 2.7.7 (en U1 se escribió evitando citar «34 superadas» porque no se habían ejecutado).
Estado final: se volvieron a borrar las salidas recién generadas (`du -sm src` = **1420 MiB**).

**El ejecutable 2.7.6 se fue sin pérdida.** Medido antes de borrar:
`sha256 VSC#/bin/publish_v2.7.6/DMWoldVirtualP2P3Dv2.7.6.exe` = `26fb446e45a937af2a6c8866efb9601ef0ec0b192d105f33aba2e01d973b150f`,
365.088.633 B, idéntico al `digest` y al `size` del `release.json` de ese propio directorio y al asset publicado
en `https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v2.7.6/DMWoldVirtualP2P3Dv2.7.6.exe`. Se borra
**la copia local de una release publicada** (R4 no se toca: la release y su asset siguen en GitHub). Con él se
van `DMWoldVirtualP2P3Dv2.7.6.pdb` (165.876 B), `release.json` (531 B) y `SHA256SUMS` (99 B), cuyo contenido
queda transcrito arriba; los tres son `**/release.json`, `**/SHA256SUMS` y `*.pdb` ignorados y re-generables por
`STM_HRTS/utils/add_utils/publish_release_v276.ps1`.

### U2.3 NO purgado: `STM_HRTS/opencode/` (881 MiB) — necesita autorización

Tres medidas mandan a la espera:

1. **Está cableado al utillaje rastreado**: `STM_HRTS/utils/STM_UTILS/lanzar_opencode.bat:5`
   (`set "OPENCODE_EXE=%SCRIPT_DIR%..\opencode\opencode.exe"`). Borrar el binario deja el arnés sin objetivo.
2. **Susconfigs sí están en la rama de rescate D**: `git cat-file -e` confirma que `package.json`,
   `package-lock.json`, `opencode.jsonc`, `README.md` y `.gitignore` existen en
   `origin/DevAntigravityIDEIA:…/src/STM_HRTS/opencode/`. Es utillaje de otra sesión, no basura de esta.
3. **Su restauración exige red**: `npm ci` (32 paquetes en `node_modules`, 679 MiB) descarga los binarios. La
   regla de esta fase es borrar sólo lo que se regenera con los mandos del árbol, sin dependencias de red.
   Medido en disco, los 4 binarios de 211.564.424 B no son 4 copias iguales: dos sha-256
   (`d7b473388cb6…98a3fa` en `opencode.exe` y `node_modules/opencode-windows-x64/bin`, `6f15c8f241f3…673b7b`
   en `node_modules/opencode-ai/bin` y `opencode-windows-x64-baseline/bin`). El `manifiesto_h0.json` canónico
   atribuye `d7b47338…` a `opencode-ai/bin`, así que **esa entrada del manifiesto está obsoleta**; se corrige
   al regenerar el manifiesto (U6).

Si el dueño autoriza: `rm -rf STM_HRTS/opencode/node_modules STM_HRTS/opencode/opencode.exe` → **537 MiB**, y se
revierte con `cd STM_HRTS/opencode && npm ci` (el `postinstall` de `opencode-ai@1.19.5` vuelve a copiar
`opencode.exe`). No se ejecuta por decisión propia: son 881 MiB de herramienta ajena y un lanzador rastreado.

### U2.4 El objetivo `≤ 300 MiB` del plan es inalcanzable sin romper una regla

Composición medida de los 1420 MiB restantes:

| Bloque | MiB | Estado |
| --- | --- | --- |
| `STM_HRTS/opencode/` | 881 | en espera de autorización (§U2.3) |
| `VSC#/wvp3d.pck` + `godot_exe.zip` + `godot_linux.zip` | 269 | **lista de no-tocar**; SHA-256 en `manifiesto_h0.json` |
| `MTBGT/…/gltfimport/{avatares,terrenoblok}` | 248 | ignoradas por diseño (`.gitignore`:221-222) pero únicas fuentes para reexportar el PCK |
| código + documentación | ~13 | las 728 rutas de la unión + `STM_DOC` (10 MiB, con la cuarentena de U1) |

Soltando sólo `opencode`: **537 MiB**. Bajar de 300 exigiría sacar del árbol los 269 MiB de insumos de exportación
o los 248 MiB de texturas, que son precisamente lo que la limpieza del 2026-10-30 juró conservar. **Criterio de
salida reescrito:** «0 MiB de contaminación regenerable dentro de `src`» en lugar de «`du -sm src ≤ 300`», con el
techo estructural de 537 MiB anotado.

### U2.5 Auditoría de `.gitignore` y restos de la propia fase

- **Ningún candidato a commit de basura**: las 634 rutas `untracked` no ignoradas de la zona son
  150 `.py`, 98 `.gd`, 85 `.cs`, 46 `.md`, 42 `.uid`, 38 `.tscn`, 30 `.tres`, 29 `.orig`, 19 `.json`, 12 `.png`,
  10 `.ps1`… **ninguna supera 5 MiB y no hay ni un `.exe`, `.dll`, `.zip` o `.pck`**. La política de la raíz ya
  basta; no hacen falta las reglas de negación que anticipaba el plan (el arte pesado está ignorado *por
  diseño*, no por accidente).
- **Único hueco real**: `*.orig` no está ignorado y las 29 copias `.orig` de los divergentes (0,6 MiB) viven en
  `STM_DOC/rescate_zona_20261105/divergentes_preunificacion/`. Se conservan como evidencia de U1 y **se retiran
  del árbol antes de cualquier commit** (tarea de U6); no se añade una regla que las tape, porque entonces la
  evidencia no sería revisable en la PR.
- **Manifiesto H0 obsoleto tras la purga**: 10 de sus entradas `binarios_grandes` apuntan ahora a rutas
  `existe_disk=False` (`VSC#/bin/Debug/…` y `VSC#/obj/Debug/…`) y `arbol.ficheros` declara 6356 frente a los
  6055 medidos. Se regenera con `python STM_HRTS/utils/STM_UTILS/generar_manifiesto_h0.py` al cierre (U6), no
  ahora: reescribir un fichero rastreado en mitad del plan ensuciaría el diff de cada fase.

**U2 cerrada con 922 MiB purgados, 0 rutas rastreadas afectadas y las tres compilaciones + 168 pytest + 34 xUnit
volviendo a pasar desde el árbol limpio.**

## U3 — Núcleo C# común (2026-11-05)

### U3.1 Un ensamblado, dos visores

`VSC#/Nucleo/Nucleo.csproj`: `net8.0` sin UI, `AssemblyName=WoldVirtualNucleo`, `RootNamespace=Visor3D` (el
traslado es de **propiedad**, no de código: los namespaces no cambian) e `InternalsVisibleTo=Visor3DTests`. Sin `<Version>`
a propósito: declarar la versión en cuatro sitios era justo la deuda que U5 cierra.

**25 ficheros `.cs`** en el núcleo (excluidos `bin/` y `obj/`), por bloque: `Chat/` 5 · `RedP2P/` 4 ·
`STM_actualizar/` 3 · `Seguridad/` 4 · `Services/` 9. Los 21 iniciales eran los 17 que `VisorLinux.csproj` enlazaba
a mano más `WebNodoService`, `DescubrimientoP2P`, `RateLimiter` y `VisorLog`; los 9 de `Services/` son esos 5 más
las 4 fichas nuevas del troceo de §U3.4.

- **17 `<Compile Include="../…">` eliminados** y sustituidos por un `ProjectReference`. El WPF conserva su glob por
  defecto y añade `<Compile Remove="Nucleo\**">` (más los `Remove` de `EmbeddedResource`, `None` y `Page`): sin esa
  exclusión el SDK compilaría los mismos ficheros dos veces.
- **Recursos compartidos movidos al núcleo** (`bip39-english.txt`, `index.html`, `metaverso.jpg`) con sus
  `LogicalName` intactos, y verificados **en ejecución**, no en la build: `--cuenta-selftest` genera frase semilla
  BIP-39 desde el recurso embebido y `--webnodo-selftest` sirve el portal (14.760 caracteres). `godot_exe.zip` y
  `wvp3d.pck` se quedan en cada visor (listas de no-tocar, §U2.4).
- **Costura de plataforma explícita en lugar de un `using` cruzado.** `PerfilUsuario.TieneIdentidad(bool)`
  ([Nucleo/Seguridad/PerfilUsuario.cs:48](file:///E:/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/VSC%23/Nucleo/Seguridad/PerfilUsuario.cs#L48))
  recibe el sello de equipo: el núcleo no puede conocer `RegistroPcUnico`, que tiene una implementación por
  plataforma (`Seguridad/Seguridad_sesion_unica/` en WPF, `VisorLinux/Linux/` en Avalonia). Se rechazó inyección por
  delegado o interfaz porque un registro olvidado **fallaría abierto** y permitiría una segunda cuenta en el PC.
  Call sites medidos: `MainWindow.xaml.cs:211/527/567`, `FormularioUsuarioWindow.xaml.cs:42`,
  `VisorLinux/Linux/CuentaLinux.cs:49`.
- `RedP2P/TunnelProcessRegistry.cs` pasó de `internal` a `public` (lo usan 4 sitios de `MainWindow`); se optó por
  eso antes que un `InternalsVisibleTo("DMWoldVirtualP2P3Dv2.7.7")`, que habría vuelto a atar el grafo de proyectos
  a un literal de versión.
- `Visor3D.sln` (formato clásico, no `slnx`: el SDK preview 11.0.100 genera `slnx` por defecto y las Actions con SDK
  estable no lo entienden) con los 4 proyectos: Nucleo, Visor3D, VisorLinux, Tests.

### U3.2 Correcciones a lo que afirmaba el plan

| Afirmación del plan | Medido |
| --- | --- |
| §1.8 «`WebNodoService.cs`… **896 líneas**» | **1.116 líneas** al abrir la fase. Tras el troceo y quitar la cadena del portal: 1.011 líneas repartidas en 5 ficheros. |
| §1.8 «**tres propietarios** del seudosingleton» | Los 3 sitios están en **3 caminos de arranque distintos**, no conviven en un proceso: `App.xaml.cs:12` (WPF), `VisorLinux/Vistas/VentanaPrincipal.cs:23` (GUI de Linux) y `VisorLinux/Linux/ComprobacionLocal.cs:71` (modo `--comprobar`, que retorna en `Program.cs:14` antes de que `Vistas/Aplicacion.cs:20` cree la ventana). Es duplicidad **de tipo**, no de instancias vivas: no había a qué asignar un dueño único. |
| Salida de U3 «los **62 métodos solapados** desaparecen» | La cifra **no se reprodujo** al medir: el solapamiento real eran 17 ficheros enlazados dos veces, y así se cerró. |
| DT-13 «puntos de sutura dentro de `WebNodoService.cs`» | Ahora son `AnuncioRelease.LeerReleaseParaPrueba`, `.SembrarReleaseParaPrueba` y `.RutaBinarioEnEjecucion`. |

### U3.3 Decisión pendiente del dueño: SMTPLC

El plan (§U3.3, punto 3) pedía elegir entre llevar `SMTPLC` al núcleo o declararlo exclusivo de Windows. **No es
tarea de código, es decisión (§5)** y se deja sin tomar. Datos para tomarla: 8 ficheros y **1.918 líneas** en
`VSC#/Seguridad/SMTPLC/`, con `SmtplcNativeMethods.cs` declarando **6 `DllImport` de `iphlpapi`** (API de
adaptadores de Windows). Consumidores medidos: `FormularioUsuarioWindow.xaml.cs` (WPF) y `Services/StartupSelfTest.cs`
(WPF, se quedó en `Visor3D`). Por eso el visor Linux **no ejecuta** hoy las comprobaciones del issue #26; el sello
de cuenta única (`RegistroPcUnico`) sí existe en ambas plataformas.

### U3.4 Troceo del WebNodo

Un `partial class` repartido en cuatro responsabilidades más el anuncio de release. Cero cambios en la superficie
pública:

| Fichero | Ln | Responsabilidad |
| --- | --- | --- |
| `Nucleo/Services/WebNodoService.cs` | 234 | raíz del ciclo de vida: **único dueño de los campos mutables**, `Start`/`Stop`/`Dispose` y bucle del `HttpListener` |
| `Nucleo/Services/WebNodoService.PortalHttp.cs` | 374 | router (antes `:788-998`), recursos del portal, IP de cliente, límites y 429 |
| `Nucleo/Services/WebNodoService.ProxyTcp.cs` | 203 | proxy TCP, reescritura de `Host`, marcador de confianza y saneado de cabeceras |
| `Nucleo/Services/WebNodoService.ProxyWebSocket.cs` | 61 | transporte del handshake al motor (8911) o al relay (`/chat`) |
| `Nucleo/Services/AnuncioRelease.cs` | 246 | qué release se anuncia: `release.json`, refresco por sesión, binario en ejecución |

- **El HTML del portal salió de la cadena** (plan §U3.4): se eliminaron las **105 líneas** de `IndexHtml` y la única
  fuente es `webnodo/public/index.html` (disco → recurso embebido). La cadena estaba **obsoleta** frente al recurso:
  ~5 kB sin el marcador `{{API_TOKEN}}` que el router ya sustituye, contra 14.772 B del fichero. Con ella se fue el
  `Replace("{{TUNNEL_URL}}", …)`, que **no aparece en el recurso** (medido: el enlace lo resuelve el JS con
  `/api/p2p-status`) y solo existía para alimentarse a sí mismo.
- `ObtenIndexHtml()` ahora devuelve `null` y el router responde **503** si falta el recurso, en vez de servir una
  página vacía: se cambia el duplicado de 105 líneas por 3 comprobaciones que piden el portal de verdad.
- **Estáticas que siguen siendo de proceso, con dueño nombrado:** `AnuncioRelease` es la única que guarda estado
  **mutable** (`ReleaseActiva`, `_ultimaConsulta`, `_consultaEnCurso`) porque portal y OTA tienen que ver la misma
  release aunque el nodo se reinicie. En `WebNodoService` sólo quedan estáticas **inmutables por diseño**:
  `_apiToken` y `_valorMarcadorProxy` (secretos de sesión por RNG), `_limiteApi`/`_limiteDescarga` (cubetas por IP),
  `_cabecerasSuplantables` (regex) y `Port`. Hacerlas de instancia partiría el token de sesión que comparten el
  portal, el relay de chat y `TokenSesionChat`.
- Pruebas de fuente repuntadas: `test_stage1_s3_ip.py` y `test_stage1_s2_chat.py` leen ahora el **conjunto de
  parciales en orden fijo**, y la comprobación del «token literal de 32 hex en la cadena de chat» recorre las 5
  fichas. **168 pytest siguen pasando sin reescribir ninguna aserción.**

### U3.5 Regresión encontrada al medir (y su guarda)

Mover la clase a una librería cambió **a qué ensamblado pregunta la versión**. Medido antes de tocar nada:

```
WoldVirtualNucleo.dll        ProductVersion = 1.0.0+294a72a…   (librería, sin <Version>)
DMWoldVirtualP2P3Dv2.7.7.exe ProductVersion = 2.7.7+294a72a…
--webnodo-selftest (antes):  fallback: nombre = DMWoldVirtualP2P3Dv1.0.0.exe
                             /api/info version_instalada = 1.0.0
```

`ObtenerVersionEnsamblado()` usaba `typeof(WebNodoService).Assembly`, que tras U3.1 dejó de ser el ejecutable. El
efecto real: sin `release.json` legible y sin red, el portal habría anunciado un binario **inexistente** y
`/descargar` habría redirigido a `…/v1.0.0/DMWoldVirtualP2P3Dv1.0.0.exe` (404), además de mentir en
`version_instalada`. Ninguna prueba lo detectaba: todas comparaban contra el propio valor.

Arreglo: la versión se lee de `Assembly.GetEntryAssembly()` (el visor que corre), con respaldo al ensamblado propio.
Guarda nueva en `--webnodo-selftest`: compara la versión **anunciada** con el `ProductVersion` del `.exe` en
ejecución. Medido después: `PE «2.7.7» vs anunciada «2.7.7»`, 23 líneas y 0 fallos. Es además la primera evidencia
positiva de **DT-08** («no hay prueba de que `GetEntryAssembly()` devuelva el ensamblado correcto»), aunque sólo
cubre el arranque por apphost de Windows; falta el caso Linux.

### U3.6 Qué queda de U3 sin hacer

- **`ReinicioCuenta` sigue duplicado** (plan §U3.1 pedía migrarlo): `Seguridad/Seguridad_sesion_unica/ReinicioCuenta.cs`
  (326 ln) y `VisorLinux/Linux/ReinicioCuenta.cs` (258 ln) **no son una copia**: 184 de las 584 líneas difieren — la
  de Windows fija rutas `LocalApplicationData` y preserva `cloudflared.exe`; la de Linux usa `RutasLinux`. Unirlas
  exige la abstracción de plataforma que el plan anticipaba (`IPlataforma`) y **tocan el archivo de la base de
  usuarios**: fuera del radio de esta fase (riesgo sobre identidad, no sobre formato).
- **`MainWindow.xaml.cs` sin adelgazar** (plan §U3.5): **3.428 líneas** medidas hoy (el plan citaba 3.389). Es la
  pieza grande que queda; su lógica ya tiene dónde ir (`Nucleo`), pero es una fase en sí misma y no se ha tocado.
- `STM_DOC/clasificacion_arbol_20261105.tsv` (728 rutas) queda **desfasado** para los 21 ficheros movidos y las 4
  fichas nuevas: se regenera en U6 junto con el manifiesto, como los demás índices.

**U3 cerrada en lo estructural y en el troceo con:** build de la solución 0 errores / 0 advertencias · 34/34 xUnit ·
168/168 pytest · `--webnodo-selftest` 23 líneas 0 fallos · `--update-selftest` 0 fallos · `--cuenta-selftest` OK ·
`--startup-selftest` OK · `--red-selftest` 7 líneas 0 fallos · `--chat-selftest` fallos=0 (incluye el proxy `/chat`
a través del WebNodo). Quedan abiertas, con la medida arriba: la decisión de SMTPLC (§5), la fusión de
`ReinicioCuenta` y el adelgazamiento de `MainWindow`.

---

## U4 — Godot y red: puertos, parser de destino y autoload (2026-11-05)

### U4.1 Una sola tabla de puertos — y por qué son dos ficheros

El plan (§U4.3) pedía «un único `ConfigRed` leído por `Red.gd` y por el C#». Se ha implementado como **una tabla por
lenguaje con un gate que las obliga a coincidir**, y la razón es medida, no de gusto: el C# no puede leer `res://`, así
que un JSON compartido sólo existiría bien en un lado; y un fichero ausente o sin reexportar en el PCK sería un modo de
fallo nuevo encima de uno que ya estaba cerrado.

- `VSC#/Nucleo/RedP2P/ConfigRed.cs` — **112 ln**, 8 constantes (`PuertoMotorWs` 8911, `PuertoBalizaUdp` 8912,
  `PuertoApiP2P` 7890, `PuertoPortal` 3030, `PuertoPortalMax` 3040, `DesplazamientoProxyInterno` 100, `PuertoChat`
  8920, `RangoChat` 10) y 5 métodos (`EsPuertoReescribibleAlMotor`, `PuertoMotorDesde`, `PuertosPortalCandidatos`,
  `ProbarDestino`).
- `MTBGT/…/gdscrip/Red.gd` — 5 constantes hermanas: `PUERTO_WS`, `PUERTO_BEACON` (nueva), `PUERTO_API_P2P` (nueva),
  `PUERTO_PORTAL_MIN`/`PUERTO_PORTAL_MAX` (nuevas).
- `tests/test_config_red.py` — **186 ln, 6 pruebas**: espejo const por const sobre 6 números, veto de literales en
  **12 ficheros consumidores** (ignorando comentarios y prosa de UI), identidad de la regla de reescritura en los dos
  lenguajes y delegación del parser en ambos visores. Este gate es la fuente única: si alguien mueve 8911 en un lado,
  pytest para.
- Los 12 consumidores fueron repuntados sin cambiar nombres públicos: `DescubrimientoP2P.PuertoBeacon`/`.PuertoGodot`
  quedan como alias de la tabla para no agitar call sites ni pruebas; `ChatRelayServer.Start()` toma los defaults de la
  tabla y su mensaje de error ahora imprime el rango calculado (`{puertoPreferido}-{puertoPreferido + intentos - 1}`)
  en vez del «8920-8929» escrito a mano.

pytest pasó de **168 a 174** (1 descartada) con las 6 pruebas nuevas.

### U4.2 El parser de destino: de tres copias a una

Medido antes de tocar: la misma operación —recortar esquema, cortar en `/`, separar host y puerto, y decidir si ese
puerto es del mundo o hay que reescribirlo a 8911— estaba copiada en `MainWindow.xaml.cs` (`TryParseConnectionTarget`,
36 ln), `LanzadorMundo.cs` (`TryParsearDestino`) y `Red.gd` (`parsear_url_host_puerto`). Los tres fallaban distinto:

| Defecto | Dónde | Ahora |
|---|---|---|
| `ws://ip:puerto` devolvía host `"ws"` | WPF y Avalonia | ambos visores delegan en `ConfigRed.ProbarDestino` (`MainWindow.xaml.cs:1163`, `LanzadorMundo.cs:225`) |
| un roster con `https://host` producía `wss://https://host` | `Red.resolver_url_ws` | `limpiar_destino()` recorta `ws/wss/http/https/woldvirtual` antes de decidir |
| off-by-one en `woldvirtual://` (corte en `[15..]`, el esquema mide 14) | `LanzadorMundo.cs` | desaparece con la delegación |
| la regla «3030-3040, 7890, 80 y 443 no son el mundo: reescribe a 8911» en tres sitios | los tres | `EsPuertoReescribibleAlMotor` (C#) con gate de identidad contra `parsear_url_host_puerto` (Godot) |
| un host público con puerto explícito perdía el puerto | `resolver_url_ws` | `lleva_puerto_explicito()`: `wss://host:puerto` para dominio público, `ws://host:puerto` para LAN |

El lado Godot conserva su propio parser —es otro lenguaje— pero sobre los helpers nuevos y los números de la tabla.

### U4.3 Banderas de comando convertidas en función pura

El bucle de argumentos de `Red.gd` estaba mezclado con la resolución de destino, así que no se podía probar sin levantar
la SceneTree. Extraído a `static func analizar_args(all_args: Array) -> Dictionary` que devuelve
`{ip, port (0 = no indicado), is_client, force_host, invitacion}` y acepta también enlaces `ws://`/`wss://` sueltos.
`resolver_objetivo()` ahora la llama. Esto es lo que ha permitido la evidencia siguiente.

### U4.4 Evidencia nueva: `STM_HRTS/utils/STM_UTILS/probar_red_puerto.gd`

**175 ln, 41 comprobaciones en cinco grupos** (tabla de puertos, banderas de comando, enlaces y direcciones, URL final
del WebSocket, ruta del roster). Instancia `ChunkManager.new()` para ejercitar `_url_candidato` real. Resultado
medido: `== RESULTADO RED-PUERTO: 41 líneas, 0 fallos ==`. Cubre directamente el criterio de #1 (puerto configurable
efectivo) salvo la prueba física entre dos equipos, que sigue siendo externa (DT-04).

### U4.5 Correcciones al plan: lo que la medición desmintió

- **«Autoload `OptimizadorAvatares`, hoy sin uso» (§U4.1) — falso.** Está declarado en `project.godot:65` con `*`, su
  `_ready()` fija `root.mesh_lod_threshold = 4.0` (probado en headless: el propio script imprime
  `[OptimizadorAvatares] mesh_lod_threshold global -> 4.0`) y su `_process()` recorre cada frame un registro siempre
  vacío. Lo que no se usa es la **API** de texturas/VRAM/LOD: `optimizar_nodo`, `aplicar_configuracion_global`,
  `limpiar_cache` y `avatar_optimizado` tienen **0 call sites externos**. Retirarlo o neutralizarlo cambia el binario →
  decisión del dueño (§5) + reexport del PCK (RU5). **No se ha tocado nada.**
- **«`Red.gd:153`/`:161` no respetan `port`» (§U4.3) — a medio verificar.** El número ya viajaba en
  `parsear_url_host_puerto`; lo roto era `resolver_url_ws`, que descartaba el puerto explícito, y la ausencia total de
  la regla de reescritura en los visores C#. La tabla de arriba deja la medida concreta en lugar de la línea del plan.
- **«`_url_candidato` añade `:8911` a una URL `ws://ip:puerto`» — falso.** `resolver_url_ws` devuelve tal cual las URLs
  que ya llevan esquema. La sospecha del plan no se reprodujo; se conserva como comprobación explícita en
  `probar_red_puerto` para que no vuelva.
- **`AVH1.gltf` sí está en la zona** (§1.9 lo citaba como referencia colgante). Además #63 restauró en `main` los
  `gltfimport/avatares`: verificado en la zona 16 `.glb`, 9 `.gltf` y la carpeta `gltfimport/avatares` presentes — la
  promoción no pierde los assets de #63.

### U4.6 Qué queda de U4 sin hacer

- **RU5 pendiente.** Ningún arreglo de `Red.gd`/`ChunkManager.gd` llega al binario publicado hasta reexportar
  `VSC#/wvp3d.pck` (en disco: 114.591.724 B, SHA-256 `ebeff90c…5e14`, el de la 2.7.4). Requiere
  `E:/areadetrabajo/wvp270/godot` y autorización del dueño. Mientras tanto el `v2.7.6` en la calle conserva los defectos
  de la tabla U4.2.
- **Literales de puerto en prosa de UI**, no funcionales pero que mienten si se edita la tabla: «IP:8911» en
  `VentanaPrincipal.Mundo`/`VentanaPrincipal.Red` (Avalonia) y en `Construccion.gd:1495`.
- **Asertas acopladas al texto fuente**, que hubo que reescribir durante la fase: 4 en `test_stage1_s2_chat.py` (ahora
  afirman contra los tokens `ConfigRed.PuertoChat`/`RangoChat`), 1 en `test_h2_h3_red.py`, y el gate nuevo escanea
  fuente. Es el peaje de este estilo de prueba; la alternativa (probar sólo comportamiento) queda para U5.
- **`gltfimport/` y `AreaDeTrabajo/` dentro de `src/` con el ancla de `AnimacionesCompartidas.gd:13`** (§U4.2): no
  ejecutado; la zona arranca igual pero el ancla sigue apuntando fuera.
- **IPv6 con corchetes** en `DescubrimientoP2P.cs` (DT-09): no tocado, vive en el parseo de la baliza, que la tabla
  nueva no cubre.

**U4 cerrada en lo estructural con:** build 0 errores / 0 advertencias · 34/34 xUnit · **174 passed / 1 descartada**
pytest · seis selftests exit 0 (`WEBNODO: 23 líneas 0 fallos`, `UpdateSelfTest: 0 fallo(s)`, `CUENTA: OK`,
`ARRANQUE: OK`, `RED: 7 líneas 0 fallos`, chat `fallos=0`) · 12 pruebas Godot headless exit 0, incluida
`probar_red_puerto` 41/0 y las dos de sonda en ejecución concurrente (anfitrión sondas=1, invitado 0).

Deuda de esta fase y de los merges #55–#63, con su orden de trabajo, registrada en el
**issue #65** ([Deuda Tecnica] Merges #55-#63, ramas no absorbidas y unificacion U0-U4).

---

## U5 — Versión única, puertas de prueba y CI (2026-11-05)

### U5.1 El número de versión: cinco fuentes, tres valores

Medido antes de tocar nada, en las tres referencias del árbol:

| Referencia | `Visor3D.csproj` | `VisorLinux.csproj` | `RutasLinux.Version` | Motor (`Godot_v…`) |
|---|---|---|---|---|
| rescate pre-U1 de la zona (`STM_DOC/rescate_zona_20261105/divergentes_preunificacion`) | `2.7.4` (4 literales) | `2.7.4` | — | — |
| `origin/main` @ `actualizacion_aeef1149` | `2.7.5` (4 literales, incluido `AssemblyName`) | `2.7.5` | `2.7.5` | 3 literales (`RutasLinux:16`, `AppExtractor:58` y `:115`, `GodotConfig:16`) |
| `origin/DevAntigravityIDEIA` (la que adoptó U1) | **`2.7.6`** | — | **`2.7.5`** | mismos literales |

La última fila es la contradicción heredada: el `.exe` se llamaba `…v2.7.6.exe` y el visor Linux
anunciaba `2.7.5` desde su propio constante. Diez literales repartidos en cinco ficheros, ninguno con
una relación declarada entre sí. **Ahora hay uno solo:** `src/VERSION.json`

```
{"version":"2.7.7","motor":"4.7.2","pck_sha256":"ebeff90c…5e14","pck_bytes":114591724,"fecha":"2026-11-05"}
```

y dos ficheros MSBuild lo reparten: `VSC#/Directory.Build.props` (extrae `WoldVersion`, `WoldMotor`,
`WoldPckSha256`, `WoldFecha` con property functions y falla el build con tres `<Error>` si la tabla
falta, no es semver o el motor está vacío) y `VSC#/Directory.Build.targets` (materializa
`internal static class WoldInfoVersion` en `$(IntermediateOutputPath)`). `$(WoldVersion)` es hoy el
valor de `<Version>`, `<AssemblyVersion>`, `<FileVersion>` y `<AssemblyName>` en los cuatro csproj, y
`WoldInfoVersion.*` el de `RutasLinux`, `AppExtractor.NombreMotorWindows`, `GodotConfig` y la prosa de
`VentanaPrincipal(.Mundo)`.

Dos trampas medidas del puente MSBuild, para quien vuelva a escribirlo:

- `$([regex]::Match(…))` **no existe**: da `error MSB4212`. Hay que usar el nombre completo
  `$([System.Text.RegularExpressions.Regex]::Match(…))` con las comillas del JSON escapadas como `&quot;`.
- `$(IntermediateOutputPath)` está **vacío** durante la evaluación de `Directory.Build.props`, así que
  generar allí escribía `WoldInfoVersion.g.cs` en la carpeta fuente (`Nucleo/`). La generación se mueve
  a `Directory.Build.targets`, que corre después de la carga del SDK; verificado en
  `Nucleo/obj/Debug/net8.0/WoldInfoVersion.g.cs` (cuatro copias, una por proyecto, todas dentro de `obj/`).

Sin default silencioso a propósito (DT-08): si la tabla falta, el build se para. Un `2.7.0`
de rebote volvería a fabricar el desenfoque que acabamos de medir.

### U5.2 La puerta: `version_unica.py` + 11 casos

`STM_HRTS/utils/add_utils/version_unica.py` (`--leer` / `--comprobar` / `--registrar-pck`) valida el
esquema de la tabla, que ningún csproj vuelva a llevar un número literal, que `RutasLinux` no recupere
su constante, que ningún `.cs` escrito a mano vuelva a poner `Godot_v\d+\.\d+\.\d+`, y que el PCK en
disco siga siendo el SHA-256 y el tamaño declarados (si se reexporta, `--registrar-pck` reescribe la
tabla). `tests/test_version_unica.py` son 11 casos, incluido el cruzado de lenguajes:
`dotnet msbuild Visor3D.csproj -getProperty:WoldVersion` tiene que dar el mismo valor que
`version_unica.leer()`.

Prueba negativa ejecutada (no razonada): se inyectó `<Version>2.7.5</Version>` en `Nucleo.csproj` y

```
FALLO Nucleo/Nucleo.csproj: <Version>2.7.5</Version> es un literal   → exit 1
OK version unica: 4 csproj heredan el numero y el PCK esta anclado    → exit 0 (restaurado)
```

### U5.3 xUnit: 34 → 67 casos, y un defecto encontrado por el camino

| Fichero nuevo | Casos | Qué fija |
|---|---|---|
| `Tests/LedgerPruebas.cs` | 9 | sello HMAC del ledger (caída cerrada si se altera), cuota, enfriamiento, fusión externa e IP pública sólo hasheada |
| `Tests/PerfilEstadoPruebas.cs` | 10 | `PerfilUsuario.Diagnosticar` en sus tres estados (incluido JSON ilegible = resto, no acceso) y la decisión `vacio/incompleto/completo` de `EstadoGlobal` |
| `Tests/ReinicioCuentaPruebas.cs` | 10 | archivado en vez de borrado, marcador por versión, reset total único, y que `runtime`/`logs`/cachés del motor sobreviven |
| `Tests/SmtplcUmbralesPruebas.cs` | 4 | igualdad detector ↔ política de los dos umbrales y los defaults de cuota (1 cuenta / 4320 min) |
| `Tests/PruebasEntorno.cs` | — | `[ModuleInitializer]` que aísla el log (abajo) |

Ninguno toca el perfil real: todo pasa `baseDir`/`godotDir`/ruta del ledger a temporales. No se llama a
`VmDetector.Analyze()` ni a `VpnDetector.AnalyzeLocal()`: leen WMI, registro y procesos, y su resultado
depende del equipo que ejecuta la prueba — lo que se puede fijar es el umbral, no la lectura.

**Defecto medido y corregido:** los casos de `ReinicioCuenta` escribían 10 líneas tipo
`[cuenta] Base de usuarios reiniciada para 2.7.7` en
`%LOCALAPPDATA%\WoldVirtualP2P3D\logs\visor-*.log`, que es el texto que el visor entrega como
«Copiar diagnóstico» y el usuario manda a soporte. Contado: `wvp_reset_*` aparecía 10 veces en el log
de hoy. Solución: `VisorLog.Carpeta` honra `WOLD_LOG_DIR` (igual que `AppExtractor` honra
`WOLD_RUNTIME_DIR`) y el ensamblado de pruebas lo apunta a un temporal. Verificado tras el cambio:
log real **472 líneas antes y 472 después** de la suite, 12 líneas en el temporal. Las autopruebas del
`.exe` también quedan aisladas cuando el entorno lo pide.

### U5.4 Selftests: umbral de VPN añadido

`VpnDetector` comparaba contra `0.40` escrito dos veces (`AnalyzeLocal` y `AnalyzeAsync`) mientras la
política guardaba el mismo valor en `VpnConfidenceThreshold`; `VmDetector` ya tenía su `UmbralVm`.
Extraído `public const double UmbralVpn = 0.40` en las dos comparaciones, `StartupSelfTest` pasa de
`ComprobarUmbralVm` a `ComprobarUmbralesSeguridad` y `--startup-selftest` imprime ahora:

```
[OK] Umbral de VM unificado (0,50) — detector=0,50 política=0,50
[OK] Umbral de VPN unificado (0,40) — detector=0,40 política=0,40
```

Las seis banderas (`--update`, `--red`, `--cuenta`, `--chat`, `--webnodo`, `--startup`) sobre
`DMWoldVirtualP2P3Dv2.7.7.exe` con `WOLD_RUNTIME_DIR` y `WOLD_LOG_DIR` temporales: **exit 0 las seis**.
El nombre del binario ya no se escribe: sale de `$(WoldVersion)` y es lo que la puerta de CI compara.

### U5.5 pytest sin `-c`: intentado, medido y retirado

El plan (U5.5 / DT-10) pedía `pytest.ini` en `src/tests` para soltar el `-c` obligatorio. Se probó de
verdad: creada la config en la raíz y actualizada `rutas.PYTEST_INI`, la suite pasaba pero
`python -m pytest tests/` sin flags dejaba `.pytest_cache` en la raíz de `src`. Y el árbol ya tenía una
decisión en contrario, testada: `tests/test_regresion.py:99-115` afirma `PYTEST_INI.parent == ADD_UTILS_DIR`
y `not (SRC_DIR / "pytest.ini").exists()`, y `tests/test_hrts_rutas.py:124` fija que el runner pasa
`-c rutas.PYTEST_INI`. Mover la config significaba reescribir dos pruebas que protegen la regla de
configuración única — la misma regla por la que U1 contó el `pytest.ini` raíz como «ausencia justificada»
en la unión de 728 rutas. **Retirado el cambio** (`rutas.py` y la config vuelven a su estado; la única
pieza que se queda es `tests/conftest.py`).

Lo que sí se arregla: `tests/conftest.py` añade `src/` a `sys.path` antes de recoger, que es la parte de
DT-10 que importaba. Medido: `python -m pytest tests/ -q -p no:cacheprovider --timeout=60` **sin `-c`**
→ 185 passed / 1 deselected. Los 13 ficheros que llevaban su propio `sys.path.insert` quedan cubiertos
e intactos; no se han reescrito porque son idempotentes y no estorban.

Y una advertencia preexistente, reproducida en las dos variantes: con `-p no:cacheprovider` **y** `-c`,
pytest avisa `Unknown config option: cache_dir` (la opción la registra el plugin que se acaba de
desactivar). Como `cache_dir = STM_HRTS/.pytest_cache` es justamente lo que evita ensuciar `src/`, se ha
quitado `-p no:cacheprovider` del `ci.yml`, no la config. Ejecutado de las dos formas: con el flag, 185
passed + 1 warning; sin él, **185 passed, 0 warnings** y la cache en `STM_HRTS/.pytest_cache` (que se
autoignora sola con su `.gitignore`). El comando canónico local y el de CI coinciden ahora.

### U5.6 CI reescrito y sin depender de la ruta del snapshot

`STM_HRTS/.github/workflows/ci.yml`: job `resolver-taller` localiza `VERSION.json` con `find` y exporta
`src` y `version` como outputs; los demás jobs usan `${{ env.SRC }}`, así que da igual que el snapshot se
llame `actualizacion_aeef1149`, `91883d55` o el hash del próximo merge (D-01). La suite Python pierde el
`continue-on-error: true` (D-06/§16.4); el job C# compila `Visor3D.sln`, corre `dotnet test`, comprueba
que el `.exe` generado se llama exactamente `v$WOLD_VERSION.exe` y recorre las seis autopruebas con
entorno temporal propio por bandera. `rutas.verificar()` y `version_unica.py --comprobar` son pasos
previos. Sigue sin estar activo: el workflow vive dentro del taller, donde GitHub Actions no lo lee, y
copiarlo a `.github/workflows/` de la raíz es decisión del dueño (#65, P0-2). Las pruebas Godot headless
no entran en el CI: requieren el árbol de assets del PCK (§U4.6, RU5).

**U5 cerrada en lo estructural con:** build 0 errores / **0 advertencias** · **67/67 xUnit** (34 en U4) ·
**185 passed / 1 descartada** pytest (174 en U4) · `version_unica --comprobar` OK con su prueba negativa ·
seis selftests exit 0 con el umbral de VPN nuevo · log real intacto (472 → 472 líneas) · `ci.yml` YAML válido.


