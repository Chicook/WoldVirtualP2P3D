# Plan de implementación — WoldVirtualP2P3D

**Análisis de código y hoja de ruta de mejoras** · Rama `development` · 2026-11-02

> Base analizada: `main` @ `19cc65e` (v2.7.5, 2026-11-01). Repositorio: 514 ficheros
> rastreados (≈130 Python / 80 C# / 65 GDScript), README de 891 líneas / 118,9 KB,
> `SRC = VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src`.
>
> Este documento condensa un análisis exhaustivo del repositorio completo:
> **82 hallazgos** (6 verificados adversarialmente + 76 de catálogo) y **9 huecos** de
> completitud, organizados en un plan de trabajo por etapas. No sustituye a
> `README_DESARROLLO.md` ni a `STM_DOC/HOJA_DE_RUTA.md`: los complementa con una
> visión integral y priorizada.

---

## 0. Cómo leer este plan

**Convención de identificadores:**

| Prefijo | Significado | Cantidad |
|---|---|---|
| `V1–V6` | Hallazgos **verificados** (contraste adversarial contra el código fuente; severidad ajustada tras verificación) | 6 |
| `H1–H15` | Hallazgos de catálogo **ALTOS** | 15 |
| `M1–M39` | Hallazgos de catálogo **MEDIOS** | 39 |
| `L1–L22` | Hallazgos de catálogo **BAJOS** | 22 |
| `G1–G9` | **Huecos** detectados por la pasada de completitud (temas que ningún hallazgo cubría) | 9 |

**Esfuerzo estimado:** `S` = quirúrgico (horas, uno o dos ficheros) · `M` = medio
(días, varios ficheros o coordinación) · `L` = grande (semanas o decisión de diseño).

**Convención de ramas:** todo el trabajo se hace en `development`; `main` solo refleja
snapshots de upstream (`Chicook/WoldVirtualP2P3D`). Publicar releases, fusionar a
`main` o cerrar issues de upstream requiere confirmación del propietario.

**Nota sobre etapas:** el proyecto ya usa `F0–F7` (fases del README §15) y `P0–P2`
(prioridades del §16.4). Para no colisionar, las etapas de este plan se llaman
**Etapa 0 … Etapa 6** y se cruzan con las existentes en la sección 6.

---

## 1. Resumen ejecutivo

WoldVirtualP2P3D es un producto real y en varios tramos bien construido: el visor C#
.NET 8 con doble objetivo (WPF + Avalonia), el motor Godot 4.7.2 integrado, el relé de
chat, el actualizador OTA con descarga *fail-closed* por SHA-256, la cadena local con
PoW doble-SHA-256 en `127.0.0.1:8545` y la orquestación Kubo son genuinos. El análisis
no encontró ni un solo `eval`/`exec`/`pickle` ni `except:` desnudo en la periferia
Python, y el extractor bloquea Zip Slip correctamente.

Los problemas se concentran en seis temas:

1. **Veracidad del núcleo neuronal (V1).** Las ~24.500 líneas de
   `LC_STM/red_neuronal` **no aprenden**: los bucles de época fabrican `loss` y
   `accuracy` con `np.random.rand()` y nunca invocan un optimizador. No hay torch ni
   sklearn en el manifiesto. La red está hoy **desconectada del visor** (el runtime usa
   un shim local), pero la documentación —incluida la propia deuda D1 y
   `STM_IA/conocimiento/red_neuronal.md`— la describe como 50 neuronas «activas».
2. **Seguridad de la sesión P2P (V2, H7, G1, G4, M22).** No hay autenticación de
   pares: UUID autoafirmados, LAN/directo `ws://` sin credencial alguna, relé de chat
   abierto a cualquiera (también por el túnel público), X-Forwarded-For falsificable
   que anula el rate-limit, y las IPs domésticas de todos los participantes se
   difunden y persisten. La promesa del README §3.4 («solo el dueño de la isla
   edita») es eludible por diseño actual.
3. **Fiabilidad del actualizador y del visor (H3, H4, H5, M16–M19).** La etapa
   *apply* del OTA no re-verifica el paquete descargado y puede dejar la instalación
   inutilizable sin rollback; la ruta de «reanudar sin volver a bajar» destruye el
   `.part` completo; el bucle de accept del portal muere en silencio ante cualquier
   excepción; `cloudflared.exe` se descarga y ejecuta sin verificar digest ni firma.
4. **CI muerta y pruebas sin comportamiento (H8–H11, V4, M25–M30).** El único
   `ci.yml` está anidado 5 niveles y GitHub nunca lo ejecuta; aunque se promoviera,
   sus `working-directory` apuntan a un árbol que no existe. 87 de las 98 pruebas de
   regresión son *advisory* en CI (`continue-on-error`), ~1/3 de la suite son greps de
   cadenas fuente o pruebas acopladas al entorno, y el núcleo neuronal carece por
   completo de pruebas de comportamiento: el arnés está verde mientras `SL10.optimize_weights()`
   revienta con `AttributeError` en su primera llamada real.
5. **Estructura del repositorio contra sí misma (M36–M39, H15).** El ciclo de renamed
   `actualizacion_<hex>` (8 nombres históricos) rompe 72 enlaces del README por ciclo;
   el README de 118,9 KB es a la vez manual, changelog, roadmap y bitácora; las
   instrucciones de reconstrucción del PCK (§11) son imposibles desde un clon limpio
   porque los assets del mundo no están versionados (D12).
6. **Cadena de suministro y datos de usuario (G3, G5, G8).** Nada está firmado en
   ninguna capa (el SHA-256 del OTA viene del mismo JSON de release que la URL del
   asset); no hay copia de seguridad ni exportación de mundos ni del ledger; un repo
   MIT con dependencias LGPL-3.0/Apache-2.0 y un PCK de 114,6 MB sin provenance no
   tiene NOTICE ni THIRD-PARTY_NOTICES.

**Qué hacer esta semana (Etapa 0):** once arreglos quirúrgicos de esfuerzo `S`
(incluidos `import math` en `_sl_math.py`, re-apuntar `STM_RFC_DIR`, y el guardado
anti-génesis del ledger) más tres correcciones documentales de honestidad. Detalle en
la sección 8.

**Cifras del análisis:** 82 hallazgos (15 altos / 39 medios / 22 bajos en el catálogo,
más 2 verificados que bajaron de crítico→alto y 1 de alto→medio) + 9 huecos. El
sistema de seguimiento propio del proyecto (D1–D16, DT-01..DT-10 del issue #45, §16.4
P0–P2, hitos H5/H6, issues #15/#22) ya reconoce parte de esta deuda: el cruce exacto
está en la sección 6.

---

## 2. Estado por subsistema

### 2.1 Núcleo Python (LucIA): `STM_HRTS`, `LC_STM/red_neuronal`, `STM_IA`

`STM_HRTS` está bien diseñado: utilidades de rutas, contención H1 con pruebas
estrictas, herramientas con catálogo. El problema es `red_neuronal`: 60 ficheros en
cinco familias (RNP, SLRN, ENRN, RF_EN, RF_SL) que replican la misma estructura con
~24.700 líneas cuyo entrenamiento es simulado (ver V1). Patrones agravantes: 126
`except Exception` que tragan fallos y devuelven métricas cero, efectos colaterales a
la hora de importar (reseed global de numpy, `logging.basicConfig` en bibliotecas,
carga ansiosa de los 10 módulos por familia), inicializadores «ortogonales/espectrales»
matemáticamente incorrectos exportados en `RF_EN/__init__.py` mientras los correctos
viven en `_rfen_base.py`, y claves de modelo LLM incrustadas en la capa de neuronas.
El empaquetado no existe como tal: el único `pyproject.toml` está en `STM_HRTS/` y no
puede empaquetar sus paquetes hermanos; todo el runtime depende de `sys.path.insert`.

### 2.2 Periferia Python: `STMIPFS`, `STM_BKCH`, `SBSTM`, `STM_SGR`, `STM_JSON`, `STM_CH`, `STMGNRL`, CONTRRF

Lo mejor del análisis salió aquí: la orquestación de Kubo es real (arranque, espera de
API, reintentos), la cadena de bloques local funciona de verdad (PoW doble-SHA-256
dificultad 2, Merkle, escritura atómica tmp+replace), CONTRRF/RFPRMN es una herramienta
de refactor bien construida (verificación por recuento, bookkeeping de envíos), y hay
**cero** `except:` desnudos, `eval`, `exec` o `pickle`. Los defectos reales: el ledger
se resetea a génesis en silencio ante cualquier error de lectura (H1), el flujo de
cierre de `IALOCAL.py` llama a métodos que no existen en el shim (M14), los CIDs falsos
del shim se minan en bloques inmutables (M13), la semilla maestra del vault está
hardcodeada en un repo público (M8), hay módulos muertos (M12), tres duplicaciones del
wrapper Kubo (M11) y dos rutas `C:\Users\User\Desktop` en `stm_base.py` (M9).

### 2.3 Visor C# WPF (Windows), `VSC#/`

v2.7.5 endureció bien la mitad OTA de la descarga: verificación SHA-256 *fail-closed*
antes de extraer (`UpdateDownloader.cs:157-183`) y normalización de rutas contra Zip
Slip (`AppExtractor.cs:179-181`). `ChatClient.cs` es notablemente sólido (cierre con
timeout, reconexión). Pero: la etapa *apply* no re-verifica y puede brickear sin
rollback (H3), la reanudación destruye el `.part` completo (H4), el bucle de accept se
apaga en silencio (H5), el proxy de túnel filtra tareas y descarta sockets en uso sin
cancelación ni keepalive (M16), el túnel efímero se lanza dos veces en el flujo de
login (M17), el rate-limit se anula con un XFF falsificado porque todo el tráfico
público llega por el proxy local loopback (H2), `MainWindow.xaml.cs` es una god-class
de 3.420 líneas (M20), y los tamaños servidos en JSON usan `CurrentCulture` (L8). Los
puertos dinámicos del beacon solo se respetan en la ruta de unión LAN (L9).

### 2.4 Mundo Godot (`MTBGT`, 156 ficheros, ~10,2k líneas GDScript)

El modelo de confianza «el host manda» está bien planteado: validación de propiedad en
el servidor, clamps en deserialización, terreno editable con paso acotado. La debilidad
decisiva es la identidad (V2): sin autenticación, todas las validaciones «el remitente
es el dueño» se apoyan en un UUID autoafirmado que cualquiera puede falsificar. A eso
se suman entradas `any_peer` sin validar (`_net_position` acepta NaN y nicks sin cota,
H6; los RPCs de edición pasan radios y escalas sin clamp, M21), una migración de host
cuyo objetivo eligen los primeros en unirse (M22), I/O a disco dentro de `_process`
(M24), una pantalla de carga sin timeout ni salida (M23) y escenas muertas que viajan
en el PCK de 114,6 MB (L11).

### 2.5 Pruebas y CI

La CI está muerta dos veces: el workflow está anidado 5 directorios (GitHub solo
ejecuta desde la raíz, H8) y, ya promovido, sus `working-directory` apuntan a
`VersionDe_sesion/CONTRRF/TLLDCD/src`, un árbol inexistente (H9); además la suite
completa corre con `continue-on-error: true` (H10). El arnés Python (98 pruebas) es
real pero ~1/3 es humo/grep: 4/4 pruebas de `test_h2_h3_red.py` son greps de cadenas
exactas del fuente (M25), hay pruebas acopladas a entorno (repo IPFS real, sonda a
`localhost:11434`, M26), asserts de tiempos que fallan en máquinas cargadas (M27) y
pruebas que mutan directorios reales del usuario (M28). No existe proyecto de pruebas
C# (D15, H11) — aunque `UpdateSelfTest.cs` demuestra que el testeo hermético es viable
en este código. `StartupSelfTest`, la verificación end-to-end más fuerte, es
inejecutable en CI por los assets no versionados (M29). No hay ninguna validación entre
dos máquinas reales (upstream #22, P0; G6).

### 2.6 Scripts de build/automatización (6 .bat, 5 .ps1, 3 .sh, `herramientas.py`)

Los .sh de Linux son de alta calidad. El resto: `purgar_repositorio.ps1` apunta a una
raíz y un snapshot inexistentes, no borra nada y aun así imprime «¡Purga completada con
éxito!» (H12); `borrar_packs_viejos.ps1` borra packs de `.git/objects/pack` por nombre
hardcodeado con reintentos de 2 minutos — riesgo real de corromper el repo (H13); el
script de publicación está clavado a `E:\` y a la versión 2.7.5 (M31); cuatro
lanzadores de opencode duplicados ya divergentes (M32); la cabecera de
`woldvirtual-linux.sh` documenta un tamaño/SHA del PCK que contradice las constantes
que el propio script exige (M33); `herramientas.py` construye argv de cmd/powershell/sh
sin gating de plataforma (L16); dos .ps1 con acentos sin BOM que Windows PowerShell 5.1
decodifica como ANSI (L17); un .bat con el escritorio de otro usuario como primera
ruta (L18); y `arrancar_daemon.bat` busca un directorio `STMIPFSCOMFIG` (L20).

### 2.7 Documentación e higiene del repositorio

El README colapsa bajo su propio peso: 891 líneas que son a la vez manual de usuario,
changelog con SHA-256 por release, roadmap F0–F7/H, bitácora fechada P0–P2 y política
de versionado (M37). 72 enlaces incrustan el nombre del snapshot y se rompen en cada
ciclo RFPRMN (M36). El §11 manda reconstruir el PCK con `--import` cuando el repo no
versiona ni una sola textura o modelo — imposible desde un clon (H15). Hay
contradicciones internas (§18 dice 41 documentos, §4 dice 43, y 43 es lo correcto,
M38) y §17 describe la forma del repo upstream, no la de este fork (M35). Higiene:
7,3 MB de capturas duplicadas con blobs idénticos en `docs/img` y
`STM_DOC/docs/img` (L21); faltan `CONTRIBUTING.md`, `CHANGELOG.md` y `.editorconfig`
raíz (L22 — este último ya añadido en esta rama). 43 documentos, todos solo en
español, sin guía de contribución real (M39).

---

## 3. Hallazgos verificados (V1–V6)

Cada hallazgo pasó por un verificador adversarial independiente con acceso al código;
la «severidad final» refleja el veredicto, no la estimación inicial.

### V1 — La «red neuronal distribuida» no aprende · **ALTO** (ajustado desde crítico)

- **Evidencia.** `_rn_base.py:205` devuelve `np.random.rand()` como `loss` **y** como
  `accuracy`. Los bucles de época de RN1 (`:61,63-64,86,189-192`) nunca invocan un
  optimizador y devuelven el modelo sin cambiar. El patrón se replica en RN2:61, RN3:58,
  RN4:59, RN5:55, SL2:188, SL4:185, SL5:176, SL6:178, SL7:170, SL8:171, SL9:178 —
  todas fabrican `epoch_loss`. Ningún `torch`/`sklearn` en el manifiesto (solo numpy).
- **Mitigantes que bajan la severidad.** La red es hoy inalcanzable desde el visor
  (cero referencias a LucIA en el visor; el runtime usa el shim `STM_BKCH/compat_local.py`)
  y el README §12/deuda D1 lo admite parcialmente.
- **Hecho nuevo de la verificación.** El remedio escrito en D1 — «portar a
  LC_STM/red_neuronal (50 neuronas REALES)» — es un falso presupuesto: el destino del
  port también es simulado. Los módulos registran «éxito» y exportan puntuaciones
  fabricadas (RN1:319, RN10:290, SL3:376), y `STM_IA/conocimiento/red_neuronal.md`
  le dice a LucIA que sus neuronas están «activas».
- **Corrección propuesta.** Reetiquetar todo el paquete como *scaffolding*: sustituir
  los cuerpos aleatorios por `NotImplementedError` (los tests actuales solo importan,
  así que siguen en verde), corregir el texto de D1 y de `red_neuronal.md`, y dejar el
  entrenamiento real como proyecto futuro explícito. Etapa 4.

### V2 — Sin autenticación de pares: UUID autoafirmados · **ALTO** (ajustado desde crítico)

- **Evidencia.** `Identidad.gd:30-31` solo valida formato. `ChunkManager.gd:443-451`
  expone `_claim_island` como `any_peer`; `_puede_reclamar_isla` (517-530) solo bloquea
  titulares **conectados**, de modo que la isla de un dueño desconectado puede ser
  reclamada por cualquiera; `_adoptar_isla` (537-550) deja fuera al dueño real.
  `Construccion.gd:290-301` `_validar_remitente` protege los seis RPCs de edición
  únicamente comparando UUID declarado vs. titular.
- **Mitigante parcial.** El portal WebNodo tiene un handshake de token de invitación
  (`WebNodoService.cs:633-640`), pero es un único secreto compartido y la conexión
  LAN/directa `ws://` no lo pide (`Red.gd:217-243`).
- **No admitido en ninguna parte.** El README §3.4 promete «solo el dueño de la isla
  edita» — es eludible con el diseño actual.
- **Corrección propuesta.** Mapa host-privado uuid→peer, prueba de posesión con hash
  salado, cola de reclamaciones para islas de dueños ausentes; efecto dominó a
  revalidar: `_es_mi_isla` (`Construccion.gd:254-262`). Etapa 1.

### V3 — `_sl_math.py` sin `import math` · **MEDIO** (ajustado desde alto)

- **Evidencia.** `NameError` reproducido en runtime: rompe SL2 (`cosine_warm_restart`,
  `_sl_math.py:153`), SL3 (`adaptive_epsilon`, `SL3.py:94`), la ruta por defecto de SL4,
  y SL5.
- **Segundo defecto encontrado al verificar.** `cosine_decay` queda muerto tras un
  `return` anidado en `centered_rms_update` (`_sl_math.py:130-134`) → `SL10.py:67`
  lanza `AttributeError`.
- **Latente** (hoy nadie llama a los optimizadores en runtime), pero bloquea cualquier
  uso futuro y anula la señal de «suite verde» (ver V4).
- **Corrección.** Una línea de `import math` + re-indentar `cosine_decay` + un test de
  humo por optimizador. **Etapa 0** (quick win validado).

### V4 — El núcleo neuronal tiene cero cobertura de comportamiento · **ALTO** (confirmado)

- **Evidencia.** `tests/test_regresion.py:11-23` (`PAQUETES`) no incluye `LC_STM`;
  24.478 líneas Python verificadas sin una sola prueba que alimente datos a una
  neurona. El arnés está verde mientras `SL10.optimize_weights()` revienta en su
  primera llamada real. La cifra «98 pruebas» es exacta pero mayormente de importación.
- **Corrección.** Smoke tests con fixtures numpy que afirmen «sin excepción / éxito» —
  **no** «la pérdida baja», porque SL1:209 y SL10:166 sintetizan las curvas; e
  inicialización perezosa de `pesos` en EN1. Etapa 3/4.

### V5 — La subida IPFS de CONTRRF cortocircuita con el CID falso del shim y luego borra el registro local · **MEDIO** (ajustado desde alto)

- **Evidencia.** `stm_registro.py:262-263` acepta cualquier recibo con `cid` e ignora
  `ok`/`simulado` (viola el contrato de `compat_local.py:13-14,155-156`);
  `publicar_registro_actualizar` borra incondicionalmente `envios.json`/`registro.md`/
  `registro_pesos.json` (`:435,439-440`), imprime éxito y una URL de gateway
  inexistente (`:444-446`).
- **Por qué baja a medio.** Camino marginal: el flujo canónico vacía `RFC` antes de
  publicar y el nivel 1 ya revienta con `ModuleNotFoundError`; y el README de la
  herramienta (§1.4) documenta un éxito con CID real (`QmQ5bjYVr6…`), luego el
  cortocircuito no es la norma. Además el fallback del nivel 4 tiene la misma
  destrucción y el «directorio limpio» es diseño documentado → **decisión del
  mantenedor**.
- **Corrección.** Exigir `ok is True` / tratar `simulado` como fallo. Etapa 4.

### V6 — La integración RFPRMN está muerta: `STM_RFC_DIR` apunta a un directorio inexistente · **ALTO** (confirmado)

- **Evidencia.** `mainLCSTM.py:20` fija `CONTRRF_DIR = parents[3]` (= `PRY`) y `:26`
  `STM_RFC_DIR = actualizacion_aeef1149/STM_RFC` — ni en disco ni en git. El único
  `RFPRMN.py` real está en `VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/`.
  `_imports.py:26` hace un import desnudo → `RFPRMN_DISPONIBLE = False` siempre; 6 de
  los 11 comandos de consola de LucIA anunciados son no-ops silenciosos (hasta `cerrar`
  devuelve `True`). El README §13 los marca «Implementado» y `STM_DOC/README.md:20`
  «Operativos» — ambos equivocados.
- **Corrección validada.** Apuntar `STM_RFC_DIR` a
  `CURRENT_FILE.parents[5]/CONTRRF/STM_RFC/STM_RFPRMN` (`RFPRMN.py:17-20` se
  auto-localiza). **Etapa 0** (quick win validado).

---

## 4. Catálogo de hallazgos por severidad

### 4.1 Altos (H1–H15)

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| H1 | El ledger se resetea a génesis en silencio ante cualquier error de lectura (`except Exception: pass` → `_crear_bloque_genesis()`, sin aviso ni backup) | `BKSVCB.py:132-153` (también `:251,268`) | S |
| H2 | Rate-limit eludible: todo el tráfico público llega por el proxy local (loopback), así que `CF-Connecting-IP`/`X-Forwarded-For` — controlados por el cliente — definen la «IP del cliente»; memoria del limitador sin cota | `WebNodoService.cs:829-848,686-701` | M |
| H3 | La etapa *apply* del OTA no re-verifica el SHA del pendiente (TOCTOU vs. la política fail-closed) y el .bat puede dejar el instalador sin exe si la copia falla (sin rollback desde `.old`) | `UpdateApplier.cs:38-52,113-141` | S-M |
| H4 | «Reanudar sin volver a bajar» destruye el `.part` ya completo: no hay salida temprana, se envía `Range` desde el tamaño final → 416 → se borra el fichero completo | `UpdateDownloader.cs:103-129` | S |
| H5 | El bucle de accept HTTP muere en silencio ante cualquier excepción inesperada (`catch { break; }` sin log ni reinicio): el portal queda a oscuras hasta reiniciar | `WebNodoService.cs:552-557` (+`519,811-814`) | S |
| H6 | `_net_position` (`any_peer`) aplica valores sin validar: posiciones NaN replicadas al scene graph, nick sin cota, y cambio de `avatar_path` por paquete que fuerza reconstruir el clon remoto hasta 10×/s | `PlayerSync.gd:142-160,86-131` | S-M |
| H7 | Sesiones LAN/directas sin credencial alguna: el token de invitación solo se añade a `wss://` y nada lo valida en el lado Godot; el beacon une a cualquier host que emita en 8912 | `Red.gd:166-169,217-243` | M |
| H8 | El único workflow de CI está anidado 5 directorios — GitHub Actions nunca lo ejecuta (y el propio fichero lo admite) | `$SRC/STM_HRTS/.github/workflows/ci.yml:5-8` | S |
| H9 | Todos los `working-directory` del ci.yml apuntan a `VersionDe_sesion/CONTRRF/TLLDCD/...` — un árbol inexistente; además `pip install … \|\| pip install …` enmascara fallos de manifiesto | `ci.yml:38,44,55,64,95,99,103,107,111` | S |
| H10 | La suite completa corre con `continue-on-error: true`: solo las 11 pruebas H1 pueden rojar la build; las otras 87 son consultivas | `ci.yml:63-73` | M |
| H11 | No existe proyecto de pruebas C# (deuda D15): ~20.700 líneas en 80 ficheros cubiertas solo por 5 selftests de consola; `UpdateSelfTest.cs` demuestra que el testeo hermético es viable | `VSC#/` (sin xunit/nunit/mstest) | M-L |
| H12 | `purgar_repositorio.ps1` ancla a raíz y snapshot equivocados, no borra nada, traga errores y aun así imprime «¡Purga completada con éxito!» | `purgar_repositorio.ps1:8,14,83` | S |
| H13 | `borrar_packs_viejos.ps1` borra packs de `.git/objects/pack` por nombre hardcodeado con reintentos de 2 min — borrar packs a mano puede corromper el almacén de objetos; lo git-nativo es `git gc`/`git repack` | `borrar_packs_viejos.ps1:3-31` | S |
| H14 | Variante CI de H8/H9: además, el build C# del workflow no lleva `-p:SkipGodotAssets=true` y fallaría en un clon limpio | `ci.yml:96` | S |
| H15 | El §11 del README da instrucciones de reconstruir el PCK imposibles desde un clon: no hay ni una textura/modelo versionados (D12) — el §11 contradice al §17 | `README.md:576` vs `git ls-files` de MTBGT | S(doc) |

### 4.2 Medios (M1–M39)

**Núcleo Python (M1–M7):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M1 | 126 `except Exception` (más un `except:` desnudo) que tragan fallos y sustituyen por ceros/fallbacks fabricados — es lo que convierte el NameError de SL3/SL4/SL5 en «calidad 0» silenciosa | `LC_STM`+`STM_IA` (p.ej. `SLRN/__init__.py:237-261`) | L |
| M2 | `RF_EN/__init__.py` exporta inicializadores «ortogonales/espectrales» matemáticamente erróneos (devuelven ruido escalado); los correctos (QR/SVD) viven en `_rfen_base.py`; `get_optimizer` devuelve el *string* `'Adam'` | `RF_EN/__init__.py:29-40,116-118` vs `_rfen_base.py:94,101` | S |
| M3 | Duplicación estructural masiva: clases base, inicializadores He/Xavier/LeCun y jerarquías Config/Metrics/Result re-implementadas por familia (y 2× dentro de RF_EN, y 10 fallbacks «autocontenidos» idénticos) | ENRN/RF_EN/RNP/SLRN | L |
| M4 | No instalable con pip como conjunto: el único manifiesto está en `STM_HRTS/` y no puede empaquetar a sus hermanos; el runtime depende de 5 `sys.path.insert` y `LC_STM` ni `__init__.py` tiene | `STM_HRTS/pyproject.toml`, `mainLCSTM.py:27-29` | M |
| M5 | El módulo de «voz neuronal» no usa red neuronal alguna (re-delega en DSP) e importa 6 librerías no declaradas; el singleton descarga modelos de huggingface sin verificar digest | `SLRN/procesador_voz_neuronal.py:94-95,162-164` | S |
| M6 | Efectos colaterales a la importación: `np.random.seed` global, `logging.basicConfig` reconfigurando el logger del huésped, carga ansiosa de los 10 módulos por familia (derrota el diseño lazy) | `ENRN/__init__.py:78,359`, `RF_EN/__init__.py:388-389` | M |
| M7 | Las neuronas de entrada ENRN hacen llamadas LLM salientes con claves de modelo incrustadas (`nemotron_nano_9b`, `lyria_pro`, `gemma4`); la selección de modelo debe vivir en SBSTM/config | `ENRN/__init__.py:165-172` | S-M |

**Periferia Python (M8–M15):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M8 | Semilla maestra del vault hardcodeada en un repo público → `vault.enc` es ofuscación, no cifrado (mitigado: vault gitignored + ruta por env + máscara de clave) | `vault_openrouter.py:18,33` | S |
| M9 | Las dos únicas rutas `C:\Users\User\Desktop\...` del área (nombres de usuario personales en repo público) | `CONTRRF/…/stm_base.py:274-275` | S |
| M10 | Descubrimiento de `ipfs.exe` sesgado a Windows + `taskkill /F /IM ipfs.exe` que mata todos los daemon de la máquina; `ipfs_launcher.py` sí es multiplataforma y debería ser el único camino | `SBSTMPYIPFS/bat_runner.py:36,45` | S |
| M11 | Triple duplicación del wrapper Kubo + escritura atómica re-implementada por paquete (ambas correctas, ninguna compartida) | `STMIPFS/SBSTMPYIPFS/__init__.py` vs `ipfs_utils.py` vs `ipfs_launcher.py` | M |
| M12 | Módulos muertos sin importadores — incl. `split_tool.py`, que **corrompería ficheros si se ejecutara hoy** | `SBSTM/split_tool.py`, `config_catalogo.py`, `bat_runner.py` | S |
| M13 | Etiquetas de estado engañosas (`__status__ = "Production / Optimized"` en un shim admitido) y CIDs `QmLocal…` falsos minados en bloques inmutables | `STMIPFS/__init__.py:21`, `BKSVCB.py:193-213` | S |
| M14 | El cierre de `IALOCAL.py` llama a métodos inexistentes en el shim (`mgr.add`) → el paso «pesos → IPFS» nunca puede subir por construcción; hoy dormante | `IALOCAL.py:239-243` vs `compat_local.py:146-203` | S |
| M15 | `logging.basicConfig(CRITICAL)` a la hora de importar (silencia el logger del proceso huésped, 3ª copia) y `sys.path` calculado desde el padre equivocado | `BKSVCB.py:19-21`, `STM_BKCH/__init__.py:37-49` | S |

**Visor C# (M16–M20):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M16 | Bombeo del proxy WS: `Task.WhenAny` deja la bomba perdedora corriendo sin observar, dispone un socket aún en uso, sin CancellationToken ni KeepAlive → túneles half-open bloqueados para siempre | `WebNodoService.cs:864-906` | S-M |
| M17 | El túnel efímero se lanza dos veces concurrentes en el flujo de login (hasta 3 puntos de llamada) y el barrido de huérfanos puede matar el túnel que sí funciona | `MainWindow.xaml.cs:847-848,1404,3214,3236-3240` | S |
| M18 | La binding por hardware de `llave_acceso.json` es eludible: JSON sin firmar, hash vacío se salta la comprobación, WMI caído → cadena vacía → se omite; la «rotación» no enlaza nada secreto | `MainWindow.xaml.cs:780-794,3128-3148` | S |
| M19 | `cloudflared.exe` se descarga y ejecuta sin verificar digest ni firma — exactamente el patrón que el propio proyecto rechaza para sus binarios OTA | `MainWindow.xaml.cs:3395-3411`, `P2PWebNode.cs:300` | S-M |
| M20 | God-class `MainWindow.xaml.cs` (3.420 líneas, 68 `x:Name` sin binding) mezclando OTA, P2P, túneles, chat, amigos, webcam y auth; el lado Avalonia ya usa parciales `VentanaPrincipal.*.cs` como costura natural | `MainWindow.xaml.cs` | M-L |

**Mundo Godot (M21–M24):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M21 | Los RPCs de edición por relé pasan parámetros sin clamp ni cota: centros NaN, radios gigantes, escalas sin límite, sin tope de prims por isla ni de tasa por par | `Construccion.gd:567-584,728-751,762-773` | M |
| M22 | El objetivo de migración de host sale de URLs auto-reportadas por los pares: el primero en unirse decide a dónde se reconectan todos (combinable con V2/H7 para capturar la sesión) | `ChunkManager.gd:454-464,763-789` | M |
| M23 | Un invitado cuya conexión falla queda colgado en la pantalla de carga para siempre: sin timeout, sin reintento, sin UI de error | `Boot.gd:169-179,209-211`, `ChunkManager.gd:417-424` | S |
| M24 | I/O a disco sostenida dentro de `_process`: relectura de `p2p_session.json` cada 2 s y escritura de `registro.cfg` cada 1 s en el hilo principal, cambie o no algo | `ChunkManager.gd:1026-1039,1066-1120` | S-M |

**Pruebas y CI (M25–M30):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M25 | `test_h2_h3_red.py` son 4/4 greps de cadenas exactas del fuente y `test_h1_contencion.py` repite el patrón para C#: afirman que el texto existe, no que el comportamiento funciona | `tests/test_h2_h3_red.py:22+`, `test_h1_contencion.py:218-230` | M |
| M26 | Pruebas acopladas al entorno: repo IPFS real pre-inicializado, sonda de red a `localhost:11434`, y un assert invertido que solo pasa en máquinas sin daemon | `tests/test_sistema.py:63,83-99,193-213` | M |
| M27 | Asserts de presupuesto temporal estrictos (<15 ms, <100 ms PoW probabilístico, <5 ms de media) — flaky en máquinas cargadas y en runners CI | `test_sistema.py:206,213,243,282`, `test_emocion.py` | S |
| M28 | Pruebas no herméticas que mutan estado real del usuario (cachés, PSNRL) y reach-ins a atributos privados; `test_h1_contencion.py` ya demuestra el patrón correcto (tmp_path + parcheo) | `test_sistema.py:273-282`, `test_perfil.py:34-44` | M |
| M29 | `StartupSelfTest` — la única comprobación end-to-end extracción+arranque — es inejecutable en CI por los assets no versionados (86 MB + 114,6 MB gitignored) | `Services/StartupSelfTest.cs` | M |
| M30 | Gran superficie sin cobertura: la mayoría de módulos LC_STM solo se importan, varios SBSTM sin referenciar, GDScript y C# sin probar del todo | `tests/` | L |

**Scripts, build y docs (M31–M39):**

| ID | Hallazgo | Dónde | Eff. |
|---|---|---|---|
| M31 | Release 100% manual: sin CI, inputs no versionados, y el único script de publish clavado a `E:\`, versión 2.7.5 y un RID | `publish_release_v275.ps1:4-7` | S(param)/L(CI) |
| M32 | Cuatro lanzadores de opencode con la misma cadena de fallback, ya divergentes (`lanzar_opencode.bat` perdió la rama node_modules) | `opencode/*.bat|*.ps1`, `utils/lanzar_opencode.bat` | S |
| M33 | La cabecera de `woldvirtual-linux.sh` documenta tamaño/SHA del PCK que contradicen las constantes que el propio script exige — el usuario concluiría que un mundo genuino es inválido | `woldvirtual-linux.sh:24` vs `:48-49` | S |
| M34 | El SHA256SUMS publicado lleva BOM UTF-8 + CR y rompe `sha256sum -c` en Linux — defecto documentado en cada release pero nunca corregido | release v2.7.5, README §2/§5/§16.4 | S |
| M35 | §17 describe la forma del repo upstream (34 tags/21 releases/9 ramas), no la de este fork (solo `main`, 0 tags) — engañoso para cualquier lector de este repo | `README.md` §17 | S |
| M36 | El ciclo de rename `actualizacion_<hex>` (8 nombres históricos) rompe 72 enlaces del README por ciclo y deja reglas fósiles en .gitignore y `REGLAS_DE_ACTUALIZACION.md` ancladas al snapshot anterior | repo-wide | L |
| M37 | README de 118,9 KB simultáneamente manual/changelog/roadmap/bitácora/política — sin split a CHANGELOG/ROADMAP | `README.md` §2,§15,§16,§17 | M |
| M38 | Contradicciones internas: §18 «41 documentos» vs §4 «43» (43 es correcto); el plan de desarrollo más reciente (`src/README_DESARROLLO.md`) falta del índice y su cabecera sigue diciendo «no rastreado por Git» y ancla TLLDCD | `README.md:853` vs `:241` | S |
| M39 | 43 documentos solo en español y sin guía de contribución real (§19 son cinco viñetas, sin prerrequisitos ni rutas) | `README.md` §19 | S-M |

### 4.3 Bajos (L1–L22)

| ID | Hallazgo | Dónde |
|---|---|---|
| L1 | Supuestos Windows-only en Python portable: fallbacks `E:/`/`C:/Program Files/dotnet` y `ram_gb()` que en Linux lanza y devuelve 8,0 asumidos (afecta al tope de modelos GGUF) | `rutas.py:127-128`, `IALOCAL/gestor.py:82-92` |
| L2 | Descargas GGUF interrumpidas se aceptan como válidas (sin `.part` ni verificación de Content-Length) | `IALOCAL/gestor.py:166-181` |
| L3 | Higiene de dataclasses/anotaciones: métricas vía `locals()`, Optional implícitos, anotaciones de retorno falsas, `__autor__` por `__author__` | `_rn_base.py`, `RF_EN/__init__.py:86-118`, `ENRN/__init__.py:328` |
| L4 | Deuda CONTRRF confirmada en código: método duplicado shadowed (`def ejecutar` dos veces), re-exports tragados con `except Exception: pass`, imports sin uso | `stm_flujo.py:161-163`, `STM_RFPRMN_stmDL/__init__.py:320-375` |
| L5 | Entradas muertas del registro JSON (ficheros que nadie escribe) y rama de limpieza inalcanzable | `registro_json.py:41-44`, `STM_CH/rutas.py:98-100` |
| L6 | CONTRRF (la herramienta que purga versiones) sin ninguna prueba automatizada; verificación por recuento únicamente (deuda D5) | `CONTRRF/STM_RFC` |
| L7 | Dos `pip install` en runtime escondidos dentro de funciones de biblioteca | `SBSTM/IALOCAL.py:88-89,152-155` |
| L8 | Cultura parcial: los `tamano_mb` servidos en JSON usan `CurrentCulture` («412,3» en es-ES rompe parsers) | `WebNodoService.cs:136,192` |
| L9 | Puertos dinámicos solo en la unión LAN: chat (8920), config de sesión (8911/7890) y relés siguen hardcodeados (~30 literales) | `MainWindow.xaml.cs:1592,1316-1317`, `ChatRelayServer.cs:40,62` |
| L10 | Higiene UI: `Thread.Sleep` en el hilo UI, `async void` sin try/catch, diagnósticos tragados | `MainWindow.xaml.cs:2987,2993`, `VisorLinux/Vistas/*.cs` |
| L11 | Escenas muertas dentro del PCK de 114,6 MB (`export_filter="all_resources"` exporta también lo no referenciado) | `export_presets.cfg:9`, `MNCNT.tscn`, `SLTRTN.tscn` |
| L12 | Señales multiplayer conectadas en `_ready` y nunca desconectadas (Sonda.gd sí muestra el patrón correcto) | `ChunkManager.gd:297-302`, `PlayerSync.gd:26-30` |
| L13 | Dos ficheros dentro de `tests/` no son pruebas: uno reproduce audio 90 s por MCI de Windows, otro llama a gTTS (red) — pytest los colecciona igualmente | `tests/test_voz_lucia.py`, `tests/diag_voz.py` |
| L14 | Selftests con puerto fijo (18920), controles WPF instanciados y sincronización por `Task.Delay` — propensos a colisión justo donde correría CI | `ChatSelfTest.cs`, `RedSelfTest.cs` |
| L15 | Asserts frágiles: versión de manifiesto hardcodeada y policía de líneas (≤450) dentro del arnés de regresión | `test_sistema.py:221`, `test_perfil.py:70-72` |
| L16 | `herramientas.py` construye argv de cmd/powershell/sh sin gating de plataforma: en Linux, `FileNotFoundError` con traceback | `herramientas.py:224-229` |
| L17 | Dos .ps1 con acentos UTF-8 sin BOM: Windows PowerShell 5.1 los decodifica como ANSI (mojibake) | `limpiar_cache_godot.ps1`, `purgar_repositorio.ps1` |
| L18 | Un .bat hardcodea el escritorio de otro usuario (`C:\Users\User\Desktop\Godot…`) por delante del fallback de PATH | `Godot_abrir_y_limpiar_al_cerrar.bat:7-8` |
| L19 | `limpiar_cache_godot.ps1` cuenta huérfanos como borrados antes de saber si el borrado tuvo éxito (métrica que alimenta H5) | `limpiar_cache_godot.ps1:30-35` |
| L20 | `arrancar_daemon.bat`: directorio mal escrito (`STMIPFSCOMFIG`) y sin reportar el código de salida del daemon | `arrancar_daemon.bat:16-17,36-37` |
| L21 | 7,3 MB de capturas duplicadas (blobs idénticos) entre `docs/img` y `STM_DOC/docs/img` + una imagen huérfana (`08_construccion_prims.png`) | `docs/img/`, `STM_DOC/docs/img/` |
| L22 | Faltan ficheros raíz estándar: `.github/`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig` (⇒ **.editorconfig ya añadido en esta rama**) y hay una regla `*.gltf` muerta en .gitattributes | raíz del repo |

---

## 5. Huecos del crítico de completitud (G1–G9)

Temas que el análisis por áreas no había cubierto y que la pasada crítica consideró
imprescindibles:

| ID | Hueco | Evidencia clave |
|---|---|---|
| G1 | **Relé de chat sin autenticar, deliberadamente expuesto a todos los interfaces y por el túnel público.** `IPAddress.Any` «para atender tanto al túnel público como a la LAN»; el proxy entrega clientes del túnel directamente al chat; tras el handshake RFC6455 el cliente queda registrado sin token, origen ni identidad — cualquiera (LAN o internet) puede leer e inyectar mensajes | `ChatRelayServer.cs:17-20,50,106-144`, `WebNodoService.cs:654` |
| G2 | **El visor Linux/Avalonia (VisorLinux) quedó sin examinar.** Segundo producto .NET 8 autónomo (22 ficheros, Avalonia 11.2.3, cero .axaml — toda la UI en C#) con su propio OTA (`ActualizadorLinux.cs`, 300 líneas, sustitución del paquete en marcha), portal, chat, cuentas y registro de máquina. Se desconoce si comparte los defectos apply/sin-rollback/reanudación del WPF | `VSC#/VisorLinux/` |
| G3 | **Sin firma de código en ninguna capa.** El SHA-256 que el updater exige viene del mismo JSON de release que la URL del asset: un release (o cuenta) comprometido auto-actualiza a todos en silencio; SmartScreen/AV interfieren con un self-updater sin firma y un cuarentena a mitad de apply agrava el bug de brick ya encontrado | `UpdateChecker.cs:160`, scripts de publish |
| G4 | **Las IPs de los pares se cosechan, difunden y persisten.** Cada cliente reporta su URL+IP de LAN al host; el roster guarda `{url, ip, nick}` por par, lo serializa y lo retiene en `user://p2p_session.json`. En sesiones por túnel, cada desconocido recibe la IP doméstica real de los demás | `ChunkManager.gd:367,412,437,463,771` |
| G5 | **Sin backup, exportación ni recuperación para mundos ni ledger.** `registro.cfg`, `islas_registro.cfg`, `p2p_session.json` sin export/snapshot/versionado de esquema; STM_BKCH no contiene implementación de backup. Combinado con el reset a génesis (H1) y el robo de islas (V2), el mundo construido es irrecuperable | `ChunkManager.gd:18,126,1067`, `STM_BKCH/` |
| G6 | **Sin validación en dos máquinas del producto P2P central** (upstream #22, P0) y sin cruzar los P0 propios del proyecto con los hallazgos; hitos H5 (métricas de huella) y H6 (topes de producto) abiertos; peso del visor = issue #15 (365 MB Win / 207 MB Linux) | `CLAUDE.md` Known Issues, README §15/§18 |
| G7 | **Superficie de dependencias Python no declarada y sin escaneo.** Solo existe `STM_HRTS/pyproject.toml`; SBSTM/STMIPFS/STM_BKCH/STM_SGR/STM_IA no tienen manifest ni lockfile → pip-audit/Dependabot no tienen nada que consumir; sin gitleaks/pre-commit (la semilla del vault se cazó a mano) | `src/STM_HRTS/pyproject.toml` |
| G8 | **Licencias/atribución de terceros ausentes en un repo MIT.** AForge.Video 2.2.5 es LGPL-3.0, NAudio, cloudflared Apache-2.0, Godot y modelos Ollama embebidos/descargados, PCK de 114,6 MB sin provenance — y no existe NOTICE/THIRD-PARTY_NOTICES | `LICENSE`, `Visor3D.csproj`, README §19 |
| G9 | **Accesibilidad e i18n ausentes a nivel de código.** Un solo `AutomationProperties` en todo el WPF, cero en Avalonia, sin .resx/.po/.translation: cada cadena está hardcodeada en español — ni soporte de lector de pantalla ni camino a un segundo idioma sin extracción total | `MainWindow.xaml`, `VisorLinux/Vistas/*.cs`, `gdscrip/` |

---

## 6. Cruce con la deuda existente del proyecto

El proyecto ya rastrea parte de esta deuda. Mapa de correspondencia (a completar con
DT-01..DT-10 del issue #45 de upstream como primera acción de adopción de este plan):

| Este plan | Registro existente | Observación |
|---|---|---|
| V1 (red fabricada) | **Deuda D1** + README §12 + `red_neuronal.md` | D1 debe corregirse: su remedio asume que el destino del port es real y no lo es |
| M13 (CIDs falsos minados) | **Deuda D2** | El shim está admitido; lo que falta es no minar CIDs sintéticos ni etiquetar «Production» |
| L4 (re-exports tragados CONTRRF) | **Deuda D4** | Confirmado en código |
| L6 (CONTRRF sin pruebas) | **Deuda D5** | Confirmado: 10 ficheros, 0 tests |
| H15/M36 (assets sin versionar, enlaces rotos) | **Deuda D12** + §11/§17 | §11 hoy es engañoso; corregir el texto es S, versionar assets es L |
| H11 (sin suite C#) | **Deuda D15** | README §14 lo admite; `UpdateSelfTest` es la base de migración a xunit |
| M34 (SHA256SUMS con BOM) | **§16.4 pendiente** + §2/§5 | Documentado en cada release y nunca corregido; arreglarlo es una línea del pipeline |
| G6 (validación 2 máquinas) | **Issue #22 (P0)** | Requiere hardware; bloquea cualquier afirmación de «multijugador validado» |
| L11 + M29 (peso del visor/PCK) | **Issue #15** + hitos **H5/H6** | Escenas muertas fuera del PCK = primera rebaja medible |
| M31 (release manual) | §11/§16.4 | Parametrizar publish + CI de hasheo es el mínimo |
| M35/M36/M37/M38 (README) | §14–§18 | El split CHANGELOG/ROADMAP baja el coste de cada release |
| V6, H8–H10, M25–M30 | §14 («CI: Roto») | La CI puede revivir en una tarde (Etapa 3) |
| — | **DT-01..DT-10 (issue #45)** | Pendiente de cruce: nadie del análisis leyó su contenido en detalle |
| — | Issues **#23, #38** | Referenciados por el README; cruzar contenido al adoptar este plan |
| — | Fases **F0–F7** (§15) | Las Etapas 0–6 de abajo deben mergearse en F0–F7 al planificar sprints |

---

## 7. Plan por etapas

Orden por valor: primero lo quirúrgico y la verdad documental (Etapa 0), luego el
riesgo de producto (seguridad P2P), luego fiabilidad del visor, luego la red de
seguridad (CI/pruebas) que protege todo lo demás, y después estructura, núcleo y
ecosistema.

### Etapa 0 — Victorias inmediatas y verdad documental (esfuerzo S; ~1 semana)

**Objetivo:** cerrar los defectos de una sola línea/una sola área y eliminar las
afirmaciones documentales falsas, sin tocar diseño.

| Ítem | Acción | IDs |
|---|---|---|
| 0.1 | `import math` en `_sl_math.py` + re-indentar `cosine_decay` (muerto tras `return`) + smoke test por optimizador | V3 |
| 0.2 | `STM_RFC_DIR` → `CURRENT_FILE.parents[5]/CONTRRF/STM_RFC/STM_RFPRMN` y reactivar los 6 comandos de consola; actualizar README §13 y STM_DOC | V6 |
| 0.3 | Ledger a prueba de génesis: ante error de carga, renombrar a `blockchain_ledger.corrupt-<ts>.json`, avisar, y solo entonces decidir; estrechar los `except` de `:251/:268` | H1 |
| 0.4 | Salida temprana en `UpdateDownloader` cuando el `.part` ya tiene el tamaño final → directo a verificación de digest | H4 |
| 0.5 | Corregir `STMIPFSCOMFIG`→`STMIPFSCONFIG` y reportar ERRORLEVEL del daemon | L20 |
| 0.6 | Cabecera de `woldvirtual-linux.sh` → 114.591.724 B / `ebeff90c…7ae5e14` (o generarla de las constantes) | M33 |
| 0.7 | Reescribir §11: el PCK no se reconstruye desde el repo (apuntar a release assets como única fuente) | H15 |
| 0.8 | §18: 41→43 + indexar `src/README_DESARROLLO.md` + corregir su cabecera («no rastreado», TLLDCD) | M38 |
| 0.9 | §17: nombrar ambos repos (fork = solo main; tags/releases/issues en upstream) | M35 |
| 0.10 | `__status__ = "Prototype"` en STMIPFS/STM_BKCH; borrar `def ejecutar` muerto; `__autor__`→`__author__`; regla `*.gltf` muerta fuera | M13, L4, L3, L22 |
| 0.11 | Decisión sobre `purgar_repositorio.ps1` y `borrar_packs_viejos.ps1` (proposta: sustituir el segundo por `git gc --prune=now` documentado; eliminar o reescribir el primero anclándose a `git rev-parse --show-toplevel` + flag de confirmación + banner solo si algo se borró) — **requiere decisión del propietario** | H12, H13 |

**Criterios de aceptación:**
- `python -m pytest` verde (98) y `py_compile` limpio en los módulos tocados.
- Smoke tests nuevos de optimizadores SL1–SL10 en verde (sin excepción, éxito
  reportado).
- Arrancar `mainLCSTM.py` y ejecutar `ayuda` + los 6 comandos RFPRMN: responden (ya no
  no-ops).
- Ledger corrupto plantado a mano → se renombra, se avisa, no se pierde historia.
- Un lector nuevo del README no puede concluir que (a) el PCK se reconstruye, (b) la
  red neuronal entrena, (c) este fork tiene releases.

### Etapa 1 — Seguridad de la sesión P2P (M–L; el mayor riesgo de producto)

**Objetivo:** que «solo el dueño edita» y «sesión privada» sean ciertos incluso con
pares hostiles en la LAN o detrás del túnel.

1. **Identidad de pares (V2):** mapa host-privado uuid→peer_id; prueba de posesión
   (hash salado del uuid secreto) en la conexión; cola de reclamaciones de islas de
   dueños desconectados con confirmación diferida en lugar de adopción inmediata;
   revalidar `_es_mi_isla`.
2. **Credencial de sesión en LAN/directo (H7):** token aleatorio del host exigido como
   primer mensaje (o parámetro de URL) también en `ws://`; rechazar pares sin token en
   `peer_connected`; beacon LAN opt-in.
3. **Autenticación del relé de chat (G1):** el host genera un token por sesión y lo
   inyecta tanto a clientes locales como a conexiones llegadas por el proxy del túnel;
   cerrar clientes no autenticados tras el handshake.
4. **IP de cliente fiable (H2):** el proxy TCP escribe la IP real en
   `X-Forwarded-For` y `ObtenerIpCliente` ignora la cabecera salvo marcador de proxy
   de confianza; cota con expulsión LRU en `RateLimiter`.
5. **Validación de entradas `any_peer` (H6, M21):** rechazo de no finitos, clamps de
   radio/escala/herramienta, cota de nick, ignora cambios de avatar <2 s, tope de
   prims por isla y cubo de tokens por par.
6. **Migración de host fiable (M22):** candidatos solo entre pares verificados por el
   host (o por tiempo conectado acumulado + acuerdo de N pares); mostrar el destino en
   UI antes de conectar.
7. **Privacidad de IPs (G4):** no difundir la IP al roster general ni persistirla en
   `p2p_session.json` (basta la URL del túnel); el host la usa en memoria y nada más.

**Criterios de aceptación:** dos clientes de prueba (uno legítimo, uno hostil con uuid
falsificado) en LAN: el hostil no edita islas ajenas, no entra al chat sin token, no
fuerza migración, y no ve la IP de nadie en ningún fichero persistido; un cliente que
envía posiciones NaN/radios absurdos es ignorado o expulsado.

### Etapa 2 — Fiabilidad del visor, OTA y datos (S–M)

1. **Apply seguro (H3):** re-hash del pendiente contra `state.json` (sha256 + nombre de
   asset) antes de generar el .bat; fallback `if not exist "%EXE%" move /Y "%EXE%.old"
   "%EXE%"` tras agotar reintentos; borrar `state.json` solo con éxito.
2. **Bucle de accept resiliente (H5):** `break` solo para `ObjectDisposed`/stopping;
   cualquier otra excepción → `VisorLog.Error` + continuar con backoff; log en el 500
   de `ProcessRequest` y en `HandleProxyClientAsync`.
3. **Proxy WS correcto (M16):** `CancellationTokenSource` cancelado en `finally`,
   observar ambas bombas antes de disponer, `KeepAliveInterval`, cierre con timeout
   (patrón de `ChatClient.CerrarSocketAsync`).
4. **Túnel único (M17):** `SemaphoreSlim` alrededor de `EstablecerTunelEfimeroAsync`
   con re-chequeo del guard dentro; `BarrerHuerfano` solo sin intento en curso.
5. **cloudflared verificado (M19):** versión pinneada + SHA-256 (o verificar
   Authenticode con `X509Chain`) y fail-closed.
6. **Cierre de sesión honesto (M14):** `mgr.almacenar_pesos(...)` + ramificar por
   `ok`/`simulado` imprimiendo el error real del shim; CIDs `simulado` no se minan
   (M13b).
7. **UX de conexión (M23):** timeout de 20–30 s en `Boot._entrar_a_isla` con diálogo
   reintentar/volver; señal `conexion_imposible` desde `ChunkManager`.
8. **I/O fuera de `_process` (M24):** `get_modified_time` antes de releer sesión;
   posición guardada con debounce; persistencia en `Timer`.
9. **Detalles:** `InvariantCulture` en `tamano_mb` (L8); centralizar constantes de
   puerto y roscar el puerto del beacon al chat/config (L9); try/catch en `async void`
   y `Thread.Sleep` fuera del hilo UI (L10); binding por hardware como HMAC y hash
   vacío = fallo (M18).
10. **Firma de artefactos (G3, L — estratégico):** decidir vía (minisig multiplataforma
    o Authenticode+codesign por RID), firmar binarios y SHA256SUMS en el pipeline, y
    que el updater verifique firma además de digest. Reduce a un problema de key
    management lo que hoy es «un release comprometido = fleet comprometida».

**Criterios de aceptación:** selftests 17/26/19/7/update en verde tras cada cambio;
prueba manual de bricked-apply (exe destino bloqueado) → el .bat restaura desde `.old`;
un `.part` completo reutilizado sin re-descarga (log); portal sobrevive a una excepción
inyectada en el listener.

### Etapa 3 — CI viva y pruebas de comportamiento (S–M, una tarde + iteración)

1. **Promover CI (H8, H9, H14):** copiar `ci.yml` a `.github/workflows/` de la raíz,
   reescribir los 9 `working-directory` al árbol real, `-p:SkipGodotAssets=true` en el
   build, quitar el `|| pip install` enmascarador. Trigger: push/PR a `development` y
   `main`.
2. **Des-advisory (H10):** quitar `continue-on-error` cuando la suite sea hermética;
   mientras, separar las pruebas con daemon en un job propio nombrado.
3. **Hermeticidad (M26, M27, M28):** `conftest.py` que redirija LEDGER/PSNRL/cachés a
   `tmp_path` antes del import; repo IPFS inicializado en fixture o binario falso;
   mock del socket de Ollama; asserts de tiempo → métricas registradas o topes 10×.
4. **Comportamiento sobre grep (M25):** conservar un solo grep como tripwire y portar
   el resto (los casos C# ya existen en `UpdateSelfTest` — invocarlos o portarlos).
5. **Suite C# (H11):** proyecto `Visor3D.Tests` (xunit); portar los cinco selftests
   (Update/Cuenta casi verbatim; Red/Chat con sockets loopback); `dotnet test` en CI.
6. **Cobertura neuronal mínima (V4):** añadir `LC_STM` a `PAQUETES`; un smoke
  parametrizado por familia (forward/backward sin excepción) — ya iniciado en 0.1.
7. **Higiene del arnés:** `test_voz_lucia.py`/`diag_voz.py` fuera de testpaths (L13);
   puerto 0 en selftests (L14); versión contra pyproject y regla de líneas fuera del
   gate (L15); `StartupSelfTest` partido en parte sin assets (CI) y arranque real
   (checklist de release) (M29).

**Criterios de aceptación:** la rama `development` muestra checks verdes en GitHub; un
`git push` que rompa una prueba real (no grep) roja la build; la suite corre dos veces
seguidas en un runner limpio sin fallos por entorno ni por tiempos.

### Etapa 4 — Núcleo neuronal honesto (M–L)

1. **Reetiquetar (V1):** cuerpos aleatorios → `NotImplementedError`; corregir D1 y
   `red_neuronal.md`; los «éxitos» fabricados dejan de exportarse (RN1:319, RN10:290,
   SL3:376).
2. **Contrato del shim (V5):** `stm_registro.py` exige `ok is True`; `simulado` =
   fallo explícito; decidir con el mantenedor el borrado incondicional del registro
   local (el «directorio limpio» es diseño documentado).
3. **Tragar menos (M1):** estrechar los 126 `except Exception` alrededor de math/IO;
   modo estricto que re-lanza en los bucles de optimización para que CI vea roturas.
4. **Superficie correcta (M2, M5, M6, M7):** re-exportar `_rfen_base` desde
   `RF_EN/__init__` y borrar las copias erróneas; declarar el grupo opcional `voz` +
   digest pinneado para las descargas ONNX; quitar seed/basicConfig/eager-load a la
   importación; sacar las claves LLM de ENRN hacia SBSTM/config.
5. **Empaquetado (M4):** `pyproject.toml` en `$SRC` con packages explícitos;
   `LC_STM/__init__.py`; eliminar los `sys.path.insert` cuando los imports resuelvan
   por paquete instalado.
6. **Limpieza (M12, M8, L1, L2, L3, L7):** borrar módulos muertos (split_tool —peligroso
   si se ejecuta—, config_catalogo, bat_runner); vault: rehusar descifrar vaults
   «usuario» sin `OPENROUTER_VAULT_PW`; `ram_gb()` Linux; `.part`+Content-Length en
   GGUF; `ruff check` con la config existente; pip runtime → extra declarado.
7. **Dedup estructural (M3, L — opcional/gradual):** módulo `_common` (neurona base,
   inicializadores, dataclasses) compartido por las cinco familias; converger RNP/SLRN
   en una interfaz de optimizador.

**Criterios de aceptación:** `pip install -e .` en un venv limpio y `lucia` arranca sin
`sys.path`; ningún test verde afirma entrenamiento; el README/§12/D1 describen
scaffolding; `ruff check` limpio en los tres paquetes.

### Etapa 5 — Estructura del repositorio (M–L)

1. **Camino estable (M36):** eliminar el rename `actualizacion_<hex>` del nombre de
   directorio (mover el id del snapshot a un manifiesto); reescribir los 72 enlaces;
   purgar reglas fósiles del .gitignore y `REGLAS_DE_ACTUALIZACION.md`. Coordinado con
   RFPRMN (la herramienta es quien renombra).
2. **Split del README (M37, M39, L22):** §2 → `CHANGELOG.md`; §15–§16 → ROADMAP; §17 →
   política propia; `CONTRIBUTING.md` con prerrequisitos (Godot 4.7.2, .NET 8,
   SkipGodotAssets, 98 pruebas, REGLAS_DE_ACTUALIZACION) — `.editorconfig` raíz ya está.
3. **Scripts (M31, M32, L16–L19):** `publish_release.ps1` parametrizado (`-Version`,
   `-PublishDir` derivado de la raíz); un solo lanzador de opencode; gating de
   plataforma en `herramientas.py`; BOM en los dos .ps1; fuera el escritorio ajeno del
   .bat; contar solo borrados exitosos.
4. **Visor (M20, L9):** split de `MainWindow.xaml.cs` por la costura Avalonia
   (`VentanaPrincipal.*.cs`): UpdateViewModel, TunnelController, UserControl de
   chat/amigos — sin cambio de comportamiento.
5. **Higiene (L5, L21):** entradas de registro muertas fuera; borrar el duplicado
   `STM_DOC/docs/img` (o enlazar relativo) y la imagen huérfana; §4 vuelve a medir
   contenido único.
6. **Assets (H15-real, L11, L — vinculado a #15/H5):** decidir el destino de las
   fuentes del mundo (versionar/LFS/submódulo o declarar release-assets-only);
   mientras, escenas muertas fuera del export y re-medir el PCK.

**Criterios de aceptación:** un grep de `actualizacion_` en docs/ devuelve solo
histórico/changelog; el README baja de ~890 a <300 líneas; clon limpio + `dotnet build
-p:SkipGodotAssets=true` + `python -m pytest` funcionan sin pasos ocultos; el peso del
PCK tras limpiar escenas se publica como métrica H5.

### Etapa 6 — Producto y ecosistema (M–L)

1. **Validación en dos máquinas (G6, #22):** guion de prueba LAN + túnel (chat,
   voz/webcam, construcción, migración de host, reconexión) ejecutado y documentado;
   hasta entonces, ninguna nota de release afirma multijugador validado.
2. **Backup/exportación (G5):** export/import de isla (chunk de terreno + prims +
   registro de dueño) y snapshot del ledger; como mínimo, copia automática pre-genesis
   (complementa 0.3).
3. **VisorLinux (G2):** auditoría dirigida de `ActualizadorLinux.cs` y compañía contra
   los defectos WPF conocidos (apply/rollback/reanudación/XFF) y corrección en paralelo.
4. **Cadena de suministro (G7, G8):** manifests por paquete (o el pyproject de Etapa 4
   con extras) + pre-commit con gitleaks + pip-audit/Dependabot;
   `THIRD-PARTY_NOTICES.md` (AForge LGPL-3.0, NAudio, cloudflared Apache-2.0, Godot,
   Ollama, provenance del PCK).
5. **Accesibilidad/i18n (G9):** base mínima — `AutomationProperties` en controles
   clave, navegación por teclado, y extraer cadenas UI a .resx/.po para que un segundo
   idioma sea posible sin reescritura.

**Criterios de aceptación:** una sesión real entre dos máquinas con el guion en verde;
existe `islas_export.zip` restaurable; Dependabot/gitleaks activos con hallazgos
informativos; NOTICE cubre todas las dependencias del csproj.

---

## 8. Checklist de victorias rápidas (ya priorizado)

Pes order, cada ítem es esfuerzo `S` y aporta valor visible esta semana:

- [ ] `import math` + `cosine_decay` re-indentado + smoke tests SL1–SL10 (V3)
- [ ] `STM_RFC_DIR` re-apuntado; 6 comandos LucIA operativos (V6)
- [ ] Ledger anti-génesis con `.corrupt-<ts>` (H1)
- [ ] `.part` completo → verificación sin re-descarga (H4)
- [ ] `STMIPFSCONFIG` + ERRORLEVEL del daemon (L20)
- [ ] Cabecera `woldvirtual-linux.sh` a 114.591.724 B / `ebeff90c…` (M33)
- [ ] SHA256SUMS regenerado sin BOM/CR en el pipeline + re-subida corregida de v2.7.5
      (M34 — **acción de release: requiere confirmación del propietario**)
- [ ] README §11/§17/§18 honestos (H15, M35, M38)
- [ ] `__status__ = "Prototype"`; `def ejecutar` muerto fuera; `__author__`; regla gltf (0.10)
- [ ] Decisión propietario sobre `purgar_repositorio.ps1`/`borrar_packs_viejos.ps1` (H12/H13)
- [ ] `.github/workflows/ci.yml` en raíz con working-dirs reales (H8/H9/H14 — se puede
      adelantar de la Etapa 3: es copiar + reescribir rutas)

## 9. Criterios de éxito del plan

1. **Verdad:** ninguna documentación afirma capacidades que el código no tiene
   (entrenamiento, reconstrucción del PCK, comandos operativos, estado «Production»).
2. **Confianza:** la sesión P2P resiste un par hostil (identidad, chat, migración,
   entradas) y las IPs de los usuarios no se difunden.
3. **Recuperación:** ningún fallo de disco/red/parser borra historia (ledger) ni
   inability de arrancar (OTA con rollback).
4. **Red de seguridad:** CI en la raíz que roja la build con pruebas de comportamiento
   reales; suite hermética y no flaky; primer proyecto xunit C#.
5. **Sostenibilidad:** README dividido, camino estable sin renames, empaquetado pip
   real, dependencias y licencias declaradas.
6. **Producto:** validación en dos máquinas ejecutada; métricas H5 publicadas; peso del
   visor/PCK medido y en bajada.

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Los cambios de identidad/token (Etapa 1) rompen la compatibilidad con clientes 2.7.5 ya desplegados | Versionar el handshake; período de doble modo (token opcional→obligatorio) coordinado con el ciclo de release |
| Reetiquetar la red neuronal (V1) «quita» funcionalidad anunciada upstream | Es documentación + `NotImplementedError` en caminos ya muertos; proponerlo a upstream como PR de honestidad, no como fork divergente |
| La ruta estable (M36) choca con el flujo RFPRMN existente | Prototipo en `development` + manifiesto; coordinar con la herramienta antes del primer ciclo real |
| Assets no versionados (H15) hacen irreproducible cualquier build de release | Decisión explícita del propietario: LFS/submódulo vs. release-assets-only; documentarlo en cualquier caso |
| Borrar módulos/escenas muertos elimina algo que upstream aún usa | Cada borrado individual en su propio commit reversible; verificar con grep de importadores/referencias antes |
| Pruebas de comportamiento descubren más roturas de las esperadas (lo normal tras V3/V4) | Es el objetivo: reportarlas como hallazgos nuevos y priorizarlas por severidad, no revertir la prueba |
| Firmas (G3) introducen gestión de claves que el proyecto no tiene hoy | Empezar por minisig (clave en el repo del mantenedor, passphrase fuera) y dejar Authenticode como paso posterior |
| El trabajo se dispersa entre etapas | Adoptar el orden 0→3 primero (quick wins + seguridad + fiabilidad + CI): la Etapa 3 protege todas las demás |

## 11. Apéndice — método del análisis

Análisis integral del repositorio ejecutado el 2026-11-02 sobre `main` @ `19cc65e`
mediante revisión multi-agente (14 agentes: 7 áreas + verificación adversarial de los
6 hallazgos principales + crítica de completitud), 459 llamadas a herramientas sobre
los 514 ficheros rastreados. Cada hallazgo incluye evidencia `fichero:línea`. Este
documento condensa los 82 hallazgos y 9 huecos resultantes; las severidades de V1–V6
reflejan el veredicto de verificación (dos críticos ajustados a alto, uno de alto a
medio, tres confirmados). Las citas de línea corresponden al snapshot
`actualizacion_aeef1149` y pueden desplazarse con futuros commits.
