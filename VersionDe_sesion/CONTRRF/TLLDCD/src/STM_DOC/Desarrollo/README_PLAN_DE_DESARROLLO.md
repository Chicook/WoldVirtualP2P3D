# Wold Virtual P2P 3D — Plan de desarrollo del taller `src`

| dato | valor |
|---|---|
| **Snapshot** | `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_4e0f1cf6/src` |
| **Fecha del análisis** | 2026-11-07 |
| **Última actualización** | 2026-11-09 (sesión RFPRMN · IPFS · LucIA 3D — issues #85 · #86) |
| **Rama / HEAD del análisis** | `main` · `c408a17` «Merge branch 'DevAntigravityIDEIA' into main» (2026-11-06) |
| **Rama de la sesión 2026-11-09** | `DevDeepSeekHarnessIA` · `7cec0ec`; el 2026-11-09 se fusionó `origin/main` sobre `DevQoderIA` (commit `4388643`) |
| **Versión en el árbol** | `2.7.9` (`Visor3D.csproj:27-29`; `VERSION.json` **sigue sin existir**) |
| **Release vigente** | `v2.7.9` (publicada 2026-11-07T22:59:48Z · Latest) |
| **Issues de referencia** | [#1](https://github.com/Chicook/WoldVirtualP2P3D/issues/1) · [#15](https://github.com/Chicook/WoldVirtualP2P3D/issues/15) · [#16](https://github.com/Chicook/WoldVirtualP2P3D/issues/16) · [#26](https://github.com/Chicook/WoldVirtualP2P3D/issues/26) · [#48](https://github.com/Chicook/WoldVirtualP2P3D/issues/48) · [#65](https://github.com/Chicook/WoldVirtualP2P3D/issues/65) · [#66](https://github.com/Chicook/WoldVirtualP2P3D/issues/66) · [#69](https://github.com/Chicook/WoldVirtualP2P3D/issues/69) · [#85](https://github.com/Chicook/WoldVirtualP2P3D/issues/85) |
| **Discusión de referencia** | [#86](https://github.com/Chicook/WoldVirtualP2P3D/discussions/86) «LucIA anfitriona y wallet embebida» |
| **Documento de cabecera que este plan respeta** | `STM_DOC/Desarrollo/README_DESARROLLO.md` (§14 criterios de cierre, §15 cola dirigida, §17 blindaje) |
| **Reglas de publicación** | `STM_DOC/Otros_documentos/REGLAS_DE_ACTUALIZACION.md` (§7 checklist obligatorio, §8 prohibiciones) |

---

## 0. Cómo leer este documento

Este README **no sustituye** a `README_DESARROLLO.md`; lo **contrasta con el árbol tal y como está hoy** y lo convierte en tareas ejecutables. La diferencia de fondo es esta:

- `README_DESARROLLO.md` describe el taller `CONTRRF/TLLDCD/src` (una zona **sin rastrear por Git**) en su estado de 2026-11-06 y afirma un conjunto de cosas «verificadas» allí: `pytest` verde, `escanear` sin hallazgos, xUnit 67/67, `VERSION.json` como fuente única.
- **Ese árbol ya no es este.** La promoción del 2026-11-06 (`45a1fcf` → `ecb7c65` → `c408a17`) movió la zona a `PRY/actualizacion_cae205a3/src` y después sustituyó ese snapshot por `actualizacion_4e0f1cf6`, **perdiendo por el camino el núcleo unificado**. La medición de la §2 lo demuestra con comandos reproducibles.

Por eso el plan empieza por **devolver el árbol a verde** (F0) antes de tocar producto. No es una precaución de estilo: hoy el propio visor no arrancaría en un árbol de desarrollo (B-05) y el binario publicado no contiene el mundo que dice contener (B-03).

### 0.1 Convenciones

| Prefijo | Significado |
|---|---|
| **B-nn** | Hallazgo bloqueante: impide trabajar con garantías |
| **F-n** | Fase del plan (F0…F7) |
| **F-n.mm** | Tarea concreta dentro de una fase |
| **D-nn** | Decisión pendiente. `D1`–`D9` heredadas de `README_DESARROLLO.md §8`; `D10`–`D13` nuevas de este plan |
| **E-nn** | Evidencia exigida para cerrar una tarea (log, captura, artefacto, salida de comando) |
| **S / M / L / XL** | Esfuerzo: S ≤ 2 h · M ≈ medio día · L ≈ 1–3 días · XL > 3 días |

Toda afirmación de este documento lleva detrás **un comando ejecutado o una ruta concreta**. Lo que no se pudo verificar se marca explícitamente como **no verificado**. No se ha modificado ni un fichero del producto para escribir este plan.

### 0.2 Qué NO es este plan

- No es una propuesta de funcionalidad nueva. La §12 del README de desarrollo mantiene el backlog congelado y este plan no lo reabre.
- No autoriza ninguna publicación ni ninguna acción OTA (regla R16 de `REGLAS_DE_ACTUALIZACION.md`).
- No ordena ejecutar los scripts destructivos de `STM_HRTS/utils/STM_UTILS/` (`purgar_repositorio.ps1`, `borrar_packs_viejos.ps1`, `limpiar_cache_godot.ps1`, `Godot_abrir_y_limpiar_al_cerrar.bat`).

---

## 1. Resumen ejecutivo

**El árbol está en un estado de promoción incompleta, no de desarrollo.** La versión 2.7.8 se publicó correctamente en cuanto a metadatos y digests, pero el snapshot que quedó en `main` no es el árbol que produjo ese binario: le falta el núcleo unificado (U0–U4), le falta la fuente única de versión (`VERSION.json`) y le falta el mundo actual (el PCK sigue siendo el de la 2.7.4). Al mismo tiempo **conserva los tests de la zona unificada**, que por eso fallan en masa.

Los ocho hechos que ordenan todo lo demás:

1. **La puerta Python está en rojo**: `105 failed · 37 errors · 104 passed · 4 xfailed` y un fichero que ni se colecciona (`tests/test_version_unica.py`). Dos tercios de los fallos son estructurales (los tests buscan `VSC#/Nucleo/…`, que no existe), no defectos de conducta.
2. **La puerta de seguridad también está en rojo**: `python -m STM_HRTS.STM_DEF escanear` devuelve **26 hallazgos / veredicto ALTA / exit 1**, porque la allowlist sigue apuntando a `README_DESARROLLO.md` en la raíz de `src/` y el documento se movió a `STM_DOC/Desarrollo/`. Consecuencia directa: `ArranqueSeguro.cs` **bloquearía el visor WPF** en cualquier árbol de desarrollo.
3. **El PCK embebido es el de la 2.7.4**: `wvp3d.pck` = 114.591.724 B · `sha256 ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14` · mtime 2026-10-30 02:24. Cuatro releases (2.7.5 → 2.7.8) se han publicado sin reexportar el mundo. RU5 sigue abierto y ha envejecido.
4. **Se perdió el núcleo que el propio proyecto ya había promocionado**: entre `45a1fcf` (661 ficheros en `cae205a3/src`) y `HEAD` (629 en `4e0f1cf6/src`) desaparecen, sin equivalente, `VSC#/Nucleo/` (29 ficheros, incluido `ConfigRed.cs` y `TokenSesionChat.cs`), `VERSION.json`, `Directory.Build.{props,targets}`, `Visor3D.sln`, `ValidacionRed.gd`, `probar_red_puerto.gd`, `version_unica.py`, `publicar_version.ps1`, `STM_HRTS/__main__.py`, `LC_STM/STM_PRCS/` y 5 clases xUnit.
5. **El endurecimiento de seguridad de la Etapa 1 no está en el árbol**: identidad de pares con prueba de posesión (S1), token de sesión del relé, validación `any_peer` (S4), IP de cliente fiable (S3), registro de pares autenticado (S6)… solo sobreviven **sus tests**. Lo que la v2.7.8 llevó de verdad es `STM_DEF`, que sí está completo (14 módulos, 52 pruebas).
6. **La evidencia forense de R-01 se borró**: `STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/` contiene únicamente `MANIFIESTO.md`; las muestras (`.orc`, `opencode/init`, `transport.py`) se eliminaron en `ecb7c65`. El manifiesto quedó huérfano y `cuarentena --verificar` no puede dar «INTACTA».
7. **No hay CI**: no existe `.github/` en la raíz del repositorio. El trabajo de calidad depende de que alguien se acuerde de ejecutar cinco comandos a mano.
8. **La puerta de pruebas de Godot no puede ejecutarse**: `tests/godot/test_headless.py` importa cinco nombres que `STM_HRTS/utils/add_utils/herramientas.py` no expone (`emite_veredicto`, `PCK_OBLIGATORIO`, `MODO_ARBOL`, `MODO_PCK`, `entorno_aislado`) más `rutas.USER_DATA_DIR`; los 22 casos fallan por `AttributeError`, no por falta de motor. La suite del mundo no es una puerta: es un fichero que se rompe al ejecutarse.

**Y lo importante: nada de esto es un desastre irreversible.** El núcleo unificado está íntegro en el objeto Git `45a1fcf` y se puede recuperar con `git checkout`; el binario 2.7.8 arranca y extrae motor y PCK correctamente; `STM_DEF` es un activo real. La §4 lista lo que hay que preservar sin tocar y la §5 propone las tres decisiones que desbloquean el resto.

### 1.1 Estado al 2026-11-09 (sesión RFPRMN · IPFS · LucIA 3D)

La sesión del 2026-11-09 (issue #85) **no tocó las fases F0–F4** (reparación del árbol canónico): trabajó en la **pista cognitiva** — la que el plan de 2026-11-07 dejaba para F6 — sobre la rama `DevDeepSeekHarnessIA`, y ese trabajo ya está en `origin/main` vía PR #78 (el 2026-11-09 se fusionó sobre `DevQoderIA`). Medido:

| Pieza | Resultado |
|---|---|
| **RFPRMN** | v2.24.0 · 29 submódulos ≤ 450 líneas · 381 símbolos · **399 pruebas** en verde · ruff limpio · CI Ubuntu + Windows |
| **IPFS real** | Kubo 0.43.1 en `STMIPFS/ipfs.exe`; `STMIPFS/nodo/` (rutas, binario, repositorio, daemon, cliente API v0, pesos) |
| **LucIA 3D** | `LucIAServidor3D` (arranca `servidor_lucia.py` y habla su NDJSON) + `LucIAPuenteComandos` (autoconocimiento + intención + ejecución con el agente); E2E real del chat antes/después |
| **Modelos** | `ollama create` para GGUF, descarga reanudable, política de descartes |

**Lo que deja abierto** (deuda del propio #85, tareas F8-01…F8-10): `servidor_lucia.py` vive fuera de control de versiones, el puente no tiene pruebas, la detección de intención es por palabras clave y la ejecución bloquea el hilo del chat. Nada de esto toca F0–F4, pero **cambia el mapa de F6**: LucIA ya no es solo «red neuronal sin dueño», tiene un puente de comandos real que hay que blindar con pruebas.

**En paralelo, la discusión #86** fija la siguiente ambición de producto (**diseño, no implementación**): LucIA como **anfitriona** del registro y **wallet embebida** con alta por bloque en el `blockchain-server`. Se recoge como fase F9 (§6); sus preguntas D14–D18 quedaron **cerradas el 2026-11-09** con decisiones fundamentadas en el código actual.

**Sobre la versión:** la v2.7.9 (publicada 2026-11-07) ya embarca los arreglos F1-01/F1-02 (allowlist de `STM_DEF`) y F5-06 (falso positivo de VM). El análisis de las §2–§3 sigue siendo el del 2026-11-07 (v2.7.8): las puertas F0–F4 no se han re-medido sobre 2.7.9.

### 1.2 Las tres decisiones que desbloquean el plan

| Decisión | Pregunta | Recomendación | Bloquea |
|---|---|---|---|
| **D10** | ¿Se **re-promociona** el árbol unificado de `45a1fcf` y se le vuelve a aplicar `STM_DEF` encima, o se **re-implementa** el núcleo sobre el árbol actual? | **Re-promocionar.** Es recuperable con un `git checkout` y evita reescribir ~6.000 líneas ya probadas (67 xUnit, 185 pytest en su día). Re-implementar es un XL con riesgo de divergencia. | F0 completo, F2-F4 |
| **D11** | ¿Qué se hace con la **v2.7.8 ya publicada**? | Dejarla como está (R4 prohíbe tocar el tag) y **anunciar** en el issue #66 que su PCK es el de la 2.7.4 y que el endurecimiento S1/S3/S4/S6 no está en ese binario. La siguiente release nace del árbol reparado. | F3, comunicación |
| **D12** | ¿El snapshot sigue llamándose `actualizacion_<hash>`? | **No.** Renombrar a una ruta estable (`src/` en la raíz del repo o `PRY/actual/`). Cada merge que roza un directorio con hash reescribe rutas completas: es la causa raíz de B-01 (deuda D-01 del issue #65) y ya ha costado dos promociones. | F0, F7 |

---

## 2. Estado medido del árbol (2026-11-07)

### 2.1 Inventario

Medido sobre `src/`, excluyendo `bin/`, `obj/`, `__pycache__`, `.pytest_cache`, `node_modules`, `.godot` y `*.pyc`.

| Lenguaje | Ficheros | Líneas |
|---|---:|---:|
| C# (`.cs`) | 85 | 18.854 |
| GDScript (`.gd`) | 97 | 17.189 |
| Python (`.py`) | 159 | 35.526 |
| XAML (`.xaml`) | 8 | 1.617 |
| Escenas Godot (`.tscn`) | 38 | 3.242 |
| Shaders (`.gdshader`) | 9 | 403 |

| Zona | Rol | Estado medido |
|---|---|---|
| `VSC#/` | Visor WPF: UI, chat, voz/webcam, red P2P, OTA, SMTPLC, portal WebNodo | Implementado; **sin `Nucleo/`, sin `.sln`, sin `VERSION.json`** |
| `VSC#/VisorLinux/` | Visor Avalonia | 22 ficheros versionados; no invoca `ArranqueSeguro` |
| `VSC#/Tests/` | xUnit | **3 clases** (`PasswordHasherTests`, `UpdateCheckerTests`, `WebNodoReleaseTests`); las 5 que elevaban la cifra a 67 no están |
| `MTBGT/WoldVirtualP2P3D/` | Mundo Godot 4.7.2 | 22 `.gd` en `gdscrip/`; **sin `ValidacionRed.gd`**; `Red.gd` volvió a `const PUERTO_WS := 8911` |
| `STM_HRTS/STM_DEF/` | Subsistema defensivo | **Completo**: 14 módulos, `rutas_ignoradas.txt`, plantilla CI `workflow_call` |
| `STM_HRTS/utils/add_utils/` | Consola y utilidades (layout U1) | Presente; **sin `version_unica.py` ni `publicar_version.ps1`** |
| `LC_STM/red_neuronal/` | Red neuronal distribuida | 60 ficheros, ~22,7 k líneas reales con numpy; **desconectada del runtime** |
| `tests/` | Arnés pytest | 22 ficheros con 242 `def test_`; escritos **contra el árbol unificado** |
| `STM_DOC/` | Documentación | Reorganizada en `Desarrollo/` y `Otros_documentos/`; la allowlist de `STM_DEF` no se enteró |

### 2.2 Tamaño y ruido

| Artefacto | Tamaño | Nota |
|---|---:|---|
| `VSC#/wvp3d.pck` | 114.591.724 B (109,28 MiB) | **PCK de la 2.7.4** (sha256 `ebeff90c…`) |
| `VSC#/godot_exe.zip` | 86.155.888 B (82,16 MiB) | motor Windows; en `.gitignore` |
| `VSC#/godot_linux.zip` | 79.135.021 B (75,47 MiB) | motor Linux; en `.gitignore` |
| `VSC#/bin/` | 710,1 MiB | ruido de compilación |
| `VSC#/obj/` | 397 MiB | ruido de compilación |
| `ISLA3DCHUNK_rocky_terrain_02_diff_4k.png` | 25,52 MiB | textura de terreno 4K en fuente (el export usa 2K) |
| Árbol de trabajo completo | 957 ficheros · 607,85 MB | incluye los tres artefactos anteriores |

Release vigente `v2.7.8` (4 assets): Windows `365.088.633 B` · `f9700aa1…` · Linux `207.220.008 B` · `ccfa84d0…`. Sigue por encima de la meta propuesta en #15 (≤ 250 MiB) y **sin métrica de huella instalada**.

### 2.3 Las siete puertas, medidas hoy

Ejecutadas en esta máquina (Windows 11, `dotnet 11.0.100-preview`, Python 3.14.7), con `WOLD_RUNTIME_DIR` y `WOLD_LOG_DIR` redirigidos a directorios temporales.

| # | Puerta | Comando | Resultado medido | Veredicto |
|---|---|---|---|---|
| P1 | Regresión Python | `python -m pytest -q` en `src/` | **105 failed · 37 errors · 104 passed · 4 xfailed** + 1 error de colección (`test_version_unica.py`) | 🔴 |
| P2 | Puerta de seguridad | `python -m STM_HRTS.STM_DEF escanear` | **26 hallazgos · veredicto ALTA · exit 1** | 🔴 |
| P3 | Autoprueba de arranque | `DMWoldVirtualP2P3Dv2.7.8.exe --startup-selftest` | **2 FALLOS · exit 1** («Portal WebNodo escucha»; «Motor arranca desde el PCK», `errores=True`) | 🔴 |
| P4 | Autoprueba de red | `… --red-selftest` | **1 fallo · exit 1** («Portal WebNodo escucha — Controlador no válido») | 🔴 (a confirmar en sesión interactiva) |
| P5 | Punto de entrada Python | `python -m STM_HRTS` | **`ModuleNotFoundError: No module named STM_HRTS.__main__`** | 🔴 |
| P6 | Build C# | `dotnet build Visor3D.sln` | **no ejecutable**: `Visor3D.sln` no existe en el snapshot | 🟡 |
| P7 | CI | — | **no existe `.github/` en la raíz del repositorio** | 🔴 |

Desglose de P1 (para no confundir causa estructural con defecto de conducta):

| Grupo | Fallos | Causa |
|---|---:|---|
| `tests/godot/test_headless.py` | 19 | **la puerta importa 6 nombres que `herramientas.py` no expone** → `AttributeError`; además `probar_red_puerto` no existe en `STM_UTILS/` |
| `test_stage1_s1…s6` | 62 | asertan contra literales del árbol unificado (`DOMINIO_PRUEBA`, `VERSION_PRUEBA`, `_desafio_posesion`, `ValidacionRed.gd`…), que **no está en este snapshot** |
| `test_config_red.py` | 6 | requiere `VSC#/Nucleo/RedP2P/ConfigRed.cs` |
| `test_g4_privacidad_ip.py` | 5 | privacidad de IP en GDScript endurecido, ausente |
| `test_perfil`, `test_memoria`, `test_sistema`, `test_hrts_rutas`, `test_h1_contencion` | 13 | a triar (rutas y contratos del árbol viejo) |
| **Errores** `test_stm_def.py` (32) y `test_h1_contencion.py` (5) | 37 | `PermissionError` al crear el directorio temporal de pytest **en el entorno de este análisis**; no son defectos del código y deben re-medirse con `TMP` escribible |

> **Causa exacta de los 37 errores, medida después:** el sandbox de este entorno deja **ilegibles los directorios creados con modo `0700`** (`os.makedirs(d, 0o700)` seguido de `os.listdir(d)` → `WinError 5`; con `0o755` funciona). El *tmp factory* de pytest crea siempre su `basetemp` con `0700`, así que las 32 pruebas que usan `tmp_path` no pueden ni arrancar aquí. **No es un defecto del proyecto**: en un escritorio normal o en GitHub Actions no ocurre. Verificado además que las 21 pruebas que no usan `tmp_path` pasan.

> **Nota de honestidad:** el entorno de análisis no permite escribir en el directorio temporal del sistema (`C:\Users\…\Temp\dsh-*`). Por eso 37 pruebas de `STM_DEF` no llegaron a ejecutarse. **No se han contado como verdes ni como rojas**: están pendientes de re-medición (tarea F0-02).

### 2.4 Cruce `issue` ↔ árbol real

| Issue | Lo que el issue dice | Lo que hay hoy en el árbol | Delta |
|---|---|---|---|
| **#1** Red LAN | Código hecho en H3; falta prueba física de 2 equipos (DT-04) e IPv6 (DT-09) | `Red.gd` volvió a `const PUERTO_WS := 8911`; no hay `ConfigRed.cs`; **el binario publicado lleva el PCK de la 2.7.4**, así que ningún arreglo de GDScript llegó a la calle | **Empeoró**: además de la prueba falta el PCK |
| **#15** Peso | 348,17 MiB; falta métrica de huella y D3 | Windows 365.088.633 B (348,19 MiB) · Linux 207.220.008 B | Igual: sin métrica ni decisión |
| **#16** LucIA | Fuera de alcance | `LC_STM/` presente pero **desconectado del visor**; `STM_PRCS/` perdido | Sin cambio |
| **#26** SMTPLC | Bloqueado por D5 y D8; ledger sin llamador | `vault_openrouter.py` sigue en **XOR sin MAC** con semilla hardcodeada; `LocationAccountLedger.ExportJson/MergeExternalRecords` sin llamador | Igual; el XOR está confirmado |
| **#48** Deuda DT-01…DT-16 | Paraguas de deuda | DT-01 (CI) sigue abierto; la ampliación xUnit (67 casos) **se perdió** con el snapshot | **Empeoró** |
| **#65** Unificación U0–U4 | «Pendiente de absorber» | La unificación **se absorbió y luego se perdió** en la promoción (`45a1fcf` → `c408a17`) | Cambia de naturaleza: ya no es absorber, es **revertir una regresión** |
| **#66** Deuda v2.7.7 | Tres casillas de release abiertas | Siguen abiertas; ahora la 2.7.8 añade una cuarta (PCK un ciclo más viejo) | Empeoró |
| **#69** Deuda `STM_DEF` | Escaneo «0 hallazgos»; falta CI raíz y firma en OTA | `STM_DEF` completo, pero la **allowlist está mal apuntada** → 26 hallazgos | Empeoró |

---

## 3. Hallazgos bloqueantes

Cada hallazgo se cierra con una tarea de la §6 y una evidencia de la §10. Mientras un hallazgo P0 esté abierto, **no se abre producto nuevo**.

### B-01 · La promoción del 2026-11-06 perdió el núcleo unificado

**Síntoma.** Los tests del árbol unificado están en `main`, su implementación no.

**Evidencia.**

```powershell
git ls-tree -r --name-only 45a1fcf | Select-String "/actualizacion_cae205a3/src/" | Measure-Object   # 661
git ls-tree -r --name-only HEAD    | Select-String "/actualizacion_4e0f1cf6/src/"  | Measure-Object   # 629
```

107 rutas de `cae205a3/src` no tienen contrapartida en `4e0f1cf6/src`; 75 son nuevas. De las 107, unas son **movidas** (`VSC#/Chat/ChatProtocol.cs` → existe plano; `README_DESARROLLO.md` → `STM_DOC/Desarrollo/`) y otras están **perdidas sin equivalente**:

| Perdido | Por qué importa |
|---|---|
| `VERSION.json` | Fuente única de versión y ancla del PCK (R2/R3). Sin él, `test_version_unica.py` no se colecciona y `version_unica --comprobar` no existe |
| `VSC#/Directory.Build.props` + `.targets` | Reparten `VERSION.json` a los csproj; sin ellos vuelve la dispersión de literales |
| `VSC#/Visor3D.sln` | El árbol no tiene solución: `dotnet build Visor3D.sln` falla; el README de desarrollo documenta ese comando |
| `VSC#/Nucleo/` (29 ficheros) | `ConfigRed.cs` (tabla única de puertos), `TokenSesionChat.cs` (token del relé), `AnuncioRelease.cs`, `RateLimiter`, `VisorLog`, `WebNodoService.*` en parciales |
| `MTBGT/…/gdscrip/ValidacionRed.gd` | Helper de la Etapa 1 (H6/M21) para validar todo `any_peer` |
| `STM_HRTS/utils/STM_UTILS/probar_red_puerto.gd` | Prueba de puerto de red (41 líneas / 0 fallos) |
| `STM_HRTS/utils/add_utils/version_unica.py` | Puerta de versión única (11 casos) |
| `STM_HRTS/utils/add_utils/publicar_version.ps1` | Guion de publicación con el arreglo de `gh` y (en diseño) el ancla del PCK |
| `STM_HRTS/__main__.py` | Punto de entrada que declara `pyproject.toml:25-27` |
| `LC_STM/STM_PRCS/` (5 ficheros) | Procesos cognitivos (actualizador de pesos, colector de sistema, visualizador) |
| `VSC#/Tests/{Ledger,PerfilEstado,PruebasEntorno,ReinicioCuenta,SmtplcUmbrales}Pruebas.cs` | Los 33 casos que llevaban xUnit de 34 a 67 |

**Causa raíz.** El snapshot vive en un directorio **nombrado por hash** (deuda **D-01** del issue #65). Un merge que trae otro directorio con otro hash no se fusiona: se suma o se sustituye. `ecb7c65` sustituyó.

**Cierre.** D10 resuelta + F0-01 ejecutada + `git diff --stat` entre el árbol restaurado y `cae205a3` vacío (o con divergencias explicadas, una por una).

### B-02 · El gate Python está en rojo por causas estructurales

**Síntoma.** `105 failed · 37 errors · 104 passed · 4 xfailed` y `tests/test_version_unica.py` ni se colecciona.

**Evidencia.**

```powershell
python -m pytest -q
# ERROR collecting tests/test_version_unica.py
# ImportError: cannot import name 'version_unica' from 'STM_HRTS.utils.add_utils'
# 105 failed, 104 passed, 4 xfailed, 37 errors
```

Y el fallo típico, que delata la causa:

```
tests\test_config_red.py:65: assert ruta.is_file(), f"fuente no encontrada: {ruta}"
E  AssertionError: fuente no encontrada: .../src/VSC#/Nucleo/RedP2P/ConfigRed.cs
```

**Causa raíz.** Es la cara visible de B-01: los tests vinieron, el código no.

**Cierre.** F0-02: `pytest` en verde (o con exclusiones **declaradas y justificadas**, nunca silenciadas con `continue-on-error`) y `test_version_unica.py` coleccionando.

### B-03 · El PCK está congelado en la 2.7.4 — el binario publicado no lleva el mundo

**Síntoma.** Cuatro releases publicadas sobre el mismo mundo.

**Evidencia.**

```powershell
(Get-FileHash VSC#/wvp3d.pck -Algorithm SHA256).Hash
# ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14   (114.591.724 B)
(Get-Item VSC#/wvp3d.pck).LastWriteTime    # 30/10/2026 02:24
```

Y la propia documentación lo confirma: `STM_DOC/notas_v2.7.7.md:10` declara ese mismo digest como «PCK embebido» de la 2.7.7, y `STM_DOC/Otros_documentos/README_peso_repositorio_20261030.md:294` lo identifica como **el PCK de la 2.7.4**.

**Impacto.** Todo cambio en `MTBGT/**/*.gd` desde el 2026-10-30 (incluido el endpoint LAN dinámico de H3 y la validación `any_peer` de la Etapa 1) **no está en ningún binario publicado**. La autoprueba lo confirma: `--startup-selftest` informa `[OK] PCK íntegro (extraído = embebido) · embebido=109,3 MiB` — íntegro, pero viejo: comprueba que el PCK extraído coincide con el embebido, **no** que corresponda a este commit.

**Cierre.** F3-01 y F3-02: PCK reexportado del árbol canónico, `pck_sha256` registrado en `VERSION.json`, y **ancla verificada** en el guion de publicación con su prueba negativa.

### B-04 · La evidencia forense de R-01 se borró y el manifiesto quedó huérfano

**Síntoma.** La cuarentena no contiene muestras.

**Evidencia.**

```powershell
Get-ChildItem STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106
# MANIFIESTO.md   (3264 B)  — única entrada
git log --diff-filter=D --oneline -- "*cuarentena_r01*"
# ecb7c65 adDev   → borra fa-brand-400.orc, opencode_init, transport.py
```

**Impacto.** La regla del proyecto es «cuarentenar, no borrar: conservar evidencia forense» (`README_DESARROLLO.md §17.2.f`). Hoy el manifiesto describe muestras que ya no existen, así que `python -m STM_HRTS.STM_DEF cuarentena --verificar` no puede dictaminar «INTACTA». Además, el propio manifiesto **dispara la puerta de seguridad** (contiene el literal `runOn: folderOpen`).

**Cierre.** F1-03: decisión escrita sobre el destino de la evidencia (¿fuera del repo versionado, en un archivo cifrado y firmado?) y `cuarentena --verificar` con veredicto coherente.

### B-05 · Dos fuentes de verdad (puertos y versión) y el visor se autobloquea

**Síntoma.** El árbol no tiene una sola tabla de puertos ni una sola versión, y el hook de arranque bloquea el visor por su propia documentación.

**Evidencia.**

| Elemento | Hoy |
|---|---|
| Tabla de puertos | `Red.gd:6` → `const PUERTO_WS := 8911`; `ChunkManager.gd` repite el literal; `ConfigRed.cs` **no existe** |
| Versión | literal `2.7.8` en `Visor3D.csproj:27-29` y `VisorLinux.csproj:10`; `VERSION.json` **no existe** |
| Hook de arranque | `VSC#/Seguridad/ArranqueSeguro.cs:57-70` ejecuta `python -m STM_HRTS.STM_DEF arranque`; ese comando devuelve **1** porque el escaneo encuentra los IOC en `STM_DOC/**` → el visor **no abriría** en un árbol de desarrollo |

**Cierre.** F0-04 (una tabla, una versión) y F1-02 (allowlist correcta y gate verde).

### B-06 · No hay CI en la raíz

**Evidencia.** `Test-Path .github` en la raíz del repositorio → `False`. El único workflow (`STM_HRTS/.github/workflows/ci.yml`, 3.843 B) está anidado y GitHub Actions no lo descubre (**DT-01**).

**Impacto.** Nada de lo anterior se habría detectado solo. La 2.7.8 se publicó con el árbol rojo.

**Cierre.** F2-01 y F2-02: workflow en la raíz, verde, con puertas bloqueantes.

### B-07 · Las pruebas afirman contra el texto de la fuente

**Evidencia.** `test_config_red.py:65` (`_leer`), `test_stage1_s1_identidad.py:39` (`assert 'const DOMINIO_PRUEBA := …' in contenido`), `test_h2_h3_red.py:18-65`, y los «no supera N líneas» de `test_comandos.py:61-63`, `test_escucha.py:96-98`, `test_memoria.py:68-70`, `test_perfil.py:70-72`.

**Impacto.** Cualquier refactor rompe la suite sin cambiar conducta (**D-06/U-07**). Es lo que convirtió B-01 en 105 fallos en lugar de 3.

**Cierre.** F7-02: migración progresiva a pruebas de conducta; mientras tanto, prohibido añadir asertos nuevos sobre literales de código.

### B-08 · La puerta de pruebas de Godot no puede ejecutarse

**Síntoma.** Los 22 casos parametrizados de `tests/godot/test_headless.py` fallan nada más empezar. No es que falte el motor: falla la importación del contrato.

**Evidencia.**

| Símbolo que usa la puerta | Dónde | ¿Existe en `herramientas.py` (248 líneas)? |
|---|---|---|
| `herramientas.emite_veredicto` | `test_headless.py:180`, `medicion_modos.py:48` | **No** |
| `herramientas.PCK_OBLIGATORIO` | `medicion_modos.py:82` | **No** |
| `herramientas.MODO_ARBOL` / `MODO_PCK` / `entorno_aislado` | `medicion_modos.py:54, 91, 96-97` | **No** |
| `rutas.USER_DATA_DIR` | `medicion_modos.py:64, 93` | **No** |
| `Herramienta.montar_pck` (campo del dataclass) | `test_headless.py:194` | **No** |
| Guion `probar_red_puerto` en la lista `PRUEBAS` | `test_headless.py:130` | El `.gd` **no existe** en `STM_UTILS/` (se perdió con B-01) |

**Causa raíz.** La puerta se escribió contra una versión de `herramientas.py` que **no es la de este snapshot**: la de la zona unificada. Es la misma historia que B-01, un nivel más abajo: el *arnés* vino, la *utilidad* no.

**Impacto.** El mundo (`MTBGT/`) no tiene ninguna prueba ejecutable. DT-05 sigue abierto y la frase «suite Godot 201/201» que aparece en issues y documentación **no es verificable aquí**.

**Cierre.** F0-06: o se restaura el `herramientas.py` de la zona, o se reescribe la puerta contra el contrato real. En ambos casos: 22 casos ejecutados y con veredicto, y `probar_red_puerto.gd` recuperado.

---

## 4. Lo que sí está sano (no tocar, reutilizar)

| Activo | Estado medido | Uso en el plan |
|---|---|---|
| `STM_HRTS/STM_DEF/` (14 módulos, ~2,7 k líneas) | Completo y coherente: `iocs`, `deteccion`, `historial`, `monitor`, `integridad`, `blindaje`, `cuarentena`, `motor`, `arranque`, `servicio`, `firma_release` | Base de F1. Solo se corrige la allowlist y se conecta al CI |
| `tests/test_stm_def.py` (52 casos) | Escrito con `tmp_path` (88 usos), **no** toca `hosts` real | Puerta de F1 una vez re-medido |
| `VSC#/Seguridad/ArranqueSeguro.cs` + `App.xaml.cs:89` | Hook fail-closed ya cableado, con *fail-open* si no hay intérprete | Se conserva; se arregla su causa de bloqueo (B-05) |
| Binario `2.7.8` (dev build) | Extrae motor (172,5 MiB) y PCK (109,3 MiB); marcador de versión correcto; baliza UDP 8912 detecta el nodo | Sirve para las autopruebas de F0/F3 |
| Portal WebNodo | `WebNodoService.cs` (926 líneas) con `/api/info`, `/descargar`, proxy TCP y WebSocket | F4 |
| `VisorLinux/` (22 ficheros) | Avalonia 11; la v2.7.8 **sí publicó asset Linux** (207.220.008 B) | F4 |
| `LC_STM/red_neuronal/` (60 ficheros, ~22,7 k líneas) | Matemática real con numpy (forward/backward/Adam, DQN/PPO/SAC, SVM/boosting); **envoltorios con ruido** en `_rn_base.py:205,261-271` | F6: decidir si se cablea o se archiva |
| Documentación | `README_DESARROLLO.md` (1.000 líneas), `REGLAS_DE_ACTUALIZACION.md` (296), `SECURITY_AUDIT/ROADMAP` | Fuente de criterios de cierre |
| `.vscode/settings.json` de la raíz | **Limpio**: ya no tiene `task.allowAutomaticTasks` ni `runOn: folderOpen` | R-01.b cerrado (confirmado en la release v2.7.8) |
| `STM_HRTS/opencode/package.json` | `"start": "./opencode.bat"`; **no hay `node init`**, y `init` no existe | Vector 2 neutralizado |
| Búsqueda de vectores | `transport.py` ausente, `*.orc` ausente | Vector 1 y 3 ausentes del árbol |

---

## 5. Decisiones

### 5.1 Nuevas

| ID | Decisión | Opciones | Recomendación | Bloquea | Límite |
|---|---|---|---|---|---|
| **D10** | Árbol canónico | (a) re-promocionar `45a1fcf` y re-aplicar `STM_DEF`; (b) re-implementar el núcleo sobre el snapshot actual | **(a)** | F0, F2–F4 | inmediata |
| **D11** | Destino de la v2.7.8 publicada | (a) dejar y anunciar; (b) marcar prerelease; (c) republicar (prohibido por R4 si ya hay descargas) | **(a)** + nota en #66 | F3 | inmediata |
| **D12** | Nombre del snapshot | (a) estable (`src/`); (b) seguir con `actualizacion_<hash>` | **(a)** | F0, F7 | 2026-11-30 |
| **D13** | Evidencia forense de R-01 | (a) archivo firmado fuera del repo; (b) mantener solo el manifiesto y declararlo | **(a)** | F1-03 | 2026-11-15 |

### 5.2 Heredadas (sin cambios, con su estado medido)

| ID | Decisión | Estado hoy |
|---|---|---|
| **D1** | ¿Persistir ledger y pesos? | Sin decidir; el cierre ya no destruye (H1 cerrado) |
| **D2** | ¿Kubo real o shim renombrado? | Sin decidir; el shim sigue devolviendo `ok=False` cuando no hay datos |
| **D3** | Meta numérica de #15 | **Sin decidir**; sigue la propuesta ≤ 250 MiB Windows |
| **D4** | ¿Reescribir #1 como WebSocket? | De hecho aplicado en el código y en la doc; falta reflejarlo en el issue |
| **D5** | ¿SMTPLC bloquea o puntúa? | **Sin decidir**; bloquea duro en `FormularioUsuarioWindow.xaml.cs:90-95` |
| **D6** | ¿Hubo fixtures reales? | Rotación hecha en H1; falta constancia |
| **D7** | Esquema de `release.json` | **Decidida**: el portal lee `{assets[]}` (W-01/DT-11) |
| **D8** | Destino del ledger de ubicación | **Sin decidir** |
| **D9** | Destino de los tres vectores R-01 | Parcial: el árbol está limpio y el vector de la raíz retirado; **falta registrar la decisión y anunciarla** |

---

## 6. Plan por fases

**Regla de oro:** una fase no empieza hasta que la anterior tiene sus puertas en verde y su evidencia archivada. La única excepción es F1-02 (allowlist), que va en paralelo a F0 porque **desbloquea el arranque del visor**.

```
F0 vuelta a verde ──┬─▶ F2 CI real ──▶ F3 PCK + release ──▶ F4 producto (#1 #15 #48)
                    │                        │
                    └─▶ F1 seguridad R-01 ───┘
                                             └─▶ F5 SMTPLC (#26) ──▶ F7 deuda estructural (#65)

Pista cognitiva (paralela, arrancó el 2026-11-09):
F8 sesión RFPRMN · IPFS · LucIA 3D (#85) ──▶ F6 LucIA (#16) ──▶ F9 LucIA anfitriona + wallet (#86, diseño)
```

### F0 — Vuelta a verde (bloqueante · 2–3 días)

**Objetivo:** que el árbol sea *construible, medible y coherente*: lo que los tests afirman existe, la versión está en un solo sitio y el gate de seguridad abre.

**Entrada:** D10 resuelta.
**Salida:** `dotnet build` + `dotnet test` + `pytest` + `STM_DEF escanear` en verde, con log archivado.

| ID | Tarea | Esf. |
|---|---|---|
| F0-01 | Restaurar el núcleo unificado desde `45a1fcf` y re-aplicar `STM_DEF` encima | L |
| F0-02 | Poner `pytest` en verde y decidir qué se excluye (con motivo escrito) | L |
| F0-03 | Re-medir `test_stm_def.py` en un entorno con `tmp_path` usable (aquí los 33 errores son del sandbox `0700`, §2.3) y archivar la salida | S |
| F0-04 | Una sola tabla de puertos y una sola versión | M |
| F0-05 | Devolver `Visor3D.sln` y comprobar build + xUnit | S |
| F0-06 | Reparar la puerta de Godot: `herramientas.py` y `probar_red_puerto.gd` (B-08) | M |

### F1 — Seguridad y R-01 (issue #69, #66 · 2 días)

**Objetivo:** que la puerta de seguridad abra **de verdad**, que su causa de falso positivo no pueda repetirse y que la decisión D9 quede escrita y anunciada.

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| F1-01 | Corregir la allowlist de `STM_DEF` (rutas nuevas de `STM_DOC`) y sacar el `runOn` de `publish_release_v278.ps1` | S | ✅ **hecho** |
| F1-02 | `escanear` → 0 hallazgos; `arranque` → exit 0; `puerta` → ABIERTA | S | ✅ **hecho** |
| F1-03 | Resolver D9 y D13: evidencia forense y `cuarentena --verificar` coherente | S | pendiente |
| F1-04 | Nota de incidente en #66 y #69 (con el estado real, no el de noviembre 5) | S | pendiente |
| F1-05 | Conectar `firma_release.py` (Ed25519) al OTA real | L | pendiente |
| F1-06 | Gobernanza: firma de commits, 2FA, rotación, protección de rama | M | pendiente |
| F1-07 | Restaurar la validación `any_peer` en GDScript (`ValidacionRed.gd`) y cerrar los RPC abiertos (§Anexo E.2) | L | pendiente |
| F1-08 | `blindar()`: resolver DNS **antes** de envenenar `hosts` (§Anexo E.1-3) | S | pendiente |
| F1-09 | Vigilancia de DoH, IP literal y SNI en `monitor.py` (§Anexo E.1-6) | M | pendiente |

**Evidencia de F1-01/F1-02 (2026-11-07).**

```
python -m STM_HRTS.STM_DEF escanear  ->  0 hallazgos | veredicto: LIMPIO        exit 0
python -m STM_HRTS.STM_DEF arranque  ->  ARRANQUE: PERMITIDO                    exit 0
python -m STM_HRTS.STM_DEF puerta    ->  PUERTA: ABIERTA (sin bloqueos)         exit 0
```

Cambios: `rutas_ignoradas.txt` con las siete rutas reales; `deteccion.allowlist_obsoleta()` +
`hallazgos_allowlist()` (un hallazgo MEDIA por entrada que ya no existe, así el CI lo detecta sin
bloquear el arranque del visor); `motor.escanear()` los incorpora; dos pruebas nuevas y la que fijaba
la ruta vieja corregida; notas de release movidas de `publish_release_v278.ps1` a `notas_v278.md`
(verificado: el texto renderizado es **idéntico carácter a carácter** al cuerpo publicado de la v2.7.8,
2131 caracteres, y el script parsea con 0 errores).

### F2 — CI real en la raíz (DT-01, DT-10, DT-15 · 1–2 días)

**Objetivo:** que nada de lo anterior pueda volver a romperse en silencio.

| ID | Tarea | Esf. |
|---|---|---|
| F2-01 | `.github/workflows/ci.yml` en la raíz con `resolver-taller` (localiza `src/` por `VERSION.json`) | M |
| F2-02 | Jobs bloqueantes: build + xUnit, pytest estricta, 6 selftests con entorno temporal, `STM_DEF puerta` | M |
| F2-03 | Job Godot headless en modo «informativo» hasta que exista `GODOT_BIN` en el runner | S |
| F2-04 | `pytest.ini` robusto fuera de `src/` (DT-10) | S |

### F3 — PCK fresco y release coherente (RU5 · 2–3 días)

**Objetivo:** que el próximo binario **contenga** el mundo y que la release nazca de un commit.

| ID | Tarea | Esf. |
|---|---|---|
| F3-01 | Reexportar `wvp3d.pck` del árbol canónico y registrar su SHA-256 | M |
| F3-02 | Ancla del PCK en el guion de publicación + prueba negativa | M |
| F3-03 | Checklist §7 de `REGLAS_DE_ACTUALIZACION.md` completo, con evidencia | L |
| F3-04 | OTA de punta a punta en un equipo con la versión anterior (R13) | M |
| F3-05 | Release nueva desde un commit, con `release.json` + `SHA256SUMS` + Windows + Linux | M |

### F4 — Verificación de producto (#1, #15, #48 · 4–5 días)

| ID | Tarea | Esf. |
|---|---|---|
| F4-01 | Prueba LAN con dos equipos reales (DT-04), con capturas y `--red-selftest` por máquina | M |
| F4-02 | IPv6 literal `[fe80::1]:9000` en `DescubrimientoP2P.cs` (DT-09) | S |
| F4-03 | Mensajes de error de conexión comprensibles y doc de firewall al transporte WebSocket | S |
| F4-04 | Métrica de huella instalada (binario + runtime + motor + PCK) y desglose por tipo | M |
| F4-05 | Política de assets (D-02 de #65): LFS, fuera de Git o peso aceptado con número | M |
| F4-06 | `EnableCompressionInSingleFile` medido antes/después (D3) | M |
| F4-07 | DT-06, DT-07, DT-08, DT-13, DT-14, DT-16 | L |
| F4-08 | `--webnodo-selftest` y `--update-selftest` en verde sobre el binario nuevo | S |
| F4-09 | Arreglar `Personalizacion.gd:952` y los otros dos sitios con el mismo patrón | S |
| F4-10 | Fugas de memoria y topes por isla en GDScript (§Anexo E.2) | M |
| F4-11 | Empaquetado de `gltfimport/`: los `.gltf`/`.bin` referenciados están en UTF-16LE con BOM | M |
| F4-12 | Sacar a log los `catch { }` mudos de las rutas críticas (OTA, red, extracción) | M |

### F5 — SMTPLC (#26 · bloqueado por D5/D8)

| ID | Tarea | Esf. |
|---|---|---|
| F5-01 | Cerrar D5 (¿bloquea o puntúa?) y D8 (¿ledger se integra, degrada o elimina?) | — |
| F5-02 | Proveedores tras interfaces (`INetworkEnvironmentProvider`, `ISystemInfoProvider`) para pruebas sintéticas | L |
| F5-03 | Vault a AEAD (`vault_openrouter.py` hoy es XOR sin MAC, con semilla hardcodeada) | M |
| F5-04 | Lista blanca/apelación o ausencia documentada | M |
| F5-05 | Huella Wi-Fi con BSSID real | S |
| F5-06 | Falso positivo de VM en equipos físicos con Hyper-V/VBS/WSL2 (§Anexo E.5) — ✅ **hecho** el 2026-11-07 | S |

### F6 — LucIA (#16)

> **Nota 2026-11-09:** la pista cognitiva arrancó por delante de F6 (ver F8, issue #85): LucIA ya tiene puente de comandos real (`LucIAPuenteComandos`) conectado a IPFS. Las tareas F6-01…F6-04 siguen pendientes sobre el árbol canónico; el puente nuevo es el activo que F8-01/F8-02 blindan antes de tocarlo más.

| ID | Tarea | Esf. |
|---|---|---|
| F6-01 | Recuperar `LC_STM/STM_PRCS/` y decidir si se cablea o se archiva | M |
| F6-02 | Reparar `LC_STM/red_neuronal/SLRN/_sl_math.py` (`math` sin importar; `cosine_decay` anidada) | S |
| F6-03 | Quitar los envoltorios que fabrican métricas falsas (`_rn_base.py:205,261-271`, `SL6.py:177-178`) | S |
| F6-04 | Arreglar el `pyproject.toml` (entry points inválidos, `readme` inexistente, dependencias sin declarar) | S |

### F7 — Deuda estructural (#65)

| ID | Tarea | Esf. |
|---|---|---|
| F7-01 | Renombrar el snapshot a una ruta estable (D12) | M |
| F7-02 | Migrar pruebas de texto a pruebas de conducta | XL |
| F7-03 | Regenerar manifiestos obsoletos y limpiar duplicados (`duplicados_utils_flat/`) | S |

### F8 — Pista cognitiva: sesión 2026-11-09 (issue #85) · parcialmente ejecutada

**Objetivo:** LucIA conectada de verdad — refactor propio (RFPRMN), pesos e intercambio por IPFS real y un chat 3D que responde ejecutando comandos.

**Estado:** la mitad «hecha» está hecha (y ya en `origin/main` vía PR #78); la mitad «deuda» es nueva. No toca el árbol canónico de F0–F4: vive en `DevDeepSeekHarnessIA`, fusionada a `DevQoderIA` el 2026-11-09.

**Implementado (2026-11-09, evidencia en #85):**

| Pieza | Detalle |
|---|---|
| RFPRMN v2.24.0 | 29 submódulos ≤ 450 líneas · 381 símbolos · 399 pruebas · ruff limpio · CI Ubuntu + Windows |
| IPFS real | Kubo 0.43.1 (`STMIPFS/ipfs.exe`, ignorado por git); `STMIPFS/nodo/` con rutas, binario, repositorio, daemon, cliente API v0 y pesos (zip + SHA-256) |
| Conexión | `LucIAIPFS` en `mainLCSTM.py`: `.modelos` ↔ IPFS, arranque/cierre del nodo; repositorio único con `adoptar_legado()` |
| Servidor 3D | `LucIAServidor3D`: arranca `servidor_lucia.py` como proceso y habla su NDJSON |
| Puente de comandos | `LucIAPuenteComandos`: autoconocimiento + intención + ejecución con el agente |
| Modelos | `ollama create` para GGUF, descarga reanudable, política de descartes |
| Verificación | 399 pruebas (18 de IPFS + 7 de unificación); E2E real del chat antes/después (capturas en `docs/img/lucia-3d/`) |

**Deuda nueva (cada ítem de #85 §2 es una tarea):**

| ID | Deuda | Esf. |
|---|---|---|
| F8-01 | `servidor_lucia.py` vive fuera de control de versiones (el proyecto Godot de 715 MB no está versionado). Versionar solo `puente_3D/` (~4 ficheros, ~20 KB) y decidir LFS para los 124 MB de `lucia3D` | M |
| F8-02 | El puente no tiene pruebas: 6–8 casos de `LucIAPuenteComandos` con agente falso inyectado (sin Ollama) | M |
| F8-03 | Detección de intención por palabras clave («no quiero que refactorices nada» activaría la acción): negación corta o clasificador `seq2seq` | S |
| F8-04 | `_ruta_en()` heurístico (regex + búsqueda por nombre en 5 carpetas): pedir la ruta siempre o `git ls-files` + fuzzy | S |
| F8-05 | La ejecución bloquea el hilo del chat: hilo con `presupuesto_segundos` y eventos `estado` intermedios | M |
| F8-06 | `autoanalisis()` devuelve `Path` → `TypeError` al serializar (`json.dumps`): `default=str` o tipos planos | S |
| F8-07 | Paquete de pesos (`pesos.zip`) sin cifrar y CID público: documentar la decisión o cifrar con la clave del usuario | S |
| F8-08 | Tres variables de entorno del nodo (`WOLD_IPFS_BIN`, `IPFS_PATH`, `WOLD_IPFS_DATOS`…): `.env.example` propio de `STMIPFS` | S |
| F8-09 | `importar_agente()` devuelve la clase, no una instancia (bug real ya mordió): renombrar a `clase_agente()` o devolver instanciado | S |
| F8-10 | `ziva_agent` desactivada (Ziva v3.3.6, godot-cpp 4.2, crashea Godot 4.7.2): informe de deuda de `lucia3D` sin `ziva_agent` | S |

**Pendientes de la sesión (checklist de #85 §3):** versionar `puente_3D/`, pruebas del puente, presupuesto en el chat, `seq2seq` con corpus real de refactors, cifrado del paquete de pesos (si se decide), informe de deuda de `lucia3D`, y limpiar el repo raíz (`probe2/`, `bt_*`, `.pytest_cache/` ensucian `git status`).

### F9 — LucIA anfitriona y wallet embebida (discusión #86 · diseño cerrado 2026-11-09 · v1 implementada 2026-11-09, parcial)

**Naturaleza:** diseño **cerrado** el 2026-11-09; **primera implementación (v1) hecha el 2026-11-09 sobre las tres pistas** (Godot, VSC#, STM_BKCH), **con la puerta de robustez F9-00 pasada el 2026-11-09** (100 altas, 4 escenarios). Las preguntas D14–D18 ya están decididas (tabla de abajo); genera las tareas F9-00…F9-08, con la puerta F9-00 delante. Idea fuerza: **«una cuenta = un bloque = un archivo»**.

**Implementado en v1 (2026-11-09):** LucIA anfitriona antes del carrusel con formulario nuevo (`gdscrip/LuciaRecepcion.gd` + `Boot.gd`), endpoint `POST /alta-cuenta` en BKSVCB con cuota «un bloque por PC» sobre la huella **comprometida** y **cuota SMTPLC por ubicación conectada** (`ubicacion_hash` de 64 hex, tope 3 cuentas + cooldown 72 h, `STM_BKCH/BKSVCB.py::_cuota_ubicacion`; puerta F9-00 pasada con 100 altas), sustitución de rol del botón «Conectar» → «Validar conexión» (`MainWindow.xaml(.cs)`) y ventana de migración `MigracionCuentaWindow` (llave + hash PC + semilla → `cuenta.json` en `.zip`). **Pendiente (honesto):** el circuito de la cuota por ubicación **ya está cerrado**: el visor C# captura la firma SMTPLC al arrancar y escribe `user://ubicacion_smtplc.json` antes de lanzar Godot (`MainWindow.GuardarUbicacionSmtplcAsync`, límite 5 s), Godot `LuciaRecepcion.gd` lo lee y lo envía en el alta, y `MigracionCuentaWindow.xaml.cs` también lo lee y lo envía; queda validador estricto de esquema, decisión Hashcash (F9-02) y `clave_publica` (F9-03), empaquetador AES-GCM (F9-05, hoy el `.zip` solo lleva `cuenta.json` público) y pin IPFS (F9-08).

- LucIA deja de ser un chat y pasa a **recibir**: es la anfitriona del registro en su oficina, no un modal.
- La wallet deja de ser un formulario y pasa a ser **un archivo en el PC** del usuario.
- El alta lo emite la cadena: el `blockchain-server` mina un bloque por alta y devuelve un **hash único de cuenta**.

**Flujo de usuario nuevo:** entra → LucIA lo recibe y propone registro → el cliente pide el alta → el servidor mina un bloque (datos públicos, sin datos personales) y devuelve el hash → el usuario descarga un `.zip` (su cuenta; si lo pierde, la pierde, y hay que decírselo a la cara).

**Migración de usuarios existentes:** el formulario nuevo sustituye las tres piezas de hoy (`.zip` + llave de acceso + frase semilla) por **un único hash privado de cuenta** guardado en el PC.

**Contenido del `.zip` (v1):** `cuenta.json` (hash de cuenta = hash del bloque, índice, red, fecha, clave pública) · `llave.enc` (AES-GCM con clave derivada de la contraseña del usuario) · `registro.json` (huella **comprometida**, no la cruda) · `LEEME.txt`. Sin frases semilla en claro ni llaves privadas sin cifrar.

**Robustez:** huella de máquina (ya existe `MaquinaHuellaDigital`, HKDF-SHA256), cuota por ubicación (ya existe `LocationAccountLedger` SMTPLC), un bloque por alta (PoW ligera, pero **el PoW lo paga el servidor**, así que el coste anti-sybil real es la cuota por ubicación + la huella, no el PoW), límites por hardware y no por IP, reputación gradual, prueba de vida sin biometría. Meta realista: **«caro y detectable»**, no «imposible». Riesgos declarados: las VM se clonan, las huellas se falsean, todo límite acaba teniendo mercado.

**Base existente (no se parte de cero):** `blockchain-server` (`STM_BKCH/BKSVCB`), ledger de cuentas y persistencia de pesos, `Seguridad/` (bip39, sesión, huella), el chat 3D de LucIA conectado a su máquina de comandos (F8) y el nodo IPFS (`STMIPFS/nodo`) para guardar el `.zip` y dar su CID.

**Decisiones cerradas 2026-11-09 (fundamentadas en el código actual):**

| ID | Decisión | Por qué (ancla en el árbol) |
|---|---|---|
| D14 | **El bloque se mina en el servidor.** | `CelebroBlockchain.minar_transacciones_pendientes()` ya lo hace (`STM_BKCH/BKSVCB.py:215`). Minar en el cliente exigiría portar el PoW doble-SHA256 a C#/GDScript y permitiría pre-minar sin pasar por el ledger. El servidor aplica la cuota SMTPLC **antes** de minar y mantiene el ledger autoritativo. Consecuencia honesta: el PoW lo paga el servidor, así que **el coste anti-sybil no es el PoW sino la cuota por ubicación + la huella**; el PoW queda como ritmo anti-spam (1 bloque = 1 alta, serializado por el `lock`). Anti-bot opcional: desafío Hashcash ligero del cliente (decide F9-02). |
| D15 | **v1 sin recuperación social.** | El `.zip` **es** la cuenta; `LEEME.txt` lo dice a la cara. El material de recuperación viaja en un fichero aparte (`recuperacion.enc`) para que v2 pueda añadir custodia dividida (Shamir 2-de-3: IPFS + contacto + servidor) sin rediseñar. Nunca se guarda semilla ni clave privada en claro en el servidor. |
| D16 | **El hash privado en claro solo en la PC; en el `.zip` cifrado.** | En claro vive únicamente en memoria + almacén protegido de `LocalAppData` (mismo patrón que `LocationAccountLedger`, `VSC#/Seguridad/SMTPLC/LocationAccountLedger.cs:27`). En el `.zip` va `llave.enc` = AES-GCM con clave derivada de la contraseña del usuario. `cuenta.json` (público) sí va en claro. |
| D17 | **La huella cruda se queda local; a la cadena va un compromiso derivado.** | `MaquinaHuellaDigital.Obtener()` (`VSC#/Seguridad/Seguridad_sesion_unica/MaquinaHuellaDigital.cs:31`) ya devuelve HKDF-SHA256 no invertible, pero es vinculante entre cuentas. Se deriva por cuenta `huella_comprometida = HKDF(huella, salt = hash_cuenta + nonce)` para que dos cuentas en la misma máquina no compartan identificador. El clúster de ubicación (MAC del gateway, clúster Wi-Fi, IP — ya capturado por `LocationFingerprinter`) se sube **hasheado** (`ubicacion_hash`), nunca en crudo. La cuota se aplica en el servidor sobre ese hash. |
| D18 | **Migración caso a caso, con prueba de posesión.** | Tiene `.zip` + contraseña → migra normal (la semilla se sustituye por el hash). Tiene `.zip` sin llave → migra demostrando posesión del `.zip` + máquina. Sin `.zip`, sin llave y sin semilla → **no migra** (es la pérdida declarada en D15). Ventana de gracia solo si conserva la máquina y coincide la ubicación SMTPLC, y aun así marcada como vía débil con cooldown. Si se permitiera migrar sin nada, el hash único no tendría dientes. |

**Formato del bloque de alta (tx `ALTA_CUENTA`):**

```json
{
  "tipo": "ALTA_CUENTA", "emisor": "<nombre_cuenta>", "receptor": "CELEBRO_P2P",
  "cid_ipfs": "<cid del .zip, opcional en v1>",
  "datos": {
    "huella_comprometida": "<64 hex>", "ubicacion_hash": "<64 hex>",
    "clave_publica": "<hex, si ECDSA/Ed25519>", "red": "WoldVirtualP2P3D", "fecha_alta": "ISO8601Z"
  }
}
```

**El hash único de cuenta = `hash_bloque` del bloque que contiene la tx de alta** («una cuenta = un bloque = un archivo»), producido por `minar_transacciones_pendientes()` (dificultad 2, doble SHA-256, ya implementado). El `id_tx` es el identificador interno; el hash de cuenta es el hash del bloque.

**Formato del `.zip` (final v1):**

```
cuenta-<hash_bloque>.zip
├── cuenta.json      # en claro: hash de cuenta, índice del bloque, red, fecha, clave_pública
├── llave.enc        # AES-GCM(clave privada, clave derivada de la contraseña)
├── registro.json    # huella_comprometida (no la cruda) + metadatos del alta
└── LEEME.txt        # qué es, cómo se recupera, qué pasa si se pierde
```

**API — endpoint nuevo `POST /alta-cuenta`** (sobre el servidor `127.0.0.1:8545` de `STM_BKCH/bksvcb_net.py`): (1) valida el esquema y rechaza campos desconocidos — hoy `/transaction` (`bksvcb_net.py:48`) no valida nada; (2) aplica la cuota SMTPLC (`ubicacion_hash` + `huella_comprometida`) **antes** de encolar; (3) `agregar_transaccion("ALTA_CUENTA", …)` + `minar_transacciones_pendientes()`; (4) responde `201 {cuenta_hash, indice, cid_ipfs}`.

**Hallazgos de seguridad que se cierran antes de implementar (medidos hoy):**

1. `do_POST /transaction` no autentica ni valida esquema; acepta `emisor`/`receptor`/`datos` arbitrarios. El alta exige esquema estricto + rechazo de campos extra.
2. El servidor es localhost-only; en cuanto el visor (otro proceso) lo consuma hay que fijar el binding y, si se expone, autenticar (el token de sesión ya existe en `Seguridad`).
3. La cadena es **single-node** hoy (consenso PoNL local, sin multi-nodo real). El hash único es fuerte contra manipulación local (PoW + HMAC del ledger), no contra un nodo que reforge el ledger. v1 asume nodo local + pin IPFS del ledger como ancla; la distribución real es deuda futura.
4. `cuenta.json` público no debe llevar `clave_publica` si se prioriza desvinculación; decide F9-03 (privacidad vs verificabilidad).

**Tareas F9 (la puerta va delante):**

| ID | Tarea | Esf. | Bloqueada por |
|---|---|---|---|
| F9-00 | **Puerta de robustez multi-cuenta (prueba, no código):** intentar 100 altas desde la misma máquina/ubicación y demostrar que la cuota SMTPLC frena en el límite (2–3 por ubicación) con cooldown — **PASADA 2026-11-09:** mismo PC 1/100 (409), misma ubicación 1/100 (429 cooldown 72 h), tope sin cooldown 3/100 (409), 100 ubicaciones distintas 100/100 | M | — (puerta previa a todo) |
| F9-01 | Esquema de `datos` de `ALTA_CUENTA` + validador (rechazo de campos extra) | S | F9-00 |
| F9-02 | Decidir anti-bot: desafío Hashcash del cliente sí/no | S | F9-00 |
| F9-03 | Decidir `clave_publica` en `cuenta.json` (verificabilidad vs desvinculación) | S | F9-00 |
| F9-04 | Endpoint `POST /alta-cuenta` en BKSVCB con cuota SMTPLC previa al minado | M | F9-01 |
| F9-05 | Empaquetador del `.zip` (AES-GCM + derivación de clave) en `Seguridad/` | M | F9-01, F9-03 |
| F9-06 | Flujo LucIA anfitriona: escena de recepción + diálogo de registro (Godot, `puente_3D/`) | L | F9-04, F9-05 |
| F9-07 | Migración de usuarios existentes (formulario → hash único) | M | F9-04, F9-05 |
| F9-08 | Pin IPFS del `.zip` (opcional v1) y `LEEME.txt` «a la cara» | S | F9-05 |

**Qué NO se hace todavía:** no se toca el ledger actual hasta F9-01 (formato del bloque definido); no se pide migrar a nadie antes de F9-07; no se implementa **nada** sin pasar F9-00 (prueba de robustez multi-cuenta). Sin recuperación social en v1 (D15), sin consenso multi-nodo (deuda futura), sin custodiar claves en el servidor.

---

## 7. Backlog detallado

### 7.1 F0-01 · Restaurar el núcleo unificado

**Por qué.** Sin él, 68 tests no pueden pasar, no hay `.sln`, no hay fuente única de versión y el endurecimiento de la Etapa 1 no está en el producto.

**Pasos.**

1. Etiquetar el estado actual antes de tocar nada:
   `git tag respaldo/4e0f1cf6-antes-de-restaurar`.
2. Inventariar la diferencia **fichero a fichero** (no solo los 107 paths) y clasificar cada uno como *perdido*, *movido* o *sustituido por versión peor*:
   ```powershell
   git show 45a1fcf:.../cae205a3/src/VSC#/Nucleo/RedP2P/ConfigRed.cs   # ¿qué aporta?
   ```
3. Restaurar en una rama (`fix/restaurar-nucleo`), **nunca directamente en `main`**:
   ```powershell
   git checkout 45a1fcf -- "VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src/VSC#/Nucleo"
   ```
   y reubicar al snapshot actual.
4. Re-aplicar encima las piezas nuevas que sí valen (STM_DEF se queda; la reorganización de `STM_DOC` se conserva).
5. Verificar que no vuelve ningún vector de R-01 (`git status` + `STM_DEF escanear`).
6. `dotnet build Visor3D.sln` → 0 errores, 0 advertencias. `dotnet test` → 67/67.

**Criterio de aceptación.**
- `VSC#/Nucleo/` con sus 29 ficheros, `VERSION.json`, `Directory.Build.*`, `Visor3D.sln`, `version_unica.py`, `ValidacionRed.gd`, `probar_red_puerto.gd`, `STM_HRTS/__main__.py` y `LC_STM/STM_PRCS/` presentes.
- `python -m STM_HRTS.utils.add_utils.version_unica --comprobar` → OK.
- `dotnet build` y `dotnet test` en verde, con log adjunto.

**Riesgo.** Reintroducir código que en su día se retiró por seguridad. **Mitigación:** los vectores están identificados por IOC; `STM_DEF escanear` + `escanear` del historial antes de fusionar (regla §15.3.7 del README de desarrollo).

**Esfuerzo.** L.

### 7.2 F0-02 · Poner `pytest` en verde

**Pasos.**

1. Con F0-01 hecho, re-ejecutar y comparar con la línea base de la §2.3.
2. Triar los fallos restantes uno a uno en una tabla `test → causa → decisión` (`arreglar` / `excluir con motivo` / `borrar`).
3. Prohibido `continue-on-error` y prohibido `--ignore` silencioso: si algo se excluye, va en `pytest.ini` con un comentario y en la tabla del punto 2.
4. Añadir `tests/test_h1_contencion.py:240`, que exige `STM_HRTS/utils/test_user_data` (ruta ausente).

**Criterio de aceptación.** `python -m pytest -q` → 0 failed, 0 errors, y la tabla de exclusiones con ≤ 5 entradas, cada una con motivo escrito.

**Esfuerzo.** L.

### 7.3 F0-04 · Una tabla de puertos y una versión

**Evidencia del problema.** `Red.gd:6` (`const PUERTO_WS := 8911`), `ChunkManager.gd` repitiendo el literal, `Construccion.gd:1495` con «IP:8911» en prosa, y `2.7.8` escrito a mano en dos csproj.

**Pasos.**

1. Restaurar `ConfigRed.cs` (tabla C#) y la constante de `Red.gd`, con el gate `test_config_red.py` que las compara const por const.
2. Restaurar `VERSION.json` + `Directory.Build.props/targets` y eliminar los literales de los csproj (`<Version>2.7.8</Version>` sale; entra `$(WoldVersion)`).
3. Corregir la prosa de UI que aún anuncia 8911 (`VentanaPrincipal.Mundo`, `VentanaPrincipal.Red`, `Construccion.gd:1495`).

**Criterio de aceptación.** `test_config_red.py` en verde; `version_unica --comprobar` OK; prueba negativa: inyectar `<Version>2.7.5</Version>` en un csproj hace fallar la puerta (exit 1).

**Esfuerzo.** M.

### 7.4 F1-01 · Allowlist de `STM_DEF`

**Evidencia.** `STM_DEF/rutas_ignoradas.txt` lista `tests/test_stm_def.py` y `README_DESARROLLO.md`. La segunda ruta **no existe** en `src/` (el documento está en `STM_DOC/Desarrollo/`), así que la exclusión es un no-op. Resultado: 26 hallazgos ALTA, de los cuales 25 son documentación y **1 es un script**.

**Hallazgos por fichero (medido).**

| Fichero | Hallazgos |
|---|---:|
| `STM_DOC/Desarrollo/README_DESARROLLO.md` | 11 |
| `STM_DOC/procedimiento_R01b_propietario_20261106.md` | 6 |
| `STM_DOC/informe_r01b_auditoria_20261106.md` | 5 |
| `STM_DOC/issue_deuda_v2.7.7.md` | 2 |
| `STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/MANIFIESTO.md` | 1 |
| `STM_HRTS/utils/add_utils/publish_release_v278.ps1:80` | 1 |

**Pasos.**

1. Añadir a la allowlist las rutas **nuevas** de documentación; mantener la regla «nunca código ejecutable» y por tanto **no** silenciar el `.ps1`.
2. Sacar las notas de release del `.ps1` a un `.md` de datos que el guion lea: así el script deja de contener los IOC y la allowlist no crece.
3. Añadir al escáner una comprobación de que **toda entrada de la allowlist existe** (si no existe, es un error, no un aviso). Eso convierte este fallo en imposible de repetir.
4. Añadir el test correspondiente y actualizar `tests/test_stm_def.py:373`, que hoy fija la ruta equivocada.

**Criterio de aceptación.** `escanear` → 0 hallazgos / LIMPIO / exit 0; `arranque` → PERMITIDO / exit 0; `puerta` → ABIERTA / exit 0; y una prueba que falle si una entrada de la allowlist apunta a una ruta inexistente.

**Esfuerzo.** S.

### 7.5 F1-05 · Firma Ed25519 en el OTA

**Estado.** `STM_DEF/firma_release.py` firma y verifica (con `cryptography` o con el respaldo puro RFC 8032), pero **no está conectado** a `UpdateChecker.cs` / `UpdateDownloader.cs`.

**Pasos.**

1. Definir el contrato: `release.json` gana `firma` (base64) y `clave_id`.
2. `UpdateChecker` verifica la firma **antes** de descargar; `UpdateDownloader` verifica el digest **y** la firma antes de extraer.
3. Fail-closed: sin firma → rechazo. Añadir el caso a `--update-selftest`.
4. Documentar la rotación de clave.

**Criterio de aceptación.** `--update-selftest` cubre: sin firma (rechaza), firma inválida (rechaza), firma válida + digest válido (acepta). Exit 0 en los tres.

**Esfuerzo.** L.

### 7.6 F2-01 · CI en la raíz

**Pasos.**

1. Crear `.github/workflows/ci.yml` en la **raíz del repositorio** (hoy no existe `.github/`).
2. Reutilizar la plantilla `STM_HRTS/STM_DEF/.github/workflows/stm_def.yml` (`on: workflow_call`) para la puerta de seguridad.
3. `resolver-taller`: localizar `src/` buscando `VERSION.json` — el único modo de sobrevivir a que el snapshot cambie de nombre (D-01).
4. Jobs: `python-suite` (estricta), `csharp-build` + `dotnet test`, `selftests` (6 banderas, con `WOLD_RUNTIME_DIR`/`WOLD_LOG_DIR` temporales), `stm-def-puerta`, `godot-headless` (informativo).
5. Proteger la rama: sin CI verde no hay merge.

**Criterio de aceptación.** Un PR de prueba ve los 5 jobs; el rojo bloquea el merge.

**Esfuerzo.** M.

### 7.7 F3-01/F3-02 · PCK fresco y ancla

**Pasos.**

1. Con el árbol canónico restaurado:
   `godot --headless --path . --import` y `godot --headless --path . --export-pack "Windows Desktop" wvp3d.pck` desde `MTBGT/WoldVirtualP2P3D`.
2. `version_unica --registrar-pck` → graba `pck_sha256`, tamaño y fecha en `VERSION.json`.
3. El guion de publicación **compara** el `pck_sha256` registrado con el del PCK que se va a embeber, y **aborta** si no cuadra.
4. Prueba negativa: embeber un PCK viejo con `FileVersion` nueva → el guion devuelve exit 1.

**Criterio de aceptación.** Binario nuevo con `PCK embebido = <hash registrado>` en el log de `--startup-selftest`, y la prueba negativa documentada.

**Esfuerzo.** M.

### 7.8 F4-04 · Métrica de huella instalada (#15)

**Qué medir.**

| Componente | Cómo |
|---|---|
| Binario | tamaño del `.exe` publicado |
| Runtime extraído | `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\` |
| Motor | `godot.exe` extraído (medido hoy: 172,5 MiB) |
| PCK | extraído (medido hoy: 109,3 MiB) |
| Huella final | suma tras el primer arranque |

**Criterio de aceptación.** Tabla publicada en el README con número por componente, en Windows y Linux, y D3 resuelta con esa cifra delante.

**Datos ya medidos que orientan la decisión (Anexo E.2-G).** El peso no está en el binario: está en los assets del mundo.

| Dato | Medición |
|---|---|
| `MTBGT/` sin `.import` | 313,8 MiB |
| `gltfimport/` | **310,9 MB · 94,5 %** del árbol del mundo |
| Duplicados byte a byte (pares ≥ 500 KB) | **112 MiB · 34 %** |
| Avatares | 8 carpetas, **4 modelos** (3 tríos/parejas idénticos) |

Conclusión provisional: **la palanca de #15 es deduplicar `gltfimport/`, no recomprimir el `.exe`.** `EnableCompressionInSingleFile=false` (`Visor3D.csproj:17`) sigue sin probarse, pero el motor y el PCK ya viajan comprimidos, así que el margen esperado es pequeño.

**Esfuerzo.** M.

---

## 8. Secuencia propuesta (15 días laborables)

| Día | Trabajo | Puerta que deja verde |
|---|---|---|
| 1 | D10, D11, D12 resueltas y escritas. F1-01/F1-02 (allowlist) | `escanear` |
| 2–3 | F0-01 restaurar núcleo; revisión de seguridad del diff | `dotnet build` |
| 4 | F0-05 `.sln` + `dotnet test` | xUnit |
| 5–6 | F0-02/F0-03 triaje de pytest | `pytest` |
| 7 | F0-04 tabla de puertos y versión única | gates de config |
| 8–9 | F2-01…F2-04 CI en la raíz | CI verde |
| 10 | F1-03/F1-04 evidencia forense y nota de incidente | D9/D13 cerradas |
| 11–12 | F3-01/F3-02 PCK + ancla | PCK fresco |
| 13 | F3-03/F3-04 checklist §7 y OTA punta a punta | release verificada |
| 14 | F3-05 release nueva desde commit | release publicada |
| 15 | F4-01 prueba LAN de dos equipos | #1 cerrable |

**A partir del día 16:** F4-04…F4-08 (#15, #48), después F5 (#26) y F6 (#16).

**Pista cognitiva (paralela, no altera la secuencia):** F8 se ejecutó el 2026-11-09 en `DevDeepSeekHarnessIA` y ya está en `origin/main` (PR #78); F9 (diseño de #86) tiene D14–D18 cerradas desde el 2026-11-09 y tareas F9-00…F9-08, con la puerta de robustez F9-00 delante.

---

## 9. Protocolo de ingeniería

### 9.1 Ramas y commits

- `main` **no se toca**: refleja lo publicado. Todo va a `development`.
- Una tarea del backlog = una rama = un PR = una evidencia.
- Mensajes en **español**, con el ID del backlog (`fix(F0-01): restaurar el núcleo unificado desde 45a1fcf`).
- `git add <fichero>` **nunca** `-A`. Antes de commitear, comprobar que la lista staged no contiene `\.env$|successful_repos|\.tfvars|backend\.hcl|out\.terraform|\.tfstate|mykey|ghp_`.
- Nunca commitear `*.exe`, `*.dll`, `*.zip`, `*.pck` (regla R17).

### 9.2 Definition of Ready

Una tarea no empieza si no tiene: criterio de aceptación, evidencia exigida, ficheros afectados y dependencia resuelta.

### 9.3 Definition of Done

Código + prueba + evidencia en el PR + ficha marcada en este README + entrada en `README_DESARROLLO.md §13`.

### 9.4 Puertas que deben estar verdes antes de cada commit

```powershell
cd <src>
python -m pytest -q
python -m STM_HRTS.STM_DEF escanear
python -m STM_HRTS.utils.add_utils.version_unica --comprobar
cd VSC#
dotnet build Visor3D.sln -c Debug
dotnet test Visor3D.sln -c Debug --no-build
```

Y antes de una release, además, las seis autopruebas con entorno temporal:

```powershell
$env:WOLD_RUNTIME_DIR = "$env:TEMP\woldrt"; $env:WOLD_LOG_DIR = "$env:TEMP\woldlog"
foreach ($b in "startup","red","cuenta","chat","update","webnodo") {
  & ".\DMWoldVirtualP2P3Dv2.7.8.exe" "--$b-selftest"; "exit=$LASTEXITCODE"
}
```

### 9.5 Prohibiciones

1. Ejecutar `purgar_repositorio.ps1`, `borrar_packs_viejos.ps1`, `limpiar_cache_godot.ps1` o `Godot_abrir_y_limpiar_al_cerrar.bat` sin leerlos y sin confirmación explícita.
2. Publicar, recompilar tras publicar un digest, o tocar un tag ya publicado (R4, R14).
3. Escribir valores de secretos en cualquier fichero o log (`OPENROUTER_API_KEY`, `OPENROUTER_VAULT_PW`: solo nombres).
4. Ejecutar código sospechoso «para probarlo»: la evidencia de R-01 es **estática**.
5. Silenciar una prueba con `continue-on-error` o `--ignore` sin motivo escrito.

---

## 10. Matriz de pruebas objetivo

| Capa | Hoy | Objetivo | Puerta |
|---|---|---|---|
| Python (unidad) | 104 pasan / 105 fallan / 37 sin ejecutar | 0 fallos, 0 errores | `pytest` |
| Python (seguridad) | 26 hallazgos ALTA | 0 hallazgos, `arranque` permitido | `STM_DEF escanear` / `puerta` |
| C# (unidad) | 3 clases / 34 casos | 67 casos (recuperar las 5 clases) | `dotnet test` |
| C# (autopruebas) | startup 2 fallos, red 1 fallo | 6 banderas exit 0 | `--*-selftest` |
| Godot headless | 22 casos con `AttributeError` | 22 casos ejecutados con veredicto, en CI | `tests/godot/test_headless.py` |
| Contrato de puertos | roto | `test_config_red.py` verde | pytest |
| Versión única | roto | `version_unica --comprobar` OK + prueba negativa | pytest |
| LAN real | nunca ejecutada | 2 equipos, capturas, `--red-selftest` por máquina | manual + evidencia |
| OTA | fixture local | corte, timeout, reanudación, rollback, firma | `--update-selftest` |
| PCK | congelado 2.7.4 | hash registrado + ancla en publicación | `--startup-selftest` + guion |

---

## 11. Métricas de éxito

| Métrica | Base 2026-11-07 | Meta | Plazo |
|---|---|---|---|
| Tests Python en verde | 104 de 246 | 246 de 246 (o exclusiones justificadas) | día 7 |
| Hallazgos `STM_DEF` | 26 | 0 | día 1 |
| Casos xUnit | 34 | 67 | día 4 |
| Autopruebas en verde | 0 de 6 (2 fallos medidos en startup y red) | 6 de 6 | día 5 |
| Jobs de CI | 0 | 5 | día 9 |
| PCK alineado con el commit | no | sí, con `pck_sha256` | día 12 |
| Release desde commit | no | sí | día 14 |
| Huella instalada Windows | sin medir | medida y publicada | día 20 |
| Peso Windows | 348,19 MiB | ≤ 250 MiB o decisión D3 en contra | día 30 |

---

## 12. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Restaurar `45a1fcf` reintroduce código retirado por seguridad | Media | Alto | Etiqueta de respaldo, `STM_DEF escanear` + `historial` antes de fusionar, revisión fichero a fichero |
| R2 | Mergear dos árboles con hash distinto vuelve a «ganar» el equivocado | **Alta** | Alto | D12: ruta estable; `resolver-taller` en CI; una sola promoción por release |
| R3 | Reexportar el PCK altera el mundo y rompe la experiencia | Media | Alto | Recorrido carrusel → registro → portal → isla con capturas antes/después |
| R4 | Los 37 errores de `STM_DEF` resultan ser defectos reales y no del entorno | Baja | Medio | F0-03: re-medir con `TMP` escribible antes de dar nada por bueno |
| R5 | Se publica otra release con el árbol rojo | Media | Alto | F2: CI bloqueante; el checklist §7 exige evidencia |
| R6 | La evidencia forense se pierde definitivamente | Media | Medio | D13/F1-03 antes de cualquier limpieza del historial |
| R7 | `LC_STM` (22,7 k líneas) se mantiene sin uso y sin dueño | Alta | Bajo | Diferir a F6 con decisión explícita: cablear o archivar |

---

## 13. Anexos

### Anexo A · Verificación en un bloque

```powershell
$p = "E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_4e0f1cf6\src"
Set-Location $p

# 1. Regresión Python
python -m pytest -q

# 2. Puerta de seguridad
python -m STM_HRTS.STM_DEF escanear
python -m STM_HRTS.STM_DEF arranque
python -m STM_HRTS.STM_DEF puerta

# 3. Versión única (tras F0)
python -m STM_HRTS.utils.add_utils.version_unica --comprobar

# 4. Build y pruebas C#
Set-Location "$p\VSC#"
dotnet build Visor3D.sln -c Debug
dotnet test Visor3D.sln -c Debug --no-build

# 5. Autopruebas
Set-Location "$p\VSC#\bin\x64\Release\net8.0-windows\win-x64"
$env:WOLD_RUNTIME_DIR = "$env:TEMP\woldrt"; $env:WOLD_LOG_DIR = "$env:TEMP\woldlog"
foreach ($b in "startup","red","cuenta","chat","update","webnodo") {
  & ".\DMWoldVirtualP2P3Dv2.7.8.exe" "--$b-selftest"; "exit=$LASTEXITCODE"
}

# 6. Coherencia del PCK
(Get-FileHash "$p\VSC#\wvp3d.pck" -Algorithm SHA256).Hash
(Get-Item "$p\VSC#\wvp3d.pck").Length
```

### Anexo B · Inventario de decisiones por fase

| Fase | Decisiones que necesita |
|---|---|
| F0 | D10, D12 |
| F1 | D9, D13 |
| F2 | — |
| F3 | D11 |
| F4 | D3, D4, D-02 (#65) |
| F5 | D2, D5, D8 |
| F6 | D1, D2 |
| F8 | — (las propuestas de #85 son tareas, no decisiones) |
| F9 | D14, D15, D16, D17, D18 — **cerradas 2026-11-09** |

### Anexo C · Correspondencia `issue` ↔ tarea

| Issue | Tareas que lo cierran |
|---|---|
| #1 | F4-01, F4-02, F4-03, F3-01 (para que el arreglo llegue al binario) |
| #15 | F4-04, F4-05, F4-06, D3 |
| #16 | F6-01…F6-04 (y su propio issue, fuera de este árbol) |
| #26 | F5-01…F5-05, D5, D8 |
| #48 | F2-01…F2-04 (DT-01, DT-10, DT-15), F4-07 (DT-06/07/08/13/14/16), F0-05 (F1) |
| #65 | F0-01 (revertir la regresión de U0–U4), F4-05 (política de assets), F7-01, F7-03 |
| #66 | F3-01…F3-05, F1-04 |
| #69 | F1-01, F1-02, F1-03, F1-05, F2-02 |
| #85 | F8-01…F8-10 (deuda de la sesión 2026-11-09) |
| #86 | F9-00…F9-08 (diseño cerrado; puerta de robustez F9-00) |

### Anexo D · Glosario

| Sigla | Significado en el proyecto |
|---|---|
| **R-01** | Nombre del incidente de código dañino implantado (dropper EtherHiding) |
| **STM_DEF** | Subsistema defensivo que invierte el dropper (detección, sello, blindaje, cuarentena, firma) |
| **RU5** | Reexportar `wvp3d.pck` y registrarlo con `--registrar-pck` |
| **U0–U5** | Fases de la unificación del árbol (layout `Nucleo`, versión única, CI) |
| **DT-nn** | Deuda técnica numerada del issue #48 |
| **W-01 / DT-11** | Coherencia entre el portal WebNodo y el binario tras el OTA |
| **D-nn** | Decisión pendiente |
| **PCK** | Paquete exportado del proyecto Godot que el visor embebe |

### Anexo E · Defectos de código verificados

Lectura directa de la fuente. Solo se listan defectos **comprobables en el código**, no sospechas. Cada uno alimenta una tarea de la §7.

#### E.1 · `STM_HRTS/STM_DEF` (subsistema defensivo)

| # | Defecto | Evidencia | Tarea |
|---|---|---|---|
| 1 | La allowlist apunta a una ruta inexistente | `rutas_ignoradas.txt:9-10` vs. `STM_DOC/Desarrollo/README_DESARROLLO.md` | F1-01 |
| 2 | Una entrada de allowlist inexistente **no** se denuncia | `deteccion.rutas_ignoradas()` no comprueba existencia | F1-01 |
| 3 | `blindar()` resuelve DNS **después** de envenenar `hosts` → reglas firewall con `remoteip=0.0.0.0` | `blindaje.py:230` (sinkhole) antes de `:231` (firewall), y `lineas_firewall` resuelve en `:158` | F1-08 |
| 4 | El escáner no ve el historial salvo con la orden explícita | `deteccion.py:33-36` excluye `.git`; `historial.py:22-43` usa 5 términos y 2 rutas | aceptado (§17.3) |
| 5 | No ve binarios con NUL, ni ficheros > 512 KiB, ni extensiones fuera de `EXTENSIONES_TEXTO` | `deteccion.py:19, 76-80, 210, 215` | aceptado |
| 6 | El monitor no cubre DoH ni IP literal ni SNI | `monitor.py:114-133` compara host/IP contra dominios IOC y puertos 8545/8546 | F1-09 |

#### E.2 · GDScript (`MTBGT/WoldVirtualP2P3D/gdscrip/`)

**A. Reclamación de isla — suplantación por `any_peer`**

| # | Defecto | Evidencia |
|---|---|---|
| 1 | `_claim_island(idx, nick, uuid)` acepta `uuid` vacío | `ChunkManager.gd:443`, hueco en `:449` |
| 2 | `_resolver_isla_reclamada` toma el índice declarado si `uuid == ""` | `ChunkManager.gd:503-511` |
| 3 | `_puede_reclamar_isla` no acota el rango del índice | `ChunkManager.gd:517` |
| 4 | Consecuencia: `next_island_index = maxi(...)` se infla y `_spawn_island_for_player` instancia islas a `±199.5 · idx` | `ChunkManager.gd:544`, `:881` |
| 5 | Sin *rate limit* en el camino de reclamación | no hay cubo ni contador por peer |

**B. RPC `any_peer` sin dueño**

| # | Defecto | Evidencia |
|---|---|---|
| 6 | `_pedir_estado(idx)` entrega a **cualquier** peer el blob completo de **cualquier** isla (trozos de 6000 B) | `Construccion.gd:1467`, `:1490-1494` |
| 7 | `_reportar_direccion(url, ip)` guarda una URL arbitraria que luego se usa como destino de `create_client` y se reemite a todos en cada llamada | `ChunkManager.gd:454` → `_url_candidato:782-789` → `Red.resolver_url_ws:155-169`; reemisión `:464` |

**C. NaN / Inf**

| # | Defecto | Evidencia |
|---|---|---|
| 8 | No existe **ni un** `is_finite` en todo `gdscrip/` | búsqueda completa |
| 9 | `_solicitar_rez` pasa `pos/rot/esc` sin sanear; `esc` NaN atraviesa `esc.clamp` y se asigna en `_aplicar_cambio_red` sin clamp → `node.scale` NaN | `Construccion.gd:762`, `:741`, `:897`, `:827` |
| 10 | `_solicitar_pincel` pasa `dt/fuerza/centro` sin sanear → NaN llega a `v.y` y **se serializa** | `Construccion.gd:566`, `TerrenoEditable.aplicar_pincel:186-193`, `:238`, `:443` |

**D. Topes y fugas**

| # | Defecto | Evidencia |
|---|---|---|
| 11 | Sin tope de prims por isla | `Construccion.gd:728-751`, `Prims.deserializar_isla:176-196`; no hay `MAX_*` en `gdscrip/` |
| 12 | `owner_names` **nunca** se borra | `ChunkManager.gd:41`; escrituras `:408, :451, :852`; `_on_peer_disconnected:694-714` no lo toca |
| 13 | `island_owners` tampoco (no hay `.erase` en todo `gdscrip/`) | idem |
| 14 | `Construccion.olvidar_isla` borra `_recibiendo` con clave `int`, pero las claves son `"idx:tipo"` → no libera | `Construccion.gd:208` vs. `:1499` |

**E. El error de `Personalizacion.gd`**

`surface_get_arrays()` devuelve `null` en los slots `ARRAY_BONES`/`ARRAY_WEIGHTS` cuando la superficie no está *skinneada*; asignarlo a una variable tipada `PackedInt32Array` / `PackedFloat32Array` lanza el `SCRIPT ERROR` conocido. Cadena real: `_aplicar_figura:242` → `_buscar_cuerpo:887` → `_cuenta_cabeza:945` → `_vertices_cabeza:950-958`.

| Sitio | Líneas | Arreglo |
|---|---|---|
| `_vertices_cabeza` | `950-958` (asignaciones en `952-953`) | guardar con `if arr[Mesh.ARRAY_BONES] is PackedInt32Array …` o asignar un array vacío antes |
| `_geometria` | `570-571` | mismo patrón, sin guarda |
| `_mascaras_de` | `737-738` | mismo patrón, sin guarda |

Coste: 2–3 líneas por sitio. **Consecuencia actual:** `probar_registro` y `probar_flujo_portal` lo disparan **y devuelven exit 0 igualmente** — un verde falso, la peor clase de defecto.

**F. `OptimizadorAvatares`**

Es el **único autoload** del proyecto (`project.godot:65`) y su API tiene **cero llamadas externas** en todo `src/` (`optimizar_nodo()` solo aparece en documentación y en sus propios mensajes). Su único efecto real es fijar `root.mesh_lod_threshold = 4.0` (`OptimizadorAvatares.gd:110`) desde `_ready()`; su `_process()` (`:79`) recorre cada frame un registro que siempre está vacío. Decisión de dueño pendiente (U-05): activarlo de verdad o retirarlo.

**G. Peso del mundo (datos para #15)**

| Dato | Medición |
|---|---|
| Árbol `MTBGT/` sin `.import` | 265 ficheros · 329.089.683 B (**313,8 MiB**) |
| `gltfimport/` | **310,9 MB · 94,5 % del total** |
| Duplicados byte a byte (pares ≥ 500 KB) | **117.395.461 B (112 MiB, 34 %)** |
| Avatares | 8 carpetas, **4 modelos distintos**: `AVH2 = AVH3 = AVH4`, `AVMJ1 = AVMJ4`, `AVMJ2 = AVMJ3` |
| Animaciones | los 8 `.gltf` declaran los mismos 5 clips, y además `AnimacionesCompartidas.gd:13` los copia de `AVH1` |

**H. Defecto de empaquetado (impacto no verificado)**

Los `.gltf`/`.bin`/`.import` que **sí** referencian las escenas (`gltfimport/avatares/AVH*.gltf`, `AVMJ*`) están re-codificados en **UTF-16LE con BOM** (`AVH1.gltf` empieza `FF FE 7B 00`). Los originales válidos en UTF-8 están en `gltfimport/avatares/avatares/`, carpeta que **ningún** `.tscn` referencia. No se ha abierto el proyecto en Godot para no escribir `.godot/`; hay que confirmar en F4-11 si el import funciona por casualidad o si los avatares se cargan desde otra ruta.

#### E.3 · Python LucIA

| # | Defecto | Evidencia |
|---|---|---|
| 1 | `pyproject.toml` declara `hrts = "STM_HRTS.__main__:main"` y ese módulo **no existe** | `add_utils/pyproject.toml:25-27`; `python -m STM_HRTS` → `ModuleNotFoundError` |
| 2 | `readme = "README.md"` apunta a un fichero ausente; sin `[tool.setuptools]` los paquetes quedan fuera de la distribución | `pyproject.toml:9` y ausencia de `packages` |
| 3 | `vault_openrouter.py` **no es Fernet**: PBKDF2-HMAC-SHA256 + **XOR sin MAC**, con **semilla maestra hardcodeada** como respaldo → ofuscación, no cifrado | `STM_SGR/vault_openrouter.py:18, 23, 33, 37, 43, 48, 61` |
| 4 | `_sl_math.py` usa `math` **sin importarlo** → `NameError` en `:58` y `:97` (llamados desde `SL3/SL4/SL5`) | `LC_STM/red_neuronal/SLRN/_sl_math.py:58, 97` |
| 5 | `cosine_decay` quedó **anidada** dentro de `centered_rms_update` → `AttributeError` al usarla | `_sl_math.py:130-134`, consumida en `SL10.py:67` |
| 6 | Envoltorios que fabrican métricas falsas: `loss`/`accuracy` aleatorios, gradientes con ruido, curva de pérdida inventada | `_rn_base.py:205, 261-271`; `SL6.py:177-178` |
| 7 | `mainLCSTM` **no usa** `red_neuronal`: usa el shim `compat_local.py` (proyección sha256 → tensor + 3 pasos de Newton-Schulz) | `STMGNRL/mainLCSTM.py`; `STM_BKCH/compat_local.py:39-133` |
| 8 | 7 órdenes de RFPRMN siempre responden «no disponible» porque `RFPRMN.py` no existe en este árbol | `mainLCSTM.py:113, 320-322` |
| 9 | Dependencias opcionales **no declaradas** (psutil, cryptography, gtts, soundfile, scipy, comtypes…) | `pyproject.toml:15-17` solo declara `numpy` |

> **Nota de honestidad sobre E.3:** el punto 7 no es un defecto por sí mismo — puede ser una decisión deliberada (el conversor determinista es más barato y no requiere pesos). Lo que **sí** es deuda es que 22.700 líneas de red neuronal no tengan camino de ejecución ni dueño. F6-01 decide: cablear o archivar.

#### E.4 · C# (`VSC#/`)

**A. Fallo silencioso**

| # | Defecto | Evidencia |
|---|---|---|
| 1 | **143 `catch { }` vacíos** en `VSC#/`. Los mayores: `MainWindow.xaml.cs` (21), `WebNodoService.cs` (18), `P2PWebNode.cs` (9), `TunnelProcessRegistry.cs` (7), `ChatVoice.cs` (6), `StartupSelfTest.cs` (6), `UpdateDownloader.cs` (6) | recuento con `Select-String "catch\s*\{\s*\}"` |
| 2 | Consecuencia: un fallo de red, de OTA o de extracción **no deja rastro**. Es la razón por la que el proyecto repite «no puede afirmarse que…» en su propia documentación | — |

**B. Parsers de endpoint divergentes (D-07 sigue vivo)**

| Sitio | Código | Efecto |
|---|---|---|
| `App.xaml.cs:193` | `arg.StartsWith("woldvirtual://")` | solo detecta |
| `MainWindow.xaml.cs:1164` | `s.Substring(14)` | corta 14 |
| `LanzadorMundo.cs:227` | `s[15..]` | corta 15 → **off-by-one** |

Los tres coexisten porque el tipo unificado vivía en `VSC#/Nucleo/` (B-01). Se cierra al restaurar el núcleo (F0-01).

**C. IPv6 (DT-09, vivo)**

`DescubrimientoP2P.TrySepararHostPuerto:148-165` usa `LastIndexOf(':')`:

- `[fe80::1]:9000` → `host = "[fe80::1]"` **con corchetes**, que después no se quitan antes de `TcpRespondeAsync` → falla la resolución.
- `fe80::1` (IPv6 sin puerto) → interpreta `1` como puerto y deja `host = "fe80:"`.

**D. Estado estático en `WebNodoService` (DT-13 / DT-16, vivos)**

| Línea | Elemento |
|---|---|
| `:89` | `static readonly (…) ReleaseLocal = LeerReleaseLocal();` — **lee un fichero en el inicializador estático**, al cargar el tipo |
| `:90` | `ReleaseActiva` mutable |
| `:106` | `_ultimaConsulta` mutable |
| `:107` | `_consultaEnCurso` mutable |

Sin parciales: hoy es un único fichero de 926 líneas, no los `WebNodoService.{PortalHttp,ProxyTcp,ProxyWebSocket}.cs` que existían en la zona.

**E. Andamiaje muerto**

`LocationAccountLedger.cs:141` (`ExportJson`) y `:152` (`MergeExternalRecords`) existen y **no tienen ningún llamador** en `VSC#/` (grep sin resultados). Es la deuda DT-1 de #26, confirmada.

**F. Tamaño**

`Visor3D.csproj:17` → `<EnableCompressionInSingleFile>false</EnableCompressionInSingleFile>`. El experimento de compresión que pide #15 **no se ha intentado**; el binario es `PublishSingleFile` + `SelfContained` sin comprimir.

**G. Lo que hay que recuperar y hoy falta**

`TokenSesionChat.cs` (token de sesión del relé, PR #59), `AnuncioRelease.cs`, `ConfigRed.cs`, `WebNodoService.*` parciales, `Nucleo.csproj`, `Directory.Build.*`, `Visor3D.sln`, y 5 clases xUnit. Todo en `45a1fcf` (F0-01).

**H. Comprobado y ya corregido — no volver a reportarlo**

| Elemento | Verificación |
|---|---|
| Umbral VM «inoperante» (DT-2 antiguo) | **Corregido**: `VmDetector.cs:25` `UmbralVm = 0.50`, `:113` `IsVm = score >= 0.50`; `SmtplcSecurityService.cs:55` repite la condición pero con el mismo umbral. El selftest lo confirma: `[OK] Umbral de VM unificado (0,50)` |
| Vector R-01.b (`.vscode` de la raíz) | Retirado; `settings.json` no contiene `allowAutomaticTasks` ni `runOn: folderOpen` |
| Vector R-01 A5-2 (`opencode/init`) | Ausente; `package.json` ya no ejecuta `node init` |

**I. Pendiente de confirmar en sesión interactiva**

`--startup-selftest` y `--red-selftest` fallan en «Portal WebNodo escucha — Controlador no válido». En este entorno de análisis no hay sesión interactiva plena y el error es el que devuelve `HTTP.sys` cuando no está disponible. **Debe re-medirse en un escritorio normal antes de abrir un defecto de producto** (F0-05).

#### E.5 · SMTPLC — falso positivo de VM (incidente real, 2026-11-07)

Un usuario recibió el veto duro del registro: «Entorno Virtualizado No Permitido …
(Hipervisor de CPU, Microsoft Hyper-V)». **No estaba en una máquina virtual.**

**Causa.** `VmDetector.Analyze()` suma señales hasta 0,50. En un equipo **físico** con
Hyper-V, VBS o WSL2 activos:

| Señal | Puntos | ¿Prueba de VM? |
|---|---:|---|
| `Win32_ComputerSystem.HypervisorPresent = true` (VBS/Hyper-V/WSL2 encienden este flag en hardware real) | +0,25 | **No**, solo corrobora |
| Adaptador `vEthernet (Default Switch)` / `vEthernet (WSL)`: Windows lo crea por software y le asigna la OUI de Hyper-V `00:15:5D` | +0,50 | **No**, es del anfitrión |

0,25 + 0,50 = 0,75 ≥ 0,50 → `IsVm = true` → `SmtplcSecurityService.cs:54-71` veta el registro y
`FormularioUsuarioWindow.xaml.cs:90-95` lo muestra. La política viene con
`BlockVirtualMachines = true` por defecto, así que afecta a **cualquier** usuario con Hyper-V/WSL2/VBS.

Además, tres categorías sumaban **por cada coincidencia** (una por NIC, una por controlador, una por
proceso), de modo que varias NIC del mismo conmutador inflaban la puntuación por sí solas.

**Corrección aplicada.**

1. `VmDetector.EsAdaptadorNoFisico()` (función pura, pública y testeable): excluye como evidencia los
   adaptadores que Windows crea por software — `Hyper-V Virtual Ethernet Adapter` / `vEthernet`,
   `VMware Virtual Ethernet Adapter`, `VirtualBox Host-Only`, `Wintun`/`WireGuard`, `Teredo`, `ISATAP`,
   loopback y túneles.
2. El adaptador de un **invitado** de Hyper-V se llama `Microsoft Hyper-V Network Adapter` (sin
   «Virtual Ethernet») y **sigue contando**: la corrección no abre la puerta a las VM reales.
3. Una sola puntuación por categoría (NIC, controladores, procesos).
4. `Hipervisor de CPU` deja de anunciarse como hipervisor detectado por el mero flag: solo se nombra
   si el veredicto final es VM, para que el mensaje no acuse a un hipervisor que no existe.

**Verificación.** 11 casos en `VSC#/Tests/SmtplcVmPruebas.cs` (xUnit): 5 conmutadores por software
excluidos, 4 NIC reales/de invitado que sí cuentan, 2 loopback/túnel. Compilado y ejecutado en
aislamiento con Roslyn: `RESULTADO: OK`, exit 0. **No se ha compilado el proyecto completo** en este
entorno (el sandbox bloquea `VSC#/obj` y los *named pipes* de MSBuild): hay que pasar
`dotnet build` + `dotnet test` antes de publicar.

**Pendiente de decisión (D5).** Esta corrección arregla el falso positivo, no el modelo: el bloqueo
sigue siendo duro y sin recurso. Convertirlo en puntuación con fricción (o en aval) sigue siendo
decisión de producto.

### Anexo F · Registro de cambios de este documento

| Fecha | Cambio |
|---|---|
| 2026-11-07 | Versión inicial. Medición completa del snapshot `actualizacion_4e0f1cf6`, 8 hallazgos bloqueantes, 8 fases y 48 tareas |
| 2026-11-07 | **F1-01 y F1-02 ejecutadas** (rama `DevDeepSeekHarnessIA`). Puerta de seguridad en verde: `escanear` 0/LIMPIO, `arranque` PERMITIDO, `puerta` ABIERTA. El visor ya no se autobloquea. Causa exacta de los 37 errores de pytest identificada (sandbox `0700`, no el código) |
| 2026-11-07 | **F5-06: falso positivo de VM corregido** (incidente real: veto del registro a un usuario en equipo físico con Hyper-V/VBS). `VmDetector.EsAdaptadorNoFisico()`, puntuación única por categoría y `Hipervisor de CPU` solo si el veredicto es VM. 11 casos xUnit; compilado en aislamiento con Roslyn (el sandbox no permite `dotnet build`) |
| 2026-11-09 | **Sesión RFPRMN · IPFS · LucIA 3D (issue #85)**: RFPRMN v2.24.0 (399 pruebas), nodo IPFS real (`STMIPFS/nodo`, Kubo 0.43.1), `LucIAServidor3D` + `LucIAPuenteComandos` en `DevDeepSeekHarnessIA` (fusionada a `DevQoderIA` el mismo día). Se añaden F8 (10 tareas de deuda de la sesión) y F9 (diseño de #86: LucIA anfitriona + wallet embebida; D14–D18 cerradas el mismo día con formato de bloque, `.zip`, endpoint `/alta-cuenta` y tareas F9-00…F9-08). Cabecera actualizada a v2.7.9 |

---

*Documento generado a partir de la medición directa del árbol y de la lectura de los issues #1, #15, #16, #26, #48, #65, #66, #69 y #85, y de la discusión #86. Las cifras son reproducibles con los comandos del Anexo A; lo no verificado se declara como tal.*
