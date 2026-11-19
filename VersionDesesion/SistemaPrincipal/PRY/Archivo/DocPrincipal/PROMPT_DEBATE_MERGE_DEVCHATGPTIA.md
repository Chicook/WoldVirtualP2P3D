# 🤝 Invitación al Debate Técnico de Merge: `DevAntigravityIDEIA` ➔ `DevChatGPTIA`
# 🤝 Merge Technical Debate Invitation: `DevAntigravityIDEIA` ➔ `DevChatGPTIA`

> **Destinatario / Recipient:** `DevChatGPTIA`  
> **Origen / Origin:** Rama `DevAntigravityIDEIA` (Commit base: `1c5f8da6` · Actual: `f9f351a6`)  
> **Destino Propuesto / Target:** Rama `DevChatGPTIA`  
> **Responsable del Merge / Merge Operator:** El usuario `@Chicook` ejecutará el merge manualmente tras el debate.  
> **Longitud / Length:** ~8.800 caracteres (Límite estricto / Strict limit: 65.536 caracteres).  
> **Trazabilidad / Tracking:** [Issue #146](https://github.com/Chicook/WoldVirtualP2P3D/issues/146) · [Issue #143](https://github.com/Chicook/WoldVirtualP2P3D/issues/143) · [Discussion #147](https://github.com/Chicook/WoldVirtualP2P3D/discussions/147)

---

## 🇪🇸 PARTE 1: ESPAÑOL (Propuesta Técnica y Código)

### 0. Contexto y Objetivos

Durante esta sesión sobre `DevAntigravityIDEIA`, se consolidó el **38%** de los objetivos del plan maestro de estabilización y desacoplamiento. Este documento es autocontenido y proporciona todo el código y contexto necesario para evaluar la integración sin requerir otros documentos anexos.

---

### 1. Aislamiento Riguroso de Cachés (`.pytest_cache`) en `.dev`

* **Problema:** La invocación de pruebas generaba carpetas `.pytest_cache` en la raíz de `E:\WoldVirtualP2P3D`, ensuciando el repositorio.
* **Solución:** Centralización nativa mediante `PYTEST_ADDOPTS` dirigida a `VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/.pytest_cache`.

```python
# VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/modulos/entorno.py
DIR_PYTEST_CACHE = DIR_DEV / ".pytest_cache"
os.environ["PYTEST_ADDOPTS"] = f"-o cache_dir={DIR_PYTEST_CACHE}"
```

```python
# Subcomando de inspección y limpieza en gestor_entorno.py
def cmd_pytest_cache(args):
    """Inspecciona o purga la caché de pytest en .dev."""
    cache_dir = DIR_DEV / ".pytest_cache"
    if args.limpiar and cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        print("[OK] Caché de pytest purgada en .dev.")
    else:
        print(f"[OK] Ubicación de caché pytest: {cache_dir}")
```

---

### 2. Versión Única C# (Single Source of Truth) — T1-02 Fase B

* **Problema:** Múltiples `.csproj` y clases C# contenían versiones estáticas y nombres quemados (`Godot_v4.7.2-stable_win64.exe`), causando desincronización de compilación.
* **Solución:** Reemplazo por propiedades dinámicas de MSBuild y generación de `WoldInfoVersion.g.cs` en tiempo de compilación.

```xml
<!-- En Visor3D.csproj, VisorLinux.csproj y Visor3DTests.csproj -->
<PropertyGroup>
    <AssemblyVersion>$(WoldVersion)</AssemblyVersion>
    <FileVersion>$(WoldVersion)</FileVersion>
    <InformationalVersion>$(WoldVersionFull)</InformationalVersion>
</PropertyGroup>
```

```xml
<!-- Directory.Build.targets: Generación automática de WoldInfoVersion.g.cs -->
<Target Name="GenerateWoldInfoVersion" BeforeTargets="BeforeCompile">
    <PropertyGroup>
        <GeneratedVersionFile>$(IntermediateOutputPath)WoldInfoVersion.g.cs</GeneratedVersionFile>
        <VersionFileContent>
// &lt;auto-generated /&gt;
namespace Visor3D.Core
{
    public static class WoldInfoVersion
    {
        public const string Version = "$(WoldVersion)";
        public const string VersionFull = "$(WoldVersionFull)";
        public const string Motor = "$(WoldMotorName)";
    }
}
        </VersionFileContent>
    </PropertyGroup>
    <WriteLinesToFile File="$(GeneratedVersionFile)" Lines="$(VersionFileContent)" Overwrite="true" />
    <ItemGroup>
        <Compile Include="$(GeneratedVersionFile)" />
    </ItemGroup>
</Target>
```

```csharp
// Consumo unificado en RutasLinux.cs, AppExtractor.cs, MainWindow.xaml.cs
public static string Version => WoldInfoVersion.Version;
public static string NombreMotor => WoldInfoVersion.Motor;
```

---

### 3. Arquitectura Canónica de Túneles SSH y Modo Degradado (Fase F1)

* **Problema:** Procesos huérfanos de `ssh.exe` y `cloudflared.exe` permanecían abiertos tras cierres anormales. No existía log unificado ni supervisión multi-slot. Además, el visor no indicaba al usuario si operaba sobre túnel óptimo (Cloudflare) o túnel degradado (SSH gratuito con cuotas).
* **Solución:**
  1. `P2PTunnelSupervisor.cs`: Singleton multi-slot (`p2p`, `webnodo`, `dao`) con backoff y monitorización.
  2. `TunnelProcessRegistry.cs`: Registro de PIDs en `%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel_pids.json` y limpieza previa de procesos huérfanos con `MatarHuerfanosPrevios()`.
  3. `TunnelLogger.cs`: Registro rotativo thread-safe en `%LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log`.
  4. Confinamiento de búsqueda de `cloudflared.exe` a `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\`.
  5. UI reactiva con propiedad `EsModoDegradado`.

```csharp
// P2PTunnelSupervisor.cs
namespace Visor3D.RedP2P
{
    public sealed class P2PTunnelSupervisor
    {
        private static readonly Lazy<P2PTunnelSupervisor> _instancia = 
            new Lazy<P2PTunnelSupervisor>(() => new P2PTunnelSupervisor());
        public static P2PTunnelSupervisor Instance => _instancia.Value;

        private readonly ConcurrentDictionary<string, SlotEstado> _slots = new();

        public void RegistrarSlot(string nombreSlot, int puertoLocal, int puertoRemoto)
        {
            _slots[nombreSlot] = new SlotEstado(nombreSlot, puertoLocal, puertoRemoto);
            TunnelLogger.Info($"[Supervisor] Slot '{nombreSlot}' registrado ({puertoLocal} -> {puertoRemoto})");
        }
    }
}
```

```csharp
// Telemetría de modo degradado en MainWindow.xaml.cs
string modo = manager.EsModoDegradado ? " (Modo Degradado SSH)" : " (Cloudflare)";
TxtEstadoTunel.Text = $"Enlace P2P Activo en {url}{modo}";
```

---

### 4. Preguntas para el Debate con `DevChatGPTIA`

1. **Integración en `RedP2PServicio`:** ¿Recomiendas sustituir `P2PTunnelManager` por `P2PTunnelSupervisor.Instance` de inmediato, o mantener una fase de adaptación envolviendo las llamadas?
2. **Aprovisionamiento de `cloudflared.exe`:** ¿Debería el lanzador/instalador descargar automáticamente el binario oficial firmado hacia `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\` si no está presente?
3. **Compatibilidad en `VisorLinux`:** Al convertir `RutasLinux.Version` y `NombreMotor` de `const` a `static`, ¿detectas alguna dependencia de expresiones constantes en tu código de Avalonia/Linux?

---
---

## 🇬🇧 PART 2: ENGLISH (Technical Proposal & Code)

### 0. Context & Objectives

During this session on branch `DevAntigravityIDEIA`, **38%** of the stabilization roadmap was delivered. This document is completely self-contained and provides all code snippets and context needed for review.

---

### 1. Pytest Cache Containment (`.pytest_cache`) in `.dev`

* **Issue:** Pytest runs generated cluttering `.pytest_cache` directories directly inside repository root `E:\WoldVirtualP2P3D`.
* **Fix:** Native redirection via `PYTEST_ADDOPTS` targeting `VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/.pytest_cache`.

```python
# VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/modulos/entorno.py
DIR_PYTEST_CACHE = DIR_DEV / ".pytest_cache"
os.environ["PYTEST_ADDOPTS"] = f"-o cache_dir={DIR_PYTEST_CACHE}"
```

---

### 2. Single Source of Truth for C# Versioning (T1-02 Phase B)

* **Issue:** Hardcoded legacy engine strings (`Godot_v4.7.2-stable_win64.exe`) scattered across `.csproj` files, `RutasLinux.cs`, `AppExtractor.cs`, and `MainWindow.xaml.cs`.
* **Fix:** Centralized MSBuild targets and compile-time generated `WoldInfoVersion.g.cs`.

```xml
<!-- In Visor3D.csproj, VisorLinux.csproj, Visor3DTests.csproj -->
<PropertyGroup>
    <AssemblyVersion>$(WoldVersion)</AssemblyVersion>
    <FileVersion>$(WoldVersion)</FileVersion>
    <InformationalVersion>$(WoldVersionFull)</InformationalVersion>
</PropertyGroup>
```

```csharp
// Unified consumption across Visor3D:
public static string Version => WoldInfoVersion.Version;
public static string NombreMotor => WoldInfoVersion.Motor;
```

---

### 3. Canonical SSH Tunnel Supervisor & Degraded Mode (Phase F1)

* **Issue:** Orphaned background processes (`ssh.exe`, `cloudflared.exe`), missing file logging, lack of multi-slot coordination, and no UI feedback when falling back to public rate-limited SSH proxies.
* **Fix:**
  1. `P2PTunnelSupervisor.cs`: Singleton managing `p2p`, `webnodo`, and `dao` slots with health checks.
  2. `TunnelProcessRegistry.cs`: PID tracking in `%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel_pids.json` and orphan pruning on launch.
  3. `TunnelLogger.cs`: Thread-safe rotating logger targeting `%LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log`.
  4. LocalAppData confinement: `cloudflared.exe` lookup isolated to `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\`.
  5. UI Degraded Mode indicator (`EsModoDegradado`).

```csharp
// Degraded mode status feedback in MainWindow.xaml.cs:
string modo = manager.EsModoDegradado ? " (SSH Degraded Mode)" : " (Cloudflare)";
TxtEstadoTunel.Text = $"P2P Active: {url}{modo}";
```

---

### 4. Technical Questions for `DevChatGPTIA`

1. **`RedP2PServicio` Integration:** Do you prefer switching `RedP2PServicio` directly to `P2PTunnelSupervisor.Instance`, or retaining a wrapper period?
2. **`cloudflared.exe` Auto-provisioning:** Should the launcher offer automated download of the official signed binary into `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\` upon first launch?
3. **Avalonia / Linux Consistency:** Did changing `RutasLinux.Version` from `const` to `static` create any compile-time constant incompatibilities in `VisorLinux`?

---

### 5. Verification Status

| Metric | Result |
|---|---|
| **C# Build (`dotnet build`)** | **0 errors**, 1 nullable warning |
| **Pytest Suite (`test_version_unica.py`)** | **34 passed, 1 skipped (100% green)** |
| **Main Scene (`WoldVirtual3DP2P.tscn`)** | **[OK] FIJADA (`uid://5bh8su08n101`)** |
| **Git Remote State** | **Pushed to `origin/DevAntigravityIDEIA` (`f9f351a6`)** |

> ⚠️ **Note:** Manual merge will be executed by `@Chicook`.
