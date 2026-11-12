# LucIA 3D — módulo de personaje (fase 1)

Estado: **~90 %** del módulo 3D (2026-11-07). Seguimiento con fotos en
[`ISSUE_LUCIA_3D.md`](ISSUE_LUCIA_3D.md) y en el issue público
<https://github.com/Chicook/WoldVirtualP2P3D/issues/16>.

Fecha de cierre de la fase de texto: **2026-10-25**. Rigging, animación,
puesto de trabajo y chat holográfico: **2026-11-07** (secciones 5.1–5.3).

LucIA es un personaje 3D en Godot que recibe consultas escritas, consulta un modelo local
servido por Ollama y responde con texto y voz. El texto pasa por el núcleo neuronal del
proyecto (PSN de 50 neuronas + RPLC) y la boca del personaje se anima mientras habla.
Todo el transporte entre Godot y Python es un socket TCP local con líneas JSON.

> Estado honesto: la generación del cuerpo del texto la sigue haciendo qwen2.5. El núcleo
> neuronal condiciona el prompt, actualiza sus pesos, reformula la forma de la respuesta y
> aporta métricas reales; todavía no es una red generativa entrenada que produzca tokens
> por sí sola.

---

## 1. Qué funciona hoy

- Interfaz Godot con cámara, iluminación, barra de entrada y estado; el texto de
  la conversación aparece en un **holograma 3D** junto al personaje (ya no hay
  panel de chat grande).
- Servidor Python que elige un modelo de Ollama, lo precarga en VRAM y atiende por socket.
- Núcleo neuronal adaptado del proyecto principal:
  - Conversor PSN de 50 neuronas (5 capas × 10: ENRN, RF_EN, RF_SL, RNP, SLRN).
  - RPLC: vectorización, modulación hebbiana y reformulación a la voz de LucIA.
  - Memoria de sesión persistente y rúbrica de calidad.
  - Pesos persistentes en `STM_CH/PSNRL/psnrl_lucia.npz`.
- Voz por socket: gTTS + DSP (1.16×) con respaldo Windows OneCore si gTTS falla.
- Personaje con **rig real**: `LucIA_rig.glb` lleva el esqueleto Mixamo de 65
  huesos, un skin con pesos normalizados y el morph `BOCA` conservado.
- Animación procedural sobre ese rig: IDLE con respiración y balanceo, gestos
  de brazos/cabeza al hablar, parpadeo y lipsync, todo escrito por un único
  script (sin AnimationPlayers peleando por las mismas pistas).
- **Puesto de trabajo**: silla en el despacho, `sentarse()`/`levantarse()` y un
  ciclo de marcha; el escritorio está delante con el monitor mirándola.
- Reconexión automática del cliente cada 2 s si se cae el servidor.

---

## 2. Cómo ejecutarlo

Requisitos:

- Godot 4.7.2 (probado con la build mono en Windows, D3D12).
- Python 3.14 con: `numpy`, `soundfile`, `scipy`, `pedalboard`, `gTTS`, `comtypes`.
- Ollama en `http://127.0.0.1:11434` con al menos un modelo de chat.
- Modelo usado en las pruebas: `qwen2.5:7b` (~4.6 GB de VRAM). Para menos VRAM:
  `ollama pull qwen2.5:3b` (el servidor lo prefiere si está instalado).

Servidor:

```bash
cd E:/LcshLucIA/GLTF_lucIA/celebro_3D/puente_3D
python -u servidor_lucia.py
```

Opciones:

```bash
python servidor_lucia.py --modelo qwen2.5:3b
python servidor_lucia.py --puerto 8765 --host 127.0.0.1
python servidor_lucia.py --sin-voz
python servidor_lucia.py --sin-precalentar
```

Cliente:

1. Abrir `E:/LcshLucIA/project.godot` con Godot 4.7.2.
2. Ejecutar el proyecto; la escena principal es
   `res://GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn`.
3. Esperar el estado `En línea con LucIA · qwen2.5:7b`, escribir y pulsar Enter.

---

## 3. Arquitectura

```text
┌──────────────────────────── Godot 4.7 ────────────────────────────┐
│ LucIA_Interfaz.tscn                                               │
│  ├─ LucIAbsIA.tscn        rig Mixamo (65 huesos) + morph BOCA     │
│  ├─ AudioStreamPlayer     reproduce PCM16 recibido por socket     │
│  ├─ Holograma (3D)        SubViewport -> Sprite3D billboard       │
│  └─ lucia_cliente.gd      barra de entrada, typewriter, boca,     │
│                           voz, holograma, reconexión             │
└───────────────────────────────┬───────────────────────────────────┘
                                │ TCP 127.0.0.1:8765 · NDJSON UTF-8
┌───────────────────────────────▼───────────────────────────────────┐
│ puente_3D/servidor_lucia.py                                       │
│  ├─ elige/precalienta modelo en Ollama                            │
│  ├─ prepara estado neuronal y enriquece el prompt                 │
│  ├─ acumula la respuesta del modelo                               │
│  ├─ reprocesa con RPLC y registra memoria/calidad                 │
│  └─ sintetiza voz y envía texto final + métricas                  │
└───────────────────────────────┬───────────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────────┐
│ nucleo/orquestador_lucia.py                                       │
│  ├─ ConversorPSNLucia  (50 neuronas, checkpoint NPZ)              │
│  ├─ RPLC               (analizador + transformador + reformulador)│
│  ├─ MemoriaSesion      (JSON por sesión)                          │
│  └─ rubrica.evaluar_calidad                                       │
└───────────────────────────────┬───────────────────────────────────┘
                                │ HTTP local
                         Ollama /api/chat
                         qwen2.5:7b (stream interno)
```

### Flujo de un turno

1. Godot envía `{"tipo":"consulta","texto":"..."}`.
2. El servidor responde `estado: pensando`.
3. `NucleoLucia.preparar_turno()` vectoriza la consulta, actualiza las 50 sinapsis y guarda
   el checkpoint.
4. El prompt a Ollama incluye el sistema, el estado neuronal (tono, valencia, delta, deriva)
   y la memoria de la sesión.
5. Ollama genera en streaming, pero el servidor **no** reenvía los tokens parciales: espera
   la respuesta completa.
6. RPLC reprocesa la respuesta, se elimina el pie de métricas y se registra el turno.
7. Se envía un único `token` con el texto final, luego `estado: sintetizando`, luego `voz` y
   finalmente `fin` con `nucleo` y `metricas`.
8. Godot vuelca el texto pendiente al empezar el audio, anima la boca y cierra el turno al
   terminar la voz.

---

## 4. Protocolo del socket

Entrada (Godot → Python):

| Tipo      | Campos             | Uso                          |
|-----------|--------------------|------------------------------|
| `consulta`| `texto`            | Pregunta del usuario         |
| `ping`    | —                  | Comprobación de vida         |

Salida (Python → Godot):

| Tipo     | Campos                                                                 | Notas |
|----------|------------------------------------------------------------------------|-------|
| `hola`   | `protocolo`, `modelo`                                                  | Al conectar |
| `estado` | `estado`: `pensando` \| `sintetizando`                                  | Fase actual |
| `token`  | `texto`                                                                | **Texto final completo**, no incremental |
| `voz`    | `pcm` (base64), `rate`, `canales`, `duracion`, `backend`, `ms`          | PCM16 |
| `aviso`  | `mensaje`                                                              | Voz no disponible, etc. |
| `fin`    | `texto`, `modelo`, `ms`, `nucleo`, `metricas`                           | Cierre del turno |
| `error`  | `mensaje`                                                              | Error controlado |
| `pong`   | —                                                                      | Respuesta a ping |

`nucleo` contiene: `neuronas`, `deriva`, `turno`, `tono`, `valencia`, `activas`.
`metricas` contiene además: `tono`, `valencia_sinaptica`, `densidad_semantica`,
`neuronas_activas`, `deriva_media`, `tiempo_rplc_ms`, `repeticion_detectada`,
`calidad`, `voz_ajena_detectada`.

---

## 5. Estructura relevante

```text
E:/LcshLucIA/
├─ project.godot
├─ _herramientas/
│  ├─ rig_lucia.py                  rigging headless en Blender (genera LucIA_rig.glb)
│  ├─ validar_rig.gd                comprueba huesos, skin, morphs y clips del GLB
│  ├─ render_pruebas.gd             capturas de reposo, gestos, boca y giro de cabeza
│  └─ comparar.py                   hoja de contactos antes/después
├─ _pruebas/                        capturas de verificación (antes/, despues/, comparacion.png)
├─ GLTF_lucIA/
│  ├─ AreaDeTrabajo/Constructor3D_IA/
│  │  ├─ LucIA_Interfaz.tscn        escena principal
│  │  ├─ LucIAbsIA.tscn             personaje (instancia LucIA_rig.glb)
│  │  └─ gdscrip/
│  │     ├─ lucia_cliente.gd        cliente Godot (UI, socket, voz, boca)
│  │     ├─ lucia_personaje.gd      capa de animación sobre el rig
│  │     └─ lucia_oficina.gd        oficina construida por código
│  ├─ AreaDeTrabajo/LucIA3D/
│  │  ├─ LucIA.glb                  malla original sin rig (referencia)
│  │  ├─ LucIA_rig.glb              malla + skin Mixamo + morph BOCA + clips
│  │  └─ esqueleto.glb              esqueleto Mixamo de origen
│  └─ celebro_3D/
│     ├─ puente_3D/
│     │  ├─ servidor_lucia.py       servidor TCP + Ollama + núcleo
│     │  └─ voz_lucia.py            síntesis y PCM16
│     ├─ nucleo/
│     │  └─ orquestador_lucia.py    adaptador PSN + RPLC + memoria
│     ├─ STM_BKCH/
│     │  └─ compat_local.py         conversor PSN copiado del proyecto principal
│     ├─ STM_CH/
│     │  ├─ rutas.py                rutas runtime adaptadas
│     │  └─ PSNRL/                  pesos y memoria generados al ejecutar
│     ├─ sub_sistemas/
│     │  ├─ RPLC.py                 reformulador lingüístico-cognitivo
│     │  ├─ memoria_sesion.py       memoria persistente por sesión
│     │  ├─ rubrica.py              evaluación de calidad
│     │  └─ voice_helpers.py        gTTS + DSP + OneCore
│     ├─ Sistema_de_arranque_y_sincronizacuin3D/
│     │  └─ mainLCSTM.py            orquestador original (no ejecutable aquí)
│     └─ IA_local_de_referencia/     material de referencia, no se ejecuta
```

Origen de piezas clave:

- `STM_BKCH/compat_local.py` se copió desde
  `E:/WoldVirtualP2P3D/VersionDe_sesion/Sistema_Principal/PRY/actualizacion_f7bfd9ba/src/STM_BKCH/compat_local.py`.
- `RPLC.py`, `memoria_sesion.py` y `rubrica.py` son copias locales del subsistema del
  proyecto principal; `RPLC.py` recibió una corrección (ver deuda técnica).
- `mainLCSTM.py` no se ejecuta en este borrador porque depende de paquetes `SBSTM`,
  `STM_BKCH.BKSVCB`, `STM_IA` y `STM_CH` completos que aquí no existen. El adaptador
  `nucleo/orquestador_lucia.py` integra solo el subconjunto necesario.
- `LucIA_rig.glb` se generó con `_herramientas/rig_lucia.py` a partir de
  `LucIA3D.blend` + `esqueleto.glb`; el proceso está documentado en la sección 5.1.

### 5.1 Rigging y animación (nov-2026)

El modelo original (`LucIA.glb`) es **una sola malla fusionada de 73k vértices,
sin esqueleto**. El módulo anterior se fabricaba en GDScript un rig de 10 huesos y
calculaba los pesos por distancia con radios; el resultado visible era:

- hombros que se inflaban y axila rota al bajar los brazos,
- la manga no seguía al brazo (pesaba al torso/clavícula),
- el cuello y el cuello de la chaqueta se estiraban al girar la cabeza,
- la cavidad de la boca era una caja flotante mal colocada.

Ahora el rig se hornea una vez en Blender (`_herramientas/rig_lucia.py`):

1. Normaliza la malla a 1,75 m con los pies en `z=0` y conserva la shape key `BOCA`.
2. Importa el esqueleto Mixamo y **corrige las longitudes de hueso**: el
   importador glTF las deja ~100× más largas (Hips 9,13 m en vez de 9 cm). Con
   esas longitudes el *bone heat* degenera y la cadera acaba dominando la cabeza.
3. Padres con pesos automáticos, normaliza a 1,0 y exporta GLB con skin,
   morphs y el clip Mixamo (en Blender 5 hay que asignar el *slot* de la acción
   o la animación no se exporta).

Comprobación: `_herramientas/validar_rig.gd` imprime árbol, huesos, skin y clips;
el rig actual tiene 65 huesos, 1 skin, morph `BOCA` y pesos que suman 1,0.

La animación del día a día **no** usa AnimationPlayer: `lucia_personaje.gd` escribe
las rotaciones de 14 huesos por frame. Las rotaciones se piden en ejes del mundo y
se convierten con `pose = rest_local · (R_global⁻¹ · Q · R_global)`; así el código
no depende de la orientación interna de cada hueso Mixamo. IDLE, gestos y parpadeo
se suman como cuaterniones con envolventes suaves (`GESTO_ATAQUE`/`GESTO_RELEASE`),
de modo que empezar/terminar de hablar no produce saltos.

El lipsync mueve el morph `BOCA`. Las UVs de la boca se **remapean al arte de
labios que ya trae el atlas** (antes apuntaban a zonas blancas), así que la boca
tiene color y dibujo reales sin shader ni parche. El óvalo oscuro que hacía de
interior se eliminó: con los labios pintados y el morph abriéndolos ya no hace
falta.

> Estado: **parcial**. El arte de labios es el del atlas, no propio; las
> constantes del remapeo (`0.4938, 0.5572` y escalas `0.66/0.56`) son
> específicas de este atlas; si se re-exporta la textura hay que revisarlas, y
> queda un pequeño artefacto en la comisura derecha.

Dos correcciones de arranque (nov-2026):

- El primer frame ya sale con la pose aplicada. Antes, mientras D3D12 compilaba
  shaders, se veía la T-pose y parecía que "subía los brazos".
- La boca ya no se queda muda: mientras se sintetiza la voz (o si la voz falla)
  se mueve con una envolvente sintética, y en reposo tiene una micro-apertura
  lenta. Antes el cliente forzaba cerrarla durante `_voz_preparando`, que era
  justo el momento en que se veía gesticular con los labios quietos.

### 5.2 Cuerpo: andar y silla (nov-2026)

El rig tiene piernas, así que el módulo también las anima (todavía sin clips de
Mixamo: es procedural, con las limitaciones que eso tiene).

- **Silla** en `lucia_oficina.gd`, con el asiento a 0,45 m y el respaldo a la
  altura de la cadera sentada.
- **Escritorio delante de ella**, con el monitor mirándola (a su derecha, en el
  extremo del tablero): parece una videollamada desde su puesto. Sentada gira
  la cabeza 0,32 rad hacia la pantalla y, al hablar, vuelve en buena parte
  hacia la cámara.
- **`sentarse()` / `levantarse()`**: cruce suave de 0,85 s; la cadera baja
  0,42 m, los muslos quedan horizontales, las espinillas verticales y los dedos
  de los pies apoyados en el suelo (medido: 0,005 m).
- **`caminar_adelante(m)` / `volver()`**: ciclo de marcha con muslos ±0,42 rad,
  rodilla que se dobla al recoger el pie, balanceo de brazos y bob de cadera.
  El punto más bajo del pie queda a −2 mm del suelo (sin hundirse).
- **Atajos** en el cliente: `F1` sentarse/levantarse, `F2` andar 0,8 m,
  `F3` volver. No chocan con el campo de texto.
- El panel del chat baja a alpha 0,62 para que se vean las piernas y la silla.

Capturas: `_pruebas/silla/` (`ui_02_sentada.png`, `04_andando_a.png`,
`03_sentada_perfil.png`).

### 5.3 Chat en el espacio 3D (nov-2026)

El panel grande de chat ya no existe: `Salida` queda invisible y el
`PanelContainer` se encoge a una barra de entrada en la parte inferior.
El texto del turno aparece en un **holograma 3D** al lado de LucIA:

- `SubViewport` (440×330, fondo transparente) con un `RichTextLabel` y una
  tarjeta translúcida redondeada.
- `Sprite3D` con `viewport.get_texture()`, `billboard` activado y
  `pixel_size` 0,0028 (≈1,23 × 0,92 m), anclado al personaje para que le
  acompañe al andar o sentarse.
- Muestra solo el turno actual: `Tú:` en azul y `LucIA:` en dorado, con el
  mismo efecto de máquina de escribir que el log oculto. Se desvanece cuando
  no hay texto y la cámara se desplaza 0,30 m para dejarle sitio.

Capturas: `_pruebas/holograma/03_completo.png`.


---

## 6. Pruebas realizadas

Hardware de referencia: Intel Arc A750, qwen2.5:7b en GPU.

| Prueba | Resultado |
|--------|-----------|
| Dos turnos headless en Godot | Audio 12.99 s y 10.84 s; estado con `50 sinapsis · deriva` |
| Consulta directa por socket | Texto en 0.88 s; voz 13.03 s generada en 1.04 s; total 1923 ms |
| Cuatro turnos manuales | Generación 1.8–8.2 s; calidad 0.68–0.76; voz 22.8–41 s |
| Persistencia de pesos | Deriva pasó de `0.000000` a `0.000140`; checkpoint NPZ creado |
| Bug de repetición RPLC | Corregido: ahora devuelve `False` en el primer texto nuevo |
| Voz de respaldo | OneCore probado cuando gTTS no está disponible |
| Rig Mixamo horneado | 65 huesos, 1 skin, morph `BOCA`; pesos normalizados a 1,0; 61 167 vértices con peso |
| Pruebas visuales del rig | 10 capturas en `_pruebas/despues/` y hoja `_pruebas/comparacion.png` |
| Integración con la UI | Turno falso por socket: `hola` → `token` → `voz` → `fin` sin errores de script |
| Turno real (2026-11-07) | qwen2.5:7b: texto en 4,6 s; voz 20,7 s; boca máx 1,0; cierre con deriva 0,0042 |
| Boca sin audio | Durante la síntesis: 0,11–0,65 (antes se quedaba cerrada) |
| Arranque | Primer frame con pose aplicada: mano y 0,99 (antes T-pose) |
| Silla y marcha | Dedo del pie mínimo −2 mm al andar; sentada 0,003–0,005 m |
| Holograma 3D | Tarjeta `SubViewport` 440×330 visible con 189 caracteres y alfa 1,0 |
| Copia E: | `lucia_personaje.gd`, `lucia_cliente.gd`, escena y GLB con hash idéntico al workspace |

Las pruebas se hicieron con scripts temporales. Los que quedan viven en `_herramientas/`
y son reproducibles: `validar_rig.gd`, `render_pruebas.gd` y `comparar.py`. No hay
suite automatizada ni CI; eso sigue en la deuda técnica.

---

## 7. Criterios de honestidad

- El cuerpo textual lo genera el LLM local. RPLC aporta apertura/conector propios,
  transformación y métricas; no genera el contenido desde cero.
- Las 50 neuronas son el conversor del proyecto (proyección hash/espectral + actualización
  de pesos), no un transformer entrenado.
- Las métricas que se muestran son calculadas por el código, no decorativas.
- La persistencia es verificable en `STM_CH/PSNRL/`; si se borra, la deriva vuelve a cero.
- No se afirma que la blockchain esté integrada: no lo está.

---

## 8. Deuda técnica

Prioridad: **A** = bloquea uso o calidad, **M** = afecta mantenimiento/experiencia,
**B** = mejora deseable.

> El backlog específico del módulo 3D (14 deudas priorizadas, 27 tareas y la
> definición de terminado 90 % → 100 %) está en el issue público
> <https://github.com/Chicook/WoldVirtualP2P3D/issues/16> y en
> [`ISSUE_LUCIA_3D.md`](ISSUE_LUCIA_3D.md).

| # | Deuda | Origen | Prioridad |
|---|-------|--------|-----------|
| 1 | El contenido sigue saliendo del LLM; no hay pesos generativos propios ni entrenamiento | Heredada | A |
| 2 | `mainLCSTM.py` no es ejecutable: faltan `SBSTM`, `STM_BKCH.BKSVCB`, `STM_IA` y `STM_CH` completos | Heredada | A |
| 3 | Blockchain, transacciones sinápticas, minado e IPFS no integrados | Heredada | A |
| 4 | El conversor PSN es un shim sintético (hash + ortogonalización); el tono se elige por hash, no por semántica | Heredada | A |
| 5 | RPLC repite preámbulos (“50 sinapsis procesadas”) y alarga la voz: 22–41 s en respuestas normales | Adaptación | M |
| 6 | El preámbulo de RPLC también se sintetiza; no hay opción de mostrarlo solo en texto | Adaptación | M |
| 7 | Se cambió `token` de incremental a texto final sin subir la versión del protocolo (sigue en 1); clientes externos se rompen | Introducida | M |
| 8 | `compat_local.py` se copió a mano: no hay sincronización con el proyecto principal y puede divergir | Introducida | M |
| 9 | Se modificó `RPLC.py` local (fix de repetición); hay que propagar el fix al proyecto principal | Introducida | M |
| 10 | `nucleo/orquestador_lucia.py` duplica parte de la lógica de `mainLCSTM.py`; dos orquestadores que pueden separarse | Introducida | M |
| 11 | Memoria por sesión: cada arranque crea una sesión nueva y no hay selector ni política de limpieza de JSON/NPZ | Heredada/adaptada | M |
| 12 | Sin pruebas automatizadas ni CI; solo pruebas manuales y scripts temporales | Introducida | M |
| 13 | Voz bloqueante y sin cancelación ni barge-in: no se puede interrumpir a LucIA; gTTS depende de red | Heredada | M |
| 14 | Respuestas demasiado largas: `num_predict=180` no garantiza 2–4 frases; no hay presupuesto por frase | Adaptación | M |
| 15 | Sin entrada por micrófono/VAD; solo texto (aunque exista `escucha.py` sin integrar) | Heredada | B |
| 16 | Solo un cliente y sin autenticación; aceptable en localhost, no para red | Heredada | B |
| 17 | Si el núcleo falla, el servidor termina; no hay modo degradado explícito | Introducida | B |
| 18 | `fin` envía `nucleo` y `metricas` con datos solapados; el payload puede simplificarse | Introducida | B |
| 19 | Listas de preferencia de modelos duplicadas entre `servidor_lucia.py` e `IALOCAL/gestor.py` | Heredada | B |
| 20 | Logs de consola con mojibake en Windows para algunos acentos (el socket UTF-8 está bien); no hay log a archivo | Heredada | B |
| 21 | Animación resuelta en parte: rig real, gestos y parpadeo procedurales. Sigue sin sincronía fonema-audio y sin morphs de párpados (el parpadeo es un cabeceo) | Heredada | B |
| 22 | Las capturas de prueba ya no están en la raíz: viven en `_pruebas/` con `.gdignore` | Introducida | B |
| 23 | `voz_lucia.py` depende de una copia de `voice_helpers.py`; no hay paquete de voz común con el proyecto principal | Heredada | B |
| 24 | Labios: **parcialmente resuelto** — UVs de la boca remapeadas al arte del atlas y óvalo eliminado. Pendiente: arte propio, constantes UV robustas y comisura derecha | Introducida | M |
| 25 | El clip `mixamo_com` de prueba tiene *root motion* (el personaje se sale de cámara); no sirve como idle. Falta un pack Idle/Talking de Mixamo | Introducida | M |
| 26 | `lucia_personaje.gd` no reproduce clips: toda la animación es procedural. Falta un AnimationTree con estados IDLE/HABLAR cuando haya clips buenos | Introducida | B |
| 27 | El proyecto vive en dos copias (`C:\Users\User\Desktop\LcshLucIA` y `E:\LcshLucIA`); hay que sincronizarlas a mano al cambiar código | Introducida | M |
| 28 | El holograma 3D muestra solo el turno actual; el historial completo queda en el `RichTextLabel` oculto | Introducida | B |
| 29 | Marcha y sentada procedurales: la falda de la chaqueta se arruga en la cadera al sentarse (AI-mesh fusionado) | Introducida | M |

---

## 9. Próximos pasos sugeridos

1. Decidir el objetivo real de la fase 2: ¿LucIA debe sonar con la voz de RPLC aunque el
   audio sea largo, o priorizar brevedad y dejar RPLC solo como capa de estado?
2. Reducir la locución: limitar a 2 frases, ocultar el preámbulo en voz y medir latencia
   (hoy el preámbulo ocupa media tarjeta del holograma).
3. Integrar el resto del orquestador (BKSVCB/PSNRL) o declarar formalmente que esta fase
   usa solo el subconjunto PSN + RPLC.
4. Añadir una suite mínima de pruebas del protocolo y del núcleo, sin depender de Godot.
5. Sincronizar `compat_local.py` y el fix de RPLC con el proyecto principal, o convertir las
   copias en un paquete compartido.
6. Subir la versión del protocolo a 2 y documentar el cambio de `token` incremental a final.
7. Bajar un pack Idle/Walk/Sit/Talking de Mixamo, importarlo y montar un AnimationTree con
   estados, para alternar clips reales con los gestos procedurales.
8. Arte propio de labios (el remapeo al atlas ya está): textura dedicada o
   material aparte, y limpiar la comisura derecha.
9. Decidir una sola copia canónica del proyecto (o automatizar el sync C: ↔ E:) para
   no volver a editar la equivocada.

---

## 10. Comandos útiles

```bash
# Servidor
cd E:/LcshLucIA/GLTF_lucIA/celebro_3D/puente_3D
python -u servidor_lucia.py

# Ver quién escucha en el puerto
netstat -ano | grep ":8765"

# Ver checkpoints y memoria generados
ls E:/LcshLucIA/GLTF_lucIA/celebro_3D/STM_CH/PSNRL

# Abrir el cliente desde consola con Godot
"C:/Users/User/Desktop/Godot_v4.7.2-stable_win64.exe" --path "E:/LcshLucIA"

# Regenerar el rig (Blender headless). Tarda ~1-2 min: corrige longitudes de
# hueso, pesa la malla, normaliza y exporta LucIA_rig.glb.
blender --background --python _herramientas/rig_lucia.py

# Validar el GLB resultante (huesos, skin, morphs, clips)
godot --headless --path . --script res://_herramientas/validar_rig.gd \
      -- res://GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb

# Capturas de reposo, gestos, boca y giro de cabeza
godot --path . --script res://_herramientas/render_pruebas.gd

# Hoja de contactos antes/después
python _herramientas/comparar.py
```
