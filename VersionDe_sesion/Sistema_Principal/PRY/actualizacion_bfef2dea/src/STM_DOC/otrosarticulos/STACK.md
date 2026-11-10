# Stack tecnológico — actual y objetivo

**Documento técnico de referencia** · Rama `development` · 2026-11-02

> Este documento describe **el stack que el proyecto usa hoy** (as-is, v2.7.5 en
> `main` @ `19cc65e`) y **el stack que exige el plan de implementación**
> (to-be, Etapas 0–6), para poder distinguir de un vistazo qué hay instalado, qué
> funciona de verdad, qué está simulado y qué habrá que añadir.
>
> Compañeros: `README.md` / `README_EN.md` (producto y uso), `docs/IMPLEMENTATION_PLAN.md`
> / `docs/IMPLEMENTATION_PLAN_EN.md` (hallazgos y etapas). Los identificadores
> `V*/H*/M*/L*/G*` citados aquí remiten al catálogo de hallazgos del plan.
> Versión en inglés de este documento: `docs/STACK_EN.md`.

---

## 0. Convenciones

- `SRC = VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src`.
- **As-is** = medido sobre v2.7.5 (`main` @ `19cc65e`). **To-be** = lo que las
  Etapas 0–6 del plan requieren, nada más.
- «Simulado» no es un insulto: es el estado verificado del código (plan V1/V5/M13).

---

## 1. Stack actual (as-is, v2.7.5)

### 1.1 Productos y lenguajes

| Capa | Tecnología | Versión exacta | Dónde |
|---|---|---|---|
| Visor Windows | C# / .NET (**WPF**), self-contained single-file | `net8.0-windows` | `$SRC/VSC#/` (`Visor3D.csproj`) |
| Visor Linux | C# / .NET (**Avalonia**), UI 100 % en C# (sin .axaml) | `net8.0` + Avalonia `11.2.3` (Desktop, Themes.Fluent, Fonts.Inter) | `$SRC/VSC#/VisorLinux/` |
| Motor del mundo | **Godot** embebido en el visor, GDScript | Godot `4.7.2` | `$SRC/MTBGT/WoldVirtualP2P3D/` (156 ficheros, ~10,2k líneas) |
| Cognición (LucIA) | Python (paquetes, no integrada en el visor) | `requires-python >= 3.10` | `$SRC/STM_HRTS`, `LC_STM`, `SBSTM`, `STM_IA`, `STMGNRL`, … |
| Herramienta refactor | Python (CONTRRF/RFPRMN, fuera del build) | — | `VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/` |

**Paquetes NuGet del visor** (completo, no hay más): `System.Management 8.0.0`
(huella de máquina por WMI), `NAudio 2.3.0` (audio), `AForge.Video 2.2.5` +
`AForge.Video.DirectShow 2.2.5` (webcam). Sin frameworks de UI adicionales, sin
JSON de terceros, sin MQTT/ZeroMQ: la red es `System.Net.WebSockets` del BCL.

**Manifiesto Python** (`$SRC/STM_HRTS/pyproject.toml`, único del repo):
`lucia-woldvirtualp2p3d 2026.5.0` · runtime `numpy>=1.24.0` · dev
`pytest>=7.0.0` + `ruff>=0.1.0` (line-length 120, target py310) · entry points
`lucia` → `STMGNRL.mainLCSTM:main` y `hrts`. No hay torch, sklearn, ni
websockets/pip-audit: todo lo demás del área Python usa stdlib + los servicios
externos de §1.4.

### 1.2 Red y distribución (P2P/WebNodo)

| Pieza | Implementación | Detalle |
|---|---|---|
| Relé de chat | Servidor WebSocket propio (`ChatRelayServer.cs`) | Escucha en `IPAddress.Any`, sin token post-handshake (G1) |
| Descubrimiento LAN | Beacon UDP | Puerto 8912 (datos del payload; 8911 solo fallback) |
| Puertos fijos | Chat 8920, config 8911/7890, ~30 literales | Solo la unión LAN respeta el beacon (L9) |
| Portal público | `WebNodoService.cs`: HTTP + proxy TCP + rate-limit | IP de cliente tomada de cabeceras falsificables (H2) |
| Túneles efímeros | `cloudflared.exe` descargado en caliente | Sin verificación de digest ni firma (M19) |
| Multiplayer Godot | `gdscrip/Red.gd` + RPCs `any_peer` | Modelo «el host manda»; identidad = UUID autoafirmado (V2) |

### 1.3 Seguridad, identidad y datos

- **Identidad**: bip39 (`VSC#/Seguridad/`), huella de máquina vía WMI,
  `llave_acceso.json` sin firmar con binding eludible (M18).
- **OTA**: descarga *fail-closed* por SHA-256 (`UpdateDownloader.cs:157-183`) y
  extracción con guarda anti Zip-Slip (`AppExtractor.cs:179-181`); la etapa
  *apply* no re-verifica ni tiene rollback (H3).
- **Blockchain local**: PoW doble-SHA-256 (dificultad 2), Merkle, escritura
  atómica tmp+replace, RPC en `127.0.0.1:8545` (`STM_BKCH/BKSVCB.py`). Real.
- **IPFS**: orquestación de Kubo real (`STMIPFS`), wrapper triplicado (M11),
  shim local con CIDs `QmLocal…` falsos cuando no hay daemon (M13).
- **Persistencia**: todo JSON — ledger, `registro.cfg`, `islas_registro.cfg`,
  `p2p_session.json` (`user://`), pesos neuronales al cerrar. **Sin backup ni
  exportación** de mundos o ledger (G5).
- **Secretos**: `OPENROUTER_API_KEY` + `OPENROUTER_VAULT_PW`
  (`SBSTM/IAFREE.py`, `STM_SGR/vault_openrouter.py`); semilla maestra del vault
  hardcodeada (M8). Repo público: `.env` ignorado, `.env.example` con placeholders.

### 1.4 Servicios externos

| Servicio | Uso | Estado |
|---|---|---|
| OpenRouter (LLM) | `IAFREE.py` (chat cognitivo) | Real, requiere API key |
| Ollama (`localhost:11434`) | Modelos GGUF locales (`IALOCAL/`) | Descargas sin `.part` (L2) |
| HuggingFace / ONNX | Modelos de voz | 6 librerías no declaradas, sin digest (M5) |
| gTTS | Voz de respaldo | Prueba que toca la red (L13) |
| Cloudflare (cloudflared) | Túneles efímeros del portal | Binario no verificado (M19) |
| Kubo (IPFS) | Publicación descentralizada | Orquestación real (STMIPFS) |

### 1.5 Verdad funcional: qué funciona y qué no

| Componente | Estado real |
|---|---|
| Visores WPF + Avalonia, OTA fail-closed, extractor, relé de chat, Kubo, blockchain local, RFPRMN/CONTRRF | **Real** (verificado en v2.7.5) |
| `LC_STM/red_neuronal` (~24.500 líneas, 60 ficheros) | **Simulado**: fabrica `loss`/`accuracy` con `np.random.rand()`; sin optimizador, sin torch/sklearn (V1) |
| «Voz neuronal» | **Simulado**: re-delega en DSP; no hay red (M5) |
| Integración RFPRMN en LucIA (6 de 11 comandos de consola) | **Muerta**: `STM_RFC_DIR` apunta a un directorio inexistente (V6) |
| Subida IPFS desde CONTRRF | **Cortocircuitada** por el shim (acepta CIDs falsos) (V5) |
| CI | **Muerta dos veces**: workflow anidado 5 niveles + `working-directory` a un árbol inexistente (H8/H9) |

### 1.6 Build, pruebas y release

- **Build**: `dotnet publish -c Release -r win-x64|linux-x64 --self-contained`
  (iteración con `-p:SkipGodotAssets=true`); PCK con `godot --headless --import`
  + `--export-pack`. **Inputs no versionados**: `godot_exe.zip` (86 MB) y
  `wvp3d.pck` (114,6 MB / 114.591.724 B, SHA-256 `ebeff90c…7ae5e14`) — el repo
  no versiona ni una textura del mundo (H15/D12).
- **Pruebas**: pytest 98 (≈1/3 humo/grep; sin cobertura de comportamiento del
  núcleo neuronal, V4) + 5 selftests de consola del exe (`--startup` 17/17,
  `--chat` 26/0, `--cuenta` 19/19, `--red` 7/7, `--update`). **Sin suite C#**
  (D15/H11).
- **Release**: 100 % manual, script clavado a `E:\` y v2.7.5 (M31);
  `SHA256SUMS` publicado con BOM UTF-8 que rompe `sha256sum -c` (M34); **sin
  firma de código en ninguna capa** (G3); visor de 365 MB (Win) / 207 MB
  (Linux) (issue #15).

---

## 2. Stack objetivo por etapa (to-be)

Principio del plan: **añadir lo mínimo, exigir honestidad antes que ports**. La
única dependencia nueva obligatoria del runtime/build es **xunit**; todo lo
demás es tooling de desarrollo o decisiones pendientes del propietario.

| Etapa | Stack que se AÑADE o cambia | IDs clave |
|---|---|---|
| 0 — Victorias inmediatas | Nada nuevo (fixes quirúrgicos + smoke tests pytest) | V3, V6, H1, H4, L20, M33, M34, H15, M35, M38 |
| 1 — Seguridad P2P | Nada nuevo: primitivas existentes (SHA-256/HMAC del BCL, `Crypto` de Godot) + arnés de 2 clientes de prueba | V2, H2, H6, H7, M21, M22, G1, G4 |
| 2 — Fiabilidad OTA/visor | cloudflared con versión pinneada + SHA-256 verificado; **firma de artefactos** (recomendado: minisig; Authenticode después) | H3, H5, M16–M19, G3 |
| 3 — CI viva | **GitHub Actions en la raíz** (checkout, setup-dotnet 8, setup-python 3.10+), **proyecto xunit `Visor3D.Tests`**, `conftest.py` hermético | H8–H11, M25–M30, V4 |
| 4 — Núcleo honesto | `pyproject.toml` en `$SRC` (paquetes explícitos, extras `voz` con digest), `LC_STM/__init__.py`, `ruff` limpio; **NO se añade torch/sklearn** | V1, V5, M1–M7, M8, M12 |
| 5 — Estructura | `CHANGELOG.md`/`ROADMAP`/`CONTRIBUTING.md`; `publish_release.ps1` parametrizado; split de `MainWindow.xaml.cs` en parciales; decisión assets (**Git LFS** / submódulo / solo-release-assets) | M20, M31, M36–M39, L11, L21, L22, H15 |
| 6 — Producto/ecosistema | `gitleaks` + `pre-commit`; `pip-audit` + Dependabot; `THIRD-PARTY_NOTICES.md`; `.resx`/`.po` (i18n) + `AutomationProperties`; export/import de islas (zip); guion de validación en 2 máquinas | G2, G5–G9, #22 |

### 2.1 Detalle por etapa

- **Etapa 0**: cero stack nuevo. Los smoke tests SL1–SL10 son pytest
  parametrizado sobre el arnés existente.
- **Etapa 1**: cero dependencias nuevas. Tokens de sesión, prueba de posesión
  (hash salado), mapa privado uuid→peer, `X-Forwarded-For` de proxy confiable,
  LRU en el rate-limit, clamps en RPCs — todo con `System.Security.Cryptography`
  y `Crypto` de Godot. Nuevo artefacto: pequeño **arnés de dos clientes**
  (legítimo + hostil) como pruebas de integración.
- **Etapa 2**: la verificación de `cloudflared` exige publicar/pinnear su
  SHA-256 (nuevo requisito de distribución, no una dependencia). La firma (G3)
  es **decisión del propietario**: minisig multiplataforma primero (clave del
  mantenedor, passphrase fuera del repo), Authenticode/codesign por RID después;
  el updater pasa a verificar firma además de digest.
- **Etapa 3**: workflow en `.github/workflows/` de la raíz con `working-directory`
  reales, `dotnet build -p:SkipGodotAssets=true`, pytest sin
  `continue-on-error`, job separado para pruebas con daemon. Único paquete
  nuevo: **xunit** (`Visor3D.Tests`), portando los selftests existentes
  (Update/Cuenta casi verbatim; Red/Chat con sockets loopback y puerto 0).
  `StartupSelfTest` completo queda en el checklist de release (los assets no
  versionados no caben en CI, M29).
- **Etapa 4**: el remedio de V1 es **honestidad** (relabeled *scaffolding*,
  `NotImplementedError`), no portar entrenamiento: el plan no incorpora
  torch/sklearn. El empaquetado real (`pip install -e .`) elimina los
  `sys.path.insert`; el grupo opcional `voz` declara las 6 librerías con
  digests pinneados.
- **Etapa 5**: sin cambio de runtime. Git LFS **solo si** el propietario decide
  versionar las fuentes del mundo (H15); mientras, limpiar escenas muertas del
  `export_filter` y re-medir el PCK (métrica H5).
- **Etapa 6**: tooling dev-only (gitleaks, pre-commit, pip-audit, Dependabot
  informativos), `THIRD-PARTY_NOTICES.md` (AForge **LGPL-3.0**, NAudio,
  cloudflared Apache-2.0, Godot, modelos Ollama, provenance del PCK — hoy el
  repo MIT no tiene NOTICE, G8), i18n con `.resx` (WPF) / `.po` (Godot), y el
  guion LAN + túnel en dos máquinas reales (#22, P0).

---

## 3. Matriz de dependencias nuevas (consolidada)

| Dependencia | Propósito | Etapa | Obligatoria | Estado |
|---|---|---|---|---|
| `xunit` (NuGet) | Suite C# (`Visor3D.Tests`) | 3 | Sí (build/test) | Nueva |
| GitHub Actions (`actions/checkout`, `setup-dotnet`, `setup-python`) | CI en la raíz | 3 | Sí (calidad) | Nueva, SaaS sin self-hosted |
| minisign / minisig | Firma de binarios + `SHA256SUMS`; updater verifica firma | 2 | Recomendada | **Decisión pendiente del propietario** (G3) |
| cloudflared con digest publicado | Túneles verificados | 2 | Sí (seguridad) | Cambio de distribución, no paquete |
| `gitleaks` + `pre-commit` | Secret scanning local | 6 | No | Nueva, dev-only |
| `pip-audit` / Dependabot | CVEs del área Python | 6 | No | Nueva, informativa (necesita manifests de Etapa 4, G7) |
| Git LFS | Versionar fuentes del mundo | 5 | No | **Decisión pendiente** (H15: LFS vs submódulo vs solo-release-assets) |
| `.resx` / `.po` | i18n y accesibilidad | 6 | No | Nueva capacidad (G9) |

**Lo que el plan NO añade**: ni `torch`, ni `sklearn` (V1 se corrige con
honestidad y `NotImplementedError`, no portando entrenamiento), ni reescritura
de los visores, ni cambio de motor, ni self-hosted runners, ni Docker.

---

## 4. Requisitos del entorno de desarrollo

- .NET SDK 8 (dos targets: `net8.0-windows` WPF y `net8.0` Avalonia).
- Godot 4.7.2 + export templates (solo para publicar/re-exportar el PCK).
- Python ≥ 3.10 con `numpy`, y en dev `pytest` + `ruff`
  (`pip install -e $SRC/STM_HRTS` o `python $SRC/STMGNRL/mainLCSTM.py`).
- Variables: `OPENROUTER_API_KEY`, `OPENROUTER_VAULT_PW` (LucIA/vault);
  `GODOT_BIN`, `DOTNET_BIN` solo si no están en PATH (`STM_HRTS/rutas.py`).
- Publicación real: colocar `godot_exe.zip` (86 MB) y `wvp3d.pck` (114,6 MB) en
  `$SRC/VSC#/` (gitignored); sin ellos solo compila `-p:SkipGodotAssets=true`.
- Entornos mixtos: `/mnt/*` WSL es 9p (I/O muy lenta); los `node_modules`/cachés
  instalados desde Windows rompen shims — reinstalar desde el lado que ejecuta.
- Reglas del repo público: `.env` nunca se commitea; solo `.env.example`.

---

## 5. Referencias

- `docs/IMPLEMENTATION_PLAN.md` — catálogo completo de hallazgos (V/H/M/L/G),
  etapas 0–6 con criterios de aceptación y cruce con la deuda D1–D16.
- `README.md` — manual de usuario, flujo de release (§11), calidad (§14) y hoja
  de ruta F0–F7 (§15).
- `CLAUDE.md` / `AGENTS.md` — guía de build/test/entorno para agentes de IA.
- `$SRC/STM_DOC/REGLAS_DE_ACTUALIZACION.md` — reglas obligatorias de release.
