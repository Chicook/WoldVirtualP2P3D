# Rescate del índice huérfano — U0.2 (2026-11-05)

El repositorio tenía **cuatro entradas de índice anómalas sin `MERGE_HEAD`** (estado `UU`, `DU` y dos `MD`) que
bloqueaban cualquier fusión. No provenían de un merge en curso: eran restos de una operación interrumpida.

Se resolvieron **por fichero**, sin `git reset --hard` y sin tocar el árbol de trabajo más de lo necesario.
Cada blob que estaba en el índice se volcó aquí antes de resolver, con nombre `<blob-sha-8>__<nombre>` para que
el contenido sea verificable con `git hash-object`.

| Blob en el índice | Stage | Ruta original | Qué se hizo | Copia aquí |
|---|---|---|---|---|
| `05c9cdfd` | 0 (staged, ≠ HEAD `bf651e3a`) | `PRY/actualizacion_91883d55/src/SBSTM/IAFREE.py` | `git reset -- <ruta>` → el índice vuelve a HEAD; el fichero sigue ausente en disco (borrado normal de RFPRMN, **sin commitear**) | `05c9cdfd__IAFREE.py` |
| `19bfe70b` | 0 (staged, ≠ HEAD `3aa50968`) | `PRY/actualizacion_91883d55/src/STM_IA/modelosIAlocal/IALOCAL/uso_ialocal.md` | igual que arriba | `19bfe70b__uso_ialocal.md` |
| `79f41e02` | 2 (= HEAD, «ours») | `PRY/actualizacion_91883d55/src/STMGNRL/mainLCSTM.py` | `git reset -- <ruta>` limpia los tres stages y deja la versión de HEAD en el índice | `79f41e02__mainLCSTM.stage2-HEAD.py` |
| `97ea0f1c` | 1 (base) | idem | se preserva el blob; no hay decisión de contenido | `97ea0f1c__mainLCSTM.stage1.py` |
| `f67df05e` | 3 («theirs») | idem | se preserva el blob (51.374 B, la copia más grande: trabajo posterior) | `f67df05e__mainLCSTM.stage3.py` |
| `42022d27` | 3 (= lo que hay en disco) | `CONTRRF/TLLDCD/src/STM_CH/PSNRL/cierre_sesion_blockchain.json` | `git rm --cached -f <ruta>`: **sale del índice y se queda en disco**. Es un marcador de sesión, no código; `HEAD` y `origin/main` no lo contienen y `.gitignore` **no** lo ignora (comprobado con `grep -n cierre_sesion .gitignore` → 0 coincidencias). | `42022d27__cierre_sesion_blockchain.json` |

**Verificación de la extracción:** `git hash-object` sobre cada fichero rescatado devuelve el mismo prefijo de
`05c9cdfd`, `19bfe70b` y `79f41e02` (3/3 OK).

**Salida medida:** `git status --porcelain | grep -E '^(UU|DU|MD|AA|…)'` → 0 entradas. Quedan `466` borrados sin
confirmar (RFPRMN, RU2: **no se commitean**) y 2 rutas sin rastrear (`CONTRRF/TLLDCD/` y el instantáneo
`PRY/actualizacion_2f040968/`), que es el estado normal del flujo.

**Referencias de seguridad creadas (locales, cero push):** `rescate/20261105/DevQoderIA-HEAD` → `294a72a`,
`rescate/20261105/main` → `490817d`, `rescate/20261105/DevAntigravityIDEIA` → `a43202b`.
