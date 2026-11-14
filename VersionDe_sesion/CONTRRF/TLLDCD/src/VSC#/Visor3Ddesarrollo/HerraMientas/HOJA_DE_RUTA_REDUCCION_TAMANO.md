# Hoja de ruta: reducir el tamaño del visor sin perder contenido

Ámbito: `src\VSC#\Visor3Ddesarrollo` · Versión de partida: **2.8.3** · Fecha: 2026-11-13
Objetivo: bajar el peso de cada release manteniendo **todo** el contenido actual
(avatares, isla, Lucía, chat, blockchain) y la misma experiencia de uso.

---

## 1. De dónde sale el peso (medido, no estimado)

### Release publicada

| Componente | MB | % |
|---|---:|---:|
| `actualizacion_v2.8.3.zip` (mundo + Lucía + config) | 1.109,4 | 82,3 % |
| Runtime .NET autocontenido + WPF + código | ~157 | 11,6 % |
| `godot_exe.zip` (motor incrustado) | 82,2 | 6,1 % |
| **Total `.exe`** | **1.348,3** | 100 % |

### Interior del mundo (`wvp3d.pck`, 1.224,5 MB, 940 ficheros)

| Tipo | Ficheros | MB | % del PCK |
|---|---:|---:|---:|
| `.ctex` (texturas importadas) | 194 | **1.154,5** | **94,3 %** |
| `.bin` (datos de escenas/animación) | 18 | 37,0 | 3,0 % |
| `.scn` (escenas empaquetadas) | 105 | 31,6 | 2,6 % |
| resto (fuentes, scripts, shaders, remaps) | 623 | 1,4 | 0,1 % |

Las diez texturas más grandes son **mapas de normales de avatar de 4K** (25–35 MB
cada una): `AVmj6_Ch49_1002_Normal` (35,3 MB), `AVmj6_Ch49_1001_Normal` (27,4),
`AVmj3_Ch26_1001_Normal` (26,7)…

**Conclusión: el 82 % del `.exe` es textura de avatar.** Cualquier plan serio
actúa ahí, no en el código (1,4 MB) ni en los scripts.

---

## 2. Principios

1. **No se elimina contenido**: mismos avatares, mismas escenas, mismas funciones.
   Se cambia la *representación* (formato y resolución de textura) y la
   *entrega* (qué viaja en el `.exe` y qué se descarga).
2. **Cada cambio se mide**: PCK antes/después, SHA-256 del `.pck`, arranque
   headless y comparación visual de una captura por avatar.
3. **Reversible**: toda conversión conserva el PNG original en el repositorio
   (fuera del paquete), así que se puede re-exportar a otra calidad.
4. **Un objetivo por release**: 2.9 ataca texturas; 3.0 ataca la distribución.

---

## 3. Líneas de trabajo

### L1 · Texturas de avatar: formato y resolución — objetivo −700 MB

| Acción | Ahorro estimado | Riesgo | Esfuerzo |
|---|---:|---|---|
| Reimportar con **ASTC 4x4 / ETC2** en vez de BPTC sin pérdida | −35/−45 % del `.ctex` (~400–520 MB) | Calidad en normales | Medio |
| Bajar normales de avatar de **4K a 2K** | −60 % de esas 10 texturas (~250 MB) | Bordes en primeros planos | Bajo |
| Diffuse/roughness a 1K (se ven a >1 m) | −80 % de esas | Bajo | Bajo |
| Mipmaps solo hasta 512 en objetos de fondo | −5 % | Poping leve | Bajo |

Cómo: en cada `.import`, `compress/mode=2` (VRAM comprimida) con
`compress/high_quality=false`, `compress/hdr_compression=1` y
`compress/channel_pack=1`; `mipmaps/limit` para el tope. Reimportar y
**volver a exportar** el PCK.

**Criterio de aceptación**: PCK ≤ 600 MB, mismos 194 `.ctex` (o menos si se
deduplican), captura comparativa de cada avatar sin artefactos visibles,
`--headless --main-pack` arranca y llega a `[Recepcion]`.

### L2 · Duplicados exactos — objetivo −100/−250 MB

En el árbol fuente se midieron **591 MB en 51 conjuntos de ficheros idénticos**
(mismo SHA-256), sobre todo texturas de avatar repetidas entre
`AreaDeTrabajo` y `gltfimport\avatares`. En el PCK siguen viajando como
`.ctex` distintos si el `.import` difiere.

Acción: script de deduplicación por hash → una sola ruta canónica + `.import`
que apunte a ella; los `.tscn` usan `uid://`, así que el cambio es seguro.
Verificación: `godot --headless --check-only` sobre las escenas afectadas y
arranque completo.

### L3 · Motor fuera del `.exe` — objetivo −82 MB por release

`godot_exe.zip` se incrusta en cada build y además se extrae a
`%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\Servidor3D`. Es el mismo
binario en todas las versiones.

Acción: publicar el motor **una vez** (recurso separado o descarga en el primer
arranque, con SHA-256 en `release.json`); el `.exe` solo lo verifica.
`AppExtractor.EnsureExtracted` ya valida hashes: basta con que el ZIP no vaya
incrustado y se resuelva por ruta/descarga.

### L4 · Entrega del mundo por IPFS — objetivo −1.100 MB por release

Hoy el `.exe` embebe el ZIP OTA completo (1.109 MB). El proyecto ya tiene nodo
IPFS propio, manifiesto con CID + SHA-256 y herramienta de restauración
(`_archivo_ipfs`).

Acción:
1. Publicar `wvp3d.pck` (o el ZIP) en IPFS y anotar el CID en `release.json`.
2. El visor descarga por CID la primera vez (gateway local o peers) y verifica
   SHA-256 antes de montar; si falla, cae al paquete embebido de emergencia.
3. El `.exe` pasa a ~90 MB (código + runtime) y el mundo se cachea en
   `%LOCALAPPDATA%`.

Resultado: release inicial ~90 MB + descarga única del mundo; arranques
posteriores sin descarga.

### L5 · Actualizaciones delta — objetivo −95 % por actualización

Con el mundo en IPFS, cada versión publica un **delta** (bsdiff/zstd) contra el
PCK anterior. Pasar de 1.100 MB a 20–60 MB por actualización.

Requiere: guardar el PCK de la versión instalada, aplicar el parche, verificar
SHA-256 del resultado y conservar el paquete completo como *fallback*.

### L6 · Publicación y empaquetado — objetivo −15/−25 MB

- `EnableCompressionInSingleFile=true` en `Visor3D.csproj` (hoy `false`).
- `DebugType=none` en Release; no publicar `.pdb`.
- `PublishTrimmed` solo si WPF lo permite (probar con `-p:PublishTrimmed=true`
  y el self-test de arranque; si rompe XAML, descartar).
- Un único paquete OTA: retirar la cadena de `Condition="Exists(...)"` de
  2.8.1/2.8.2 cuando 2.8.3 esté consolidado.

### L7 · Higiene del repositorio (no afecta al `.exe`)

- `lucia3D\LcshLucIA\...\ImportlucIA\LucIA3D.blend` + `.blend1` = **62,5 MB**
  que no se exportan: mover a almacén externo (IPFS) y dejar solo el `.glb`.
- `.godot/` es caché: nunca versionar (ya está ignorado).
- El paquete OTA no debe incluir `_aux`, `_archivo_ipfs` ni `docs`
  (ya excluidos en `empaquetar_actualizacion.ps1`).

---

## 4. Fases y objetivos

| Fase | Contenido | `.exe` objetivo | PCK objetivo | Ahorro |
|---|---|---:|---:|---:|
| **2.9** | L1 + L2 + L6 | ~600 MB | ~550 MB | −55 % |
| **3.0** | L3 + L4 | ~90 MB (+ descarga) | ~550 MB | −93 % de release |
| **3.1** | L5 | ~90 MB | ~550 MB | −95 % por update |

Hitos medibles en cada PR:

```powershell
# 1. tamaño del PCK
(Get-Item .\wvp3d.pck).Length / 1MB

# 2. reparto por tipo dentro del PCK (script de análisis del proyecto)

# 3. arranque sin ventana
& $env:LOCALAPPDATA\WoldVirtualP2P3D\runtime\2.8.3\Servidor3D\Godot_v4.7.2-stable_win64.exe `
  --headless --main-pack .\wvp3d.pck --quit
```

---

## 5. Verificación (no perder nada)

| Prueba | Criterio |
|---|---|
| Inventario de contenido | Mismos 940 ficheros (o menos solo por deduplicación justificada) |
| Avatares | Captura de los 12 modelos, comparación lado a lado |
| Isla y escenas | `[Boot.gd] Arranque…`, `[Recepcion] modo=…` en el log |
| Lucía | Cerebro en `127.0.0.1:8765`, gesto y voz |
| Chat / blockchain | Relay en 8920, servidor oficial en 8545 |
| Testigos SHA-256 | Los 12 ficheros críticos intactos (`testigos_visor.json`) |
| Tiempo de arranque | No más de +15 % respecto a 2.8.3 |

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Artefactos en normales al pasar a ASTC | Comparar por avatar; si hay artefactos, subir calidad solo en esa textura |
| `uid://` roto al deduplicar | Verificación de escenas + arranque; los `.tscn` usan UID, no ruta |
| IPFS no disponible en el primer arranque | Fallback al paquete embebido y reintento con gateway público |
| Delta corrupto | SHA-256 obligatorio y descarga completa como respaldo |
| `PublishTrimmed` rompe WPF | Probar con el self-test; si falla, no aplicar |

---

## 7. Orden de ejecución recomendado

1. Medir y congelar la línea base (PCK 1.224,5 MB; `.exe` 1.348,3 MB).
2. L2 deduplicación (bajo riesgo, mide el suelo real).
3. L1 texturas por avatar, de uno en uno, con captura comparativa.
4. L6 publicación.
5. L3 motor fuera.
6. L4 IPFS + L5 deltas.

Cada paso: PCK nuevo, SHA-256, arranque headless y captura. Sin los tres, no se
publica.
