# Rutas corregidas · 2026-11-09

Auditoría y arreglo de las referencias `res://` del proyecto principal
(`MTBGT/WoldVirtualP2P3D`) después de restaurar LucIA 3D en `lucia3D/`.

## Resultado

| Métrica | Antes | Después |
|---|---:|---:|
| Referencias `res://` revisadas | 607 | 607 |
| Rotas | 40 | 5 (solo documentación y un archivo de ejecución) |
| Archivos corregidos | — | 23 |

Respaldo con los originales: `MTBGT/_respaldo_rutas_20261109_023440.zip`
(rutas relativas al proyecto Godot; para restaurar, descomprimir sobre la raíz).

## Correspondencias aplicadas

| Ruta antigua | Ruta nueva |
|---|---|
| `res://gltfimport/avatares/av_texturas/` | `res://gltfimport/avatares/avatares/av_texturas/` |
| `res://GLTF_lucIA/` | `res://lucia3D/GLTF_lucIA/` |
| `res://_herramientas/` | `res://lucia3D/_herramientas/` |
| `res://_pruebas/` | `res://lucia3D/_pruebas/` |

Solo se reescribió una referencia cuando el destino existía realmente, así que
ninguna sustitución es a ciegas.

## Lo que sigue sin resolver (y por qué)

- `lucia3D/README.md` y `lucia3D/_pruebas/LEEME.md`: son la documentación del
  proyecto independiente; sus `res://` son correctos **si se abre `lucia3D`
  como proyecto propio**. No se tocan para no falsear esa documentación.
- `gdscrip/Red.gd` → `res://p2p_session.json`: no es un asset, es un archivo que
  el juego escribe en ejecución.
- `res://.godot/...` (`skin_*.png`, `ziva_*.json`, `*.ctex`): rutas de caché que
  generan los propios scripts al ejecutarse.

## Caché `.godot` regenerada

Con Godot 4.7.2 (extraído de `VSC#/godot_exe.zip` a `_tmp_tests/godot`):

```
Godot_v4.7.2-stable_win64.exe --headless --path <proyecto> --import
```

Terminó con **exit 0** y reimportó los assets. `project.godot` no cambió de
escena principal ni de plugins.

## Extensión desactivada (importante)

`addons/ziva_agent/ziva_agent.gdextension` → renombrada a
`ziva_agent.gdextension.disabled`.

Motivo: al cargarla, Godot 4.7.2 **crashea** (violación de acceso,
`0xC0000005`) justo en el paso «Verificando GDExtensions», antes de importar
nada. Con ella desactivada, la importación termina bien.

### Lo que se probó (2026-11-09)

| Prueba | Resultado |
|---|---|
| Descargar la última release (v3.3.6) y comparar la DLL | **Idéntica** (mismo SHA-256): ya era la oficial |
| Cargar la DLL con `ctypes` | Carga bien y exporta `libziva_agent_gdextension_init` |
| Runtimes VC++ (`msvcp140`, `vcruntime140`, `concrt140`) | Presentes |
| WebView2 | Instalado (157.0.4341.42); procesos colgados eliminados |
| Con la extensión en un proyecto **vacío** | **Funciona** (exit 0, `EditorPluginZiva` carga) |
| Con nuestro `project.godot` en ese proyecto vacío | Funciona |
| Sin el otro addon (`limpiar_cache`) | Sigue crasheando |
| Con la base de datos de Ziva apartada | Sigue crasheando |
| Con `runtime`/`bin-deps` regenerados | Sigue crasheando |
| Con caché `.godot` limpia o transplantada | Sigue crasheando |
| Copia del proyecto en ruta corta (`E:\x\WVP`, 8 chars) | Sigue crasheando |
| Solo `addons` + archivos raíz (sin carpetas de assets) | Sigue crasheando |

**Conclusión**: la build oficial (godot-cpp **4.2**) es inestable al cargar en
este proyecto con Godot 4.7.2; en un proyecto vacío sí carga. No hay fuentes
públicas del addon ni toolchain C++ en el equipo, y **ninguna** de las 30
releases del fabricante está compilada para Godot 4.3+ (todas son
`godot-v4.2.0`), así que no se puede recompilar ni actualizar a una versión
compatible. Queda desactivada hasta que el fabricante publique una build para
4.7; el proyecto importa y abre correctamente sin ella.

