# README de refactorización general (2026-11-06)

**Ámbito:** `VersionDe_sesion/CONTRRF/TLLDCD/src` — sin salir de este directorio.
**Referencias vivas:** [`README_DESARROLLO.md`](README_DESARROLLO.md) (diagnóstico, §14 cierre por issue, §15 cola dirigida, §16 unificación, §17 runbook) · [Discusión #67](https://github.com/Chicook/WoldVirtualP2P3D/discussions/67) · issues abiertos [#66](https://github.com/Chicook/WoldVirtualP2P3D/issues/66), [#65](https://github.com/Chicook/WoldVirtualP2P3D/issues/65), [#48](https://github.com/Chicook/WoldVirtualP2P3D/issues/48), [#26](https://github.com/Chicook/WoldVirtualP2P3D/issues/26), [#15](https://github.com/Chicook/WoldVirtualP2P3D/issues/15), [#1](https://github.com/Chicook/WoldVirtualP2P3D/issues/1), [#16](https://github.com/Chicook/WoldVirtualP2P3D/issues/16).
**Método:** lectura vía `gh` de los 7 issues abiertos y de la Discusión #67, contraste contra `README_DESARROLLO.md` y medición estática del árbol (sólo lectura, sin compilar ni ejecutar: **R-01 sigue abierto**).

Este documento **no sustituye** a `README_DESARROLLO.md`: lo consolida y lo secuencia como un plan de
refactorización único. Donde difieran los números, manda el que tenga la fecha de medición más reciente.

---

## 1. Estado de partida (medido)

### 1.1 El árbol

- La zona `src` **no está rastreada por Git** (`git ls-files` sobre `VersionDe_sesion/CONTRRF/TLLDCD/src` = 0 ficheros).
  Todo el trabajo U0–U5 vive aquí y no es conmutable; su única copia de seguridad está en
  `STM_DOC/rescate_zona_20261105/` y `respaldo/*` (riesgo de pérdida real si alguien limpia `CONTRRF`).
- **8.126 ficheros** medidos por `find` (2026-11-06). Desglose por directorio: `STM_HRTS` 5.408 · `VSC#` 2.059 ·
  `MTBGT` 315 · `STM_DOC` 142 · `LC_STM` 66 · `STM_CH` 61 · `tests` 26 · `SBSTM` 23 · `STM_IA` 9 · `STMIPFS` 6 ·
  `STM_BKCH` 4 · `STMGNRL` 2 · `STM_JSON` 2 · `STM_SGR` 1.
- El grueso es **ruido no conmutable**: `STM_HRTS/opencode` 881 MiB, `VSC#/bin` 713 MiB, `VSC#/Tests` 402 MiB,
  `VSC#/obj` 386 MiB (medido el 2026-11-05, §16.10). El techo estructural sin `opencode` es 537 MiB (§16.6).

### 1.2 Puertas verdes (medidas el 2026-11-05, §13.6/§17.5)

| Puerta | Resultado medido |
|---|---|
| `dotnet build VSC#/Visor3D.sln` | 0 errores / 0 advertencias |
| `dotnet test` (xUnit) | **67/67** |
| `version_unica --comprobar` | exit 0 (4 csproj heredan + PCK anclado) |
| `pytest` completo | **215 aprobadas + 4 `xfail` estrictos, 0 fallidas** (53 s / 55 s) |
| puerta Godot `-m godot` | 18 aprobadas + 4 `xfail` con PCK; **12 + 1 + 9 omitidas en 21 s** sin PCK (situación del runner) |
| 6 selftests del `.exe` | exit 0 (startup, red, cuenta, update, chat, webnodo 23 líneas/0 fallos) |

Estos verdes **no se han re-medido hoy**: R-01 prohíbe compilar/ejecutar el árbol, así que se conservan como
referencia del último cierre medido. El primer acto de cualquier refactorización que toque código vuelve a correr
esta tabla entera.

### 1.3 Release vigente

`v2.7.7` publicada el **2026-11-05 22:57:32Z** con 3 assets (sin Linux), tag sobre `294a72a` (commit de `DevQoderIA`
del 2026-10-30, **que no contiene el árbol que compiló el binario**). `DMWoldVirtualP2P3Dv2.7.7.exe` =
365.114.325 B (348,19 MiB). **El checklist §7 de `REGLAS_DE_ACTUALIZACION.md` está 6 de 12 casillas sin cerrar**
(detalle en el comentario de [#66](https://github.com/Chicook/WoldVirtualP2P3D/issues/66#issuecomment-6671805928)).

### 1.4 Issues abiertos y su único bloqueo

| Issue | Tema | Único bloqueo que lo mantiene abierto |
|---|---|---|
| #66 | Deuda de publicar la 2.7.7 (17 casillas) | **R-01 abierto** + árbol sin promover + RU5 |
| #65 | Deuda de merges #55–#63 y de U0–U4 | árbol canónico sin reflejar en `main` (D-01) + CI (D-04) |
| #48 | Deuda DT-12…DT-16 + heredadas | DT-01 (CI a la raíz) y las heredadas |
| #26 | SMTPLC: ledger P2P, anti-VM/VPN, apelación | decisiones **D5** y **D8** (producto) |
| #15 | Peso del visor | decisión **D3** (meta numérica) + métrica de huella |
| #1 | Red LAN configurable | prueba física de **dos equipos** (DT-04) |
| #16 | LucIA externa | fuera de alcance de este taller |

---

## 2. Lo que manda: R-01 (Etapa 0) es la primera refactorización

La hoja de ruta de seguridad pone **R-01 por delante de cualquier funcionalidad, clonado, apertura o publicación**.
El árbol contiene **tres mecanismos de código dañino plantado** que desenrollan al mismo cargador de segunda etapa,
alimentado por un punto muerto de Ethereum (medido el 2026-11-05, §16.11):

| ID | Mecanismo | Estado en la zona |
|---|---|---|
| A1-1 | `STM_HRTS/utils/transport.py` + `STM_HRTS/__main__.py:10` → RCE en tiempo de importación al `python -m STM_HRTS` | **NO ALCANZABLE**: no hay `transport.py` ni `__main__.py`; `grep -rn transport --include=*.py` = 0 |
| A5-1 | `fa-brand-400.orc` (30.627 B, sha256 `89adac5b…`) + tarea `folderOpen` de `.vscode` | el `.orc` está; **no hay `.vscode/`** en la raíz del árbol de trabajo |
| A5-2 | `STM_HRTS/opencode/init` línea 35 = 31.751 caracteres ofuscados (sha256 `8f79baa4…`), ejecutado por `npm start` | **VIVO**: mismo sha256, misma ruta |

**Replantación:** las ramas `DevChatGPTIA`, `DevCursorIA`, `DevDeepSeekHarnessIA` y `DevDevinIA` llevan el snapshot
`actualizacion_91883d55` con `fa-brand-400.orc` y `utils/transport.py` dentro: fusionar cualquiera replanta dos de los
tres mecanismos. `DevQoderIA` (rama de trabajo): 0 coincidencias.

**La autoría no está probada** y así se mantiene en los issues y en la Discusión #67: no se atribuye a ninguna persona.

### 2.1 Pasos de cierre (reversibles, no borran evidencia)

1. **Cuarentena** (mover, no borrar): sacar `utils/transport.py`, `fa-brand-400.orc` y `opencode/init` a una carpeta
   fuera del árbol activo (o dentro de `STM_DOC/rescate_zona_20261105/`), anotando sus sha256 en el issue de incidente.
2. **Restaurar `opencode/init`** a su fragmento benigno (34 líneas) o quitar el script `start` de `package.json`.
3. **Retirar `"task.allowAutomaticTasks": true`** de `.vscode/settings.json` (si existe en la copia).
4. **Escribir el `__main__.py` limpio** (6 líneas: `from STM_HRTS.utils.add_utils.__main__ import main; sys.exit(main())`)
   o reorientar `pyproject.toml:27` a `STM_HRTS.utils.add_utils.__main__:main`; y cambiar
   `test_manifiesto_declara_la_consola`, que hoy fija la cadena rota (§16.11).
5. **Criterio de aceptación** (hoja de ruta): búsqueda en todo el repo sin `runOn: folderOpen`, sin
   `allowAutomaticTasks`, sin `.orc`, sin `transport.py`.

### 2.2 R-01b (decisión del propietario, fuera de este entorno)

Desofuscar las dos cargas JS e inspeccionar la transacción de Ethereum **en sandbox aislada, sin credenciales y sin
ruta de red de retorno**; auditar `d510acd`/`3caf0e7` (PR #47); anunciar el alcance a las máquinas expuestas. **No se
hace desde este taller.**

**Estado (2026-11-06):** de los tres verbos de R-01b, la **auditoría de PR #47** es de sólo lectura y sí procede:
hecha y registrada en [`informe_r01b_auditoria_20261106.md`](informe_r01b_auditoria_20261106.md) (procedencia
`d510acd`/`c395284`/`3caf0e7`, los cuatro blobs confirmados vivos en `origin/main` por sha256, disparador A1-1
`import utils.transport` y cargador Ethereum en `transport.py`; **sin atribuir autoría**). La **desofuscación en
sandbox** y el **anuncio a máquinas expuestas** siguen siendo del propietario, fuera de este entorno.

**Procedimiento para el propietario:** el runbook paso a paso (entorno aislado sin egress, desofuscación offline de las
dos cargas, lectura del calldata de Ethereum sin correr el loader, alcance, anuncio y purga en dos niveles con sus
compuertas) está en [`procedimiento_R01b_propietario_20261106.md`](procedimiento_R01b_propietario_20261106.md).

---

## 3. Frentes de refactorización (paquetes de trabajo)

Cada paquete dice qué cierra, qué entrega y qué lo bloquea. El orden está en §4.

### WP-0 — R-01 (Etapa 0)
Ver §2. Cierra la fila 0 de la cola (§15.2) y desbloquea **todo** lo demás: mientras R-01 esté abierto, ni siquiera
se puede re-medir la tabla de §1.2. Sin WP-0 no hay refactorización.

**Estado (2026-11-06):** pasos 1–5 de §2.1 ejecutados y medidos — cuarentena de `.orc` y `opencode/init`
(sha256 verificados), trigger `start` de `package.json` eliminado, `grep` = 0 para los cuatro marcadores en el
árbol activo (excluida `STM_DOC/`), y paso 4 resuelto por la **opción A**: `STM_HRTS/__main__.py` limpio que
reenvía a `STM_HRTS.utils.add_utils.__main__:main`, de modo que `pyproject.toml:27` (`hrts = "STM_HRTS.__main__:main"`)
ahora resuelve sin tocarlo y `python -m STM_HRTS` funciona (pytest **216 passed + 4 xfailed**). Evidencia en
`STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/MANIFIESTO.md` y registro §13.8 de `README_DESARROLLO.md`.
Queda R-01b (del dueño, fuera de este taller).

### WP-1 — Promoción del árbol canónico a un commit real
- **Qué cierra:** #65 D-01/U-01/U-02 · #66 §1.1 (el binario sin fuente commiteada) y §2 (73 borrados + 49 nuevos).
- **Entregable:** un commit en la rama de trabajo que contenga la zona completa; borrar los **73 paths de `main`**
  (44 copias planas de `STM_HRTS/utils`, 9 de la raíz `STM_HRTS/`, 20 de `VSC#/{Chat,Services,Seguridad,RedP2P,STM_actualizar}`
  movidos a `VSC#/Nucleo`) y meter los **49 ficheros nuevos** del núcleo; restaurar el README profesional de la raíz
  (blob `722bbdb8`) que `main` sustituyó por la carta de 1.795 B (D-03).
- **Bloquea a:** WP-2 (CI), WP-3 (que el tag siguiente nazca de un commit), y el cierre de la release que contenga la Etapa 1.
- **Bloqueado por:** decisión del propietario (la promoción es un `git push`/merge fuera de la zona: R16).

**Estado (2026-11-06): 🟨 mitad local hecha, falta el remoto.** La zona se promocionó a
`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src` y quedó commiteada en `DevQoderIA` (`45a1fcf`) con sus
rutas interiores corregidas (§13.9 de `README_DESARROLLO.md`). Luego `main` **local** absorbió ese árbol en un merge con
padres `75eaff8` + `45a1fcf` (1.388 conflictos *rename/rename* por el cambio de nombre de instantánea, resueltos con
subárbol idéntico y los docs de raíz de `main` conservados; el sha del commit no se cita porque estos ficheros viajan
dentro de su árbol) — evidencia medida en §13.9.1.
Lo del entregable que **no** se cumplió tal como estaba escrito: los «73 paths de `main`» y «49 ficheros nuevos» eran la
foto de noviembre sobre otro layout; hoy el árbol de la instantánea son **661 ficheros rastreados** idénticos entre
`main` y `DevQoderIA`, y el README profesional de la raíz **no** se restauró desde el blob `722bbdb8` sino que se conservó
el de `main` (más reciente) re-apegando `aeef1149` → `cae205a3` — en las dos lenguas: la documentación en inglés
(`README_EN.md`, `docs/STACK*`, `AGENTS.md`, `CLAUDE.md`) es privativa de `main` y seguía apuntando a la instantánea
muerta. Sin hacer: `git push`/PR, el re-medido de la tabla §1.2 y que el tag siguiente nazca de un commit real.
**No se fusiona `origin/main`** (38 commits por delante con las cargas vivas bajo `aeef1149` y
`__main__.py:10 import utils.transport`): eso es R-01b + fase G.

### WP-2 — CI real en la raíz
- **Qué cierra:** #48 DT-01/DT-10/DT-15 · #65 D-04/D-06 · la mitad de F1 de #48.
- **Entregable:** `.github/workflows/ci.yml` en la **raíz** del repo (hoy anidado en `src/STM_HRTS/.github/workflows/`,
  donde GitHub **no lo lee**; sus 4 jobs —`resolver-taller`, `python-suite`, `csharp-suite`, `godot-headless`— **no se
  han ejecutado nunca**). Suite Python estricta (sin `continue-on-error`), xUnit en el runner, los seis selftests con
  `WOLD_RUNTIME_DIR`/`WOLD_LOG_DIR` temporales, y el job `godot-headless` resolviendo el motor desde `VERSION.json`.
- **Bloqueado por:** WP-1 (el workflow debe llegar a la raíz) y por el dueño (#65 P0-2).

### WP-3 — PCK fresco, anclaje y checklist §7 completo (RU5)
- **Qué cierra:** RU5 · #66 §1.3 (anclar `pck_sha256` en `publicar_version.ps1`) · las 6 casillas de §7 abiertas.
- **Entregable:** reexportar `VSC#/wvp3d.pck` (hoy el de la 2.7.6, `ebeff90c…`, 114.591.724 B) desde
  `E:/areadetrabajo/wvp270/godot` y ejecutar `version_unica --registrar-pck`; añadir al guion de publicación la
  comparación del PCK embebido contra la tabla (con su prueba negativa); repetir `tests/godot/medicion_modos.py`
  (~4 min) y revisar la matriz de §17.6; correr el checklist §7 entero sobre el binario reexportado, incluida **la
  OTA de punta a punta en un equipo con la 2.7.6** (R13, §8.8: sin ella ninguna afirmación «los clientes ya tienen X»
  es defendible).
- **Bloqueado por:** WP-0 (hay que poder arrancar el motor/el visor) y por el dueño (reexportar exige
  `E:/areadetrabajo/wvp270/godot` y autorización).
- **Decisión pendiente mientras tanto:** dejar `Latest` en 2.7.7 o marcarla **prerelease** para frenar el OTA (R4
  prohíbe tocar el tag; prerelease no toca assets ni tag). Anotada en #66.

### WP-4 — Núcleo C# residual (U3 abierto) y WebNodo testable
- **Qué cierra:** #48 DT-12…DT-16 · parte de #65 U-10.
- **Entregables, en orden:**
  1. **DT-13/DT-16:** extraer el parseo de `release.json` a un tipo puro y testeable (`AnuncioRelease`), sacar el
     estado estático de `WebNodoService` y eliminar los puntos de sutura `internal` (`LeerReleaseParaPrueba`,
     `SembrarReleaseParaPrueba`, `RutaBinarioEnEjecucion`).
  2. **DT-12:** decidir renombrado del `.exe` en el reemplazo del OTA (o documentar el desajuste como aceptado).
  3. **DT-14:** invalidar el anuncio de release al detectar un OTA aplicado (refresco de 5 min).
  4. **Fusión de `ReinicioCuenta`** (326 ln Windows vs 258 ln Linux; 184 líneas de diferencia; toca la base de usuarios).
  5. **Adelgazar `MainWindow.xaml.cs`** (3.398 líneas tras U4).
  6. **SMTPLC** queda fuera de este paquete: es WP-6 (#26), bloqueado por D5/D8.
- **Bloqueado por:** WP-0 y por las pruebas (nada se toca sin su prueba en el mismo commit — R2).

### WP-5 — Puerta de Godot (#66 §3)
- **Qué cierra:** los 4 `xfail` de §17.6 y las casillas §3 de #66.
- **Entregables, en orden:**
  1. **`Personalizacion.gd:952`** (`Nil → PackedInt32Array` en `_vertices_cabeza`): es el único defecto que da
     `SCRIPT ERROR` con salida 0; al arreglarlo la puerta falla con `XPASS` hasta quitar la marca `xfail(strict=True)`.
  2. Los dos verdes ciegos: `validar_anim_glb` (ve `0 modelos`) y `validar_personalizacion` (ve `0 escenas` con el PCK)
     — recuperar sus fixtures o decidir su retirada explícita.
  3. Los **11 guiones sin veredicto** (`capturar_*`, `render_avatares`, `probar_cara/cuerpo/personalizacion`,
     `inspeccionar_avatar`, `inspect_anim`, las dos sondas LAN, `sonda_escena_construccion`): darles veredicto o
     excluirlos del CI con motivo.
  4. `probar_red_invitacion`: quitar la dependencia de `trycloudflare.com` de ejemplo.
  5. `test_headless.py:88-94`: corregir el `max()` que puede ocultar el veredicto real cuando un guion imprime dos cifras.
- **Bloqueado por:** WP-3 (tras reexportar hay que repetir `medicion_modos.py` o la puerta se discrepa del árbol en silencio).

### WP-6 — Issues funcionales (#1, #15, #26)
- **#1 (red LAN):** prueba física con **dos equipos reales** (DT-04) + IPv6 literal con corchetes (DT-09); reescribir
  el criterio del issue a WebSocket/puerto dinámico (D4). Código ya hecho (H3).
- **#15 (peso):** métrica de huella instalada (binario + runtime + motor + PCK), desglose por tipo, manifiesto de
  assets fuente con hash/licencia, pipeline reproducible, experimento `EnableCompressionInSingleFile` medido, y
  decisión **D3** (propuesta: ≤ 250 MiB Windows).
- **#26 (SMTPLC):** **D5** (bloqueo duro vs. puntuación de riesgo) y **D8** (ledger: integrar con firma + revocación /
  degradar a exportación local / eliminar) primero; después proveedores tras interfaces (`INetworkEnvironmentProvider`,
  `ISystemInfoProvider`), umbral VM coherente (`IsVm` 0,40 vs `VmConfidenceThreshold` 0,50), BSSID real en la huella
  Wi-Fi, y apelación/lista blanca decidida.

### WP-7 — Higiene y gobierno del repo
- **Qué cierra:** #65 D-02/D-03/U-06/U-08/U-09 y la purga de ramas (P2).
- **Entregables:** política de assets para lo que metió #63 (252,3 MiB, 40 PNG = 222,0 MiB: LFS / fuera del repo /
  aceptar explícitamente) · regenerar manifiestos obsoletos (`manifiesto_h0.json`, `clasificacion_arbol_20261105.tsv`)
  · unificar la prosa de puertos en UI («IP:8911» en Avalonia y `Construccion.gd:1495`) · mover los dos guiones de
  publicación obsoletos a `STM_DOC/rescate_zona_20261105/` (el catálogo baja de 48 a 46 herramientas) · purgar ramas
  redundantes **sólo tras confirmación nominal del dueño** (RU3, sin `--force`).

---

## 4. Secuencia (orden estricto y qué se puede paralelizar)

| # | Paquete | Cierra | No empezar hasta | Bloqueado por |
|---|---|---|---|---|
| 0 | WP-0 R-01 | fila 0 · #66 §0 | — | dueño (cuarentena + R-01b) |
| 1 | WP-1 Promoción | #65 D-01/U-01/U-02 · #66 §1.1/§2 | WP-0 | dueño (push/merge) — local hecho el 2026-11-06 |
| 2 | WP-2 CI real | #48 DT-01/10/15 · #65 D-04/D-06 | WP-1 | dueño (raíz) |
| 3 | WP-3 PCK + §7 | RU5 · #66 §1.3 · §7 | WP-0 | dueño (reexport) + `E:/areadetrabajo/wvp270/godot` |
| 4 | WP-5 Puerta Godot | #66 §3 · 4 `xfail` | WP-3 (repetir matriz) | — |
| 5 | WP-4 Núcleo residual | #48 DT-12…16 · #65 U-10 | WP-0 + R2 | — |
| 6 | WP-6 Funcional (#1/#15/#26) | #1 · #15 · #26 | WP-0; #15 tras WP-2; #26 tras D5/D8 | hardware (#1), decisiones D3/D5/D8 |
| 7 | WP-7 Higiene | #65 D-02/03 + U-06/08/09 + P2 | WP-1 | dueño (borrado de ramas) |

- **WP-3 y WP-4/WP-5** pueden solaparse: no tocan los mismos ficheros (PCK vs C#/Godot).
- **WP-6·#1** sólo necesita hardware, no código: se puede intentar en cuanto WP-0 deje arrancar el visor.
- **WP-6·#26 y WP-7** son los de menor urgencia; no abren mientras haya un paquete P0/P1 sin cerrar (§12 del README).

**Principio rector (heredado de §15.3):** una casilla = un commit = una evidencia. Sin log, captura o artefacto
reproducible, la casilla sigue abierta aunque el código parezca correcto.

---

## 5. Decisiones pendientes (propietario), con opción conservadora

| ID | Decisión | Bloquea | Límite | Si no se decide |
|---|---|---|---|---|
| R-01b | desofuscar + auditar PR #47 en sandbox | WP-0 completo | — | no procede desde el taller; se documenta como pendiente del dueño |
| — | marcar 2.7.7 como prerelease para frenar el OTA | §7 | ya | dejar `Latest` (los 2.7.6 instalados pueden actualizar a un binario no auditado) |
| D2 | integrar IPFS real o renombrar el shim | WP-7 | 2026-11-10 | renombrar y documentar el shim como no-op |
| D3 | meta numérica de #15 | WP-6·#15 | 2026-12-22 | ≤ 250 MiB tras la primera medición de huella |
| D4 | reescribir #1 a WebSocket/puerto dinámico | WP-6·#1 | 2026-11-24 | sí, y documentarlo en el issue |
| D5 | SMTPLC bloquea o puntúa | WP-6·#26 | 2027-01 | mantener bloqueo duro y anotarlo |
| D8 | destino del ledger de ubicación | WP-6·#26 | 2027-01 | degradar a exportación local documentada |
| DT-12 | renombrar el `.exe` en el OTA | WP-4 | — | documentar el desajuste como aceptado |
| U-03 | una tabla de puertos o dos + gate | WP-7 | — | mantener el gate de pytest (dos tablas comparadas) |

---

## 6. Definición de hecho (por paquete)

- **WP-0:** `grep` del repo = 0 para los cuatro marcadores; `__main__.py` limpio en su ruta; `python -m STM_HRTS`
  resuelve sin ejecutar nada importado; sha256 de lo cuarentenado anotados en el issue de incidente.
- **WP-1:** commit con el árbol completo; la tabla de §1.2 re-medida y verde; tag siguiente nacido de un commit real.
  🟨 **2026-11-06:** primer punto cumplido en local (`45a1fcf` en `DevQoderIA` y un merge en `main` local cuyo árbol
  reproduce el subárbol de 661 ficheros y da 0 marcadores de R-01); faltan el re-medido de §1.2 y que el tag nazca de un
  commit — ambos tras R-01b y a discreción del dueño (R16, no se empuja).
- **WP-2:** los 4 jobs de `ci.yml` ejecutándose en GitHub Actions con run verde (no «creídos»: run real enlazado).
- **WP-3:** `--comprobar` en verde con el PCK reexportado; `publicar_version.ps1` rechaza un `.exe` con PCK ajeno
  (prueba negativa); §7 con 12/12; OTA e2e documentada con captura/log.
- **WP-4:** `WebNodoService` sin miembros `internal` de sutura; `dotnet test` cubre `AnuncioRelease`; `MainWindow.xaml.cs`
  por debajo del umbral acordado; `ReinicioCuenta` unificado (una implementación).
- **WP-5:** 0 `xfail` restantes o cada uno justificado; la matriz de modos de §17.6 regenerada tras WP-3.
- **WP-6:** §14.1 / §14.2 / §14.4 con todas las casillas marcadas y evidencia adjunta.
- **WP-7:** manifiestos regenerados; catálogo sin guiones de publicación obsoletos; política de assets escrita y aplicada.

---

## 7. Riesgos

1. **Pérdida del trabajo no commiteado** (U-02): la zona no está en Git; cualquier limpieza de `CONTRRF` borra
   U0–U5. Mitigación: WP-1 es la segunda prioridad, inmediatamente tras R-01.
2. **OTA repartiendo un binario no auditado** (§7 abierto): mientras `Latest` sea 2.7.7 con R-01 abierto, un visor
   2.7.6 instalado puede actualizarse a un binario cuya carga útil no está auditada. Mitigación: prerelease (decisión del dueño).
3. **RU5 perpetúa el desfase**: sin reexportar el PCK, **nada** de U3/U4 (red, puertos) llega a los clientes, por
   muchas releases que se publiquen. Es el punto que conecta la deuda con #1.
4. **Dos layouts de árbol** (D-01): mientras `main` siga con el layout plano y la zona con el de `DevTraeIA`, cualquier
   script o CI que importe `STM_HRTS.rutas` vale para un árbol y rompe en el otro.
5. **Replantación por merge**: fusionar `DevChatGPTIA`/`DevCursorIA`/`DevDeepSeekHarnessIA`/`DevDevinIA` replanta dos
   de los tres mecanismos de R-01. Prohibido hasta la purga (WP-7, confirmación nominal del dueño).
