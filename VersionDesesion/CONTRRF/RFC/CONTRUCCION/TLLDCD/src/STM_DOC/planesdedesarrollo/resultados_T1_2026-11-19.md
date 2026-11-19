# Resultados T1 + F1 y Consolidación (~38% del Plan de Desarrollo · 2026-11-19)

Avance verificado del tramo acumulado (~38%) del [plan_desarrollo_boy_2026-11-19.md](plan_desarrollo_boy_2026-11-19.md).
Consolidado e integrado en la rama canónica **`DevAntigravityIDEIA`** tras resolver el merge de `DevQoderIA`, centralizar la jerarquía modular y CI en `.dev`, resolver la caché de pytest en `.dev/.pytest_cache`, cerrar la versión única C# (T1-02 Fase B) y consolidar el supervisor de túneles y watchdog (F1 · T2-01 a T2-06). Sin merge a `main`.

---

## 1. Lo Ya Hecho (Completado y Verificado en `DevAntigravityIDEIA`)

### 1.1 Centralización de Caché Pytest en `.dev/.pytest_cache`
- Se eliminó la carpeta `.pytest_cache` suelta de la raíz del repositorio.
- Se configuró `modulos/entorno.py` con `PYTEST_ADDOPTS = "-o cache_dir=.dev/.pytest_cache -c .dev/pytest.ini"`.
- `run_pytest.bat` y `run_pytest.ps1` inyectan automáticamente `PYTEST_ADDOPTS`.
- Se añadió el subcomando `python gestor_entorno.py pytest-cache` y salvaguardas en `limpiar_cache_raiz()`.
- `.gitignore` configurado para ignorar `**/.pytest_cache/` y `/.pytest_cache/`.

### 1.2 T1-02 (Fase A y Fase B) · Fuente Única de Versión (100% CERRADO)
- `src/VERSION.json` verificado (`2.9.5`, motor `4.7.2`).
- `VSC#/Directory.Build.props` y `Directory.Build.targets` generan `obj/WoldInfoVersion.g.cs` de forma reproducible.
- Eliminados todos los literales hardcodeados de versión:
  - `HerraMientas/Visor3D.csproj`: `$(WoldVersion)` en AssemblyName, Product, Version, AssemblyVersion, FileVersion, Title, Description.
  - `VisorLinux/VisorLinux.csproj`: `$(WoldVersion)` en Version y Description.
  - `Tests/Visor3DTests.csproj`: `$(WoldVersion)` en Version.
  - `VisorLinux/Linux/RutasLinux.cs`: utiliza `WoldInfoVersion.Version` y `WoldInfoVersion.Motor`.
  - `AppExtractor.cs`, `GodotConfig.cs` y `MainWindow.xaml.cs`: motor Godot referenciado dinámicamente con `WoldInfoVersion.Motor`.
- `version_unica.CSPROJ` actualizado con los proyectos reales (`HerraMientas/Visor3D.csproj`, `VisorLinux/VisorLinux.csproj`, `Tests/Visor3DTests.csproj`).
- **Pruebas en verde**: `pytest tests/STM_test3/test_version_unica.py` (14 passed, 1 skipped); `version_unica.py --comprobar` OK.
- `dotnet build Visor3D.csproj -p:SkipGodotAssets=true` compila con **0 errores**.

### 1.3 F1 · Túneles SSH Estables en Distribución (#141, #143, #131 · 100% CERRADO)
- **T2-01 (Confinamiento de `cloudflared.exe`)**:
  - `P2PWebNode.cs`, `P2PTunnelManager.cs` y `P2PTunnelSupervisor.cs` buscan o descargan `cloudflared.exe` exclusivamente en `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\cloudflared.exe`. Nunca se guarda en el repositorio ni en la carpeta base.
  - Si falta o no hay red, realiza fallback inmediato y transparente a los servidores SSH.
- **T2-02 (Supervisor Unificado y PIDs)**:
  - Implementado `P2PTunnelSupervisor.cs` bajo `Visor3D.RedP2P`, orquestando los 3 slots (`p2p` en 7890, `webnodo` en 8082, `dao` en 7892).
  - Integrado `TunnelProcessRegistry` en todos los slots: persiste PIDs en `tunnel-{slot}.pid` y realiza barrido de huérfanos al arrancar (`BarrerHuerfano`).
- **T2-03 (Watchdog WebNodo)**:
  - Implementado `RunWebNodeTunnelWatchdogAsync` en `P2PWebNode.cs`: detecta caídas de proceso con `WaitForExitAsync`, reconecta automáticamente con backoff exponencial (5s a 30s) y emite `OnTunnelDied` / `OnTunnelReconnected`.
- **T2-04 (Observabilidad Unificada)**:
  - Implementado `TunnelLogger`: todas las trazas de túneles (`P2PTunnelSupervisor`, `SshTunnelWatchdog`, `P2PWebNode`, `P2PTunnelManager`) se escriben a `%LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log` con rotación a 10 MB.
- **T2-05 (Robustez SSH y Regex)**:
  - Regex `.lhr.life` y opciones de robustez (`-o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o ConnectTimeout=15`) aplicadas en todos los proveedores SSH (`localhost.run`, `serveo.net`).
- **T2-06 (Modo Degradado en UI)**:
  - Propiedad `EsModoDegradado` / `IsDegradedMode` expuesta.
  - `MainWindow.xaml.cs` refleja en `TxtEstadoP2P` y en `validacion_resultado.json`: `"🟢 Cloudflare Túnel"` vs `"🟡 Modo degradado (SSH gratuito)"`.

### 1.4 Hitos Previos Verificados
- Triaje y neutralización R01b de `transport.py`.
- Integración de `SshTunnelWatchdog.cs`.
- Inventario de copias del árbol C# (72/130/142 ficheros).
- Centralización modular de CI en `.dev/.github/workflows/` (raíz limpia).
- Fijación de escena canónica `res://WoldVirtual3DP2P.tscn` (`uid://5bh8su08n101`).
- Entorno Python canónico `.dev/.python/python.exe` (3.15.2 amd64), 20 pruebas Zero Trust en verde (100%).

---

## 2. Lo Pendiente Especificado (Backlog Inmediato a Partir del 38%)

### 2.1 F2 — IPC Visor ↔ Godot sin Archivos (#140 · L)
- **T3-01**: Sustituir `user://*.json` (`tunel_solicitud`, `tunel_lucia_url`, `tunel_dao_url`, `validacion_resultado`) por Named Pipes (`\\.\pipe\WoldVirtualIPC`) o WebSocket loopback.
- **T3-02**: Máquina de estados de red unificada (`Desconectado/Conectando/TúnelActivo/Error/Reconectando`) desacoplada del panel de teletransporte.
- **T3-03**: Validación de esquema y timeouts con backoff exponencial.
- **T3-04**: Limpieza de artefactos obsoletos de sesiones previas en `user://`.

### 2.2 F3 — Zero-Trust y SMTPLC (#122, #26 · L)
- **T4-01**: `NamedMutex` cross-process en `AlmacenSeguro` (`Global\WVP3D_Storage_Mutex`) contra contienda sobre `cadena_local.jsonl`.
- **T4-02**: CLI `--provision-tpm` con elevación UAC (índice NV `0x01500001`).
- **T4-03**: Checkpoints canónicos cada 100 bloques (`ICheckpointTestigo`).
- **T4-04**: Vistas WPF `RegistroCuentaView` / `RecuperacionNivel3View` conectadas solo a `INucleoSeguro`.
- **T4-05**: SMTPLC: cerrar D5/D8; extraer interfaces (`INetworkEnvironmentProvider`, `ISystemInfoProvider`) para pruebas con mocks.

### 2.3 F4 — Fortalecer Pruebas (paralelo · #79–#83, #48 · M)
- **T5-01**: `medicion_modos.py`: JSON consistente, `time.monotonic()`, escritura atómica.
- **T5-02**: `stm_flujo.py`: eliminar duplicados, límites de fragmentos y solape real.
- **T5-03**: `stm_gestion.py`: reemplazo transaccional y verificación por hash.

### 2.4 F5 — Godot / Mundo (#141 H2, #94 · M)
- Re-exportar `wvp3d.pck` limpio sin `AVATARES/`.
- Corregir `PackedInt32Array` en `Personalizacion.gd:952`.

### 2.5 F6 — LucIA (#124, #130 · M)
- Versionado limpio de `puente_3D` y pruebas de `LucIAPuenteComandos` con agente falso inyectado.

### 2.6 F7 — Empaquetado y Distribución (#90, #141 · L)
- Pipeline reproducible de un comando para `.exe` + PCK + ZIP firmado con SHA256SUMS.
