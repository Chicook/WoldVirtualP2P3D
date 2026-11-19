# LipSync para LucIA · propuesta para más adelante

Documento de investigación, sin cambios en el proyecto. Recoge qué addons
existen, cuál encaja con Godot 4.7 y qué haría falta para que LucIA mueva la
boca al ritmo de su voz.

## Estado actual

- `lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/gdscrip/lucia_personaje.gd`
  expone un único morph llamado `BOCA` (`fijar_apertura_boca`) y una cavidad
  interior que se escala con la apertura.
- `.../gdscrip/lucia_cliente.gd` mueve ese morph con una envolvente sintética
  (`_boca_sintetica`, varias frecuencias sumadas) incluso cuando hay audio TTS.
- Resultado: la boca abre y cierra, pero no guarda relación con los fonemas
  reales de la frase. Es un efecto de "está hablando", no LipSync.

## Addons encontrados (verificados con sus repositorios, 2026-11-16)

### 1. Baked Lipsync — recomendado para esta etapa

- Repositorio: https://github.com/fbcosentino/godot-baked-lipsync
- Asset Library: https://godotengine.org/asset-library/asset/3629
- Licencia MIT · GDScript · proyecto de ejemplo en Godot **4.3** · 51 estrellas
- Qué hace: usa [Rhubarb](https://github.com/DanielSWolf/rhubarb-lip-sync)
  para hornear las formas de boca de un WAV y genera un recurso de animación.
  En ejecución, `AudioStreamPlayerLipsync`, `AudioStreamPlayerLipsync2D` y
  `AudioStreamPlayerLipsync3D` reproducen el audio y emiten señales cada vez
  que hay que cambiar de forma de boca (admite también "expresiones").
- Instalación: copiar `addons/baked_lipsync`, activar el plugin. La primera
  vez descarga Rhubarb dentro de `addons/` con un `.gdignore` (no se exporta).
  Ojo: esa carpeta no debe acabar en git; el binario es una dependencia local,
  igual que el criterio de `.dev` en este proyecto.
- Encaje: ideal para la voz pregrabada de la cinemática del alta y los saludos
  fijos de la DAO. No resuelve TTS en vivo.

### 2. Rhubarb Lip Sync TPI — solo como referencia

- Repositorio: https://github.com/AniMesuro/rhubarb-lipsync-tp-integration-godot
- Licencia MIT · último commit 2022 (época Godot 3.x)
- Integra la CLI de Rhubarb en una ventana de editor: eliges
  `AnimationPlayer` + `AudioStreamPlayer`, asignas las bocas y genera el
  track. Útil para entender el flujo, pero **hay que verificar compatibilidad
  con Godot 4.7 antes de plantearlo**; Baked Lipsync ya cubre lo mismo en 4.x.

### 3. Rhubarb Lip Sync (CLI) — la base

- Repositorio: https://github.com/DanielSWolf/rhubarb-lip-sync
- Herramienta de línea de comandos (Windows/macOS/Linux) que reconoce el habla
  de un WAV y devuelve 9 formas de boca (A–H y X, silencio) con marcas de
  tiempo. Es de donde salen los datos de las dos anteriores.

## Ruta propuesta (sin implementar todavía)

1. **Cinemáticas y frases fijas (fase A).** Hornear con Baked Lipsync los WAV
   de la cinemática del alta y de los diálogos fijos de la DAO. Como el modelo
   solo tiene el morph `BOCA`, empezar mapeando A–H a aperturas distintas
   (`0.0`–`1.0`) y, si convence, añadir al GLB morphs de vocales
   (A/E/I/O/U/MBP/FV) para que no todo sea "más o menos abierto".
2. **Voz TTS en vivo (fase B).** Sin fonemas no hay visemas exactos. Opciones:
   - forzar al motor TTS a devolver visemas o fonemas y convertirlos aquí;
   - mientras no exista eso, mover `BOCA` y la "boca ancha" con una envolvente
     real del audio (bandas de `AudioEffectSpectrumAnalyzer` leídas cada
     frame), que ya mejora mucho la envolvente sintética actual;
   - servicios externos (por ejemplo StoryFlow) que hacen LipSync en tiempo
     real, a cambio de depender de la nube.
3. **Integración limpia (fase C).** `lucia_cliente.gd` deja de llamar a
   `abrir_boca`/`cerrar_boca` en bucle y pasa a consumir las señales del
   reproductor de LipSync (o de la envolvente), con un `AnimationTree` o un
   pequeño controlador que mezcle el morph `BOCA` con los gestos actuales.

## Alcance

Nada de esto está instalado ni cableado. El onboarding habla por HUD
(`_decir`) y la voz TTS de LucIA sigue pendiente; cuando se aborde, este
documento es el punto de partida y la decisión de addon es la de la sección 1.
