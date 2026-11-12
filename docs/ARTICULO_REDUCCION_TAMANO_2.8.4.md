# Reducción del tamaño de WoldVirtualP2P3D para la próxima versión

## Situación actual (v2.8.3)

| Artefacto | Tamaño |
|---|---:|
| `LCDMWoldVirtualP2P3Dv2.8.3.exe` | 1,41 GB |
| `actualizacion_v2.8.3.zip` incrustado | 1,16 GB |
| `wvp3d.pck` | 1,28 GB |
| Workspace completo de desarrollo | ≈26,7 GB |
| Motor Godot comprimido (`godot_exe.zip`) | 86 MB |

El ejecutable ya es autocontenido, pero paga dos veces por el contenido: el PCK
viaja comprimido dentro del ZIP y el ZIP viaja dentro del ejecutable. Además el
workspace conserva copias de seguridad, proyectos duplicados y materiales que
no forman parte del mundo jugable.

## Objetivo

Reducir la descarga inicial **sin perder ninguna funcionalidad ni contenido
actual**:

- mismo mundo y mismas islas;
- misma Lucía 3D, voces y modelos;
- mismo editor de construcción y mismas escenas guardadas;
- mismos avatares, animaciones y textos.

La reducción debe ser medible, reversible y verificable por hash.

## Principios

1. **Una sola fuente de verdad por recurso.** Nada de mantener dos copias del
   proyecto Godot o de los modelos de Lucía.
2. **Lo opcional no viaja en el ejecutable.** Voces, datasets de Lucía y
   contenido extra se descargan aparte y se verifican con SHA-256.
3. **Comprimir una sola vez.** No volver a comprimir un ZIP ya comprimido ni
   empaquetar el PCK dentro de otro archivo comprimido.
4. **Presupuesto de tamaño por release.** Si una release supera el presupuesto,
   el pipeline falla antes de publicar.
5. **Nada se borra sin manifiesto.** Cada exclusión debe estar justificada y
   cubierta por una prueba de contenido.

## Líneas de trabajo

### 1. Auditoría y manifiesto de contenido

- Generar un inventario de todos los archivos del PCK con tamaño, hash,
  procedencia y si se usan en tiempo de ejecución.
- Detectar duplicados exactos y versiones antiguas de modelos, texturas,
  avatares y escenas de prueba.
- Marcar con `.gdignore` todo lo que no deba entrar en el export:
  `tests/`, escenas de captura, `version_prueba/`, `bin/`, `obj/`, logs,
  respaldos y copias de seguridad.
- Añadir un `manifest.json` de release con SHA-256 por entrada.

**Ahorro esperado:** 10–25 % solo por eliminar duplicados y material de
desarrollo que hoy se cuela en el PCK.

### 2. Optimización de texturas y mallas

- Convertir texturas grandes a WebP/VRAM comprimida y limitar resolución según
  distancia de uso (por ejemplo, 2048 para primera línea, 1024 para fondo).
- Generar LODs para avatares, islas y decorados; conservar el LOD0 actual.
- Eliminar mapas de textura no conectados a ningún material.
- Revisar importaciones `.gltf` que conservan la geometría original y el GLB
  importado a la vez.

**Ahorro esperado:** 20–35 % del PCK, sin cambios visuales perceptibles.

### 3. Separar contenido opcional

Mantener en el ejecutable solo el núcleo necesario para entrar:

- motor Godot;
- mundo base y islas;
- avatares y animaciones;
- interfaz, registro y construcción;
- Lucía mínima para conversar.

Mover a paquetes descargables:

- voces TTS adicionales;
- datasets y modelos grandes de Lucía;
- documentación y ejemplos;
- contenido audiovisual de la web.

Cada paquete se descarga desde WebNodo, se verifica y se guarda en
`user://paquetes/`, sin volver a tocar el ejecutable.

**Ahorro esperado:** 300–600 MB en la descarga inicial.

### 4. Dejar de duplicar el ZIP dentro del EXE

Dos opciones, en este orden:

1. **Paquete externo firmado:** el `.exe` contiene motor + interfaz + un
   manifiesto; el contenido viaja como `contenido_v2.8.4.zip` junto al
   ejecutable o se descarga en el primer arranque.
2. **Extracción selectiva:** si se mantiene el ZIP incrustado, guardar solo el
   mundo base y descargar el resto; evitar el ZIP de 1,16 GB dentro de un
   ejecutable de 1,41 GB.

El instalador debe mostrar progreso, verificar hash y permitir reanudar.

**Ahorro esperado:** 800 MB–1 GB en el binario principal.

### 5. Unificar los proyectos Godot y los servidores de Lucía

- Una sola copia canónica del proyecto Godot; `CONTRRF` y `actualizacion` deben
  generarse desde ella, no mantenerse a mano.
- Un solo servidor Lucía y un solo `servidor_lucia.py`; eliminar copias
  divergentes y rutas absolutas.
- Empaquetar el runtime de Python necesario o declararlo como dependencia
  externa, pero no duplicarlo por versión.

**Ahorro esperado:** cientos de MB en el repositorio y en el instalador; menos
errores de deriva.

### 6. Pipeline de release con presupuesto

- Exportar el PCK en CI con una lista blanca de recursos.
- Medir tamaño por carpeta y comparar con la release anterior.
- Fallar si el `.exe` supera el presupuesto acordado o si un archivo crece más
  de un porcentaje sin justificación.
- Publicar tabla de tamaños y hashes junto a la release.
- Firmar el ejecutable y adjuntar `SHA256SUMS`.

## Plan propuesto para 2.8.4

### Fase 0 — Medición (1–2 días)

- Inventario completo y línea base de tamaños.
- Detectar duplicados y archivos no usados.
- Documentar qué se puede excluir sin perder nada.

### Fase 1 — Limpieza segura (3–5 días)

- Excluir tests, respaldos, capturas y material de desarrollo del PCK.
- Eliminar duplicados exactos.
- Reexportar y comparar visualmente islas, avatares, Lucía y construcción.

### Fase 2 — Texturas y LODs (1 semana)

- Optimizar texturas y mallas.
- Medir VRAM y calidad en las mismas escenas.
- Mantener una comprobación visual automática de capturas clave.

### Fase 3 — Paquetes opcionales (1–2 semanas)

- Separar voces y datasets de Lucía.
- Descarga y verificación desde WebNodo.
- Primer arranque con progreso y reintento.

### Fase 4 — Release delgada (2–3 días)

- Ejecutable sin el ZIP gigante.
- Instalador/paquete de contenido.
- Firma, hashes y pruebas en un PC limpio.

## Presupuesto orientativo

| Versión | Descarga inicial | Ejecutable |
|---|---:|---:|
| 2.8.3 actual | ≈1,41 GB | 1,41 GB |
| 2.8.4 con limpieza | ≈700–900 MB | ≈350–500 MB |
| 2.8.4 con paquetes opcionales | ≈350–550 MB | ≈250–350 MB |

Son objetivos, no promesas: dependen de cuánto contenido de Lucía se pueda
separar sin romper la experiencia offline.

## Criterios de aceptación

- [ ] El mundo, las islas y la construcción se ven igual que en 2.8.3.
- [ ] Lucía responde, habla y conserva su voz.
- [ ] Los avatares y animaciones no cambian.
- [ ] Las cuentas y los ZIP de cuenta siguen funcionando.
- [ ] El primer arranque explica qué se descarga y verifica su hash.
- [ ] Existe una prueba en PC limpio sin dependencias de desarrollo.
- [ ] El pipeline falla si se supera el presupuesto de tamaño.

## Riesgos

- **Romper contenido por una exclusión agresiva.** Mitigación: manifiesto,
  hashes y capturas de comparación.
- **Depender de la red en el primer arranque.** Mitigación: modo offline con
  contenido base y reintentos.
- **Duplicar esfuerzo entre proyectos.** Mitigación: una sola fuente canónica y
  generación automática.
- **Optimizar texturas con pérdida visible.** Mitigación: comparación lado a
  lado y límites por tipo de recurso.

## Conclusión

La mayor parte del tamaño no está en el código, sino en assets duplicados,
material de desarrollo y volver a comprimir lo ya comprimido. La ruta más segura
es medir, limpiar, optimizar texturas y separar lo opcional; nunca borrar sin
manifiesto ni prueba de contenido.
