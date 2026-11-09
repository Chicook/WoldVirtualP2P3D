# Test Visual de LucIA Recepción

## Descripción

Este test permite ver la vista preliminar del formulario de recepción de LucIA sin necesidad de iniciar el visor C# completo.

## Requisitos

- Godot 4.7.2 instalado
- Proyecto Godot en `MTBGT/WVP/`

## Ejecución

### Desde línea de comandos:

```bash
cd VersionDe_sesion/CONTRRF/TLLDCD/src/MTBGT/WVP
godot --path . --script res://gdscrip/test_lucia_recepcion.gd
```

### Desde Godot Editor:

1. Abrir el proyecto Godot: `MTBGT/WVP/project.godot`
2. Ir a `Project -> Project Settings -> Application -> Run`
3. En `Main Scene`, dejar vacío
4. En `Main Run Args`, poner: `--script res://gdscrip/test_lucia_recepcion.gd`
5. Presionar F5 para ejecutar

## Modos de Test

El test muestra el formulario en modo "nuevo" por defecto. Para probar otros modos, modifica el script:

### Modo Nuevo (Usuario sin cuenta)

```gdscript
var recepcion = Recepcion.new()
# Por defecto es modo "nuevo"
```

### Modo Existente (Usuario con cuenta)

Crea `user://cuenta.json` antes de ejecutar:

```json
{
  "nick": "usuario_test",
  "cuenta_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
  "red": "WoldVirtualP2P3D",
  "fecha_alta": "2026-11-09 13:00:00"
}
```

### Modo Migración (Cuenta antigua)

Crea `user://registro.cfg` antes de ejecutar:

```ini
[jugador]
nick = "usuario_antiguo
avatar_scene = "res://SLCAV/AVATARESCONANIMACION/AVMJ1.tscn"

[identidad]
uuid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
```

## Directorio user:// de Godot

**Windows**: `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\`

**Linux**: `~/.local/share/godot/app_userdata/WoldVirtualP2P3D/`

## Qué Verás

### Modo Nuevo
- LucIA con su escena 3D (personaje, oficina, holograma)
- Formulario con:
  - Título: "LucIA te recibe en Wold Virtual 3D"
  - Subtítulo: "Es tu primera vez: yo te acompaño a crear tu cuenta y luego eliges tu avatar."
  - Campo de texto para nick
  - Botón: "Crear mi cuenta"

### Modo Existente
- LucIA con su escena 3D
- Formulario con:
  - Título: "LucIA te recibe en Wold Virtual 3D"
  - Subtítulo: "Te saludo de nuevo, [nick]. Para iniciar sesión en esta versión, valida tu conexión con el link generado por LucIA."
  - Link de validación (generado automáticamente)
  - Botón: "Validar conexión"

### Modo Migración
- Igual que modo existente
- Botón adicional: "Migrar mi cuenta antigua al hash único"

## Controles

- **ESC**: Salir del test
- **Click en botones**: Interactuar con el formulario
- **Teclado**: Escribir en campos de texto

## Logs en Consola

El test imprime en la consola de Godot:

```
================================================================
[Test LucIA] Iniciando test visual de recepción
================================================================
[Test LucIA] Recepción creada. Esperando interacción del usuario...
[Test LucIA] Presiona ESC para salir
```

Cuando el usuario completa la recepción:

```
[Test LucIA] Recepción completada, modo: nuevo
[Test LucIA] El usuario ha pasado al carrusel
```

Cuando se solicita validación de conexión:

```
[Test LucIA] Validación de conexión solicitada
[Test LucIA] (En el visor C# real, esto iniciaría el túnel SSH)
```

## Troubleshooting

### LucIA no aparece

**Causa**: La escena `LucIA_Interfaz.tscn` no existe en la ruta esperada.

**Solución**: Verificar que existe en `lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn`

### Error al cargar el script

**Causa**: La ruta a `LuciaRecepcion.gd` es incorrecta.

**Solución**: Ajustar la ruta en `test_lucia_recepcion.gd` según la estructura real del proyecto.

### El formulario no responde

**Causa**: El foco no está en la ventana de Godot.

**Solución**: Haz clic en la ventana de Godot para darle foco.

## Capturas de Pantalla

Para capturar la vista del test:

1. Ejecutar el test
2. Usar captura de pantalla del sistema (Win+Shift+S en Windows)
3. Guardar en `tests/screenshots/lucia_recepcion/`

## Notas

- Este test es **visual solamente**: no conecta con el servidor blockchain real
- Para pruebas completas, usar el visor C# completo con LucIAValidacionManager
- El test usa la escena LucIA real, por lo que requiere que todos los assets estén presentes
