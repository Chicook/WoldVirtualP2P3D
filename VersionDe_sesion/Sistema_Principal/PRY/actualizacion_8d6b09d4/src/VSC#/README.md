# Visor "wold virtual p2p 3d" — hoja de ruta (C# basado en Singularity)

Carpeta: `src/VSC#`. Estado: pendiente (empieza en una fase posterior).
Objetivo: visor de escritorio en C# para el metaverso, con el nombre
**wold virtual p2p 3d**, inspirado en Singularity (visor de mundos virtuales
de código abierto) pero conectado a NUESTRA red P2P, no a Second Life.

## 0. Decisiones base (antes de codificar)
- Motor 3D: Silk.NET + OpenGL (ligero, solo visor) o Godot 4 con scripts C#.
  Recomendado: Godot 4 C# — reutiliza escenas, materiales y el AnimationTree
  de hm1 sin reescribir el render.
- Protocolo de red: ENet (el mismo de Godot, puerto 8910) para hablar con
  el mundo actual sin pasarela. Alternativa: puente WebSocket si el visor
  acaba siendo web.
- Formato de avatar: importar hm1 (glTF/FBX exportado del .blend) con sus
  8 animaciones (idle, CaminarOF, CorrerOF, Correr_htr, Saltar,
  Falling_IdleOF, LeftStrafeOF, Right_StrafeOF).

## 1. Fase 1 — Núcleo y conexión
1. Proyecto C# (.NET 8) que abre ventana 3D con cielo, luz y suelo.
2. Cliente ENet que conecta a 127.0.0.1:8910 y completa el handshake
   (`_claim_island` con nick) contra un host Godot.
3. Recibir `posicion + rotacion + nick + estado` de cada avatar y mostrar
   cápsulas de colores (paridad con `PlayerSync.gd` actual).
4. Enviar posición/rotación/estado propios 10 veces por segundo.

## 2. Fase 2 — Mundo e islas
1. Descargar/generar islas: pedir al host la cuadrícula (`chunk_size 199.5`,
   10 por fila, serpentina) y la lista (índice, nick, uuid de 6).
2. Render de terreno + océano equivalentes al `ISLA3DCHUNK` y al shader
   `OCEANO` (versión simplificada).
3. Panel de islas: `Isla {nick} ({uuid})` + teleporte (reutiliza
   `TeleportManager`: posición + `SPAWN_HEIGHT 45` + `snap_camera`).

## 3. Fase 3 — Avatar completo
1. Importar hm1 con esqueleto y AnimationTree equivalente (8 estados).
2. Cámara orbital con retardo (`follow_speed 6.0`, `distance 2.0`,
   `pitch ±75°`) igual que `userbaseh_1.gd`.
3. Entrada invertida 180° (hm1 mira a +Z): W avanza a la cara, A/D a sus
   lados reales; sprint con AltGr.
4. Clones remotos con nick flotante (paridad con `PlayerSync.gd`).

## 4. Fase 4 — Flujo de entrada
1. Registro con avatar (nick mínimo 3 letras, guardado local).
2. Zona del portal: cruzar el Area3D dispara la carga del mundo.
3. Ventana "Conectando a la red P2P..." hasta `mi_isla_lista`
   (paridad con `Boot.gd`).

## 5. Fase 5 — Paridad y cierre
1. Matriz de paridad Godot <-> C#: mismos RPC, mismos nombres de islas,
   mismos uuids deterministas (`WVP3D-isla-{n}`).
2. Prueba cruzada: un avatar Godot y uno C# en la misma isla, viéndose
   con nick y animación correctos.
3. Empaquetado: ejecutable Windows + release en GitHub con el nombre
   de versión `vX.Y.Z_actualizacion_<id>` (seguir el control actual).

## Criterios de aceptación por fase
- Cada fase termina con prueba cruzada contra el host Godot en local.
- Sin romper el protocolo: cualquier cambio de RPC se aplica a la vez
  en `ChunkManager.gd` / `PlayerSync.gd` y en el visor C#.
- Rutas cortas y sin binarios gigantes en git (usar Git LFS para
  `.blend`, texturas e IPFS si hace falta versionarlos).
