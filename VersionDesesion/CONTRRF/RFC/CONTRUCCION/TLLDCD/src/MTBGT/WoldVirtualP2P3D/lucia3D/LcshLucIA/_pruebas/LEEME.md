# Pruebas visuales del personaje

- `antes/` — capturas del módulo anterior: rig sintético de 10 huesos con pesos
  calculados por radio (hombros inflados, manga clavada, cuello estirado).
- `despues/` — capturas del rig Mixamo + `lucia_personaje.gd` nuevo:
  reposo, gestos al hablar, boca abierta/cerrada, parpadeo, giro de cabeza.
- `rig/` — primeras capturas del rig Mixamo, antes de corregir el ancla de la boca.
- `interfaz/` — captura de la escena completa (`LucIA_Interfaz.tscn`) con un
  turno falso por socket.
- `charla/` — turno real contra el servidor: pensando, sintetizando, audio y
  primer frame (sin T-pose).
- `silla/` — andar y sentarse: perfiles del ciclo de marcha, pose sentada y
  capturas de la interfaz con la silla (`ui_*`).
- `comparacion.png` — hoja de contactos ANTES / DESPUÉS.

Se regeneran con:

```bash
godot --path . --script res://_herramientas/render_pruebas.gd
python _herramientas/comparar.py
```

`_pruebas/` tiene un `.gdignore` para que Godot no importe las capturas.
