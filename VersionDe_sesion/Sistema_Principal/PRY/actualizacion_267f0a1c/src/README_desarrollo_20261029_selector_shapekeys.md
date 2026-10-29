# Desarrollo selector de avatares y shape keys por código

Trabajo sobre el árbol del 2026-10-29
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c`), rama `DevQoderIA`.

**Estado: Implementado en fuentes, sin publicar.** Los `.gd`, escenas y pruebas están en el árbol y
pasan la suite headless, pero **el `wvp3d.pck` y el `.exe` no se han regenerado**: eso lo hace el
sistema de comandos del responsable desde este mismo árbol (`REGLAS_DE_ACTUALIZACION.md` §1 y §7).
Mientras no se exporte un PCK nuevo, el visor y la release v2.6.9 siguen mostrando el carrusel
anterior; no hay cambio visible para el usuario final.

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
**no se ha tocado** (la UI nueva se construye por código, así que el export del PCK no cambia rutas).

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

## Pruebas ejecutadas (evidencia)

Todas con `APPDATA` aislado en un directorio temporal, Godot 4.7.2
(`C:/Users/User/Desktop/Godot_v4.7.2-stable_win64_console.exe --headless --path . --script …`),
sobre `actualizacion_267f0a1c/src/MTBGT/WoldVirtualP2P3D`.

| Prueba | Qué cubre | Resultado |
|---|---|---|
| `tools/probar_shapekeys.gd` | mapa VRM, normalización, fusión con tintes, deformación de las 7 expresiones, pestañas, restauración exacta, idempotencia, guardado y códec | **32 OK, 0 fallos** |
| `tools/probar_selector.gd` | clic, arrastre que salta plazas, rueda, nick obligatorio, verde/rojo/ámbar, confirmación, claves guardadas, turno 4 | **26 OK, 0 fallos** |
| `tools/probar_turnos.gd` | reserva exclusiva y huecos | **0 fallos** |
| `tools/probar_carrusel_ocupado.gd` | carrusel con plazas ocupadas | **2 fallos**, ambos por falta de assets en este snapshot: «turno 1 monta 8 avatares» y «tres etiquetas OCUPADO» |
| `tools/validar_shapekeys_reales.gd` | morfología real: 0 morph targets, 7 expresiones con desplazamiento ≥ 4 mm, sin deriva, restauración | **14 OK, 0 fallos** (AVH1.gltf) |
| `tools/validar_personalizacion.gd` | 24 avatares reales: deformación, altura, idempotencia, vuelta al original | **8 avatares con assets, 0 fallos** (4.499-4.870 vértices movidos, altura 1.76-1.80 m → 2.06-2.10 m); los otros **16 fallan por «sin malla de cuerpo»** (assets ausentes en el snapshot) |

La medición real se hizo en una **copia temporal fuera del repositorio**
(`E:/areadetrabajo/wvp_shapekeys_real`: proyecto de 1,2 MB + `gltfimport/avatares` de
`actualizacion_022321c8`, 222 MB) para no tocar ni el snapshot del responsable ni
`E:/areadetrabajo/AVATARESCONANIMACION`. Esa copia no se versiona y sigue en disco.

`tools/probar_carrusel_ocupado.gd` se ajustó para escribir un nick antes de confirmar, porque la
confirmación ahora exige nick válido; sin ese ajuste la comprobación de hueco libre fallaba por
motivo equivocado.

## Qué no se ha podido probar

- **Captura visual con ventana** del selector nuevo: esta máquina no ha ejecutado la escena con
  renderizado. La deformación está medida numéricamente sobre malla real, pero **no hay PNG** del
  resultado ni comprobación de que el panel SHAPE KEYS no tape el rótulo en cada resolución.
- **PCK y `.exe`**: sin regenerar. El carrusel nuevo no está en ningún binario publicado. El motivo
  no es de código sino de assets: ver «Bloqueo del PCK» abajo.
- **Avatares 5-12** de cada género: sus mallas no están en el snapshot de fuentes, así que
  `validar_personalizacion` sólo valida 8 de 24.
- **`probar_registro.gd`** sigue sin poder ejecutarse aquí: necesita `importblend/hm1.blend` y
  `avhm1_anim.glb` (ausentes) y hace `save_png` con textura nula. Es previo a este trabajo.
- **Linux**: el paquete de `STM_LBR` no se ha vuelto a generar; sigue el de la 2.6.9.

## Bloqueo del PCK: faltan las mallas del catálogo

Para publicar `DMWoldVirtualP2P3Dv2.7.0.exe` hace falta un `wvp3d.pck` exportado de un árbol que
tenga **el código nuevo y los 24 avatares**. Este árbol tiene el código, pero no los assets:
inventariadas todas las referencias `res://` de `.tscn`, `.tres`, `.gd`, `.gdshader`, `.cfg` y
`project.godot`, salen **153 rutas distintas, 80 presentes y 73 ausentes**.

| Extensión ausente | Ficheros | Qué es |
|---|---|---|
| `.glb` | 32 | 16 `avhm1-9.glb` / `AVmj1-7.glb` y sus 16 `*_anim.glb` (avatares 5-12 de cada género) |
| `.png` | 21 | texturas de `gltfimport/avatares/av_texturas` de AVH1-4 / AVMJ1-4 |
| `.gltf` | 9 | AVH1-4, AVMJ1-4 y `ISLA3DCHUNK.gltf` |
| `.tscn` | 4 | `AreaDeTrabajo/SCNCNSTR/av3DT1.tscn`, `av3DT2.tscn` y dos rutas de directorio |
| `.blend`, `.json`, sin extensión | 7 | `importblend/hm1.blend`, el JSON de export y rutas internas de `.godot/` |

Los `.gltf` y las texturas **sí** están en `actualizacion_022321c8` (9 `.gltf`, 39 `.png` en
`av_texturas`), y con ellos se validaron las expresiones sobre malla real. Lo que no existe en esta
máquina es ningún `.glb` del catálogo: se buscó `*_anim.glb` en todo `E:`, en `F:` y en las carpetas
del usuario, y el único resultado es `C:\Users\User\AppData\Local\Temp\prubaimp\avhm9_anim.glb`,
resto de una prueba de importación. Los otros 15 animados y los 16 sin animar no están.

Sin esos 16 `*_anim.glb` el árbol no exporta un mundo completo: las escenas `AVH5-12`/`AVMJ5-12`
(`…Ch3D.tscn`) apuntan a ellos y el carrusel dejaría 16 de las 24 plazas rotas. Por eso **no se ha
exportado PCK, no se ha tocado `src/VSC#/wvp3d.pck` (537.836.524 B, 2026-10-28 14:55, el mundo de la
2.6.9) y no se ha abierto la release 2.7.0**. Sustituir el PCK por otro sin esos assets o publicar la
2.7.0 con el PCK viejo incumpliría §8 (mismo código para otro mundo) y el resultado se vería peor
que la 2.6.9.

Para desbloquearlo basta una de estas dos cosas: que el sistema de comandos del responsable exporte
el PCK desde el árbol completo (y este trabajo sigue con el bump a 2.7.0, la compilación, el paquete
Linux y la publicación), o que se indique la ruta del árbol que sí tiene los `.glb` para exportar
desde una copia, sin tocar el original.

## Checklist de §7

Ninguna casilla de publicación se puede marcar todavía: falta exportar el PCK de este árbol,
versionar (`R2`), compilar, publicar y hacer el OTA. Lo único cumplido es que el trabajo no mete
binarios en el commit (`R17`) y que esta documentación va en el mismo commit que el cambio (`R18`).
