# Animaciones para LucIA

Deja aquí los clips de Mixamo (u otro pack con esqueleto Mixamo). Formatos:

- **GLB** (preferido) o **FBX**. Si es FBX, Godot 4.7 lo importa; si falla, lo
  convierto a GLB con Blender.
- Descarga en Mixamo con **"Without Skin"** si solo quieres la animación: así el
  archivo trae esqueleto + clip, sin malla. Si viene con malla, se descarta.
- Si Mixamo ofrece "In Place", actívalo para las animaciones de estar quieta
  (idle, sentada, hablar). Para caminar/sentarse con desplazamiento se puede
  dejar el *root motion* y ya lo recorto en Godot.

## Clips que hacen falta

| Nombre sugerido        | Para qué                                   |
|------------------------|--------------------------------------------|
| `idle.glb`             | de pie, respirando                         |
| `sentada_idle.glb`     | sentada en la silla del despacho           |
| `hablar.glb`           | de pie hablando                            |
| `sentada_hablar.glb`   | sentada hablando                           |
| `levantarse.glb`       | transición de pie → sentada (opcional)     |

Con esos cinco monto un **AnimationTree** con estados
`DE_PIE` / `SENTADA` y cruces suaves, más los gestos actuales como capa aditiva.

## Lo que hago con ellos

1. Los importo y renombro, y compruebo que el esqueleto coincide (`mixamorig8_*`).
2. Mido dónde quedan las caderas y los pies en cada clip para **alinear la silla
   y el suelo** (nada de flotar).
3. Añado una silla al despacho (o uso la que me pases) y la coloco bajo las
   caderas del clip de sentada.
4. Reencuadro la cámara para que se vea el cuerpo completo por encima del panel
   de chat.
5. Pruebas visuales de pie / sentada / hablando, como las de `_pruebas/`.
