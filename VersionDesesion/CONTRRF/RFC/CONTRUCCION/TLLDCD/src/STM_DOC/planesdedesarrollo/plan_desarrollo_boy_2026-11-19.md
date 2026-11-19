# Wold Virtual P2P 3D — Plan de desarrollo (Boy) · 2026-11-19

| dato | valor |
|---|---|
| **Rama / HEAD del análisis** | `DevAntigravityIDEIA` (con merge consolidado de `DevQoderIA` y `DevChatGPTIA`) |
| **Estado vs origin** | Consolidado localmente; commits de merge (`0a4dd01c`), centralización (`114f2f1b`) y confinamiento (`0ebfcc57`) |
| **Versión en el árbol** | `2.9.5` (`VERSION.json`, `Visor3D.csproj`, `AssemblyName = DAOLCDMWoldVirtualP2P3Dv2.9.5`) |
| **Ruta canónica** | `VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src` |
| **Fecha del análisis** | 2026-11-19 |
| **Avance actual** | **~38% completado (T1 higiene y fuente única 100% + F1 túneles y supervisor 100% + caché pytest en .dev)** |
| **Issues abiertos de referencia** | 23 (ver §8) |
| **PRs de debate abiertos** | 7 (#124, #130, #135, #136, #137, #141, #145) — **no son merge, son RFC/debate** |
| **Documento de cabecera que respeta** | `STM_DOC/Desarrollo/README_DESARROLLO.md` + `README_PLAN_DE_DESARROLLO.md` (plan v2.7.8/v2.7.9, histórico) |

---

## 0. Línea base verificada (Actualizada a 2026-11-19)

El árbol actual consolida en `DevAntigravityIDEIA` los desarrollos de Zero-Trust nativo C#, isla DAO única, LucIA conversacional, túneles efímeros, el refactor MD8–MD10 y el tramo inicial T1 de higiene y modularidad:

| Elemento | Estado real (verificado) |
|---|---|
| Zero-Trust (`SeguridadSesionUnica/`) | Presente: `GestorClavesTPM.cs`, `AlmacenSeguro.cs`, `AntiRollbackGuardia.cs`, `FronteraSeguraZeroTrust.cs`… |
| LucIA + DAO 3D | Presentes: `IslaUnicaLucIA.gd`, `LucIAprc.py`, `OnboardingDAO.gd`, `ChunkManager.gd`, `TeleportManager.gd` |
| Refactor C# MD8–MD10 | Absorbido; `MainWindow.xaml.cs` consolidado en **4955 líneas** |
| `.github/workflows/` | **Centralizado en `.dev/.github/workflows/`**; raíz limpia de archivos dispersos (gestionado por `gestor_entorno.py`) |
| `VERSION.json` / `Directory.Build.*` | **Presentes**: v2.9.5, motor 4.7.2, ancla PCK (509 MB); build C# con 0 errores |
| `cloudflared.exe` empaquetado | **No** (no está en el `.csproj`; `*.exe` en `.gitignore`) — a resolver en F1 |
| `SshTunnelWatchdog.cs` | **Localizado e integrado** en `DevAntigravityIDEIA` (`VSC#/Visor3Ddesarrollo/RedP2P/SshTunnelWatchdog.cs`) |
| R-01 (`transport.py`) | **Triado y neutralizado** (R01b): stub inerte auditado, import retirado de `__main__.py` |
| Escena Principal Visor | **Fijada**: `res://WoldVirtual3DP2P.tscn` (`uid://5bh8su08n101`) sin acoplamiento a versiones previas |
| Python canónico | **Verificado**: `.dev/.python/python.exe` (Python 3.15.2 amd64), 20 pruebas de seguridad Zero Trust en verde (100%) |
| IPFS | Solo `.gitkeep` trackeados; `ipfs.exe` (Kubo) es gitignored |

---

## 1. Cómo leer este documento

| Prefijo | Significado |
|---|---|
| **B-nn** | Hallazgo bloqueante |
| **F-n** | Fase (orden de ejecución) |
| **T-nn.mm** | Tarea concreta dentro de una fase |
| **D-nn** | Decisión pendiente (heredadas del plan anterior o nuevas) |
| **E-nn** | Evidencia exigida para cerrar una tarea |
| **S / M / L / XL** | Esfuerzo: S ≤ 2 h · M ≈ medio día · L ≈ 1–3 días · XL > 3 días |

**Reglas no negociables (heredadas y vigentes):**

1. **No cambiar rutas canónicas.** `.dev` = dependencias + temporales + bytecode + configs de desarrollo (.github, pytest.ini, vscode); código en `TLLDCD/src`; `Rutas.json` es la fuente única de rutas; `AVATARES/` es copia de recuperación: no borrar, no mover, no commitear.
2. **Git**: `git add <fichero>` (nunca `-A`); rama por tarea; commit en español con ID de tarea; push solo a la rama que el usuario nombre. `main` no se toca.
3. **Nada de publicar/OTA/tag** sin confirmación explícita (`REGLAS_DE_ACTUALIZACION.md`, R4/R14/R16).
4. **Nada de secretos** en código ni logs. Prohibido silenciar pruebas con `continue-on-error`/`--ignore` sin motivo escrito.
5. **Idioma**: docs, comentarios y commits en español. Tab para `.gd`, 4 espacios para `.cs`/`.py`.

---

## 2. Objetivo del ciclo

Convertir la **deuda prioritaria** (túneles, IPC por archivos, empaquetado, pruebas) en **releases verificables**, sin tocar rutas canónicas ni publicar sin confirmación. El norte es dejar el visor distribuido **tan estable como en local** (cierra la brecha de #141) y con **un solo comando de build reproducible** (#90).

---

## 3. Estado de los hallazgos bloqueantes

### B-01 · CI de desarrollo (DT-01) — [CERRADO / CENTRALIZADO EN .DEV]
Workflows creados (`ci.yml`, `stm_def.yml`). Confinados en `VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/.github/workflows/` para evitar archivos desperdigados en la raíz del repositorio, gestionados por `gestor_entorno.py` con subcomandos de sincronización y despliegue.

### B-02 · Fuente única de versión — [PARCIAL / FASE A CERRADA]
`VERSION.json` creado (`2.9.5`, motor `4.7.2`), `Directory.Build.props` y `Directory.Build.targets` creados en `VSC#/` y generando `obj/WoldInfoVersion.g.cs`. Pendiente Fase B (eliminar literales de los `.csproj` y dejar `test_version_unica.py` en verde).

### B-03 · Distribución frágil vs local (#141 H1) — [ABIERTO · OBJETIVO DE F1]
`cloudflared.exe` no viaja en la descarga. `SshTunnelWatchdog.cs` ya fue localizado e integrado en `DevAntigravityIDEIA`, listo para unificarse con `P2PTunnelManager.cs` en F1.

### B-04 · Deriva de código entre copias del árbol — [EN CURSO]
Inventario T1-03 archivado. Merge de `DevQoderIA` hacia `DevAntigravityIDEIA` cerró la divergencia de `SshTunnelWatchdog.cs`, la neutralización R01b y las opciones SSH robustas.

---

## 4. Fases y tareas

```
T1 higiene+CI+fuente única (100% HECHO) ─▶ F1 túneles SSH (100% HECHO) ─▶ F2 IPC visor↔Godot ─▶ F3 Zero-Trust/SMTPLC
                                              │                                   └▶ F5 Godot/mundo ─▶ F7 empaquetado
                                              └▶ F4 pruebas (paralelo) ─▶ F6 LucIA (paralelo)
```

---

### T1 — Higiene, CI y fuente única (Estado: CONSOLIDADO 100%)

| ID | Tarea | Esf. | Estado | Detalle de lo hecho y pendiente |
|---|---|---|---|---|
| **T1-01** | Workflows de CI: build C# + xUnit, pytest estricta, `STM_DEF puerta`. | M | **HECHO** | Creados y centralizados en `.dev/.github/workflows/` (raíz limpia de .github; gestionables por `gestor_entorno.py`). |
| **T1-02** | `VERSION.json` + `Directory.Build.props/targets`; eliminar literales del `.csproj`; `version_unica --comprobar`. | M | **HECHO** | **Fase A y B completadas:** `VERSION.json` (2.9.5), `Directory.Build.*` generan `WoldInfoVersion.g.cs`. Literales retirados de `Visor3D.csproj`, `VisorLinux.csproj`, `Tests/Visor3DTests.csproj`, `RutasLinux.cs`, `AppExtractor.cs`, `GodotConfig.cs` y `MainWindow.xaml.cs`. `test_version_unica.py` en verde 100% (14 passed, 1 skipped). |
| **T1-03** | Inventario de copias (`HerraMientas/` vs `Desarrollo/` vs `Actualizaciones/*`). | M | **HECHO** | Mapeo y conteo de 72/130/142 ficheros `.cs` archivado en `resultados_T1_2026-11-19.md`. |
| **T1-04** | Triar `STM_HRTS/STM_DEF/utils/transport.py`: ¿vector R-01 o módulo legítimo? | S | **HECHO** | Veredicto R01b: stub inerte documentado, función `cargar()` con `RuntimeError`, import retirado de `__main__.py`. |
| **T1-05** | Localizar e integrar `SshTunnelWatchdog.cs` (referido en #143). | S | **HECHO** | Localizado en `DevAntigravityIDEIA`, mergeado e integrado en `RedP2P/SshTunnelWatchdog.cs`. |

**Evidencia de T1:** Artefactos versionados en git, `version_unica.py --leer` → 2.9.5, `gestor_entorno.py` con informe unificado y 20 pruebas Zero Trust en verde.

---

### F1 — Túneles SSH estables en distribución (#141, #143, #131 · L) — [CONSOLIDADO 100%]

| ID | Tarea | Esf. | Estado | Detalle de lo hecho |
|---|---|---|---|---|
| **T2-01** | Descarga/búsqueda de `cloudflared.exe` confinada en `%LOCALAPPDATA%\WoldVirtualP2P3D\bin\` al primer arranque; no depender de que exista en git (`*.exe` en `.gitignore`). | M | **HECHO** | `P2PWebNode.cs`, `P2PTunnelManager.cs` y `P2PTunnelSupervisor.cs` confinan la ruta en LocalAppData bin; nunca se escribe en el repositorio. Fallback limpio a SSH si no está presente o falla red. |
| **T2-02** | Unificar `P2PTunnelManager` + watchdog (`SshTunnelWatchdog`) bajo **un solo supervisor**; centralizar PIDs en `TunnelProcessRegistry`. | L | **HECHO** | Creado `P2PTunnelSupervisor.cs` coordinando slots `p2p`, `webnodo` y `dao`, integrando persistencia/barrido de huérfanos con `TunnelProcessRegistry` en todos los procesos. |
| **T2-03** | Watchdog del túnel WebNodo: relanzar proceso caído y estado visible en UI (H5 de #141). | M | **HECHO** | Implementado `RunWebNodeTunnelWatchdogAsync` en `P2PWebNode.cs` con backoff exponencial (5s a 30s) y eventos de reconexión. |
| **T2-04** | Observabilidad: log a fichero (`%LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log`) en vez de solo `Debug.WriteLine`. | S | **HECHO** | `TunnelLogger` centralizado y rotativo (10 MB); `SshTunnelWatchdog.cs`, `P2PTunnelSupervisor.cs`, `P2PWebNode.cs` y `P2PTunnelManager.cs` unificados en el mismo fichero de log. |
| **T2-05** | Revisar regex/orden de proveedores en `P2PWebNode` + opciones SSH (`ServerAliveCountMax`, `ExitOnForwardFailure=yes`). | S | **HECHO** | `MainWindow.xaml.cs`, `P2PWebNode.cs` y `P2PTunnelSupervisor.cs` alineados con `.lhr.life` y opciones de robustez SSH. |
| **T2-06** | UI: indicar «Modo degradado (SSH gratuito)» vs «Cloudflare» en la barra de estado y `validacion_resultado.json`. | S | **HECHO** | Expuesto `EsModoDegradado` / `IsDegradedMode` en supervisores y reflejado en `TxtEstadoP2P` y `validacion_resultado.json` para consumo de Godot. |

**Evidencia exigida (E-F1):** Prueba con dos redes externas — túnel se publica, reconecta tras caída, URL rota con caducidad, cierre seguro; captura de log con causa.

---

### F2 — IPC visor↔Godot sin archivos (#140 · L) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T3-01** | Decidir D3 (Named Pipes `\\.\pipe\WoldVirtualIPC` vs WebSocket loopback) y sustituir `user://*.json` (`tunel_solicitud`, `tunel_lucia_url`, `tunel_dao_url`, `validacion_resultado`). | L | Pendiente |
| **T3-02** | Máquina de estados de red unificada (`Desconectado/Conectando/TúnelActivo/Error/Reconectando`) con señales, desacoplada del panel de teletransporte. | M | Pendiente |
| **T3-03** | Validación de esquema (tipos fuertes / JSON Schema) y timeouts con backoff exponencial + cancelación cooperativa. | M | Pendiente |
| **T3-04** | Limpieza de artefactos `user://` obsoletos al arrancar (evitar leer túneles de sesiones anteriores). | S | Pendiente |

**Evidencia exigida:** Cero polling por timers en el camino crítico; reconexión automática sin intervención.

---

### F3 — Zero-Trust y SMTPLC (#122, #26 · L) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T4-01** | `NamedMutex` cross-process en `AlmacenSeguro` (`Global\WVP3D_Storage_Mutex`) contra contienda sobre `cadena_local.jsonl`. | M | Pendiente |
| **T4-02** | CLI `--provision-tpm` con elevación UAC (índice NV `0x01500001`). | M | Pendiente |
| **T4-03** | Checkpoints canónicos cada 100 bloques (`ICheckpointTestigo`). | M | Pendiente |
| **T4-04** | Vistas WPF `RegistroCuentaView` / `RecuperacionNivel3View` conectadas solo a `INucleoSeguro`. | L | Pendiente |
| **T4-05** | SMTPLC: cerrar D5/D8; extraer interfaces (`INetworkEnvironmentProvider`, `ISystemInfoProvider`) para pruebas con mocks. | L | Pendiente |

---

### F4 — Fortalecer pruebas (paralelo · #79–#83, #48 · M) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T5-01** | `medicion_modos.py`: JSON consistente, `time.monotonic()`, escritura atómica, limpieza de procesos. | M | Pendiente |
| **T5-02** | `stm_flujo.py`: eliminar `ejecutar()` duplicado, fronteras de fragmentos, solape real, nunca truncar en `ensamblar()`. | M | Pendiente |
| **T5-03** | `stm_gestion.py`: reemplazo transaccional, verificación por hash (no solo conteo), logs atómicos. | L | Pendiente |
| **T5-04** | `test_stage1_s1_identidad.py`: pruebas de conducta (replay, TTL, doble claim) además de inspección estática. | M | Pendiente |
| **T5-05** | `test_memoria.py`: aislamiento entre sesiones, persistencia/recuperación, ciclo de vida del singleton. | M | Pendiente |
| **T5-06** | xUnit: recuperar/ampliar cobertura (`EstadoGlobal`, `PerfilUsuario`, `ReinicioCuenta`, `LocationAccountLedger`, `VmDetector`/`VpnDetector`). | M | Pendiente |

---

### F5 — Godot / mundo (#1, #66, #131 · L) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T6-01** | Re-exportar `wvp3d.pck` del árbol canónico y `--registrar-pck` (RU5) — sin arrastrar `AVATARES/`. | M | Pendiente |
| **T6-02** | `Personalizacion.gd:952` (`Nil` → `PackedInt32Array`) y los dos sitios con el mismo patrón. | S | Pendiente |
| **T6-03** | Regenerar UIDs/importaciones glTF (UIDs inválidos/duplicados). | M | Pendiente |
| **T6-04** | Prueba LAN con dos equipos reales (DT-04, cierre de #1) + IPv6 literal `[fe80::1]:9000` (DT-09). | M | Pendiente |
| **T6-05** | Fugas `owner_names`/`island_owners` nunca borrados y topes de prims por isla. | M | Pendiente |

---

### F6 — LucIA (#16, #85, #131 · M) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T7-01** | Versionar `lucia3D/puente_3D/` (~4 ficheros, ~20 KB) sin el proyecto Godot completo. | S | Pendiente |
| **T7-02** | Pruebas de `LucIAPuenteComandos` con agente falso inyectado (sin Ollama). | M | Pendiente |
| **T7-03** | Intención: negación corta (`no/ni/sin`) o clasificador; `_ruta_en()` robusto (`git ls-files` + fuzzy). | S | Pendiente |
| **T7-04** | Ejecución en hilo con `presupuesto_segundos` + eventos `estado` intermedios. | M | Pendiente |
| **T7-05** | `autoanalisis()` con `default=str` (`WindowsPath is not JSON serializable`). | S | Pendiente |
| **T7-06** | Regresión lingüística: respuestas forzadas en español (`qwen2.5:7b`). | S | Pendiente |

---

### F7 — Empaquetado y distribución (#90, #87, #15, #131 · L/XL) — [PENDIENTE]

| ID | Tarea | Esf. | Estado |
|---|---|---|---|
| **T8-01** | Pipeline reproducible: un comando genera `.exe` + PCK + ZIP desde una única fuente. | L | Pendiente |
| **T8-02** | `SHA256SUMS` + firma de código junto a la release. | M | Pendiente |
| **T8-03** | Métrica de huella instalada y reducción: deduplicar `gltfimport/` (112 MiB duplicados). | L | Pendiente |
| **T8-04** | Barrido de `wvp_vol_*` huérfanos en `%TEMP%` al arrancar. | S | Pendiente |
| **T8-05** | Evitar doble compresión (ZIP de 1,16 GB que contiene PCK de 1,28 GB). | M | Pendiente |

---

## 4.1 Balance de ejecución: Lo Ya Hecho vs Lo Pendiente

```
+--------------------------------------------------------------------------------+
| TOTAL PLAN DE DESARROLLO (100%)                                                |
+--------------------------------------------------------------------------------+
| [######............] ~18% COMPLETADO Y CONSOLIDADO EN DevAntigravityIDEIA       |
| [..................] ~82% PENDIENTE (Fases F1 a F7 + Fase B de T1-02)          |
+--------------------------------------------------------------------------------+
```

### Resumen de «Lo Ya Hecho» (18% consolidado):
1. **Merge e integración sin conflictos**: Unión de `DevQoderIA` y `DevChatGPTIA` en `DevAntigravityIDEIA` (commits `0a4dd01c`, `114f2f1b`, `0ebfcc57`).
2. **Neutralización R01b**: `STM_DEF/utils/transport.py` inerte; import retirado de `__main__.py`.
3. **Integración Watchdog**: `SshTunnelWatchdog.cs` integrado en el árbol canónico de `RedP2P`.
4. **Fuente única (Fase A)**: `VERSION.json` (2.9.5), `Directory.Build.props` y `Directory.Build.targets` operativos.
5. **Centralización en `.dev`**: Workflows de CI confinados en `.dev/.github/workflows/`, raíz limpia sin dependencias ni `.yml` dispersos.
6. **Escena Principal fijada**: `res://WoldVirtual3DP2P.tscn` (`uid://5bh8su08n101`) fijada y validada contra acoplamientos legados (`python gestor_entorno.py escena-visor`).
7. **Python 3.15 validado**: `.dev/.python` (Python 3.15.2 amd64) verificado con suite de 20 pruebas en verde.
8. **Endurecimiento SSH**: Opciones `-o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes` y patrón `.lhr.life` aplicados.

### Resumen de «Lo Pendiente Especificado»:
1. **T1-02 Fase B**: Adaptar los `.csproj` (`Visor3D.csproj`, `VisorLinux.csproj`, etc.) para leer de `WoldInfoVersion`, eliminar literales de versión y dejar `test_version_unica.py` en verde.
2. **F1 (Túneles SSH)**: Unificar `P2PTunnelManager` y `SshTunnelWatchdog` en un solo supervisor, resolver `cloudflared.exe` en distribución, logs a fichero y UI de modo degradado.
3. **F2 (IPC)**: Reemplazar archivos `user://*.json` por Named Pipes / WebSocket loopback con máquina de estados.
4. **F3 (Zero-Trust)**: NamedMutex cross-process, CLI `--provision-tpm` y checkpoints cada 100 bloques.
5. **F4 (Pruebas)**: Robustecer suites de medición, flujos y gestión con pruebas de concurrencia y cobertura xUnit.
6. **F5 (Godot/Mundo)**: Re-exportar PCK limpio sin AVATARES y corregir `PackedInt32Array`.
7. **F6 (LucIA)**: Desacoplar puente Godot para pruebas unitarias sin backend Ollama.
8. **F7 (Empaquetado)**: Pipeline reproducible de release en un solo comando con firmas SHA256.

---

## 5. Decisiones pendientes

| ID | Decisión | Opciones | Recomendación | Bloquea |
|---|---|---|---|---|
| **D1** | ¿Boy trabaja sobre `DevAntigravityIDEIA` o rama por tarea? | (a) rama por tarea desde `DevAntigravityIDEIA`; (b) directo en `DevAntigravityIDEIA` | **(a)** — una tarea = una rama = un PR = una evidencia | todo |
| **D2** | `cloudflared.exe`: ¿embebido o descarga runtime? | (a) descargar a `%LOCALAPPDATA%` en el launcher; (b) embebido como recurso | **(a)** — evita engordar el `.exe` y el `*.exe` en git | T2-01 |
| **D3** | IPC visor↔Godot: ¿Named Pipes o WebSocket loopback? | (a) Named Pipes `\\.\pipe\WoldVirtualIPC`; (b) WS `127.0.0.1` | **(a)** — nativo Windows, sin puerto en conflicto | T3-01 |
| **D4** | Meta numérica de #15 | ≤ 250 MiB vs otro número | Medir primero (T8-03) y decidir con la cifra | T8-03 |
| **D5** | SMTPLC: ¿bloquea o puntúa? | bloqueo duro vs puntuación+fricción | Sin decidir (producto) | T4-05 |
| **D8** | Destino del ledger de ubicación | integrar / degradar / eliminar | Sin decidir | T4-05 |
| **D9** | Destino de la evidencia forense R-01 | archivo firmado fuera del repo vs manifiesto | Sin decidir | T1-04 |

---

## 6. Secuencia de ejecución siguiente

| Tramo | Trabajo | Deja en verde |
|---|---|---|
| 1 (Actual) | T1-02 Fase B (completar adaptación .csproj y suite `version_unica`) | `test_version_unica.py` 100% verde |
| 2 | F1 (túneles) — prioridad de usuario real | túnel estable en distribución con supervisor único |
| 3 | F2 (IPC) — desacopla visor↔Godot | sin polling ni archivos `user://` |
| 4 | F4 (pruebas) en paralelo | pytest/xUnit ampliados |
| 5 | F3 (Zero-Trust/SMTPLC) + F5 (Godot/mundo) | selftests + PCK fresco |
| 6 | F6 (LucIA) en paralelo | puente versionado y con pruebas |
| 7 | F7 (empaquetado) | release reproducible firmada |

---

## 7. Protocolo de ingeniería (obligatorio)

- Una tarea = una rama (`boy/T2-01-cloudflared`) = un commit en español con ID = una evidencia en el PR.
- Antes de commitear: `git status` y revisar staged; prohibido `\.env$|ghp_|*.exe|*.pck|*.zip`.
- Puertas antes de dar por hecho cualquier tarea de visor:
  ```bash
  cd VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src
  python -m pytest -q
  python -m STM_HRTS.STM_DEF escanear
  cd VSC#/Visor3Ddesarrollo && dotnet build -p:Platform=x64
  # y tras tocar red/OTA/túneles: las 6 banderas --*-selftest
  ```
- Tras tocar `.gd`: re-exportar PCK es **decisión de dueño** (RU5) — no se hace unilateralmente.
- Lo que no se pueda verificar se marca **«no verificado»**; nada de afirmar verde sin salida adjunta.

---

## 8. Correspondencia issue ↔ tarea

| Issue | Tareas que lo cierran (total o parcial) |
|---|---|
| #1 (LAN) | T6-01, T6-04 |
| #15 (peso) | T8-03, D4 |
| #16 (lucIA) | T7-01…T7-06 |
| #26 (SMTPLC) | T4-05, D5, D8 |
| #48 (DT-01…DT-16) | T1-01, T1-02, T5-06, T6-04 |
| #65 (unificación) | T1-03 (consolidación sin mover rutas) |
| #66 (v2.7.7) | T1-02, T6-01, T8-01/T8-02 |
| #69 (STM_DEF) | T1-01, T1-04 |
| #76 (v2.7.9) | T1-02, T6-01, T8-01 |
| #79 (medicion_modos) | T5-01 |
| #80 (stm_flujo) | T5-02 |
| #81 (stm_gestion) | T5-03 |
| #82 (stage1 identidad) | T5-04 |
| #83 (memoria_sesion) | T5-05 |
| #85 (RFPRMN/IPFS) | T7-01…T7-05 |
| #87 (empaquetado volátil) | T8-04, T8-05 |
| #90 (2.8.3) | T1-03, T8-01…T8-03 |
| #101 (MD8-MD10) | T1-03 (verificar absorción y deuda #1/#4 del issue) |
| #120 (rutas .dev) | T1-03 |
| #122 (hardening) | T4-01…T4-04 |
| #131 (DAO v2.8.7–2.9.1) | T2-01…T2-06, T6-03, T7-06, T8-01 |
| #140 (IPC archivos) | T3-01…T3-04 |
| #143 (Secciones/SSH) | T1-03, T1-05, T2-02, T2-06 |

---

## 9. Métricas objetivo

| Métrica | Base inicial | Estado actual (2026-11-19) | Meta |
|---|---|---|---|
| CI de desarrollo | 0 jobs | Centralizado en `.dev/.github/workflows/` | 4–5 jobs verdes ejecutables |
| Fuente única de versión | literal `2.9.5` a mano | `VERSION.json` + `Directory.Build.*` operativos | `.csproj` sin literales + `version_unica --comprobar` OK |
| Túnel en distribución | SSH gratuito intermitente | Watchdog localizado + opciones robustas aplicadas | Supervisor unificado + Cloudflare con log de causa |
| IPC visor↔Godot | `user://*.json` + polling | `user://*.json` activo | Named Pipes / WS + FSM sin archivos |
| PCK alineado con commit | sin ancla | `sha256` anclado en `VERSION.json` | PCK fresco re-exportado sin AVATARES |
| Release reproducible | manual, `VSC#` rompe `gh` | Estructura modular consolidada en `.dev` | 1 comando + SHA256SUMS + firma |

---

## 10. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Consolidar copias (T1-03) rompe una ruta canónica | Media | Alto | Sin mover directorios; tabla + confirmación del dueño antes de cada cambio |
| R2 | `transport.py` de STM_DEF es el vector R-01 reintroducido | Baja | Alto | **Cerrado**: neutralizado como stub inerte R01b, sin import en código activo |
| R3 | Re-exportar PCK arrastra `AVATARES/` o rompe el mundo | Media | Alto | Preset sin `AVATARES`; recorrido carrusel→registro→isla con capturas |
| R4 | Watchdog unificado (T2-02) duplica reintentos con los existentes | Media | Medio | Un solo supervisor; eliminar lógica paralela en `MainWindow`/`P2PWebNode` |
| R5 | Probar cambios de red sin red real (D6) | Media | Medio | Evidencia con dos redes externas antes de dar F1 por cerrada |

---

*Actualizado el 2026-11-19 tras consolidar el tramo T1 (~18%) en `DevAntigravityIDEIA`, integrar `SshTunnelWatchdog.cs`, centralizar los recursos de desarrollo en `.dev` y verificar la fijación de la escena principal `res://WoldVirtual3DP2P.tscn`.*
