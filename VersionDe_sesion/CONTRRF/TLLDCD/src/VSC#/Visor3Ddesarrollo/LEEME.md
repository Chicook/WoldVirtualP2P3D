# Reconstrucción de avatares · Wold Virtual 3D

Fecha: 2026-11-11. Esta carpeta queda como punto de trabajo del visor. El
sistema de avatares se ha rehecho **dentro del proyecto Godot**, que es el que
dibuja el mundo; el C# no necesitó cambios para los avatares.

## Qué se ha rehecho

Módulo nuevo en `MTBGT/WoldVirtualP2P3D/avatares/`:

- `CatalogoAvatares.gd`: los 8 avatares (`AVH1-4`, `AVMJ1-4`) con id, nombre,
  género y rutas.
- `AvatarJugador.gd`: normaliza la altura a 1,80 m, crea cápsula y cámara,
  mueve con WASD/flechas y reproduce las 5 animaciones originales.
- `CarruselAvatares.tscn/.gd`: selector 3D con ratón, rueda, flechas, clic y
  ENTER.
- `GestorAvatares.gd`: autoload `Avatares`; guarda la elección.
- `AVH1.tscn` … `AVMJ4.tscn`: ocho escenas mínimas (script + glTF).
- `EditorAspecto.tscn/.gd`: segunda validación. Editor 3D del aspecto con
  tintes por prenda, proporciones, cara y expresiones. Guarda en
  `registro.cfg` (`[personalizacion]`) y `ChunkManager` lo aplica al entrar.

## Nuevo flujo del visor C#

El código fuente C# se restauró en esta misma carpeta y compila
(`dotnet build`, 0 errores). Cambios de experiencia:

- Al arrancar, el visor entra **directamente en la oficina de LucIA**
  (`MainWindow.OnLoaded` → `AbrirOficinaLucia`). El registro nuevo, la
  recepción y la conexión viven allí.
- El C# arranca también el **cerebro de LucIA** en el puerto 8765
  (`Services/ServidorLucIAOficial.cs`) al iniciar el visor.
- La barra superior ya **no muestra el enlace de invitación**. Quedan WebNodo,
  Chat y los accesos a la oficina.
- Nuevos botones: **«Oficina con avatar»** (escribe
  `abrir_oficina_avatar.flag` y abre la oficina con tu avatar) e
  **«Invitar a LucIA»** (escribe `invitar_lucia.flag`; Godot la lleva a tu isla).
- En la oficina, el botón **CONECTAR** escribe `tunel_solicitud.json` con
  `accion: "conectar"`. El C# arranca el túnel P2P y responde en
  `validacion_resultado.json`; la oficina muestra «CONECTADO» o el error.
- WebNodo (`webnodo/public/index.html`) ya solo ofrece la descarga del visor
  más reciente: se quitaron el botón de enlace de invitado, el enlace P2P y el
  paso de conexión manual.

Pendiente para publicar: embeber el PCK nuevo en
`actualizacion_v2.8.2.zip` y recompilar el `.exe`; el `dotnet build` de la UI
ya está validado.

## Vista previa del visor C#

Antes de empaquetar se compiló la UI y se abrió con el PCK enlazado al lado del
`.exe` de desarrollo. La captura `captura_visor_nuevo.png` demuestra:

- barra superior sin enlace de invitación;
- accesos «Lucía 3D», «Oficina con avatar» e «Invitar a LucIA»;
- WebNodo y Chat;
- oficina de LucIA con la cuenta `ChicookFarrior`;
- botón **CONECTADO** y túnel WebNodo activo;
- chat operativo.

No se generó un `.exe` de distribución ni se tocó el ZIP: solo la vista previa.


## Segunda validación: editor de aspecto

El flujo queda: recepción → carrusel → **editor de aspecto** → isla.

- Usa `Personalizacion.gd`, el sistema que ya deforma y tiñe estos avatares
  (no necesita morph targets).
- Controles: 5 colores (piel, pelo, camiseta, pantalón, zapatillas), cuerpo
  (complexión, cabeza, hombros, torso, brazos, piernas, altura), cara (nariz,
  labios, orejas, ojos) y expresiones (sonrisa, enfado, tristeza, sorpresa,
  parpadeo, boca abierta, boca ancha).
- `GUARDAR Y ENTRAR` persiste el aspecto; `RESTABLECER` vuelve al aspecto de
  fábrica; `ENTRAR SIN CAMBIOS` no toca el perfil.
- El editor se probó con `test_editor_aspecto.tscn` (tiñe 2 superficies y
  guarda `camiseta=e61a1a`) y con `test_flujo_editor.tscn`
  (carrusel → editor → isla).

Integración:

- `Boot.gd`: recepción → carrusel nuevo → isla, sin el registro intermedio.
- `Turnos.gd`: las rutas de reserva apuntan ahora a `res://avatares/`.
- `PlayerSync.gd`: acepta `res://avatares/` para los clones remotos.
- `ChunkManager.gd`: al entrar, el avatar se apoya **sobre la superficie real
  de la isla** con un raycast (sin teletransporte ni caída desde el aire).

## PCK exportado

`wvp3d.pck` (1,28 GB) está en esta carpeta y se ha probado con el motor. Incluye
los avatares nuevos y el modelo riggeado de LucIA:

```bat
Godot_v4.7.2-stable_win64.exe --headless --main-pack wvp3d.pck ^
  res://tests/test_avatares_nuevo.tscn
```

Resultado: `RESULTADO: OK`.

También se ha probado el flujo completo dentro del PCK
(`integracion_boot.tscn`): arranca como anfitrión, genera la isla y coloca el
avatar `AVMJ2` sobre el terreno (y ≈ 40, sin teletransporte).

Capturas de verificación en `capturas/`:

- `captura_carrusel.png`: los 8 avatares en el anillo.
- `captura_integracion.png`: el avatar ya de pie sobre la isla.
- `captura_recepcion.png`: oficina de LucIA con tu avatar, botón CONECTAR y chat.
- `captura_integracion.png`: LucIA invitada, de pie junto a tu avatar en la isla.
- `captura_lucia_gesto.png`: LucIA a mitad del saludo, sin T-pose.
- `captura_editor_aspecto.png`: editor de la segunda validación.
- `captura_lucia_chat.png`: LucIA respondiendo por el socket 8765.
- `captura_visor_nuevo.png`: vista previa del visor C# completo con el PCK.
- `captura_chat_auto.png`: chat de LucIA respondiendo dentro del visor.


## Chat de LucIA conectado

LucIA atiende por **TCP 127.0.0.1:8765** con líneas JSON:

- Cliente Godot: `lucia_cliente.gd` (reconexión cada 2 s).
- Servidor: `lucia3D/GLTF_lucIA/celebro_3D/puente_3D/servidor_lucia.py`.
- Modelo: `qwen2.5:7b` servido por Ollama en `127.0.0.1:11434`.
- Arranque manual: `Lanzar_Lucia.bat`.
- Arranque completo (8545 + 8765 + PCK): `Lanzar_PCK_Completo.bat`.

El panel de chat se muestra abajo a la derecha en la recepción y permite
preguntar dudas. El holograma 3D duplicado se desactiva en recepción para no
tapar el formulario.

Los pesos de la red neuronal se escriben en
`%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\lucia\PSNRL` (escribible aunque
el proyecto esté en una carpeta de solo lectura).

La voz ya está activa. Se instaló **comtypes** en el Python embebido y en la
copia que usa el visor, así que LucIA usa **OneCore** (Laura/Helena) y deja
System.Speech como respaldo. `Lanzar_Lucia.bat` y `Lanzar_PCK_Completo.bat` ya
**no** pasan `--sin-voz`.

- La primera frase puede tardar unos segundos por el arranque de COM; el
  servidor precarga el hilo de voz y las siguientes bajan a menos de 1 s.
- El PCM viaja por el socket 8765 y Godot lo reproduce con `AudioStreamWAV` y
  mueve la boca con la envolvente.
- `test_lucia_audio.tscn` confirma `sonando=true` y ~10 s de audio para una
  respuesta normal.

Probado con `test_lucia_chat.tscn`: conecta, envía una pregunta y recibe la
respuesta de `qwen2.5:7b` en ~3 s.

## Arreglos que desbloquean el mundo

1. **LucIA 3D**: `LucIAbsIA.tscn` apuntaba a un `LucIA.glb` inexistente. Ahora
   usa `LucIA_rig.glb` (con esqueleto y animaciones `mixamo.com` y
   `lucIA_ablando`). Se importó en un proyecto limpio y se copiaron la escena y
   las texturas a `.godot/imported`, porque el importador del proyecto grande
   crasheaba por la extensión Ziva.
2. **Extensión Ziva**: desactivada (`ziva_agent.gdextension.disabled`) y
   `extension_list.cfg` vaciado. Godot 4.7.2 crasheaba al importar con ella.
3. **Isla vacía**: `Red.gd` ya no lee el `res://p2p_session.json` empaquetado
   (una foto de una sesión muerta) y respeta `esCliente=false` /
   `rolEfectivo=servidor_local`. Antes, cualquier arranque autónomo se convertía
   en cliente de un túnel caído y se quedaba sin isla. Ahora arranca como
   anfitrión local.
4. **Servidor 8545**: el Python embebido está en
   `.../actualizacion_c5074e3b/src/LC_STM/python/python.exe`, que es la primera
   ruta que busca el visor. El servidor arranca solo y responde `/status`.
5. **Animaciones de LucIA**: su GLB solo traía `mixamo.com` (idle) y
   `lucIA_ablando` (que deja el cuerpo en T). Se generó
   `lucia3D/.../LucIA3D/animaciones_avatar.tres` a partir de las animaciones de
   `AVH1` (mismo esqueleto Mixamo, huesos `mixamorig_` → `mixamorig8_`),
   corrigiendo la pose de reposo:
   `Qdestino = Qrest_destino · (Qrest_origen⁻¹ · Qorigen)`.
   Clips resultantes: `avatar/lucia_parado`, `lucia_caminar`, `lucia_correr`,
   `lucia_strafe_izq` y `lucia_strafe_der`. `LuciaIdle` usa `lucia_parado` y
   `LuciaMovimiento.caminar()` usa `lucia_caminar`. Los avatares `AVMJ` no se
   usan para esto porque llevan un rig propio de 168 huesos, incompatible.
   Además se creó `avatar/lucia_hablando`: cuerpo en idle + pista `BOCA` de
   `lucIA_ablando`. Es el gesto que se reproduce al hablar, así que LucIA mueve
   los labios sin ponerse en T. `test_lucia_labios.tscn` mide el blend shape y
   confirma un rango de apertura de ~0,67.
6. **Cuenta existente**: la cuenta de `ChicookFarrior` se quedó sin
   `cuenta.json` (el visor la tenía en RAM, no en el `user://` de Godot) y la
   recepción pedía «Crear mi cuenta». Se reconstruyó desde el bloque 6 del
   `blockchain_ledger.json`:
   - hash `008c4072…a9678442`, nick `ChicookFarrior`, alta `2026-11-11 00:24:34`;
   - escrito en `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\cuenta.json`,
     `%LOCALAPPDATA%\WoldVirtualP2P3D\user\cuenta.json` y
     `%LOCALAPPDATA%\WoldVirtualP2P3D\cuenta.json`.
   Además, `LuciaRecepcion.gd` recupera la identidad antigua desde
   `user_profile.json` / `credentials.json` si `cuenta.json` falta o está
   corrupto. La recepción muestra «Hola de nuevo, ChicookFarrior» y
   «Entrar al mundo», no el formulario de alta.

## Cómo probarlo

- `Lanzar_Desarrollo.bat`: abre el proyecto Godot (para editar y probar).
- `Lanzar_PCK.bat`: ejecuta el mundo ya exportado (`wvp3d.pck`).
- `Lanzar_PCK_Completo.bat`: arranca el servidor oficial en el 8545 y después
  el mundo exportado. Es la forma más parecida al visor final.

Pruebas automáticas:

```bat
...Godot_v4.7.2-stable_win64.exe --headless --path <proyecto> ^
  res://tests/test_avatares_nuevo.tscn
```

Resultado esperado: `RESULTADO: OK` (8 avatares, carrusel y persistencia).

Capturas:

```bat
...Godot_v4.7.2-stable_win64.exe --path <proyecto> ^
  res://tests/captura_carrusel.tscn --resolution 1280x720
```

## Addons valorados

- **Quaternius Universal Animation Library** (CC0, 120+ animaciones, compatible
  con Godot 4.7.2 y Mixamo): la mejor opción para añadir saludo, sentarse,
  bailar o combate. La descarga binaria no se pudo hacer desde este entorno;
  se integra con el mismo retargeting de `animaciones_avatar.tres` cuando el
  pack esté en el proyecto.
- **Configura** (MIT, mínimo Godot 4.6): character creator modular con
  blendshapes, ropa y colores. No se instaló porque estos avatares son de una
  sola malla y Configura espera piezas modulares; el editor de aspecto usa
  `Personalizacion.gd`, que ya está adaptado a ellos.
- **Humanizer** (CC0, Godot 4.3): genera personajes MakeHuman completos; no
  encaja con los avatares actuales.

## Módulo principal STMGNRL en LucIA 3D

El servidor 3D de LucIA carga ahora `STMGNRL/mainLCSTM.py`:

- `_cargar_puente()` busca `STMGNRL/mainLCSTM.py` subiendo directorios desde
  `puente_3D`.
- Se añadió `LucIAPuenteComandos` al prompt: capacidades reales (RFPRMN),
  detección de comandos y relato de lo ejecutado.
- Se copió `CONTRRF/STM_RFC` a
  `Sistema_Principal/PRY/STM_RFC`, que es donde `_imports.py` lo busca.
- `pythonw` deja `sys.stdout`/`stderr` en `None`; RFPRMN llama a
  `stdout.isatty()` y fallaba con `NoneType has no attribute isatty`. El
  servidor les asigna un flujo válido antes de importar STMGNRL.
- Arranque verificado con `pythonw`:
  `[cerebro] Modulo principal STMGNRL: ACTIVO`.

## WebNodo

`HttpListener` falla con «Controlador no válido» dentro del hilo STA de WPF,
por eso el portal no abría aunque `--webnodo-selftest` pasara.

Ahora, si el portal interno no arranca, el visor lanza
`webnodo/fallback.py` con el Python del visor:

- escucha en `127.0.0.1:3030`;
- sirve la portada real, `/api/info` y `/descargar`;
- el túnel y el botón WebNodo usan ese mismo puerto.

Verificado: `3030 LISTENING` y `HTTP 200` al abrir el visor.

## Arranque directo en el despacho

`OnLoaded` ya no llama a `MostrarPantallaBienvenida()`. Oculta la ventana
antigua y abre el mundo 3D en el mismo arranque, así que la primera pantalla
es el despacho de LucIA.

Al **cerrar sesión** tampoco se vuelve a la ventana antigua: se detiene el chat
y se regresa al despacho de LucIA. `MostrarPantallaBienvenida()` ya no tiene
ninguna llamada en el flujo normal.

## Servidor de LucIA del visor

El servidor indicado en
`lucia3D/LcshLucIA/.../puente_3D/servidor_lucia.py` se importó a la copia de
LucIA que usa realmente el visor:

```text
Sistema_Principal/PRY/actualizacion_c5074e3b/src/MTBGT/WoldVirtualP2P3D/
  lucia3D/GLTF_lucIA/celebro_3D/puente_3D/servidor_lucia.py
```

- Se guardó el anterior como `servidor_lucia.py.bak`.
- `ServidorLucIAOficial.cs` busca primero el servidor dentro del proyecto del
  visor; el respaldo también apunta a esa copia, no a `CONTRRF`.
- `Abrir_VistaPrevia.bat`, `Lanzar_Lucia.bat`, `Lanzar_PCK_Completo.bat` y
  `Reiniciar_Lucia.bat` arrancan ese mismo servidor.
- Verificado con el visor abierto: el puerto 8765 queda `LISTENING`, el chat
  responde y devuelve audio (`VOZ 641748`, 22050 Hz).

## Chat de LucIA

El visor C# arranca LucIA desde la copia
`Sistema_Principal/PRY/actualizacion_c5074e3b`. Esa copia conservaba un
`rutas.py` antiguo que escribía los pesos PSNRL dentro del proyecto y el chat
devolvía:

```text
Fallo el nucleo neuronal: Permission denied ... PSNRL/psnrl_lucia.npz
```

Ya se sincronizaron `STM_CH/rutas.py` y `puente_3D/voz_lucia.py`; ahora usa
`%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\lucia\PSNRL` y el chat responde.
Verificado con una sonda TCP (`TOKEN … FIN …`) y con `test_lucia_chat.tscn`
contra el servidor que arranca el propio visor.

Si aparece solo el aviso **«No se pudo sintetizar la voz»**, el texto sigue
funcionando: la voz usa COM/System.Speech y en el sandbox de pruebas está
bloqueada. Con `Lanzar_PCK_Completo.bat` (servidor fuera del sandbox) la voz
sí se reproduce.

Además, el visor ahora:

- muestra el estado **`🧠 LucIA: 8765`** en la barra superior;
- comprueba cada 6 s que LucIA no solo tenga el puerto abierto, sino que
  conteste el saludo; si es un `pythonw` zombi, lo mata y arranca otro;
- vuelve a levantar el servidor si se cae mientras el visor está abierto;
- deja el campo de chat **siempre editable**; si LucIA aún no está lista,
  al pulsar Enter reintenta la conexión en vez de bloquear la escritura.

También se corrigió la comunicación fina:

- el servidor importado ya no usa `SO_REUSEADDR` en Windows, así que no pueden
  quedar dos servidores escuchando el 8765 a la vez;
- `GodotHwndHost` genera el `WM_CHAR` que WPF no traducía al interceptar
  `WM_KEYDOWN`; antes el avatar se movía pero el `LineEdit` no recibía letras;
- en cuentas existentes el chat recibe el foco automáticamente al abrir la
  oficina.
- Verificado en el visor: `Tú: Hola LucIA` y respuesta
  «¡Hola! Me alegra verte. ¿Cómo estás hoy?» en el panel.

Correcciones de estabilidad posteriores:

- El vigilante **ya no mata** a LucIA cuando el puerto está ocupado pero el
  saludo tarda: antes la reiniciaba en mitad de una consulta y parecía que
  «solo contestaba una vez».
- El servidor usa `listen(32)` para no quedarse sin backlog con el chat, el
  túnel y el chequeo de salud.
- La voz se sintetiza con **timeout de 6 s**; si COM/OneCore se atasca, el
  turno termina igualmente con texto y aviso, sin bloquear la siguiente
  consulta.
- Verificado con tres consultas seguidas (misma conexión y conexión nueva):
  las tres terminan en `FIN` y el servidor sigue vivo.

### Arranque fiable de LucIA

El arranque desde el `.exe` directo puede fallar porque el proceso hijo hereda
un entorno de WPF que no siempre inicializa COM/Python igual. La vía verificada
es el lanzador:

`Abrir_VistaPrevia.bat` → PowerShell → `servidor_lucia.py`

El `.bat` espera hasta 25 s a ver `LISTENING` en 8765 antes de abrir el visor.
Con ese lanzador se probaron tres consultas seguidas sin reiniciar LucIA.

La voz se sintetiza en `voz_worker.py`, un proceso hijo aparte: si COM/OneCore
revienta, el servidor de chat no se cae. La precarga de voz se desactiva con
`--sin-precarga-voz`.

También se corrigió un error de sintaxis en la línea de `self.puente` que
impedía arrancar el servidor.

## Conocimiento del registro

LucIA recibe un bloque fijo de hechos reales para no inventar:

- una cuenta = un bloque de la blockchain oficial; su hash **es** la cuenta;
- cuenta nueva: sin contraseña ni frase semilla;
- alta en la oficina de LucIA, nick de 10 a 15 letras;
- servidor de bloques en 8545, `/alta-cuenta` y descarga ZIP;
- `cuenta.json` guarda `cuenta_hash`, `nick`, `alta` y `bloque`; es la llave;
- avatar y aspecto van aparte en `avatar_jugador.cfg` y `registro.cfg`;
- migración: ZIP + llave + 12 palabras semilla.

Si le preguntan algo fuera de esos hechos, debe decir que no tiene el dato y
remitir a la oficina, no improvisar.

Verificado:

```text
P: ¿Qué es una cuenta y qué archivo la guarda?
R: ... una cuenta es un bloque ... su hash ... cuenta.json ...
```

## Contexto de cuenta y avatar en LucIA

El cliente 3D envía en cada consulta un bloque `contexto` con:

- metaverso y lugar (`oficina_de_lucia`);
- nick y hash corto de `cuenta.json`;
- `avatar_id` y escena de `registro.cfg`;
- colores/proporciones de `[personalizacion]` guardados por el editor.

El servidor lo añade al prompt del sistema, de modo que LucIA reconoce al
jugador, su avatar y que está dentro de WoldVirtualP2P3D. Verificado:

```text
Estoy en la oficina de LucIA, en WoldVirtualP2P3D.
Tu avatar registrado es AVMJ2...
```

## Persistencia de la construcción

Al aplicar una escena de Godot, el visor guarda una copia dentro de los datos
de la isla del jugador:

```text
user://construccion/isla_<indice>_godot.tscn
user://construccion/isla_<indice>_godot.json   (posición y rotación)
```

Al volver a entrar, `Construccion.registrar_isla()` la carga y la coloca en su
posición guardada. Ya no desaparece al cerrar el visor.

- Al aplicar una nueva escena se elimina de la isla la construcción anterior
  **en caliente**, sin salir y volver a entrar.
- Si borras todo, la isla queda vacía y se guarda `vacio: true` para que al
  volver a entrar siga vacía.
- Si la copia de la isla estuviera vacía por una versión anterior (sin marca
  `vacio`), se usa la última escena del editor
  (`user://isla_construida.tscn`).
- Se soportan `MeshInstance3D` y `CSGMesh3D`; los shaders externos se copian a
  `user://shaders/` para que el visor pueda cargarlos.

![Construcción restaurada al volver a la isla](<VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/Visor3Ddesarrollo/capturas/captura_construccion_persistida.png>)

Verificado:

```text
[Construccion] Escena de Godot guardada en la isla 2
[Construccion] Escena de Godot restaurada en la isla 2
```

## Construcción con Godot → isla

El visor tiene un botón **«🏗 Construcción»** en la barra superior:

1. Al pulsar **«🏗 Construcción»** ya **no pregunta dónde guardar**. Usa una
   carpeta fija escribible del visor:
   `...\ISLA3D` junto al ejecutable; si no se puede escribir, usa
   `%LOCALAPPDATA%\WoldVirtualP2P3D\ISLA3D`.
   Allí copia el proyecto vacío y crea `ISLA3D/isla.tscn`.
   Las carpetas importadas del PC van a `ISLA3D/importado/<nombre>`.
2. El editor se incrusta sin bordes y abajo quedan **«🏝 Llevar a mi isla»**
   y **«Cerrar constructor»**.
3. Al pulsar **«Llevar a mi isla»**, el visor pide al plugin un **guardado
   forzado** de la escena actual (con las últimas escalas, plataformas y
   transformaciones), espera a que confirme y solo entonces cierra el editor y
   escribe `user://construccion_lista.flag`. El `ChunkManager` carga la escena
   junto al jugador (`+2.2, 0, +1.2`).

Antes la escena se añadía en `(0,0,0)`, lejos de la isla, por eso no se veía.

![Construcción de Godot ya colocada en la isla](<VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/Visor3Ddesarrollo/capturas/captura_construccion_isla.png>)

El editor se incrusta como ventana sin bordes con owner del visor, no con
`SetParent`, porque el reparentado nativo hacía crashear a Godot.

![Editor de construcción incrustado en el visor](<VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/Visor3Ddesarrollo/capturas/captura_constructor_embebido.png>)

Plugin: `addons/constructor_isla/` (`plugin.cfg` + `plugin.gd`), habilitado en
`[editor_plugins]` del proyecto vacío y del proyecto de desarrollo.

Verificado con una escena de prueba:

```text
[Construccion] Escena de Godot añadida a la isla: user://isla_construida.tscn
```

## Oficina caminable

Al entrar con **«Oficina con avatar»**, la oficina usa el mismo controlador que
la isla:

- avatar `AvatarJugador` con `es_selector = false`;
- cámara en tercera persona detrás del avatar;
- **WASD o flechas** para andar, botón derecho para girar la cámara;
- **Espacio** para saltar; **Enter no salta** (solo envía el chat si el campo
  tiene el foco), así que se acabó el salto molesto al escribir;
- strafe izquierda/derecha corregido (antes las animaciones estaban cruzadas);
- **T** o el botón **«Hablar con LucIA (T)»** enfoca el chat sin perder el
  movimiento; **Escape** lo suelta;
- el botón **Enviar** está siempre activo; si LucIA aún no está lista,
  reintenta la conexión en vez de quedarse deshabilitado;
- la ayuda en pantalla dice `WASD o flechas: andar · botón derecho: mirar · clic en el chat: escribir`;
- el chat ya no roba el foco al entrar; al enviar una consulta se libera para
  que WASD vuelva a mover al avatar;
- suelo con colisión para no caer;
- la misma personalización de la isla;
- WASD no mueve al avatar mientras se escribe en el chat.

![Oficina caminable con cámara detrás](<VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/Visor3Ddesarrollo/capturas/captura_oficina_caminable.png>)

## Avatar en la oficina

Cuando se abre la oficina con avatar, `LuciaRecepcion` crea el mismo modelo del
catálogo y le aplica `Personalizacion.aplicar(avatar, Personalizacion.leer())`,
igual que `ChunkManager.set_player_avatar()` en la isla. Así se ven los mismos
colores, proporciones, cara y altura; no solo el modelo base.

## Guardar e importar la cuenta

La oficina de LucIA incluye ahora:

- **«💾 Guardar copia de seguridad (.zip)»**: abre un diálogo para elegir la
  carpeta y genera un ZIP con `cuenta.json` y `metadata.txt`. Se genera
  localmente, aunque falle la descarga del servidor.
- **«Ya tengo cuenta · Importar .zip»** en el alta nueva: abre un ZIP o un
  `cuenta.json`, valida `cuenta_hash` y `nick`, lo guarda en `user://cuenta.json`
  y deja entrar sin crear otra cuenta.
- El ZIP antiguo se puede importar directamente; no hace falta adjuntarlo a
  ningún servidor.

## Cerrar sesión

El botón **Cerrar Sesión** ahora cierra el visor de verdad: detiene el chat y
el cierre ordenado para Godot, blockchain, LucIA y WebNodo. Verificado con
UI Automation: el proceso desaparece y los puertos 8765/3030 dejan de
escuchar.

## Pendiente para publicar

El visor sigue arrancando el `wvp3d.pck` antiguo embebido en el `.exe`. Para que
los cambios lleguen al ejecutable hay que sustituir `wvp3d.pck` dentro de
`actualizacion_v2.8.2.zip` por el de esta carpeta y volver a compilar el visor
C# con `dotnet publish` (el proyecto C# está en el ZIP de respaldo de esta
carpeta). El PCK nuevo ya está exportado y probado; no hace falta regenerarlo.
