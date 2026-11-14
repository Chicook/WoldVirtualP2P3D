# 📋 README de Desarrollo — Sesión 2026-10-26
## WoldVirtualP2P3D · CONTRRF / TLLDCD

> **Rama de integración:** `DevQoderIA`  
> **Repositorio:** `https://github.com/Chicook/WoldVirtualP2P3D.git`  
> **Directorio de trabajo:** `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`

---

## 📦 Resumen ejecutivo

En esta sesión se realizaron **7 bloques de trabajo** sobre dos subsistemas. Los estados
correspondientes a comportamiento de runtime quedan pendientes de prueba real:

| # | Bloque | Subsistema | Estado |
|---|--------|-----------|--------|
| 1 | Sistema de cuenta única por PC | `VSC#` (C# WPF) | Implementado, sin prueba real |
| 2 | Validación de llave vinculada al hardware | `VSC#` (C# WPF) | Implementado, sin prueba real |
| 3 | Segunda barrera de seguridad en el login | `VSC#` (C# WPF) | Implementado, sin prueba real |
| 4 | Corrección de animaciones de avatares | `MTBGT` (Godot 4) | Implementado, sin prueba real |
| 5 | Fix de foco de teclado / flechas en Godot embebido | `VSC#` (C# WPF) | Implementado, sin prueba real |
| 6 | Sistema de optimización de texturas y avatares | `MTBGT` (Godot 4) | Implementado, sin prueba real |
| 7 | Eliminación de carpeta `test_user_data` junto al .exe | `VSC#` (C# WPF) | Implementado, sin prueba real |

---

## 🔐 Bloque 1 — Sistema de Cuenta Única por PC

### Objetivo
Impedir que un mismo PC pueda crear más de una cuenta en Wold Virtual P2P 3D.

### Archivos creados

#### `VSC#/Seguridad/Seguridad_sesion_unica/MaquinaHuellaDigital.cs`
Genera un identificador de máquina estable y anónimo usando **HKDF-SHA256 (RFC 5869)** sobre 7 atributos WMI:

| Fuente WMI | Atributo | Estabilidad |
|-----------|----------|------------|
| `Win32_BaseBoard` | `SerialNumber` | Muy alta |
| `Win32_BaseBoard` | `Product` | Muy alta |
| `Win32_Processor` | `ProcessorId` | Muy alta |
| `Win32_BIOS` | `SerialNumber` | Muy alta |
| `Win32_BIOS` | `Version` | Alta |
| `Win32_DiskDrive` | `SerialNumber` | Media |
| `Win32_ComputerSystem` | `Model` | Alta |

El salt de dominio `"WoldVirtualP2P3D::SesionUnica::v1"` aísla el espacio de derivación.  
**El identificador nunca se guarda en texto plano en disco.**

#### `VSC#/Seguridad/Seguridad_sesion_unica/RegistroPcUnico.cs`
Almacena y verifica el **sello de cuenta única** en `%LocalAppData%\WoldVirtualP2P3D\Seguridad\pc_sello.json`.

- El sello es un JSON firmado con **HMAC-SHA256**.
- La clave HMAC se deriva en tiempo de ejecución desde WMI (nunca en disco).
- Copiar `pc_sello.json` a otro PC → clave distinta → firma inválida → bloqueado.
- Usa **comparación de tiempo constante** para evitar ataques de timing.

#### `VSC#/Seguridad/Seguridad_sesion_unica/SesionUnicaGuarda.cs`
Fachada pública que actúa en **3 puntos del flujo**:

```
PUNTO 1: OnCrearCuentaClicked()
  ComprobarAntesDeRegistro() → ¿sello existe? → Bloqueado

PUNTO 2: FormularioUsuarioWindow.OnCrearUsuarioClicked()
  SellarDespuesDeRegistro(uuid) → Escribe pc_sello.json

PUNTO 3: OnLoginClicked() (segunda barrera)
  ComprobarSesionActivaEnPc(uuid) → ¿sello de otro usuario?
  → "Este PC ya está conectado, cierre la sesión anterior"
```

### Archivos modificados
- `MainWindow.xaml.cs` — `OnCrearCuentaClicked()`: llama a `ComprobarAntesDeRegistro()`
- `MainWindow.xaml.cs` — `OnLoginClicked()`: llama a `ComprobarSesionActivaEnPc()` + nuevo helper `ObtenerUuidDelPerfil()`
- `FormularioUsuarioWindow.xaml.cs` — llama a `SellarDespuesDeRegistro(_uuid)` al guardar el perfil

---

## 🔑 Bloque 2 — Llave de Acceso Vinculada al Hardware

### Objetivo
La `llave_acceso.json` solo debe ser válida **en el PC donde se creó la cuenta**. Cualquier copia en otro equipo debe ser rechazada.

### Lógica implementada en `MainWindow.xaml.cs`

```
Credenciales OK
      ↓
¿llave.usuario == usuario logueado?  ✗ → Denegado
      ↓ ✓
¿llave.hardware_hash == hash del PC actual?  ✗ → "Llave de otro equipo"
      ↓ ✓
Rotar hash → guardar SOLO en el archivo que el usuario seleccionó
      ↓
Acceso concedido ✓
```

### Nuevos métodos en `MainWindow.xaml.cs`

| Método | Función |
|--------|---------|
| `ObtenerHardwareHashActual()` | Recalcula el hash WMI (OS + Motherboard + CPU → SHA-256) |
| `ObtenerWmiValor()` | Helper WMI reutilizable |
| `ObtenerUuidDelPerfil()` | Lee el UUID del perfil local para la comprobación de sesión activa |

### Cambio clave
Se **eliminó** la escritura de copia local de la llave durante el login. La llave válida es únicamente la que el usuario custodia en la carpeta que él eligió.

---

## 🎭 Bloque 3 — Corrección de Animaciones de Avatares (Godot 4)

### Diagnóstico de bugs

| Bug | Causa raíz |
|-----|-----------|
| Carrusel sin animación | `SLAV.gd` llamaba `.play()` directamente sobre `AnimationPlayer` con `AnimationTree` activo |
| Rutas hardcodeadas | `userbaseh_1.gd` usaba `$User1H1/hm1/AnimationTree` — solo existe en avatar `hm1` |
| Parámetros inexistentes | Escribía 7 parámetros de blend en árboles que solo tienen 5 |

### Archivos corregidos

- **`SLAV.gd`** — Añadido `_arrancar_idle()` que activa el `AnimationTree` correctamente con randomización de fase
- **`userbaseh_1.gd`** — `find_child()` dinámico, null-guards, detección de árboles de 5 vs 7 parámetros
- **`AVMJ1Ch3D.gd`** — Comprobación de existencia de parámetro antes de `set()` en `_update_tree()`

---

## 🎮 Bloque 4 — Fix de Foco de Teclado (Godot embebido en WPF)

### Problema
Las **teclas de flecha** no movían el avatar de forma consistente tras interactuar con la UI de WPF.

### Causas y soluciones en `GodotHwndHost.cs`

| # | Causa | Solución |
|---|-------|---------|
| 1 | WPF captura flechas como aceleradores antes de `TranslateAcceleratorCore` | `ComponentDispatcher.ThreadPreprocessMessage` → intercepta antes de WPF |
| 2 | `AttachThreadInput` con thread ID incorrecto (`GetCurrentThreadId`) | `GetWindowThreadProcessId(_hostHwnd)` ↔ `GetWindowThreadProcessId(_childHwnd)` |
| 3 | Foco perdido al hacer clic en controles WPF | `WndProc` override: `WM_SETFOCUS` → `SetFocus(_childHwnd)` |

### Nuevas P/Invoke
- `GetFocus()` — comprueba quién tiene el foco Win32 real
- `GetParent()` — helper `IsChildOf()` para recorrer jerarquía de ventanas

---

## ⚡ Bloque 5 — Sistema de Optimización de Texturas y Avatares (Godot 4)

### Archivo creado: `MTBGT/.../gdscrip/OptimizadorAvatares.gd`

Singleton Autoload registrado en `project.godot`.

| Técnica | API Godot 4 | Ahorro |
|---------|------------|--------|
| Redimensionado | `Image.resize(w, h, INTERPOLATE_LANCZOS)` | Hasta 75% VRAM por paso |
| Mipmaps | `Image.generate_mipmaps(renormalizar)` | GPU bandwidth + elimina aliasing |
| Compresión VRAM | `PortableCompressedTexture2D` | Sin pipeline de importación |
| LOD de malla | `GeometryInstance3D.lod_bias = 0.6` | LOD más agresivo en remotos |
| HLOD / Visibility range | `visibility_range_end = 80m` | Cull total de avatares lejanos |
| Throttle de animaciones | `AnimationTree.active = false` a > 30m | Ahorra CPU en remotos |
| LOD global | `mesh_lod_threshold = 4.0` | Más agresivo en toda la escena |

```gdscript
# Uso desde cualquier script GDScript:
OptimizadorAvatares.optimizar_nodo(avatar_node, true)   # remoto
OptimizadorAvatares.optimizar_nodo(mi_avatar, false)    # propio
OptimizadorAvatares.desregistrar_avatar(avatar_node)    # al destruir
```

---

## 📁 Bloque 6 — Eliminación de `test_user_data` junto al .exe

### Cambio
De `AppDomain.CurrentDomain.BaseDirectory\test_user_data\` a `%LocalAppData%\WoldVirtualP2P3D\`

### Archivos actualizados
`MainWindow.xaml.cs`, `FormularioUsuarioWindow.xaml.cs`, `DescargaLlaveWindow.xaml.cs`,
`RegistroWindow.xaml.cs`, `SemillaWalletWindow.xaml.cs`, `App.xaml.cs`

### Estructura final de datos en producción
```
%LocalAppData%\WoldVirtualP2P3D\
├── credentials.json
├── user\
│   ├── user_profile.json
│   ├── llave_acceso.json
│   ├── hardware_id.json
│   └── semilla_wallet.json
└── Seguridad\
    └── pc_sello.json
```

---

## 🔒 Diagrama de seguridad completo

```
CREAR CUENTA:
  [Botón Crear Cuenta]
       ↓
  ComprobarAntesDeRegistro()  →  ¿sello válido?  SÍ → Bloqueado
       ↓ NO
  Registro → Formulario → SellarDespuesDeRegistro(uuid) → pc_sello.json

LOGIN:
  [Usuario + Contraseña]  →  PBKDF2-SHA256 OK
       ↓
  ComprobarSesionActivaEnPc(uuid)  →  ¿otro usuario?  SÍ → Bloqueado
       ↓ NO
  [Seleccionar llave_acceso.json]
       ↓
  ¿llave.usuario == logueado?          NO → Denegado
  ¿llave.hardware_hash == hash WMI?    NO → "Llave de otro equipo"
       ↓ SÍ
  Rotar hash → WriteAllText(archivo elegido por usuario)
       ↓
  ✅ Acceso concedido → IniciarGodotMain()
```

---

## Auditoría de integración — 2026-10-26

**Estado: Parcial.** Esta rama conserva una instantánea de desarrollo; no es una release ni
acredita el funcionamiento de los flujos de runtime.

### Validaciones ejecutadas sobre esta integración

- [x] `dotnet build VSC#/Visor3D.csproj -p:SkipGodotAssets=true`: 0 errores y 0 advertencias.
- [x] 113 archivos Python analizados mediante AST, sin importar ni ejecutar módulos.
- [x] 3 archivos JSON parseados correctamente.
- [x] Índice sin `.exe`, `.dll`, `.zip`, `.pck`, datastores IPFS, ledgers, memorias ni `vault.enc`.
- [ ] Importación y ejecución en Godot: no hay ejecutable Godot localizado en esta validación.
- [ ] Pytest en copia aislada: las pruebas existentes pueden escribir datos, usar red, IPFS, Ollama o audio.
- [ ] Flujo real Registro → Semilla → Llave → Login.
- [ ] Tres instancias, migración de anfitrión y OTA de punta a punta.

### Deuda priorizada antes de una release

1. **Crítica — vault:** `STM_SGR/vault_openrouter.py` usa XOR con una semilla predeterminada y sin
   autenticación; no proporciona confidencialidad ni integridad adecuadas. Sustituirlo por cifrado
   autenticado y una clave externa obligatoria.
2. **Alta — descargas y OTA:** exigir digest/firma y fallar cerrados si faltan o no coinciden;
   reverificar antes de sustituir o ejecutar cualquier binario.
3. **Alta — persistencia:** no borrar ledger ni estado local cuando IPFS no esté disponible o la
   publicación no se haya verificado.
4. **Alta — red:** verificar hosts SSH y definir autenticación, autorización y límites para
   WebSocket, RPC y endpoints que modifican estado.
5. **Media — reproducibilidad:** completar dependencias de `STM_HRTS`, corregir su CI anidada y
   separar pruebas unitarias de las que requieren servicios o dispositivos.
6. **Media — evidencia:** las afirmaciones de sesiones anteriores no sustituyen las pruebas
   pendientes anteriores ni el checklist de `REGLAS_DE_ACTUALIZACION.md` §7.

### Reglas para continuar esta fase

1. No publicar un binario desde esta instantánea hasta completar el checklist obligatorio de release.
2. Mantener credenciales, vault, memoria, ledgers, caches y datos de usuario fuera de Git.
3. Conservar localmente las texturas e importaciones necesarias para el PCK, sin duplicarlas en commits.
4. Ejecutar pruebas con red, voz, IPFS u Ollama solo de forma explícita y sobre datos temporales.

---

## 🛠️ Stack tecnológico

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| Visor (frontend) | C# WPF | net8.0-windows |
| Motor 3D | Godot 4 | 4.7.2 |
| Renderizado | Direct3D 12 | Windows |
| Firma criptográfica | HMAC-SHA256 | .NET BCL |
| Derivación de clave | HKDF-SHA256 (RFC 5869) | .NET BCL |
| Hash contraseñas | PBKDF2-SHA256 | .NET BCL |
| Compresión texturas | `PortableCompressedTexture2D` | Godot 4 |
| Detección hardware | WMI `System.Management` | Windows |

---

*Generado el 2026-10-26 — Sesión Antigravity IDE*
