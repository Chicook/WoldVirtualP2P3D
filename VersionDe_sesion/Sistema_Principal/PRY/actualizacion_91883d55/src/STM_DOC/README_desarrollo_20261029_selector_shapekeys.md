# Desarrollo selector de avatares, shape keys por código y animaciones compartidas

Trabajo sobre el árbol del 2026-10-29
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c`), rama `DevQoderIA`.

**Estado: Implementado, empaquetado y publicado como v2.7.0.** Los `.gd`, escenas y pruebas están en
el árbol, el `wvp3d.pck` se ha exportado de este mismo árbol, el visor se ha compilado como
`DMWoldVirtualP2P3Dv2.7.0.exe`, las cuatro autopruebas del visor terminan en verde y la release
`v2.7.0` está publicada como *Latest* con sus cuatro assets verificados por API. Lo que sigue sin
acreditar es el OTA de punta a punta y la respuesta de `/descargar` (ver checklist de §7).

---

## Objetivo

1. Revisar el selector de avatares y hacerlo manejable con ratón: **clic** para enfocar un avatar y
   **arrastre horizontal** para girar el anillo en círculo, más rueda y teclado.
2. Añadir **shape keys por código más visibles**, adaptando el conjunto de presets de blend shapes de
   VRM del addon 2031 de la Asset Library (`https://godotengine.org/asset-library/asset/2031`, el
   *VRM Importer* de V-Sekai, licencia MIT) al sistema de personalización existente.
3. Poder **escribir el nick en la misma pantalla** del selector.
4. Mostrar un aviso **en verde: «✔ AVATAR ORIGINAL»**, con el turno asignado.
5. Mantener la elección internamente, asignarla a un turno y hacer el paso **obligatorio** para
   entrar al metaverso, de modo que **cada avatar sea único** cuando entren más jugadores que plazas.
6. Que las **24 plazas del catálogo se animen** aunque de 16 de ellas sólo exista el `.glb` estático.

---

## Por qué shape keys analíticas y no morph targets

Los avatares del catálogo **no tienen morph targets**. Comprobado en el propio glTF
(`gltfimport/avatares/AVH1.gltf`): 8 mallas, 74 nodos, 1 skin y **0 `targets`** en todas las
primitivas. Por tanto `MeshInstance3D.set_blend_shape_value()` no tiene nada que mover y el camino de
VRM (`get_blend_shape_count()`/`set_blend_shape_value`) no es aplicable a estos assets.

Lo que se ha hecho es adaptar el **vocabulario** del addon 2031 y aplicarlo con la técnica que ya usa
el proyecto: deformación analítica de vértices en espacio de reposo, conservando UV, huesos y pesos,
así que la animación Mixamo sigue intacta y no hace falta reexportar ningún `.glb`.

Mapa de presets (`gdscrip/ShapeKeys.gd`):

| Preset VRM | Expresión del sistema | Efecto |
|---|---|---|
| `joy` | `sonrisa` | comisuras arriba y afuera, mejillas alzadas |
| `angry` | `enfado` | cejas abajo y hacia dentro, comisuras abajo |
| `sorrow` | `tristeza` | comisuras abajo, cejas interiores arriba |
| `fun` | `sorpresa` | mandíbula abajo, ojos más abiertos, cejas arriba |
| `blink` | `parpadeo` | párpado y pestañas cerrados |
| `a`, `o` | `boca_abierta` | óvalo de boca (suma el mayor) |
| `i`, `e`, `u` | `boca_ancha` | boca estirada en horizontal |

`neutral` no se mapea: es todo a cero. Las vocales comparten expresión y se combinan quedándose con
el valor mayor, igual que hace un morph target compartido.

Las 7 expresiones viven en `Personalizacion.EXPRESIONES`
(`gdscrip/Personalizacion.gd:22`) y viajan en `CAMPOS` (`:25`), así que se guardan, se leen y se
replican con el mismo mecanismo que tintes y proporciones.

## Amplitudes: medidas sobre una malla real

Para que las shape keys sean **visibles** se subieron las amplitudes del rostro (ojos, nariz, labios,
orejas) y se añadió la deformación de expresión en `Personalizacion._deformar_expresion`
(`gdscrip/Personalizacion.gd:392`), relativa a la cabeza medida en `_geometria` (`:560`).

Medición sobre `AVH1.gltf` real (32.809 vértices; esqueleto con hueso `Head`), con la expresión a
1,0 y contando vértices movidos más de 0,5 mm:

| Expresión | Desplazamiento máximo | Vértices movidos |
|---|---|---|
| `sonrisa` | 19,8 mm | 1.414 |
| `enfado` | 15,3 mm | 1.157 |
| `tristeza` | 11,4 mm | 1.106 |
| `sorpresa` | 23,2 mm | 2.912 |
| `parpadeo` | 16,4 mm | 2.954 |
| `boca_abierta` | 23,5 mm | 808 |
| `boca_ancha` | 8,4 mm | 905 |
| **Media / máximo** | **16,9 / 23,5 mm** | — |

Volver a cero restaura la malla original **exactamente** (diferencia 0,0 mm) y repetir una expresión
tras probar otra da la misma malla. En `SLAV` las expresiones se manejan con un panel **SHAPE KEYS**
en la esquina superior derecha, con un slider por expresión (0-100 %) y botón de reinicio
(`gdscrip/SLAV.gd:626`); al cambiar de avatar se restaura el anterior a neutro y se aplica la forma al
enfocado.

## Selector: ratón, nick y aviso verde

Todo el comportamiento nuevo está en `gdscrip/SLAV.gd`; la escena `SLCAV/AVATARESCONANIMACION/SLAV.tscn`
**no cambia de estructura** (la UI nueva se construye por código); sólo se reescribieron allí las 16
rutas `avatar_paths` de las plazas sin `_anim.glb` (ver «Animaciones compartidas»).

| Gesto | Comportamiento | Código |
|---|---|---|
| Clic izquierdo sobre un avatar | enfoca el más cercano proyectado a pantalla y salta plazas ocupadas | `SLAV.gd:191` (`_indice_bajo_punto`) |
| Arrastre horizontal | gira el anillo en círculo; 70 px por avatar, conserva el resto del recorrido | `SLAV.gd:174` (`_evento_arrastre`) |
| Rueda | siguiente / anterior | `SLAV.gd:147` |
| Teclado | flechas, `Enter` para elegir | `SLAV.gd:131` |
| Nick | campo en la parte inferior, mínimo 3 letras; sin nick válido el botón queda deshabilitado | `SLAV.gd:506` (`_confirm`) |

Estados del rótulo central (`SLAV.gd:410`, `_refrescar_estado`):

- **Verde** `✔ AVATAR ORIGINAL · <nombre> · Turno N` cuando la plaza está libre.
- **Rojo** `PLAZA OCUPADA · elige otro avatar para entrar` y confirmación bloqueada.
- **Ámbar** `TURNO 4 · catálogo completo: <nombre> se reutiliza` cuando los 24 están ocupados.

La elección se guarda en `user://registro.cfg` con claves propias
(`SLAV.gd:528`, `_guardar_eleccion`): `jugador.nick_selector`, `jugador.avatar_selector`,
`jugador.avatar_nombre`, `jugador.avatar_turno`, `jugador.avatar_reciclado`, más
`personalizacion.*`. **No escribe** `jugador.nick` ni `jugador.avatar_scene`: eso lo sigue haciendo
el registro, así que elegir avatar no permite saltarse el registro ni entrar directo por `Boot.gd`.

En `registro.gd` se prefija el nick elegido (`:81`, lee `nick_selector` y cae a `nick`) y se muestra
el mismo aviso verde `✔ AVATAR ORIGINAL · <nombre>` bajo el campo de texto
(`:115`, `_crear_aviso_original` en `:125`).

## Un avatar por jugador

La unicidad no se ha reimplementado: la sigue resolviendo la reserva exclusiva de `Turnos.gd` con
autoridad del anfitrión en `ChunkManager.gd`, más la consulta previa de `Sonda.gd` que ya alimenta
`SLAV.set_ocupados()` desde `Boot.gd`. Lo que añade este trabajo es que el hueco se elige **antes** de
tener nick y que la confirmación es **obligatoria** (sin nick y sin plaza libre no hay avance), con
turno 4 de reciclaje cuando el catálogo está completo.

## Corrección: los anclajes se miden sobre la malla sin deformar

Al revisar la deformación apareció un defecto real: `_aplicar_figura` calculaba la geometría de
referencia (anclas de ojos, nariz, labios, orejas, centros de brazos y piernas) sobre `mi.mesh`, que
tras el primer ajuste ya es la malla reconstruida. Cada cambio de slider medía sobre la malla
deformada, lo que hacía **derivar la cara** ligeramente y llenaba las cachés estáticas
(`_cache_geo`, `_cache_vertices`, `_cache_cabeza`, todas por `instance_id` de malla) con una entrada
nueva por reconstrucción.

Ahora la referencia es siempre la malla base guardada en `pers_mesh_base`
(`Personalizacion.gd:245-252`, `:877`, `:905`). Con eso los rebuilds son idempotentes y las cachés se
quedan en una entrada por recurso.

---

## Animaciones compartidas: las 5 de los principales para las 24 plazas

De los 24 avatares del catálogo sólo 8 (AVH1-4 y AVMJ1-4) tienen clips propios. Las 16 escenas
restantes apuntaban a `*_anim.glb` que **no existen en esta máquina** (ver «PCK 2.7.0»), así que
esas plazas montaban el `.glb` estático y se quedaban en la pose de reposo.

`gdscrip/AnimacionesCompartidas.gd` (nuevo, `class_name AnimacionesCompartidas`) toma las cinco
animaciones de `res://gltfimport/avatares/AVH1.gltf` —`paradoMJ1_1`, `caminarMJ1_2`, `correrMJ1_3`,
`left_StrafeMJ1_4`, `rightstrafeMJ1_5`—, reescribe las rutas de pista al esqueleto de destino y las
instala en el `AnimationPlayer` que el `AnimationTree` ya espera.

| Pieza | Comportamiento |
|---|---|
| Retarget | cada pista `Armature/Skeleton3D:mixamorig12_Cabeza` se normaliza quitando el prefijo `mixamorigNN_` y se busca ese hueso en el esqueleto destino; las pistas sin destino se descartan (`_normalizar`, `_retarget`) |
| Reproductor | se reutiliza el que declara `AnimationTree.anim_player` (`../AnimationPlayer` en las escenas Ch3D); si la malla vino sin reproductor se crea ahí mismo (`_reproductor`) |
| Biblioteca | Godot 4 no tiene `AnimationPlayer.add_animation`: los clips se añaden a la `AnimationLibrary` sin nombre (`_anadir`) |
| Refresco | tras inyectar se conmuta `AnimationTree.active` a falso y verdadero, porque el setter ignora el valor repetido (`_refrescar_arbol`) |
| Carusel | `SLAV._montar_turno` monta los `.gltf`/`.glb` crudos, no las escenas Ch3D, así que llama a `Anim.asegurar(inst)` antes de `_arrancar_idle` (`SLAV.gd:277-280`) |

**Cuándo se inyecta.** `AnimationMixer` resuelve su `anim_player` al recibir `NOTIFICATION_ENTER_TREE`;
activarlo después no reengancha un reproductor creado más tarde. Por eso la llamada va en
`_enter_tree()` de `AVMJ1Ch3D.gd` —el guión que comparten las 24 escenas Ch3D— y no en `_ready()`:
el padre entra en el árbol antes que sus hijos, así que el `AnimationPlayer` ya existe cuando el
`AnimationTree` se configura.

**Qué cambia en las escenas.** En las 16 plazas sin clips propios
(`AVH5-12Ch3D.tscn`, `AVMJ5-12Ch3D.tscn`) el `ext_resource` pasa de `…/X_anim.glb` a
`…/X.glb` (sin `uid`, porque es otro recurso) y se retiran las dos líneas que declaraban
`AnimationPlayer` con `autoplay = &"paradoMJ1_1"`: en un `.glb` estático Godot no crea reproductor y
la declaración quedaba huérfana («was modified from inside an instance, but it has vanished»); en los
dos casos que sí traen animaciones propias (AVH12 y AVMJ11) además colisionaba. Las 8 escenas
principales no se tocan.

En `SLCAV/AVATARESCONANIMACION/SLAV.tscn` se reescriben las 16 entradas correspondientes de
`avatar_paths` y en `avtrnCRS/SCNCNSTR/TURNOS/SLTRTN.tscn` se corrigen las rutas `ext_resource` de
`av3DT1.tscn`/`av3DT2.tscn` (sus `uid` ya coincidían).

---

## PCK 2.7.0: del bloqueo a la exportación

El 2.6.9 no se pudo reexportar el 2026-10-29 a primera hora porque el árbol de fuentes no tenía los
24 avatares: de las 153 rutas `res://` inventariadas faltaban 73, entre ellas los 16 `*_anim.glb` y
los 16 `.glb` estáticos de las plazas 5-12. Las animaciones compartidas resuelven la mitad del
problema (los `*_anim.glb` dejan de ser necesarios); la otra mitad se resolvió montando un árbol de
trabajo **fuera del repositorio** con los assets de `actualizacion_022321c8` y los estáticos del
catálogo:

- `E:/areadetrabajo/wvp270/godot`: proyecto Godot con 0 diferencias frente a este commit en los
  ficheros versionados (comparación SHA-1 fichero a fichero; los 333 ficheros extra son assets no
  versionados).
- Export `--export-pack "Windows Desktop"` → `E:/areadetrabajo/wvp270/wvp3d.pck`, 2026-10-29 18:01,
  **1.053.066.344 B**, 530 entradas, engine 4.7.2.
- `verify_pck.py` sobre ese PCK: **MD5 de las 530 entradas correcto**, 30 `.gdc` en el PCK = 30
  guiones del árbol (0 sobrantes, 0 ausentes), **4.041/4.041** identificadores y literales presentes,
  «el PCK es íntegro y corresponde a ese árbol».

El árbol conserva `gdscrip/AnimacionesCompartidas.gdc` (3.532 B), es decir, la inyección de clips va
dentro del mundo publicado y no depende de nada externo.

**Por qué el PCK pesa el doble que el de la 2.6.9 (537.836.524 B).** No es código: son texturas. El
`.glb` estático de cada plaza trae sus imágenes embebidas (`gltf/embedded_image_handling=1` las
extrae a `.png` junto al `.glb`) y se importan con `compress/mode=0` (lossless) y mipmaps: un mapa de
normales 4K acaba en 37 MB de `.ctex`. En el PCK de la 2.6.9 esas mismas plazas usaban los `*_anim`,
cuyas texturas eran mucho más pequeñas.

| Concepto | 2.6.9 | 2.7.0 |
|---|---|---|
| `.ctex` | 142 ficheros, 501.778.090 B | 135 ficheros, 1.018.607.504 B |
| `.scn` | 64 ficheros, 35.586.419 B | 64 ficheros, 33.969.052 B |
| Total del PCK | 537.836.524 B | 1.053.066.344 B |
| SHA-256 del PCK | `9d5c15e7…7a69ac94` | `cb17a956…d946b9e1` |

El PCK de la 2.6.9 se conserva fuera del repositorio en `E:/areadetrabajo/wvp270/wvp3d-2.6.9.pck`;
`src/VSC#/wvp3d.pck` es ahora el de la 2.7.0 (mismo MD5 que el exportado). El guión
`STM_LBR/woldvirtual-linux.sh` lleva el tamaño y la huella nuevos.

### Dónde están (y dónde no) los 16 avatares animados

Búsqueda del 2026-10-29 sobre `C:`, `D:`, `E:` y `F:` (`find` sin límite de profundidad en
`C:\Users\User`, `E:\areadetrabajo` y `F:\`, podando sólo `Windows`, `System Volume Information` y
`$Recycle.Bin`):

- **`.glb` crudos: no aparecen.** El único `*_anim.glb` de todo el equipo es
  `C:\Users\User\AppData\Local\Temp\prubaimp\avhm9_anim.glb`, resto de una prueba de importación.
  Los estáticos (`avhm1-9.glb`, `AVmj1-7.glb`) sí existen en
  `F:/PersonalizacionDavatares/AreaDeTrabajo/GTLF_GODOT/GltfIMP/AVATARES/` y en el árbol de trabajo
  `E:/areadetrabajo/wvp270/godot/…`.
- **Tampoco están en Git:** `git rev-list --all --objects | grep -i '\.glb$'` devuelve **0**
  entradas. Nunca se versionaron.
- **Sí están dentro del PCK de la 2.6.9, en forma importada.** De sus 541 entradas, **16** son las
  escenas `res://.godot/imported/<av>_anim.glb-<hash>.scn` (361.628-1.666.682 B), **87** son los
  `.ctex` de sus texturas y **111** son los `.import` originales
  (`avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES/{AVHM,AVMJ}/*_anim*.import`), 313.819.793 B en total. Las
  cabeceras de las 16 escenas empiezan por `RSCC` (recurso binario de Godot 4). No hay ninguna
  entrada `.glb` cruda: el export sólo empaqueta el resultado de la importación.

Es decir: los `.glb` de origen están perdidos, pero **los esqueletos, mallas, texturas y clips
importados de las 16 plazas se pueden reconstruir desde el PCK de la 2.6.9**. Para la 2.7.0 no hacen
falta (las animaciones se inyectan con retarget), y por eso no se ha tocado nada; queda anotado por
si alguna vez se quiere volver a los clips originales de esas plazas.

Al extraer del PCK hay que **sumar `base` (112) al `offset`** de cada entrada del directorio. Sin esa
suma los ficheros salen con bytes desplazados y Godot los rechaza con
`Unrecognized binary resource file`.

**El visor.** `Visor3D.csproj` pasa a `2.7.0` / `DMWoldVirtualP2P3Dv2.7.0`; el exe embebe
`wvp3d.pck` como `EmbeddedResource` y lo extrae en streaming (`AppExtractor` usa `stream.CopyTo`), sin
cargar el gigabyte en memoria. Publicado:
`DMWoldVirtualP2P3Dv2.7.0.exe`, **1.303.543.673 B** (1.243,2 MiB), SHA-256 `ceea0886…1318b59a`.

---

## Pruebas ejecutadas (evidencia)

Las pruebas de Godot, con `APPDATA` aislado en un directorio temporal y Godot 4.7.2
(`C:/Users/User/Desktop/Godot_v4.7.2-stable_win64_console.exe --headless --path . --script …`), sobre
`E:/areadetrabajo/wvp270/godot` (idéntico a este commit más los assets).

| Prueba | Qué cubre | Resultado |
|---|---|---|
| `tools/probar_shapekeys.gd` | mapa VRM, normalización, fusión con tintes, deformación de las 7 expresiones, pestañas, restauración exacta, idempotencia, guardado y códec | **32 OK, 0 fallos** |
| `tools/probar_selector.gd` | clic, arrastre que salta plazas, rueda, nick obligatorio, verde/rojo/ámbar, confirmación, claves guardadas, turno 4 | **26 OK, 0 fallos** |
| `tools/probar_turnos.gd` | reserva exclusiva y huecos | **0 fallos** |
| `tools/probar_carrusel.gd` | recorrido de las 24 plazas (AVH1…AVMJ12) | **0 fallos** |
| `tools/probar_carrusel_ocupado.gd` | carrusel con plazas ocupadas | **0 fallos** (con el árbol completo; en el snapshot sin assets fallaba por motivos ajenos al selector) |
| `tools/validar_shapekeys_reales.gd` | morfología real: 0 morph targets, 7 expresiones con desplazamiento ≥ 4 mm, sin deriva, restauración | **14 OK, 0 fallos** (AVH1.gltf) |
| `tools/validar_personalizacion.gd` | **24 avatares reales**: deformación, altura, idempotencia, vuelta al original | **24 avatares, 0 fallos** (2.156-16.421 vértices movidos; altura 1,706-1,805 m → 2,006-2,105 m) |
| `tools/validar_avatares.gd` | **24 avatares**: huesos, 5 clips, sin pistas huérfanas, `AnimationTree` activo y esqueleto en movimiento por sí solo | **24 avatares, 0 fallos** (33-46 huesos movidos según el esqueleto, de 65 a 168 huesos) |
| `tools/validar_ch3d.gd` | las **16 escenas** Ch3D remodeladas, dentro del árbol real | **16 escenas, 0 fallos** |

Autopruebas del visor ya compilado, con `WOLD_RUNTIME_DIR` apuntando a una carpeta temporal para no
tocar el runtime instalado:

| Prueba | Resultado |
|---|---|
| `--startup-selftest` | **RESULTADO ARRANQUE: OK** — recursos embebidos, extracción en `runtime270`, marcador `.extracted` = `2.7.0`, PCK extraído = embebido, portal escuchando, `/api/info` anuncia `DMWoldVirtualP2P3Dv2.7.0.exe`, baliza UDP 8912, recolector, y **motor arranca desde el PCK** (`exit=0 isla=True red=True errores=False`) |
| `--chat-selftest` | **fallos=0** (26 comprobaciones: amigos, relay, privados, audio, vídeo JPEG, proxy `/chat` con invitación) |
| `--cuenta-selftest` | **RESULTADO CUENTA: OK** (reset total, respaldo, estados globales) |
| `--red-selftest` | **RESULTADO RED: 7 líneas, 0 fallos** |

## Qué no se ha podido probar

- **Captura visual con ventana** del selector y del panel SHAPE KEYS: esta máquina no ha ejecutado la
  escena con renderizado. La deformación está medida numéricamente sobre malla real y el
  `AnimationTree` se comprueba por movimiento de huesos, pero **no hay PNG** del resultado ni
  comprobación de que el panel no tape el rótulo en cada resolución.
- **OTA de punta a punta**: la release ya está publicada, pero hace falta un equipo con la 2.6.9
  instalada para actualizar → relanzar → comprobar la re-extracción. No se ha hecho en esta sesión.
- **`probar_registro.gd`** sigue sin poder ejecutarse aquí: necesita `importblend/hm1.blend` y
  `avhm1_anim.glb` (ausentes) y hace `save_png` con textura nula. Es previo a este trabajo.
- **Linux**: el paquete se regenera con el motor 4.7.2 de Linux y el PCK nuevo, pero no se ejecuta
  aquí: esta máquina no tiene Linux. `woldvirtual-linux.sh --verificar` sí puede comprobar la huella.

## Checklist de §7

| Casilla | Estado |
|---|---|
| PCK fresco del árbol de este commit | **Sí** — 2026-10-29 18:01, 1.053.066.344 B, `verify_pck` íntegro |
| Versión sincronizada (csproj, tag, asset, `release.json`) | **Sí** — 2.7.0 / `v2.7.0` / `DMWoldVirtualP2P3Dv2.7.0.exe` |
| Compila con el .NET de E: (self-contained single-file) | **Sí** — 1.303.543.673 B |
| Cero binarios en el commit | **Sí** — `.exe`, `.pck` y `.tar.gz` quedan fuera de Git (`R17`) |
| Arranque limpio con `runtime\<versión>` y `.extracted` | **Sí** — `runtime270/.extracted` = `2.7.0`, sin `ERROR`/`EXCEPTION` en el log |
| El motor arranca desde el PCK | **Sí** — `isla=True red=True errores=False` |
| Portal anuncia la release vigente | **Sí** — `arranque-selftest.log` del exe publicado: `[OK] Portal WebNodo escucha — http://localhost:3030/` y `/api/info` → `{"disponible":true,"nombre":"DMWoldVirtualP2P3Dv2.7.0.exe","tamano_mb":"1243,2","url_descarga":"/descargar"}`, con `[UpdateChecker] Release vigente: v2.7.0 (DMWoldVirtualP2P3Dv2.7.0.exe)` |
| `/descargar` responde `200` con el tamaño del asset | **Pendiente** — la autoprueba cierra el portal en milisegundos (dos sondeos externos a 30-200 ms no lo alcanzaron) y en esta sesión no se ha abierto la ventana del visor, que es la que lo mantiene vivo. El asset de GitHub sí responde `200` con `Content-Length` 1.303.543.673 |
| OTA de punta a punta | **Pendiente** — requiere un equipo con la 2.6.9 instalada y relanzar; no se acredita sin esa prueba (`R13`) |
| Metadatos por API (`gh api`) | **Sí** — `digest` de los cuatro assets coincide con el SHA-256 local (ver tabla siguiente) |
| Docs en el mismo commit | **Sí** (`R18`) |

## Release v2.7.0 publicada (2026-10-29)

Tag `v2.7.0` sobre `5f75f6f` de `main`, marcada como *Latest*. Verificado con
`gh api repos/Chicook/WoldVirtualP2P3D/releases/tags/v2.7.0` (`R15`) contra el SHA-256 local:

| Asset | Bytes | `digest` de la API (= SHA-256 local) |
|---|---|---|
| `DMWoldVirtualP2P3Dv2.7.0.exe` | 1.303.543.673 | `ceea0886904017d68b99811e75d21deb8225d12667c48f9187fb529d1318b59a` |
| `WoldVirtualP2P3Dv2.7.0-linux.tar.gz` | 1.078.177.695 | `913552a72718257c78f9b05f10e66038acf86c0f1b616f01f56edc4bf7902938` |
| `release.json` | 223 | `e72f489a8b594288db2e1bbe8d6a8e5116217b3137d4693309020d77266da02b` |
| `SHA256SUMS` | 273 | `c35e4053377dd80a488e71d846a3576837a1522319fa80d51e452aa3356e1d42` |

`release.json` declara `version 2.7.0`, `tag v2.7.0`, `exe DMWoldVirtualP2P3Dv2.7.0.exe`,
`size_mb 1243.2`. Las cuatro URLs de descarga responden `200` con su `Content-Length` exacto.
