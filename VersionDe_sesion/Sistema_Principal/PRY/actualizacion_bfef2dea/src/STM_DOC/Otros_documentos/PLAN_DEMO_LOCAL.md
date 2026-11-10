# Plan de demo local · LucIA anfitriona + wallet embebida (discusión #86)

| dato | valor |
|---|---|
| **Objetivo** | Un demo inicial que funcione **en esta máquina**, de principio a fin, sin red externa ni release |
| **Árbol analizado** | `VersionDe_sesion/CONTRRF/TLLDCD/src` (taller de trabajo) |
| **Foco** | `src/MTBGT` (mundo Godot) y `src/STM_BKCH` (servidor de bloques) |
| **Artículo de referencia** | [Discusión #86 — «LucIA anfitriona y la wallet embebida»](https://github.com/Chicook/WoldVirtualP2P3D/discussions/86) |
| **Fecha del análisis** | 2026-11-10 |
| **Rama / HEAD** | `DevDeepSeekHarnessIA` · `3d539d2` «nick de 10 a 15 letras y botón Actualización de cuenta» |
| **Método** | Ejecución real: Python 3.14 + numpy 2.3.5, Godot 4.7.2 (`_tmp_tests/godot`), Windows 11 |
| **Estado** | Diseño cerrado; **no** se ha modificado ni un fichero del producto para escribir este plan |

---

## 0. Qué significa «que funcione localmente»

El demo se considera conseguido cuando una persona, en esta máquina y sin tocar código, puede:

1. Arrancar el servidor de cuentas con **un comando**.
2. Abrir el mundo y **ser recibido por LucIA** en su oficina.
3. Escribir un nick, pulsar **«Crear mi cuenta»** y recibir un **hash único** minado en la cadena.
4. **Descargar el `.zip` de su cuenta** y ver que se guarda.
5. Elegir avatar, registrarse y **entrar a su isla**.
6. Cerrar y volver a abrir: la cuenta **se reconoce** y se entra sin repetir el alta.

Eso es exactamente el flujo de la discusión #86 §2 y §3: **«una cuenta = un bloque = un archivo»**.

### 0.1 Qué NO es este plan

- No es una propuesta de funcionalidad nueva: implementa lo que #86 ya diseña.
- No toca release, PCK, `dotnet publish` ni OTA (reglas de `STM_DOC/Otros_documentos/REGLAS_DE_ACTUALIZACION.md`).
- No ordena ejecutar los scripts destructivos de `STM_HRTS/utils/STM_UTILS/`.
- No promete consenso multi-nodo, recuperación social ni IPFS real: quedan declarados como deuda (D15, F9-08 del plan general).

---

## 1. Veredicto en diez líneas

1. **La recepción de LucIA ya existe y se ve bien** (captura `_tmp_tests/captura_recepcion.png`): oficina, personaje, formulario superpuesto.
2. **El servidor de cuentas ya existe y funciona**: probado end-to-end hoy → `200 /status`, `201` alta con hash de 64 hex, `.zip` de 642 B con firma `PK`, `422` con nick corto.
3. **El cliente Godot ya habla con el servidor**: `LuciaRecepcion.gd` hace `POST /alta-cuenta` y guarda `user://cuenta.json`.
4. **Pero el flujo está partido en tres copias del proyecto**: ninguna tiene a la vez el `Boot.gd` bueno y el `LuciaRecepcion.gd` bueno.
5. **`Boot.gd` del proyecto canónico enseña la recepción siempre**, incluso al usuario que ya tiene cuenta (no hay atajo `cuenta.json`).
6. **La copia que sí tiene el atajo (`WVP`) precarga la recepción desde fuera del proyecto** (`res://../WoldVirtualP2P3D/…`) y no lleva el fichero: no puede exportarse.
7. **La isla real carga sin errores** (probado headless), pero hereda un `p2p_session.json` obsoleto y se queda esperando a `192.168.1.103:8911`: por eso la sesión anterior acabó sustituyéndola por una **maqueta de cajas**.
8. **El alta de usuario nuevo no descarga el `.zip`** (solo la migración lo hace): el paso 5 del artículo está sin cumplir.
9. **No hay lanzador del servidor**: `python -m STM_BKCH.bksvcb_net` imprime y mina, pero **no arranca el HTTP** que el cliente necesita.
10. **Nada de esto es grande**: son ~5 días de trabajo ordenado, casi todo pegamento entre piezas que ya funcionan.

---

## 2. Estado medido del árbol

### 2.1 Inventario (sin `bin/`, `obj/`, `.godot/`, `__pycache__`, `gltfimport/`)

| Métrica | Valor medido |
|---|---:|
| Ficheros | **3.147** |
| GDScript (`.gd`) | 355 ficheros · **62.370** líneas |
| Python (`.py`) | 471 ficheros · **116.957** líneas |
| C# (`.cs`) | 88 ficheros · **19.676** líneas |
| Escenas (`.tscn`) | 229 ficheros · **19.201** líneas |
| XAML (`.xaml`) | 9 ficheros · 1.748 líneas |
| `MTBGT/` | **5.069,5 MB** · 4.919 ficheros |
| `STM_BKCH/` | 8 módulos · **1.379** líneas Python |

### 2.2 `MTBGT`: cinco copias del mismo proyecto, todas distintas

Hay **cinco** `project.godot` (todos con la misma escena principal `uid://5bh8su08n101`):

| Copia | Ficheros | `Boot.gd` | `LuciaRecepcion.gd` | Papel real |
|---|---:|---|---|---|
| `WoldVirtualP2P3D/` | 1.390 | 13.689 B (`5ACD52…`) | **22.013 B** (`B1631B…`) | **Canónico**: es el que lanza el visor C# (`GodotConfig.cs:55`) y el que tiene caché `.godot` |
| `WVP/` | 726 | **14.451 B** (`9728E6…`) | **no existe** | Copia podada con el `Boot.gd` más nuevo, pero **precarga fuera del proyecto** |
| `WoldVirtualP2P3D_borrador/` | 1.261 | 13.719 B (`D8AF1F…`) | **26.765 B** (`61B377…`) | Banco de pruebas: tiene la recepción más nueva y `DemoBoot.gd` |
| `WoldVirtualP2P3D_v2/` | 988 | — | 0 B (stub) | Reorganización a medias (carpetas `00_nucleo`…`90_tests`) |
| `WoldVirtualP2P3D_borrador_recuperacion/` | — | — | — | Rescate puntual |

**Los tres `Boot.gd` tienen hashes distintos** y los dos `LuciaRecepcion.gd` también. No es duplicado: es **divergencia**.

Lo que tiene cada uno y le falta al otro:

| Capacidad | `WoldVirtualP2P3D` | `WVP` | `borrador` |
|---|:--:|:--:|:--:|
| Recepción **dentro** del proyecto | ✅ | ❌ (preload `res://../`) | ✅ |
| Atajo «ya tengo cuenta → a la isla» | ❌ | ✅ | ❌ |
| Descarga del `.zip` tras el alta | ❌ | ❌ | ✅ |
| Ganchos de demo (`forzar_nuevo`, `auto_registro`) | ❌ | ❌ | ✅ |
| Caché de importación (`.godot`) | ✅ | ❌ | ✅ |

> **Consecuencia:** hoy no hay **ninguna** copia que pueda ejecutar el flujo completo de #86 de una sola pasada. Ese es el trabajo F0.

### 2.3 `STM_BKCH`: servidor real, contrato real

| Fichero | Líneas | Rol |
|---|---:|---|
| `BKSVCB.py` | 603 | Cadena, bloques, PoW, cuota por ubicación, `alta_cuenta`, `migrar_cuenta`, `generar_zip_cuenta` |
| `bksvcb_net.py` | 163 | HTTP (`ThreadingHTTPServer`), daemon, singleton |
| `__init__.py` | 379 | Fachada del subsistema (conversor 50 neuronas, IPFS shim, diagnóstico) |
| `compat_local.py` | 181 | Shims sin daemon (IPFS no-op **que nunca borra**) |
| `demo_cuentas.py` | 53 | Demo de cuentas por consola |

**Endpoints que existen de verdad** (`bksvcb_net.py`):

| Método | Ruta | Comprobado hoy |
|---|---|---|
| GET | `/status`, `/blocks`, `/transform`, `/mine` | `200` |
| GET | `/descargar-cuenta-zip?cuenta_hash=` | `200` · 642 B · firma `PK` |
| POST | `/alta-cuenta` | `201` + `cuenta_hash` de 64 hex |
| POST | `/migrar-cuenta` | existe (no probado en esta sesión) |
| POST | `/transaction`, `/learn` | existen |

### 2.4 Lo que YA funciona (evidencia ejecutada hoy)

| # | Hecho | Evidencia |
|---|---|---|
| 1 | El servidor importa en **1,86 s** con numpy | `import STM_BKCH.bksvcb_net` → `IMPORT OK` |
| 2 | Alta de cuenta end-to-end | `201`, hash `00754b19…`, bloque #1, ledger de 3.318 B |
| 3 | Descarga del `.zip` | `200`, 642 B, cabecera `PK` |
| 4 | Validación de nick | nick de 7 letras → `422 «entre 10 y 15 letras»` |
| 5 | El proyecto Godot arranca headless | **4,4 s**, `Boot.gd` imprime su banner completo |
| 6 | La recepción se monta y se ve | Captura `captura_recepcion.png` (LucIA + formulario) |
| 7 | La isla real carga sin errores de script | `ISLA3Dblock.tscn` en headless: 0 `SCRIPT ERROR` |
| 8 | El flujo completo se automatizó una vez | `_borrador/prueba_demo_completa.log` → `[OK] … 5 capturas` |

### 2.5 Las ocho puertas del demo

| # | Puerta | Estado hoy | Detalle |
|---|---|:--:|---|
| P1 | El servidor arranca con un comando | 🔴 | No hay lanzador; `__main__` no levanta HTTP |
| P2 | El servidor persiste en ledger **de demo** | 🟡 | Escribe en el ledger compartido del sistema |
| P3 | El proyecto Godot importa y arranca | 🟢 | 4,4 s en `WoldVirtualP2P3D` |
| P4 | La recepción se ve sin errores | 🔴 | `ERROR: Can't add child '@PanelContainer'… already has a parent` |
| P5 | El alta devuelve hash y guarda `cuenta.json` | 🟢 | Probado (cuenta `chicook`, 2026-11-09 20:46) |
| P6 | El `.zip` se descarga también en el alta | 🔴 | Solo lo hace la migración |
| P7 | Se entra a la isla | 🔴 | Rol resuelto como **CLIENTE_REMOTO** por sesión obsoleta |
| P8 | Al reabrir, la cuenta se reconoce | 🔴 | El `Boot.gd` canónico no lee `cuenta.json` |

---

## 3. Hallazgos bloqueantes

Cada hallazgo lleva **síntoma · evidencia · impacto · tarea que lo cierra**.

### D-01 · El flujo está partido en tres copias divergentes
- **Síntoma:** ninguna copia tiene `Boot.gd` bueno + `LuciaRecepcion.gd` bueno.
- **Evidencia:** tres hashes distintos de `Boot.gd`; `WVP` no contiene `LuciaRecepcion.gd`; `borrador` sí pero con `Boot` viejo.
- **Impacto:** cualquier arreglo se hace tres veces y se pierde al siguiente copiado.
- **Cierra:** **F0-01/F0-02**.

### D-02 · `WVP/Boot.gd` precarga fuera del proyecto
- **Síntoma:** `const RECEPCION_LUCIA = preload("res://../WoldVirtualP2P3D/gdscrip/LuciaRecepcion.gd")`.
- **Evidencia:** `WVP/gdscrip/Boot.gd:20`; `res://../` queda fuera de la raíz del proyecto y **no existe en un PCK**.
- **Impacto:** la copia con mejor lógica **no se puede exportar**; en editor depende de que el vecino exista.
- **Cierra:** **F0-02**.

### D-03 · Panel añadido dos veces en el formulario de recepción
- **Síntoma:** `ERROR: Can't add child '@PanelContainer@18' to '@Control@15', already has a parent`.
- **Evidencia:** reproducido en headless; `LuciaRecepcion.gd` hace `raiz.add_child(panel)` en la **línea 119** y otra vez en la **131**.
- **Impacto:** el árbol de UI queda inconsistente (el estilo y el alto se aplican a un nodo ya colgado), y el error ensucia cualquier validación automática.
- **Cierra:** **F0-03**.

### D-04 · El usuario con cuenta vuelve a ver la recepción
- **Síntoma:** al reabrir con `user://cuenta.json` válido, sigue saliendo el formulario.
- **Evidencia:** `WoldVirtualP2P3D/Boot.gd` → 0 apariciones de `cuenta.json`; arranque headless con cuenta existente → `_mostrar_lucia_recepcion()` (línea 74).
- **Impacto:** el demo no puede demostrar «vuelvo y entro».
- **Cierra:** **F0-04**.

### D-05 · El alta no entrega el archivo
- **Síntoma:** tras `201`, se guarda `cuenta.json` pero **no se descarga** el `.zip`.
- **Evidencia:** `_on_alta_completada` (`LuciaRecepcion.gd:399-415`) no llama a `_descargar_zip_cuenta`; la migración sí (`:554`). En `borrador` ya está corregido.
- **Impacto:** se incumple el paso 5 de #86 («descarga un .zip con ese hash»).
- **Cierra:** **F2-01**.

### D-06 · El servidor no tiene lanzador y comparte ledger con el sistema
- **Síntoma:** `python -m STM_BKCH.bksvcb_net` imprime el resumen y mina una transacción, pero **no arranca el HTTP**; el ledger es el del sistema (`STM_CH/blockchain_ledger.json`).
- **Evidencia:** `bksvcb_net.py:154-193` (bloque `__main__` sin `iniciar_servidor_blockchain`); `BKSVCB.LEDGER_PATH` viene de `STM_HRTS.rutas`.
- **Impacto:** el cliente recibe `error 4` (no puede conectar) y el demo ensucia datos reales.
- **Cierra:** **F1-01/F1-02**.

### D-07 · La segunda ejecución choca con «un bloque por PC»
- **Síntoma:** repetir el alta con la misma huella devuelve `409`.
- **Evidencia:** `PERMITIR_REPETIR = False` (`BKSVCB.py:29`); probado: segunda alta idéntica → `409`.
- **Impacto:** un demo que se repite cada mañana se rompe a la segunda.
- **Cierra:** **F1-03** (reset de demo explícito, nunca silencioso).

### D-08 · La isla se cuelga por una sesión P2P obsoleta
- **Síntoma:** `Rol EFECTIVO: CLIENTE_REMOTO -> 192.168.1.103`, y se queda esperando handshake.
- **Evidencia:** `user://p2p_session.json` con `peerUrl: 192.168.1.103`; `ChunkManager.gd:315` marca cliente explícito si el host no es loopback.
- **Impacto:** el mundo real nunca aparece; de ahí la maqueta de cajas.
- **Cierra:** **F3-01/F3-02**.

### D-09 · Dos nicks para una cuenta
- **Síntoma:** `cuenta.json` dice `chicook` (7 letras) y `registro.cfg` dice `chicookfarrior` (14).
- **Evidencia:** ficheros en `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D`; el servidor hoy **exige 10–15** y `7` daría `422`.
- **Impacto:** la identidad de la cadena y la del mundo no coinciden; el saludo y los récords usan otra.
- **Cierra:** **F2-02**.

### D-10 · La documentación de seguridad promete lo que el código no hace
- **Síntoma:** `README_SEGURIDAD.md` anuncia *rate limiting* (10 req/min, `429`) y `GET /intentos`.
- **Evidencia:** ni `429` por IP ni `/intentos` existen en `bksvcb_net.py`; solo hay cooldown por ubicación (`BKSVCB.py:467`).
- **Impacto:** quien lea la doc creerá que el demo está protegido cuando no lo está.
- **Cierra:** **F4-03**.

### D-11 · La «validación de conexión» depende del visor C#
- **Síntoma:** el botón espera `user://validacion_resultado.json`, que escribe el visor WPF; en un demo solo-Godot nadie lo escribe.
- **Evidencia:** `LuciaRecepcion.gd:294-341` (polling) y `Boot.gd:154-160` (solo registra la señal).
- **Impacto:** el usuario existente se queda en «Solicitando validación…» para siempre.
- **Cierra:** **F2-03**.

### D-12 · Sin pruebas del contrato de cuentas
- **Síntoma:** los 24 ficheros de `tests/` no cubren `/alta-cuenta`, `/migrar-cuenta` ni el `.zip`.
- **Evidencia:** `tests/` lista `test_stage1_*`, `test_red`, `test_stm_def`… ninguno de BKCH.
- **Impacto:** cualquier cambio de nick, formato o cuota se rompe en silencio.
- **Cierra:** **F4-01** (el arnés debe crecer, no sustituirse).

---

## 4. Decisiones que hay que cerrar antes de tocar código

| ID | Decisión | Recomendación | Bloquea |
|---|---|---|---|
| **D1** | ¿Qué copia es la buena? | **`MTBGT/WoldVirtualP2P3D`**, que es la que lanza el visor (`GodotConfig.cs:55`) y la única con caché. `WVP` y `borrador` se **archivan**, no se borran | F0 |
| **D2** | ¿Se borran las copias? | **No.** Mover a `MTBGT/_archivo_20261110/` y dejar una nota. Cero pérdida, cero ambigüedad | F0 |
| **D3** | ¿Cómo valida el usuario existente? | **Validación local contra la cadena** (`GET /status` + hash presente). El túnel SSH queda como TODO explícito del visor C# | F2-03 |
| **D4** | ¿Ledger del demo? | **Aislado** (`_demo/ledger.json`) con `--reset` explícito. El ledger del sistema no se toca | F1-02 |
| **D5** | ¿El demo exporta PCK? | **No.** Se ejecuta desde fuente con el Godot 4.7.2 ya extraído. Exportar es otra fase y otro riesgo | F5 |

---

## 5. Arquitectura objetivo

```
┌─────────────────────────────┐        HTTP/JSON 127.0.0.1:8545        ┌──────────────────────────┐
│  Godot 4.7.2                │ ─────────────────────────────────────▶ │  STM_BKCH (Python)       │
│  MTBGT/WoldVirtualP2P3D     │   POST /alta-cuenta                    │  bksvcb_net  (HTTP)      │
│                             │   POST /migrar-cuenta                  │  BKSVCB      (cadena)    │
│  Boot.gd ──▶ LuciaRecepcion │   GET  /descargar-cuenta-zip           │  ledger demo aislado     │
│      │            │         │ ◀───────────────────────────────────── │                          │
│      │            │         │   201 {cuenta_hash, indice_bloque}     └──────────────────────────┘
│      ▼            ▼         │   200 (application/zip)
│  carrusel     user://       │
│  registro      cuenta.json  │
│  portal        cuenta_*.zip │
│      │                      │
│      ▼                      │
│  ISLA3Dblock (rol servidor) │
└─────────────────────────────┘
```

**Ficheros de estado** (todos en `user://` = `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\`):

| Fichero | Quién escribe | Para qué |
|---|---|---|
| `cuenta.json` | `LuciaRecepcion.gd` | hash único + nick + fecha (la cuenta) |
| `cuenta_<hash16>.zip` | `LuciaRecepcion.gd` | el archivo que el usuario guarda |
| `registro.cfg` | carrusel/registro | avatar elegido + sectores de personalización |
| `identidad/uuid` (en `registro.cfg`) | `Identidad.gd` | huella de 32 hex que valida el servidor |
| `ubicacion_smtplc.json` | visor C# (**no** Godot) | `ubicacion_hash` opcional (cuota SMTPLC) |
| `p2p_session.json` | visor C# | rol y host de red (¡fuente del cuelgue D-08!) |

---

## 6. Plan por fases

**Total estimado: 5 días** (1 persona). Orden estricto: cada fase deja el demo en un estado demostrable.

| Fase | Objetivo | Esfuerzo | Puerta de salida |
|---|---|---|---|
| **F0** | Un solo proyecto que arranca limpio | 0,5 d | Recepción visible **sin** el error de panel |
| **F1** | Servidor reproducible | 0,5 d | `.\demo_local.ps1 -Reset` deja `/status` en verde |
| **F2** | Flujo de cuenta completo | 1,5 d | Alta → hash → `.zip` → reapertura reconocida |
| **F3** | Entrar al mundo de verdad | 1 d | Isla visible en ~10 s, sin maqueta |
| **F4** | Pruebas y blindaje | 1 d | Arnés verde + E2E automático |
| **F5** | Empaquetado y guion | 0,5 d | Un comando y un guion de 3 minutos |
| **F6** | Documentación y cierre | 0,5 d | `DEMO.md` + registros actualizados |

---

### F0 — Un solo proyecto que arranca limpio (0,5 día)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F0-01** | **Congelar copias**: mover `MTBGT/WVP`, `WoldVirtualP2P3D_borrador`, `WoldVirtualP2P3D_v2` y `…_borrador_recuperacion` a `MTBGT/_archivo_20261110/` con un `LEEME.md` que diga qué contenía cada una | S | `Get-ChildItem MTBGT\*\project.godot` devuelve **una** ruta |
| **F0-02** | **Fusionar lo bueno** en `WoldVirtualP2P3D`: (a) de `WVP`, el bloque `cuenta.json → _entrar_a_isla()` (`WVP/gdscrip/Boot.gd:71-90`); (b) de `borrador`, `LuciaRecepcion.gd` (26.765 B, con descarga de `.zip` y ganchos de demo) | M | `Boot.gd` contiene la rama de cuenta; `LuciaRecepcion.gd` es el de 26 KB |
| **F0-03** | **Quitar el `add_child` duplicado**: borrar la línea **131** de `LuciaRecepcion.gd` (`raiz.add_child(panel)`) | S | Arranque headless sin `already has a parent` |
| **F0-04** | **Ruta de recepción explícita**: `preload("res://gdscrip/LuciaRecepcion.gd")` (nunca `res://../`) | S | `Select-String res://\.\./` → 0 en `gdscrip/` |
| **F0-05** | **Importar y fijar la caché** con el Godot 4.7.2 del taller | S | `--headless --import` exit 0 |
| **F0-06** | **Prueba de humo de la fase**: arranque headless 240 frames | S | stdout con `[Boot.gd]` y **cero** `ERROR` de UI |

> ⚠️ **Riesgo F0-02:** el `LuciaRecepcion.gd` de `borrador` es 5 KB más grande. Antes de copiarlo hay que **diffear** contra el canónico y quedarse con lo que aporta (zip, `forzar_nuevo`, `auto_registro`, `_url_cuentas`), no a ciegas.

---

### F1 — Servidor de demo reproducible (0,5 día)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F1-01** | **`STM_BKCH/demo_servidor.py`**: arranca `iniciar_servidor_blockchain(puerto)` de verdad, imprime la URL, espera `Ctrl+C` y apaga con `detener()`. Flags: `--puerto 8545`, `--ledger <ruta>`, `--reset` | S | `curl /status` responde en < 2 s desde otra consola |
| **F1-02** | **Ledger aislado**: `--ledger _demo/ledger.json`; por defecto **nunca** el del sistema. `--reset` archiva el ledger del demo como `ledger_<fecha>.json` (no lo borra) | S | El demo no modifica `STM_CH/blockchain_ledger.json` (comparar hash antes/después) |
| **F1-03** | **Repetibilidad**: `--permitir-repetir` para pruebas (mapea `BKSVCB.PERMITIR_REPETIR`), **apagado por defecto** | S | Dos altas seguidas: `409` sin flag, `201` con flag |
| **F1-04** | **Comprobación de salud** al arrancar: GET `/status` propio + aviso si el puerto está ocupado | S | Segundo arranque avisa «puerto 8545 ocupado» en vez de morir en silencio |
| **F1-05** | **`demo_local.ps1`** en la raíz del taller: lanza servidor, comprueba `/status`, lanza Godot con el proyecto canónico y **limpia `p2p_session.json` obsoleto** | M | Un comando abre el mundo con la recepción |

> **Por qué en PowerShell y no en Python:** el taller ya es Windows-first y el Godot no sabe arrancar el servidor. El `.ps1` es el pegamento mínimo; el `.py` sigue siendo el servidor.

---

### F2 — Flujo de cuenta completo (1,5 días)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F2-01** | **Descargar el `.zip` tras el alta**: en `_on_alta_completada`, tras `_guardar_cuenta`, llamar a `_descargar_zip_cuenta(cuenta_hash)` y avisar «Guarda este archivo: si lo pierdes, pierdes la cuenta» | S | Tras el alta existe `user://cuenta_<hash16>.zip` de ~640 B |
| **F2-02** | **Un solo nick**: el de la recepción manda. `registro.gd` recibe el nick ya validado (`set_nick`) y **no lo vuelve a pedir**; `registro.cfg.nick` se escribe con el nick de la cuenta | M | `cuenta.json.nick == registro.cfg[jugador].nick` |
| **F2-03** | **Validación local de conexión** (D3): si hay `cuenta.json`, comprobar que el hash existe en la cadena (`GET /status` + bloque) y habilitar «Entrar al mundo». Si no hay servidor, mensaje claro y opción «entrar en modo local» | M | Con servidor: entra en < 2 s. Sin servidor: mensaje, no cuelgue |
| **F2-04** | **Mensaje de pérdida, a la cara**: texto en el formulario y en el `.zip` (`LEEME.txt`) | S | El `.zip` contiene `LEEME.txt` con la advertencia |
| **F2-05** | **Migración verificada**: probar `.zip` + llave + semilla contra el servidor; el bloque de migración guarda `prueba_llave_semilla` | M | `200`, hash nuevo y `.zip` descargado |
| **F2-06** | **Estados de error legibles**: `409` (ya hay cuenta) → «Este PC ya tiene cuenta, usa Validar conexión»; `422` → el mensaje del servidor tal cual; `429` → minutos de espera | S | Los cuatro códigos se ven en pantalla, no en consola |

---

### F3 — Entrar al mundo de verdad (1 día)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F3-01** | **Rol de red determinista para el demo**: sin `p2p_session.json`, forzar `force_host` (servidor local) en lugar de «AUTO → cliente a 127.0.0.1» | M | Log: `SERVIDOR_LOCAL (WS 0.0.0.0:8911)` |
| **F3-02** | **Sesión limpia al arrancar el demo**: el `.ps1` mueve `p2p_session.json` a `.bak` (nunca lo borra) | S | Log: `Origen/Fuente: …` sin `192.168.1.103` |
| **F3-03** | **Espera de «mi isla» con tope**: si `mi_isla_lista` no llega en 20 s, quitar la ventana de carga y mostrar el mundo con aviso, en vez de quedarse en negro | M | Prueba con host ausente: se ve el mundo + aviso |
| **F3-04** | **Cámara y spawn**: corregir `look_at` antes de `add_child` en los scripts de demo (`DemoMundo.gd:74` ya lo sufre); el avatar aparece en el portal, no dentro de una caja | S | Captura con avatar y terreno |
| **F3-05** | **Retirar la maqueta**: `DemoBoot.gd`/`DemoMundo.gd`/`DemoRegistro.gd` se archivan; el demo usa `Boot.gd` real | M | `Boot.gd` es el único punto de entrada |
| **F3-06** | **Capturas del flujo real**: recepción, carrusel, registro, isla | S | 4 PNG en `_demo/capturas/` |

> **Nota de honestidad:** F3 es la fase con más incertidumbre. La isla **carga** (medido), pero no se ha visto terminar el handshake como servidor porque la sesión anterior siempre arrancó como cliente. Si F3-01 no basta, el plan B es un `modo_demo` en `ChunkManager.gd` que salte el transporte y monte el chunk local — nunca la maqueta de cajas.

---

### F4 — Pruebas y blindaje (1 día)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F4-01** | **`tests/test_bkch_cuentas.py`**: contrato del servidor — alta `201` + hash 64, nick < 10 → `422`, huella inválida → `422`, duplicado → `409`, zip `PK` ≥ 300 B, migración `200`, `status` coherente | M | `python -m pytest tests/test_bkch_cuentas.py` verde |
| **F4-02** | **Prueba de arranque de Godot**: script headless que arranca 240 frames y falla si hay `ERROR` de UI o `SCRIPT ERROR` | M | Sale `0` con el proyecto limpio; sale `1` si se reintroduce el panel duplicado |
| **F4-03** | **Alinear `README_SEGURIDAD.md`** con el código (D-10): o se implementa rate limit/`/intentos`, o se corrige el documento. **Recomendado: corregir el documento ahora**; el rate limit es F1 del plan general | S | Cero afirmaciones sin endpoint detrás |
| **F4-04** | **E2E del demo** (`_demo/e2e_demo.ps1`): servidor + alta por HTTP + comprobación de zip + arranque Godot | M | Un comando dice `DEMO OK` o falla con motivo |
| **F4-05** | **Arnés completo**: `python -m pytest` del taller sigue en verde (o se documenta el rojo preexistente, sin empeorarlo) | S | Comparativa antes/después adjunta |

---

### F5 — Empaquetado y guion (0,5 día)

| ID | Tarea | Esf. | Hecho cuando |
|---|---|---|---|
| **F5-01** | **`demo_local.ps1` definitivo**: `-Reset`, `-Puerto`, `-SinServidor`, `-SoloServidor` | S | `Get-Help` legible |
| **F5-02** | **Guion de 3 minutos** (§7) impreso en consola al arrancar | S | El demo se puede dar sin leer el código |
| **F5-03** | **Modo `--headless` para CI local**: alta + zip sin ventana | S | `DEMO OK` en < 60 s |
| **F5-04** | *(Opcional)* PCK del demo | L | **Solo** si D5 cambia; hoy está fuera |

---

### F6 — Documentación y cierre (0,5 día)

| ID | Tarea | Esf. |
|---|---|---|
| **F6-01** | `DEMO.md`: qué hace, cómo se arranca, qué se ve, qué no hace | S |
| **F6-02** | Actualizar `README_PLAN_DE_DESARROLLO.md` §6/F9 con el estado real (F9-06/F9-07 pasan a «v1 en demo local») | S |
| **F6-03** | Registro de decisiones D1–D5 y hallazgos D-01…D-12 en el changelog del documento | S |
| **F6-04** | Commit en `development` con **ficheros nombrados** (nunca `git add -A`) | S |

---

## 7. Guion del demo (3 minutos)

```
[0:00] .\demo_local.ps1 -Reset
        → «Servidor de cuentas en http://127.0.0.1:8545 · cadena: 1 bloque»
        → se abre el mundo

[0:15] LucIA recibe. «Es tu primera vez: yo te acompaño a crear tu cuenta.»
        Escribo:  demo_local_01          (10–15 letras)

[0:35] «Crear mi cuenta»
        → 201 · hash 3f9c… · bloque #2 minado
        → «Guarda tu archivo: si lo pierdes, pierdes tu cuenta.»
        → cuenta_3f9c….zip descargado

[1:00] El carrusel: elijo avatar (turno 1, plaza 3)
[1:25] Registro: el nick viene ya relleno (no se pide dos veces)
[1:40] Atravieso el portal
[1:50] «BIENVENIDO A TU ISLA, demo_local_01 · TURNO 1»

[2:20] Cierro el mundo y vuelvo a abrir
        → «Te saludo de nuevo, demo_local_01» · «Validar conexión» → entra

[2:50] Consola: GET /status → 3 bloques, cadena válida
```

**Contra-demo (lo que hay que poder decir «no»):** crear dos cuentas desde el mismo PC → `409`; nick de 5 letras → `422`; apagar el servidor → mensaje claro, no cuelgue.

---

## 8. Matriz de aceptación

| # | Criterio | Cómo se comprueba | Hoy |
|---|---|---|:--:|
| A1 | Un comando arranca servidor + mundo | `.\demo_local.ps1` | 🔴 |
| A2 | `/status` responde `200` con cadena válida | `curl` | 🟢 |
| A3 | Alta devuelve hash de 64 hex | POST + JSON | 🟢 |
| A4 | El `.zip` se descarga en el alta | fichero en `user://` | 🔴 |
| A5 | La recepción no produce errores | headless sin `ERROR` | 🔴 |
| A6 | Se entra a la isla real | captura | 🔴 |
| A7 | Al reabrir, la cuenta se reconoce | `cuenta.json` + arranque | 🔴 |
| A8 | Nick único en cuenta y registro | comparar dos ficheros | 🔴 |
| A9 | El ledger del sistema no cambia | hash antes/después | 🔴 |
| A10 | Arnés de pruebas verde | `pytest` | 🟡 |

**Definición de Done del demo:** A1–A10 en verde **y** las capturas de §7 adjuntas al commit.

---

## 9. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| F3 no consigue el rol servidor | Media | Alto | Plan B: `modo_demo` en `ChunkManager.gd` (chunk local, sin transporte) |
| El `LuciaRecepcion.gd` de `borrador` arrastra dependencias | Media | Medio | Diff antes de copiar; copiar por funciones, no el fichero entero |
| Importar el proyecto tarda mucho (5 GB) | Alta | Bajo | Ya hay caché `.godot`; no borrarla; importar una sola vez |
| El ledger del sistema queda tocado | Baja | Alto | F1-02 con `--ledger` obligatorio + comprobación de hash |
| Se rompe el arnés de regresión | Media | Medio | F4-05 mide antes/después; no se toca nada de red/OTA |
| Alguien «arregla» el demo con otra maqueta | Media | Alto | D-08/F3-05: la maqueta se archiva y el criterio A6 exige la isla real |

---

## 10. Fuera de alcance (deuda declarada, no olvido)

- **PCK y release**: el demo corre desde fuente. Publicar exige `REGLAS_DE_ACTUALIZACION.md`.
- **`.zip` cifrado** (`llave.enc` AES-GCM): hoy el `.zip` solo lleva `cuenta.json` público + `metadata.txt`. Es F9-05 del plan general.
- **IPFS real**: `compat_local.IPFSManager` devuelve `ok=False` a propósito (H1). El pin es F9-08.
- **Recuperación social**: D15 la excluye de v1.
- **Validación por túnel SSH**: D3 la sustituye por validación local en el demo.
- **Multi-nodo**: la cadena es single-node; el hash protege ante manipulación local, no ante un nodo que reforge el ledger.

---

## 11. Anexos

### A. Contrato HTTP usado por el demo

```http
POST /alta-cuenta
{"nick":"demo_local_01","huella":"<32 hex>","ubicacion_hash":"<64 hex opcional>"}
→ 201 {"nick","cuenta_hash","indice_bloque","bloque"}
→ 409 ya hay cuenta en este PC / nick repetido
→ 422 nick fuera de 10–15, huella inválida, ubicación inválida
→ 429 cooldown de ubicación (72 h)

POST /migrar-cuenta
{"nick","huella","ubicacion_hash","prueba":"<sha256 64 hex>"}
→ 200 {"nick","cuenta_hash","indice_bloque"}

GET /descargar-cuenta-zip?cuenta_hash=<64 hex>
→ 200 application/zip (cuenta.json + metadata.txt)
→ 404 cuenta no encontrada en la cadena

GET /status
→ 200 {"servidor","total_bloques","cadena_valida","ultimo_bloque"}
```

### B. Formato actual del `.zip` (medido: 642 B)

```
cuenta_<nick>_<hash16>.zip
├── cuenta.json     # nick, cuenta_hash, indice_bloque, hash_previo, fecha, tipo
└── metadata.txt    # resumen legible para el usuario
```

Objetivo de #86 (F9-05, fuera del demo): añadir `llave.enc`, `registro.json` (huella comprometida) y `LEEME.txt`.

### C. Checklist de arranque (pegar en cada sesión)

```powershell
$SRC = "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src"

# 1. Servidor de demo (ledger aislado)
python "$SRC\STM_BKCH\demo_servidor.py" --puerto 8545 --ledger "$SRC\_demo\ledger.json" --reset
# 2. Salud
curl http://127.0.0.1:8545/status
# 3. Mundo (sin sesión P2P obsoleta)
& "E:\WoldVirtualP2P3D\_tmp_tests\godot\Godot_v4.7.2-stable_win64.exe" --path "$SRC\MTBGT\WoldVirtualP2P3D"
```

### D. Comandos de humo usados para medir este plan

```powershell
# servidor: import
python -c "import sys; sys.path.insert(0, r'...\src'); import STM_BKCH.bksvcb_net"

# servidor: alta + zip (201 + PK)
python "$SRC\_demo\e2e_alta.py"

# Godot: arranque sin ventana
& $GODOT --headless --path "$SRC\MTBGT\WoldVirtualP2P3D" --quit-after 240
```

### E. Correspondencia tarea ↔ hallazgo

| Hallazgo | Tarea |
|---|---|
| D-01 copias divergentes | F0-01, F0-02 |
| D-02 preload fuera del proyecto | F0-04 |
| D-03 panel duplicado | F0-03 |
| D-04 recepción siempre | F0-02 |
| D-05 sin `.zip` en el alta | F2-01 |
| D-06 sin lanzador / ledger compartido | F1-01, F1-02 |
| D-07 segunda ejecución | F1-03 |
| D-08 isla como cliente remoto | F3-01, F3-02 |
| D-09 dos nicks | F2-02 |
| D-10 doc de seguridad | F4-03 |
| D-11 validación C#-dependiente | F2-03 |
| D-12 sin pruebas de contrato | F4-01 |

### F. Registro de cambios de este documento

| Fecha | Cambio |
|---|---|
| 2026-11-10 | Versión inicial. Medición real del taller, la copia canónica, el servidor E2E y la isla headless. |
| 2026-11-10 | **Ejecución del plan** (§12): F0–F4 hechas, F5/F6 parciales. |

---

## 12. Estado de ejecución (2026-11-10)

### 12.1 Lo que ya funciona, verificado

| Fase | Estado | Evidencia |
|---|---|---|
| **F0** un solo proyecto | ✅ | `MTBGT/_archivo_20261110/` con las 4 copias; queda un `project.godot` |
| **F0-03** panel duplicado | ✅ | `LuciaRecepcion.gd` reescrito sin `add_child` repetido |
| **F1** servidor reproducible | ✅ | `STM_BKCH/demo_servidor.py` + `demo_local.ps1`; ledger en `src/_demo/` |
| **F2** flujo de cuenta | ✅ | alta → hash → `.zip` → `cuenta.json`; nick único; entrada sin túnel |
| **F3** isla real | ✅ | `--server` → `SERVIDOR_LOCAL`, «Isla 0 preparada: 10920 vértices» |
| **F4** pruebas | ✅ | 16 de contrato + E2E de 12 hitos + 13 de firma + 6 de variantes |
| **F5/F6** docs | ✅ (parcial) | `DEMO.md`; queda el guion impreso y el PCK (fuera de alcance) |

**E2E completo** (`e2e_demo.ps1`), tiempos reales de la última pasada:

```
recepcion +0.9s · alta_solicitada +0.9s · cuenta_y_zip +0.9s · entrar_pulsado +1.5s
avatar_elegido +1.6s · validacion_2_bloqueada +1.6s · validacion_2_superada +1.8s
registro_confirmado +1.8s · portal_cruzado +2.1s · isla_montada +2.1s
isla_lista +2.1s · avatar_original_y_variantes +2.1s
```

Las **dos validaciones iniciales** quedan probadas por el propio E2E: el registro
está bloqueado con el avatar base (`validacion_2_bloqueada`) y se desbloquea al
llegar al 13 % (`validacion_2_superada`).

### 12.2 Decisiones que cambiaron respecto al plan

- **Sin migración y sin validación de conexión** (instrucción del usuario): el
  hash del bloque es la cuenta y basta. El cliente ya no pide `.zip` + llave +
  semilla, ni espera `validacion_resultado.json` del visor C#. El endpoint
  `/migrar-cuenta` sigue en el servidor, sin usar.
- **D-04 matizado**: `Boot.gd` sí tenía el camino «existente», pero colgaba de la
  validación por túnel (D-11). Al quitar el túnel, la entrada es directa.
- **F3-01 se resolvió sin tocar el motor**: `Red.gd` ya entendía `--server`; el
  lanzador pasa `-- --server` y el rol queda forzado.
- **F7 nueva (avatar propio, validación 2 de 2)**: implementada v1 — firma de 33
  dimensiones, umbral 12 %, **registro bloqueado** hasta superarlo, bloque
  `AVATAR_ORIGINAL`, entrenamiento de las 50 neuronas y 3 variantes por avatar.
  El orden se decidió con el usuario: **el bloque nace al inicio, en la oficina de
  LucIA**; el avatar propio es la segunda validación inicial, no una validación
  posterior opcional.

### 12.3 Lo que queda

| Tarea | Por qué no está |
|---|---|
| **F4-03** alinear `README_SEGURIDAD.md` | Promete rate limit y `/intentos` que no existen |
| **F4-05** `pytest` de todo el árbol | Requiere numpy y pytest en el Python del usuario; aquí se instaló pytest aparte |
| **F7-05** variantes visibles en el carrusel | ✅ hecho: `SLAV.gd` suma las variantes como plazas extra (24+3=27) y el registro guarda el aspecto elegido |
| **F7-06** generador de mallas nuevas | Necesita pipeline GLTF/Blender; el demo reutiliza el GLB con otro aspecto |
| **F5-04** PCK del demo | Fuera de alcance por decisión D5 |

### 12.4 Aviso de entorno

En esta máquina, Godot solo puede escribir dentro de `E:\WoldVirtualP2P3D`
(restricción del entorno del asistente). `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D`
se redirigió al workspace con una unión de directorios para poder probar el
guardado de `cuenta.json`. Está documentado, con el comando para deshacerlo, en
`DEMO.md` §5. En un escritorio normal no hace falta.

