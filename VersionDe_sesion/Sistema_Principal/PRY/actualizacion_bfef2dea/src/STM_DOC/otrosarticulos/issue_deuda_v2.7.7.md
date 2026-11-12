# Deuda técnica y tareas pendientes tras la v2.7.7

Issue de seguimiento abierto al publicar **v2.7.7**. Recoge la deuda que generó la unificación del árbol (U0–U5), la que
registró la auditoría fusionada en `main` (PR #64) y las tareas pendientes, cada una con la evidencia que la cierra.
Nada de lo de abajo es «creído»: los números vienen de medir sobre este árbol el 2026-11-05.

Marco de referencia: `src/STM_DOC/README_DESARROLLO.md` §16 (unificación), §17 (runbook de versión y publicación) y
`docs/SECURITY_AUDIT_2026-11-05{,_ES}.md` + `docs/SECURITY_ROADMAP_2026-11-05{,_ES}.md` (74 hallazgos, 33 entregas).

---

## 0. Bloqueo que pasa por delante de todo lo demás

**R-01 (Etapa 0) sigue abierto y la 2.7.7 se ha publicado con él abierto** — decisión del propietario, anotada en el
cuerpo de la release. Los tres mecanismos son el mismo cargador de segunda etapa, alimentado por un punto de entrega
encubierto de Ethereum.

Qué se publicó, para que este issue no dependa de abrir la release:

| dato | valor verificado en GitHub |
|---|---|
| tag | `v2.7.7` → commit `294a72a593439b79f521e06b2663993d2d97287a` (`DevQoderIA`) |
| `DMWoldVirtualP2P3Dv2.7.7.exe` | 365.114.325 B · `a8ddf7b6d04d71c3f9ec5521ff6adf22ad3f1df4d05074c66f581fd516150c80` |
| `release.json` | 531 B · `5aba52cfe31a97d4223d4fb6c1f13260c3032f9173fe4d52c7c42b7c38b04479` |
| `SHA256SUMS` | 99 B · `31deddd4d13254ef2fe9a7bd1c83f14d1de80872a61b80c7dc5f1dc17851d417` |
| `/releases/latest` | **v2.7.7** (la API que usan OTA y portal ya la sirve) |

| | `origin/main` (`cf7cfd7`) | zona de trabajo | esta máquina |
|---|---|---|---|
| **A1-1** `utils/transport.py` + `STM_HRTS/__main__.py` (RCE en tiempo de importación) | **VIVO** en el snapshot `actualizacion_aeef1149` | NO ALCANZABLE: ni `transport.py` ni `__main__.py`; `grep -rn transport --include=*.py` da 0 | copia inertizada en `STM_DOC/rescate_zona_20261105/` (sha256 `45f1e5c4…`), nunca importada |
| **A5-1** `fa-brand-400.orc` (30.627 B, ofuscado, sha256 `89adac5b…`) + disparador `.vscode` | `tasks.json` ya borrado en `7d60ceb`; quedan el `.orc` y `"task.allowAutomaticTasks": true` | el `.orc` está (mismo sha256); no hay `.vscode/` | sin disparador |
| **A5-2** `opencode/init` (32.436 B; línea 35 = 31.751 caracteres ofuscados, sha256 `8f79baa4…`) | **VIVO**: `opencode/package.json:7` sin cambios | **VIVO**: mismo sha256, misma ruta | sólo con `npm start` en esa carpeta; no ha ocurrido |

- [ ] **R-01**: cuarentena de los tres vectores (mover, no borrar la evidencia), restaurar `init` a su fragmento benigno
      de 34 líneas o quitar el script `start`, eliminar `allowAutomaticTasks`. Criterio de aceptación de la hoja de ruta:
      búsqueda en todo el repo sin `runOn: folderOpen`, sin `allowAutomaticTasks`, sin `.orc`, sin `transport.py`.
- [ ] **R-01b** (decisión del propietario): desofuscar las dos cargas JS e inspeccionar la transacción de Ethereum **en
      sandbox aislada, sin credenciales y sin ruta de red de retorno**; auditar `d510acd` / `3caf0e7` (PR #47) que trajo
      el paquete; anunciar el alcance a las máquinas expuestas.
- [ ] **Replantación por merge**: `DevChatGPTIA`, `DevCursorIA`, `DevDeepSeekHarnessIA` y `DevDevinIA` llevan el snapshot
      `actualizacion_91883d55` **con el `.orc` y `transport.py` dentro**. Fusionar cualquiera de ellas replanta dos de
      los tres mecanismos. `DevQoderIA` y su HEAD: 0 coincidencias.

## 1. Deuda nueva de esta release

- [ ] **El binario no tiene su fuente commiteada.** El tag `v2.7.7` quedó en `294a72a593439b79f521e06b2663993d2d97287a`
      (`DevQoderIA`, 2026-10-30), un commit que no tiene `VERSION.json` ni `VSC#/Nucleo`; el árbol que compiló el `.exe`
      es la zona de trabajo, versionada como snapshot aparte. Es el mismo desfase binario/anuncio que mató DT-08, esta
      vez con tag irreversible. **Cierre:** promover el árbol canónico y que la siguiente release nazca de un commit.
- [ ] **La release aparece por debajo de la 2.7.6 en la página de Releases** (medido al publicar): GitHub ordena la
      listado por `created_at`, y para un tag nuevo ese campo es **la fecha del commit señalado** — `2026-10-30` en vez
      de hoy. Consecuencia: `…/releases/latest` (la API que usan OTA y portal) sí devuelve **v2.7.7**, pero una persona
      que entra en la página ve primero 2.7.6 y 2.7.5. Es un efecto directo del punto anterior, no un ajuste de GitHub:
      se cierra solo cuando el tag apunte a un commit actual.
- [ ] **`publicar_version.ps1` no ancla el PCK.** Lee la versión del `.exe` pero no compara `pck_sha256` contra el PCK
      incrustado, así que no puede detectar la 2.7.6: un `.exe` con PCK viejo y `FileVersion` nuevo sale verde. **Cierre:**
      paso de comprobación + prueba negativa. (En la 2.7.7 el desajuste es conocido y está anunciado en las notas: el PCK
      embebido sigue siendo el de la 2.7.6 hasta reexportar — punto RU5 más abajo.)

### Cerrado en el acto de publicar (evidencia, no deuda)

El guion **no había completado nunca la ruta `-Publicar`**: con `$ErrorActionPreference = "Stop"`, el `release not found`
que `gh` escribe por stderr es un `NativeCommandError` terminal y el paso 6 moría en su propia sonda previa, antes de
subir el primer byte. Arreglado con la función `Gh` (baja la preferencia durante la llamada, deja el código en
`GH_EXITO` y muestra el mensaje si falla). Medido después del arreglo: `-Publicar` sin `-Objetivo` → salida 1; con rama
inexistente → salida 1; con `DevQoderIA` → `gh release create` y release publicada. Queda pendiente una prueba de
comportamiento automatizada (§1.3 de la hoja de rutas: hoy sólo hay evidencia de tres corridas manuales).

## 2. Deuda de promoción (bloquea que el CI exista de verdad)

- [ ] **DT-01**: `ci.yml` sigue anidado en `src/STM_HRTS/.github/workflows/`; GitHub no lo lee. Hoy tiene **cuatro jobs**
      (`resolver-taller`, `python-suite`, `csharp-suite`, `godot-headless`) y **ninguno se ha ejecutado nunca**.
- [ ] Al promocionar hay que borrar **73 paths de `main`** (44 copias planas de `STM_HRTS/utils`, 9 de la raíz
      `STM_HRTS/`, 20 de `VSC#/{Chat,Services,Seguridad,RedP2P,STM_actualizar}` movidos a `VSC#/Nucleo`) y entran **49
      ficheros nuevos** del núcleo.
- [ ] **Dos árboles en conflicto**: la zona adopta el layout de `DevTraeIA` (`STM_HRTS/utils/add_utils/*`); `main` sigue
      con el plano. El workflow naufragado importa `STM_HRTS.rutas` y usa `-c STM_HRTS/pytest.ini`, rutas que sólo valen
      en `main`. Ramas sin fusionar: `DevTraeIA` (2 ahead / 505 fich), `DevAntigravityIDEIA` (5 ahead / 618 fich),
      `security/audit-roadmap-2026-11-05` (ya fusionada en #64).
- [ ] **Entry point roto**: `pyproject.toml:27` declara `hrts = "STM_HRTS.__main__:main"` y no existe
      `src/STM_HRTS/__main__.py` (`importlib` lo confirma: `ModuleNotFoundError`). El único que existe en el repo es el
      de `main`, que es justo el fichero de A1-1 — por eso no se ha creado desde la zona. **Cierre:** al acabar R-01,
      `__main__.py` limpio de seis líneas o reorientar el manifiesto a `STM_HRTS.utils.add_utils.__main__:main`, y cambiar
      `test_manifiesto_declara_la_consola`, que hoy fija la cadena rota. Doce ficheros documentan hoy la forma rota
      (`python -m STM_HRTS rutas`); la que funciona es `python -m STM_HRTS.utils.add_utils <subcomando>`.
- [ ] **Dos guiones de publicación obsoletos siguen en el catálogo** (`publish_release_v275.ps1`,
      `publish_release_v276.ps1`): cablean versión, carpeta y notas, y pueden publicar. Ninguna prueba los referencia.
      **Cierre:** moverlos a `STM_DOC/rescate_zona_20261105/`, que deja de listarlos porque el catálogo sólo recorre
      `STM_HRTS/utils`; el catálogo baja de 48 a 46 herramientas.

## 3. Deuda de la puerta de Godot (DT-05, queda `[~]`)

- [ ] `Personalizacion.gd:952`: `SCRIPT ERROR: Trying to assign value of type 'Nil' to a variable of type
      'PackedInt32Array'` (`_vertices_cabeza` ← `_cuenta_cabeza` ← `_buscar_cuerpo` ← `_aplicar_figura`). Lo provocan
      `probar_registro` y `probar_flujo_portal`, **y los dos guiones salen 0 igualmente**. Está marcado
      `xfail(strict=True)`; al arreglarlo, la puerta falla con `XPASS` hasta quitar la marca.
- [ ] Dos verdes sin fixture: `validar_anim_glb` recorre `res://avtrnCRS/GTLF_GODOT/` y ve `0 modelos`;
      `validar_personalizacion` recorre `0` `Ch3D.tscn` con el PCK montado. Son `xfail(strict=True)` por lo mismo.
- [ ] **11 guiones fuera de la puerta** por no tener veredicto (`capturar_*`, `render_avatares`,
      `probar_cara`/`cuerpo`/`personalizacion`, `inspeccionar_avatar`, `inspect_anim`, las dos sondas LAN y
      `sonda_escena_construccion`): unos necesitan ventana y otros terminan con `quit()` a secas.
- [ ] El modo de cada prueba es **declarado** (`herramientas.PCK_OBLIGATORIO`, 9), no deducido: al reexportar el PCK hay
      que repetir `python tests/godot/medicion_modos.py` (~4 min) y revisar la matriz de §17.6, o la puerta se discrepa
      del árbol en silencio.
- [ ] `probar_red_invitacion` depende de un `trycloudflare.com` de ejemplo y se le pasan argumentos fijos (`ARGUMENTOS`);
      si el endpoint desaparece, la puerta se vuelve roja sin que nada del producto haya cambiado.
- [ ] `test_headless.py:88-94` toma `max()` de todos los recuentos de fallos del veredicto si un guion imprime dos
      cifras; un «0 FALLOS» impreso por un paso intermedio podría ocultar el veredicto real.

## 4. Deuda que ya estaba en #48 y no se tocó

DT-04 (prueba LAN de dos equipos, cierre de #1) · DT-06 (corte/timeout/reanudación en `--update-selftest`) · DT-07/08/09
(cobertura de OTA y descubrimiento, `GetEntryAssembly()`, IPv6 con corchetes) · DT-12…DT-16 (`WebNodoService`: estado
estático, puntos de sutura `internal`, refresco de 5 min) · DT-15 hecho en el workflow pero sin activar por DT-01 ·
**RU5** (reexportar `VSC#/wvp3d.pck` + `--registrar-pck`): sin ello, nada de U3/U4 llega al binario.

## 5. Deuda de issues vivos y de producto

- [#1](https://github.com/Chicook/WoldVirtualP2P3D/issues/1) red LAN: falta la prueba física de dos equipos.
- [#15](https://github.com/Chicook/WoldVirtualP2P3D/issues/15): métrica de huella. 2.7.6 = 348,17 MiB ·
  **2.7.7 = 365.114.325 B (348,19 MiB)**; sigue sin desglose instalado (binario + runtime + motor + PCK) y sin decisión
  **D3**. Sin asset de Linux en ambas.
- [#26](https://github.com/Chicook/WoldVirtualP2P3D/issues/26) SMTPLC: bloqueado por las decisiones **D5** y **D8**;
  `LocationAccountLedger.cs` exporta y fusiona sin llamador productivo.
- [#48](https://github.com/Chicook/WoldVirtualP2P3D/issues/48): paraguas de DT-01…DT-16; este issue no lo duplica, sólo
  añade lo de arriba.
- **U6 pendiente**: el `README.md` de la raíz que trae `main` es una carta de contribuidor de 1.795 B (commit `1f9c446`)
  que **sustituyó** al README profesional de 111.734 B (blob `722bbdb8`), con `readme.md` duplicado por colisión de
  mayúsculas bajo `core.ignorecase=true`.
- **Peso**: #63 añadió 252,3 MiB de assets al historial (40 PNG = 222,0 MiB) justo tras la limpieza del 2026-10-30. La
  zona, por su parte, pesa 3.402 MiB de ruido no conmutable (opencode 881, `VSC#/bin` 713, `VSC#/Tests` 402,
  `VSC#/obj` 386).

## Orden sugerido

1. **R-01** (Etapa 0) — por delante de todo, incluida la publicación.
2. Reexportar el PCK y `--registrar-pck` (**RU5**) para que U3/U4 llegue al binario.
3. Promocionar el árbol canónico + `ci.yml` a la raíz (DT-01) y con ello cerrar §1.1 y §2.
4. Ancla del PCK en `publicar_version.ps1` (§1.3), antes de la siguiente release.
5. Los cuatro `xfail` de §3, y con `Personalizacion.gd:952` primero porque es el único que da errores con salida 0.
6. §4 y §5 por hito, con la métrica de huella (#15) cuando el CI ya exista.
