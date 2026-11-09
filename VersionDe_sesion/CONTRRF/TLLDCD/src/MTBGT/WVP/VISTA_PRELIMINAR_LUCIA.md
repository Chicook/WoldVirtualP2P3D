# Vista Preliminar de LucIA Recepción

## Descripción Visual

Este documento describe lo que el usuario verá al interactuar con LucIA en el nuevo flujo de recepción.

## Layout General

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│    [Escena 3D de LucIA]                                                │
│    - Personaje LucIA en su oficina                                      │
│    - Holograma flotante con datos                                       │
│    - Iluminación ambiental azul/cian                                   │
│                                                                         │
│    [Formulario superpuesto - Capa CanvasLayer]                          │
│                                                                         │
│    ┌─────────────────────────────────────────────────────────────────┐   │
│    │                                                                 │   │
│    │    LucIA te recibe en Wold Virtual 3D                          │   │
│    │    [Título centrado, color cian claro, tamaño 30]              │   │
│    │                                                                 │   │
│    │    Es tu primera vez: yo te acompaño a crear tu cuenta          │   │
│    │    y luego eliges tu avatar.                                    │   │
│    │    [Subtítulo centrado, color azul claro, tamaño 18]           │   │
│    │                                                                 │   │
│    │    ┌─────────────────────────────────────────────────────┐     │   │
│    │    │                                                     │     │   │
│    │    │  Escribe tu nick (mínimo 3 letras)                 │     │   │
│    │    │  [███████████████████████████████]                 │     │   │
│    │    │  [Placeholder texto gris]                           │     │   │
│    │    │                                                     │     │   │
│    │    └─────────────────────────────────────────────────────┘     │   │
│    │                                                                 │   │
│    │    [Estado - Inicialmente vacío]                                 │   │
│    │    [Texto naranja/amarillo, tamaño 15]                            │   │
│    │                                                                 │   │
│    │    ┌─────────────────────────────────────────────────────┐     │   │
│    │    │                                                     │     │   │
│    │    │              Crear mi cuenta                         │     │   │
│    │    │           [Botón principal]                         │     │   │
│    │    │                                                     │     │   │
│    │    └─────────────────────────────────────────────────────┘     │   │
│    │                                                                 │   │
│    └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Paleta de Colores

### Fondo 3D
- **Fondo**: Oscuro (#0B0C10)
- **Iluminación**: Azul/cian (#0.72, 0.94, 1.0)
- **Ambiente**: Suave, tonos azulados

### Formulario
- **Panel**: Fondo semitransparente (#0.03, 0.05, 0.10, 0.92)
- **Borde**: Azul claro (#0.35, 0.8, 1.0, 0.9)
- **Título**: Cian claro (#0.72, 0.94, 1.0, 1.0)
- **Subtítulo**: Azul claro (#0.62, 0.82, 1.0, 1.0)
- **Estado**: Naranja/amarillo (#1.0, 0.8, 0.4, 1.0)
- **Botón**: Seguir estilo del proyecto

## Estados del Formulario

### 1. Modo Nuevo (Usuario sin cuenta)

**Título**: "LucIA te recibe en Wold Virtual 3D"

**Subtítulo**: "Es tu primera vez: yo te acompaño a crear tu cuenta y luego eliges tu avatar."

**Campos**:
- Nick (LineEdit)
- Estado (Label)
- Botón: "Crear mi cuenta"

**Comportamiento**:
- Usuario escribe nick (mínimo 3 letras)
- Si nick < 3: Estado muestra error
- Si nick válido: Botón deshabilitado, llama a `/alta-cuenta`
- Si éxito: Guarda `cuenta.json`, emite `recepcion_completada("nuevo")`
- Si error: Estado muestra mensaje, botón rehabilitado

### 2. Modo Existente (Usuario con cuenta)

**Título**: "LucIA te recibe en Wold Virtual 3D"

**Subtítulo**: "Te saludo de nuevo, [nick]. Para iniciar sesión en esta versión, valida tu conexión con el link generado por LucIA."

**Campos**:
- Link de validación (Label, color verde)
- Estado (Label)
- Botón: "Validar conexión"

**Comportamiento**:
- Link muestra: "Link de validación: lucia://[hash] (token: [token]...)"
- Usuario pulsa "Validar conexión"
- Botón deshabilitado, escribe `validacion_conexion.json`
- Emite señal `validacion_conexion_solicitada`
- Poll `validacion_resultado.json`
- Si éxito: Estado "Conexión validada", botón "Entrar al mundo"
- Si error: Estado muestra mensaje, botón rehabilitado

### 3. Modo Migración (Cuenta antigua)

**Título**: "LucIA te recibe en Wold Virtual 3D"

**Subtítulo**: "Ya tienes cuenta aquí. Esta versión usa un único hash de cuenta: te guío para iniciar sesión o migrar la antigua."

**Campos**:
- Link de validación (Label, color verde)
- Estado (Label)
- Botón principal: "Validar conexión"
- Botón secundario: "Migrar mi cuenta antigua al hash único"

**Comportamiento**:
- Usuario puede validar conexión (igual que modo existente)
- O pulsar "Migrar"
- Si migra: Lee `registro.cfg`, llama a `/migrar-cuenta`
- Si éxito: Descarga .zip, guarda `cuenta.json`, actualiza UI
- Recarga formulario con modo existente

## Animaciones y Transiciones

### LucIA 3D
- LucIA está animada (idle animation)
- Holograma pulsa suavemente
- Iluminación ambiental cambia sutilmente

### Formulario
- Aparece con fade-in suave
- Campos de texto tienen placeholder gris
- Botones tienen hover effect
- Estado aparece con delay para dar feedback

## Flujo de Interacción

### Usuario Nuevo

```
1. Usuario abre visor
   ↓
2. LucIA aparece (fade-in)
   ↓
3. Formulario se superpone
   ↓
4. Usuario escribe nick
   ↓
5. Si nick < 3: Error en estado
   ↓
6. Si nick válido: Usuario pulsa "Crear mi cuenta"
   ↓
7. LucIA muestra "Generando tu cuenta..."
   ↓
8. Blockchain responde con hash
   ↓
9. LucIA guarda cuenta.json
   ↓
10. LucIA desaparece (fade-out)
   ↓
11. Carrusel aparece
```

### Usuario Existente

```
1. Usuario abre visor
   ↓
2. LucIA detecta cuenta.json
   ↓
3. LucIA muestra link de validación
   ↓
4. Usuario pulsa "Validar conexión"
   ↓
5. LucIA escribe validacion_conexion.json
   ↓
6. Visor C# detecta, inicia túnel SSH
   ↓
7. Túnel obtiene URL pública
   ↓
8. Visor C# escribe validacion_resultado.json
   ↓
9. LucIA lee resultado
   ↓
10. Si éxito: Botón cambia a "Entrar al mundo"
   ↓
11. Usuario pulsa "Entrar al mundo"
   ↓
12. LucIA desaparece
   ↓
13. Carrusel aparece (si no tiene avatar)
    O isla (si ya tiene avatar)
```

## Elementos de UI Detallados

### Panel del Formulario
- **Posición**: Centrado abajo
- **Borde redondeado**: 12px
- **Sombra**: Borde azul claro con 2px de grosor
- **Padding**: 20px laterales, 16px verticales
- **Fondo**: Oscuro semitransparente con 92% de opacidad

### Campo de Nick
- **Placeholder**: "Escribe tu nick (mínimo 3 letras)"
- **Tamaño fuente**: 18
- **Altura mínima**: 46px
- **Color texto**: Blanco
- **Color placeholder**: Gris (#3A5A78)
- **Color fondo**: Oscuro (#1A1A1A)

### Botón Principal
- **Texto**: "Crear mi cuenta" / "Validar conexión" / "Entrar al mundo"
- **Tamaño fuente**: 19
- **Altura mínima**: 48px
- **Color fondo**: Azul (#2B5F8E)
- **Color texto**: Blanco
- **Color hover**: Azul más claro (#3B6F9E)
- **Color disabled**: Gris (#4A4A4A)

### Botón Secundario (Migración)
- **Texto**: "Migrar mi cuenta antigua al hash único"
- **Tamaño fuente**: 16
- **Altura mínima**: 44px
- **Color fondo**: Verde oscuro (#2B8E5F)
- **Color texto**: Blanco

### Link de Validación
- **Texto**: "Link de validación: lucia://[hash] (token: [token]...)"
- **Tamaño fuente**: 14
- **Color**: Verde claro (#0.45, 0.95, 0.55, 1.0)
- **Autowrap**: Habilitado
- **Alineación**: Centrado

### Estado
- **Texto inicial**: Vacío
- **Texto error**: Naranja/amarillo
- **Texto éxito**: Verde
- **Tamaño fuente**: 15
- **Alineación**: Centrado
- **Autowrap**: Habilitado

## Responsive Design

El formulario se adapta a diferentes resoluciones:

- **Ancho mínimo**: 680px (340px a cada lado del centro)
- **Ancho máximo**: 840px (420px a cada lado del centro)
- **Posición**: Siempre centrado vertical y horizontalmente
- **Z-index**: 210 (por encima de LucIA 3D)

## Accesibilidad

- **Contraste**: Alto contraste entre texto y fondo
- **Tamaño de fuente**: Mínimo 14px, recomendado 18px+
- **Focus**: Campos de texto y botones reciben focus visual
- **Teclado**: Navegación por Tab posible
- **Screen reader**: Etiquetas descriptivas en todos los campos

## Notas de Implementación

- **Capa CanvasLayer**: layer = 210 para estar por encima de todo
- **Font override**: `add_theme_font_size_override` para control preciso
- **Color override**: `add_theme_color_override` para consistencia
- **Outline**: `add_theme_constant_override("outline_size", X)` para legibilidad
- **Signals**: `recepcion_completada` y `validacion_conexion_solicitada` para comunicación con Boot.gd

## Futuras Mejoras Visuales

- [ ] Animación de entrada del formulario (slide desde abajo)
- [ ] Efecto de brillo en el link de validación
- [ ] Icono de LucIA en el título
- [ ] Progress circular mientras se valida conexión
- [ ] Confetti visual al crear cuenta exitosamente
- [ ] Sonido de confirmación al completar pasos
- [ ] Tooltip explicativo en el link de validación
