# R-01b · Auditoría de procedencia PR #47 — 2026-11-06

Auditoría de **sólo lectura** (git + hash, sin compilar, abrir ni ejecutar carga, sin red de retorno) de
`d510acd` / `3caf0e7` (PR #47), que la auditoría fusionada en `main` (PR #64) señala como el cambio que trajo los
tres mecanismos plantados. Es la parte de **R-01b** que sí procede desde este taller; la desofuscación de las dos
cargas JS y la inspección de la transacción de Ethereum siguen siendo **fuera de este entorno** (sandbox aislada,
decisión del propietario, §2.2).

> **La autoría no está probada.** Los campos de autor de git los fija quien commitea y no son prueba de quién escribió
> el código. Ninguna persona queda atribuida aquí ni en los issues ni en la Discusión #67.

## 1. Los dos commits

| | sha | fecha (autor) | asunto | ramas que lo contienen |
|---|---|---|---|---|
| carga | `d510acd7f6574fe4281105242b2e5688d8bd15f9` | 2026-11-01 02:15 +0100 | `feat: add CI workflow, H1/H2/H3 test suites, update scripts, and security checks for P2P network and OTA updates` | **sólo** `DevAntigravityIDEIA` |
| hermano | `c395284` (mismo asunto) | — | mismo mensaje | `main` + 12 ramas (todas las `stage1/*`, `applecat88-patch-*`, `arte/s8`, `security/audit-roadmap`) |
| merge | `3caf0e77f1af78b8a0174029e7a74a9fb63fbc79` | 2026-11-02 23:20 +0100 | `Merge pull request #47 from CesarChaMal/development` | `main` + las mismas 12 ramas |

- `gh pr view 47`: base `main`, head `development`, **estado MERGED**, mergeCommit `75eaff8…`.
- `d510acd` añade los tres mecanismos **de golpe** (`--diff-filter=A` contra la ruta exacta del snapshot
  `actualizacion_aeef1149/src`): `STM_HRTS/utils/transport.py`, `STM_HRTS/__main__.py`,
  `MTBGT/…/public/fonts/fa-brand-400.orc`, `STM_HRTS/opencode/init`, `STM_HRTS/opencode/package.json`. En total toca
  **979 ficheros** con un mensaje que no menciona nada de esto.
- El hermano `c395284` añade `__main__.py` y `opencode/package.json` en `main`: la cadena está repartida en dos ramas
  (capa D en `DevAntigravityIDEIA`, su reflejo parcial en `main`), lo que explica que `main` y la rama de Antigravity
  tengan el mismo mecanismo en rutas espejo.

## 2. Estado de los blobs (verificado por sha256 del blob, sin tocar disco)

En `origin/main`, snapshot `actualizacion_aeef1149/src` — **los cuatro siguen vivos**:

| ruta | sha256 (12) | coincide con |
|---|---|---|
| `STM_HRTS/utils/transport.py` | `45f1e5c405d1…` | A1-1 (documentado) |
| `STM_HRTS/__main__.py` | `a7b228cc4129…` | nuevo dato (ver §3) |
| `STM_HRTS/opencode/init` | `8f79baa43b4a…` | A5-2 (documentado) |
| `…/public/fonts/fa-brand-400.orc` | `89adac5ba294…` | A5-1 (documentado) |

En `HEAD` (DevQoderIA, zona) `transport.py` está **AUSENTE** (cuarentena WP-0, `MANIFIESTO.md`).

## 3. A1-1 confirmado en tiempo de importación (estructura, sin ejecutar)

`git show d510acd:…/STM_HRTS/__main__.py` → línea 10 `import utils.transport`. Ese import basta para disparar el
cargador: al ejecutar `python -m STM_HRTS` se importa `__main__` → se importa `transport` → corre su código de módulo.

`transport.py` (58 líneas) no define funciones benignas: a nivel de módulo monta la segunda etapa desde un punto de
entrega encubierto de Ethereum (medido por grep de firma, **sin** abrir la URL ni resolver el `bytes.fromhex`):

| línea | qué hace |
|---|---|
| 10 | `_addr = "0x3b1574417524c11a7403c4b232CAcBb320CceBC6"` (la dirección de entrega) |
| 19 | `f"https://api.ethplorer.io/getAddressTransactions/{_addr}"` (consulta de transacciones de la dirección) |
| 27-31 | `_rpc` a `https://ethereum.publicnode.com` con un cuerpo `jsonrpc` (traza `eth_getTransactionByHash` implícita) |
| 38 | `_source = bytes.fromhex(_rpc["result"]["input"][2:]).decode()` (descodifica el *input* de la transacción como fuente y la ejecuta) |

Es el mismo cargador de segunda etapa que la auditoría atribuye a A5-1 y A5-2: el payload vive fuera del repo, en el
*calldata* de una transacción, y sólo se materializa en runtime. **No se ha tocado la red ni se ha desenrollado la
carga desde aquí**: eso es R-01b en sandbox (proprietario).

## 4. Consecuencia para el plan

- La cuarentena de la zona (WP-0) **no limpia `main`**: los cuatro blobs siguen en `origin/main` y en 12 ramas. La
  limpieza real de R-01 sólo llega al repo al **promocionar el árbol canónico** (WP-1, push/merge = decisión del
  dueño, R16) y al llevar la cuarentena a esas ramas.
- La **replantación** que advierte #66 se ve aquí: `c395284` ya está en `main`, y fusionar `DevAntigravityIDEIA`
  (`d510acd`) reinyectaría `transport.py` y el `.orc` en el snapshot `aeef1149`.
- **Acciones del propietario que esto no puede cerrar**: (a) desofuscar las dos cargas JS y la transacción en sandbox;
  (b) anunciar el alcance a las máquinas expuestas; (c) purgar los blobs de `main` y las ramas al promocionar. Ninguna
  se hace desde el taller (R16 / fuera de entorno). **Ejecución paso a paso en
  [`procedimiento_R01b_propietario_20261106.md`](procedimiento_R01b_propietario_20261106.md).**

## Cómo reproducir (sólo lectura)

```bash
cd E:/WoldVirtualP2P3D
git show -s --format='%H %ad %s' d510acd c395284 3caf0e7        # commits
gh pr view 47 --json number,title,state,baseRefName,headRefName,mergeCommit
A="VersionDe_sesion/Sistema_Principal/PRY/actualizacion_aeef1149/src"
git show d510acd --name-only --format='' | grep -E 'transport|__main__|\.orc|opencode/(init|package\.json)'
git show "d510acd:$A/STM_HRTS/__main__.py" | grep -n 'import utils.transport'
git show "d510acd:$A/STM_HRTS/utils/transport.py" | grep -nE '_addr|ethplorer|publicnode|fromhex'
for f in STM_HRTS/utils/transport.py STM_HRTS/__main__.py STM_HRTS/opencode/init; do \
  git show "origin/main:$A/$f" | sha256sum; done
git branch -a --contains d510acd ; git branch -a --contains c395284
```
