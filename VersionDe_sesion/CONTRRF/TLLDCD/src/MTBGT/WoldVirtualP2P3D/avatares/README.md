# Módulo de avatares (reconstruido)

Sistema independiente de los avatares del metaverso. Sustituye al carrusel
antiguo (`SLCAV/.../SLAV.tscn`) y a las ocho escenas `AV*Ch3D.tscn`, que
dependían de una jerarquía de escenas muy profunda.

## Piezas

| Archivo | Papel |
|---|---|
| `CatalogoAvatares.gd` | Lista única de los 8 modelos, ids, nombres, género y rutas. |
| `AvatarJugador.gd` | Controlador: normaliza la altura, crea cápsula y cámara, mueve y anima. |
| `CarruselAvatares.tscn/.gd` | Selector 3D con ratón, rueda, flechas, clic y ENTER. |
| `GestorAvatares.gd` | Autoload `Avatares`: guarda la elección en `user://`. |
| `AVH1.tscn` … `AVMJ4.tscn` | Ocho escenas mínimas: script + glTF. |

Los modelos se cargan directamente de `res://gltfimport/avatares/*.gltf` y
comparten las cinco animaciones originales:

```
paradoMJ1_1 · caminarMJ1_2 · correrMJ1_3 · left_StrafeMJ1_4 · rightstrafeMJ1_5
```

## Flujo

1. `Boot.gd` muestra la recepción de LucIA y obtiene el nick de la cuenta.
2. Si no hay avatar guardado, abre `CarruselAvatares.tscn`.
3. Al confirmar, `Avatares.guardar(id)` escribe:
   - `user://avatar_jugador.cfg` (selección nueva),
   - `user://registro.cfg` → `jugador/avatar_scene` (compatibilidad con
     `ChunkManager`, `PlayerSync`, teletransporte y reserva de plazas).
4. `Boot` entra a la isla y `ChunkManager.set_player_avatar()` sustituye el
   `USERBASE` de plantilla por la escena `res://avatares/<ID>.tscn`.

## Pruebas

```bash
Godot_v4.7.2-stable_win64.exe --headless --path <proyecto> \
  res://tests/test_avatares_nuevo.tscn
```

Comprueba las 8 escenas (malla, esqueleto, animación, cápsula y altura 1,80 m),
el carrusel completo y la persistencia en `registro.cfg`.

Para una captura visual:

```bash
Godot_v4.7.2-stable_win64.exe --path <proyecto> \
  res://tests/captura_carrusel.tscn --resolution 1280x720
```

## Notas

- `Turnos.gd` usa ahora las rutas `res://avatares/*.tscn`; la reserva de plazas
  por turnos sigue funcionando sin cambios.
- `PlayerSync.gd` acepta `res://avatares/` para clonar el avatar remoto.
- Para añadir un avatar: copiar el `.gltf` y su `.bin` a
  `gltfimport/avatares`, crear `avatares/<ID>.tscn` con el mismo patrón y
  añadir la entrada al catálogo.
