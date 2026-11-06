# Technology stack — current and target

**Technical reference document** · Branch `development` · 2026-11-02

> This document describes **the stack the project uses today** (as-is, v2.7.5 on
> `main` @ `19cc65e`) and **the stack the implementation plan demands** (to-be,
> Stages 0–6), so you can tell at a glance what is installed, what actually
> works, what is simulated, and what will need to be added.
>
> Companions: `README.md` / `README_EN.md` (product and usage),
> `docs/IMPLEMENTATION_PLAN.md` / `docs/IMPLEMENTATION_PLAN_EN.md` (findings and
> stages). The `V*/H*/M*/L*/G*` identifiers cited here refer to the plan's
> findings catalog. Canonical (Spanish) version of this document:
> `docs/STACK.md`.

---

## 0. Conventions

- `SRC = VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src`.
- **As-is** = measured on v2.7.5 (`main` @ `19cc65e`). **To-be** = what Stages
  0–6 of the plan require, nothing more.
- "Simulated" is not an insult: it is the verified state of the code
  (plan V1/V5/M13).

---

## 1. Current stack (as-is, v2.7.5)

### 1.1 Products and languages

| Layer | Technology | Exact version | Where |
|---|---|---|---|
| Windows viewer | C# / .NET (**WPF**), self-contained single-file | `net8.0-windows` | `$SRC/VSC#/` (`Visor3D.csproj`) |
| Linux viewer | C# / .NET (**Avalonia**), 100 % C# UI (no .axaml) | `net8.0` + Avalonia `11.2.3` (Desktop, Themes.Fluent, Fonts.Inter) | `$SRC/VSC#/VisorLinux/` |
| World engine | **Godot** embedded in the viewer, GDScript | Godot `4.7.2` | `$SRC/MTBGT/WoldVirtualP2P3D/` (156 files, ~10.2k lines) |
| Cognition (LucIA) | Python (packages, not integrated into the viewer) | `requires-python >= 3.10` | `$SRC/STM_HRTS`, `LC_STM`, `SBSTM`, `STM_IA`, `STMGNRL`, … |
| Refactor tool | Python (CONTRRF/RFPRMN, outside the build) | — | `VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/` |

**Viewer NuGet packages** (complete, there are no others): `System.Management 8.0.0`
(machine fingerprint via WMI), `NAudio 2.3.0` (audio), `AForge.Video 2.2.5` +
`AForge.Video.DirectShow 2.2.5` (webcam). No additional UI frameworks, no
third-party JSON, no MQTT/ZeroMQ: networking is `System.Net.WebSockets` from
the BCL.

**Python manifest** (`$SRC/STM_HRTS/pyproject.toml`, the repo's only one):
`lucia-woldvirtualp2p3d 2026.5.0` · runtime `numpy>=1.24.0` · dev
`pytest>=7.0.0` + `ruff>=0.1.0` (line-length 120, target py310) · entry points
`lucia` → `STMGNRL.mainLCSTM:main` and `hrts`. There is no torch, sklearn, or
websockets/pip-audit: everything else in the Python area uses stdlib + the
external services of §1.4.

### 1.2 Networking and distribution (P2P/WebNodo)

| Piece | Implementation | Detail |
|---|---|---|
| Chat relay | Own WebSocket server (`ChatRelayServer.cs`) | Listens on `IPAddress.Any`, no post-handshake token (G1) |
| LAN discovery | UDP beacon | Port 8912 (data from the payload; 8911 fallback only) |
| Fixed ports | Chat 8920, config 8911/7890, ~30 literals | Only the LAN join honors the beacon (L9) |
| Public portal | `WebNodoService.cs`: HTTP + TCP proxy + rate-limit | Client IP taken from spoofable headers (H2) |
| Ephemeral tunnels | `cloudflared.exe` downloaded on the fly | No digest or signature verification (M19) |
| Godot multiplayer | `gdscrip/Red.gd` + `any_peer` RPCs | "Host rules" model; identity = self-claimed UUID (V2) |

### 1.3 Security, identity and data

- **Identity**: bip39 (`VSC#/Seguridad/`), machine fingerprint via WMI,
  unsigned `llave_acceso.json` with bypassable binding (M18).
- **OTA**: *fail-closed* SHA-256 download (`UpdateDownloader.cs:157-183`) and
  extraction with an anti Zip-Slip guard (`AppExtractor.cs:179-181`); the
  *apply* stage neither re-verifies nor rolls back (H3).
- **Local blockchain**: double-SHA-256 PoW (difficulty 2), Merkle, atomic
  tmp+replace writes, RPC on `127.0.0.1:8545` (`STM_BKCH/BKSVCB.py`). Real.
- **IPFS**: real Kubo orchestration (`STMIPFS`), triplicated wrapper (M11),
  local shim with fake `QmLocal…` CIDs when no daemon (M13).
- **Persistence**: all JSON — ledger, `registro.cfg`, `islas_registro.cfg`,
  `p2p_session.json` (`user://`), neural weights on close. **No backup or
  export** of worlds or ledger (G5).
- **Secrets**: `OPENROUTER_API_KEY` + `OPENROUTER_VAULT_PW`
  (`SBSTM/IAFREE.py`, `STM_SGR/vault_openrouter.py`); hardcoded vault master
  seed (M8). Public repo: `.env` ignored, `.env.example` with placeholders.

### 1.4 External services

| Service | Use | Status |
|---|---|---|
| OpenRouter (LLM) | `IAFREE.py` (cognitive chat) | Real, requires API key |
| Ollama (`localhost:11434`) | Local GGUF models (`IALOCAL/`) | Downloads without `.part` (L2) |
| HuggingFace / ONNX | Voice models | 6 undeclared libraries, no digests (M5) |
| gTTS | Fallback voice | A test that hits the network (L13) |
| Cloudflare (cloudflared) | Portal's ephemeral tunnels | Unverified binary (M19) |
| Kubo (IPFS) | Decentralized publishing | Real orchestration (STMIPFS) |

### 1.5 Functional truth: what works and what does not

| Component | Real status |
|---|---|
| WPF + Avalonia viewers, fail-closed OTA, extractor, chat relay, Kubo, local blockchain, RFPRMN/CONTRRF | **Real** (verified on v2.7.5) |
| `LC_STM/red_neuronal` (~24,500 lines, 60 files) | **Simulated**: fabricates `loss`/`accuracy` with `np.random.rand()`; no optimizer, no torch/sklearn (V1) |
| "Neural voice" | **Simulated**: re-delegates to DSP; there is no network (M5) |
| RFPRMN integration in LucIA (6 of 11 console commands) | **Dead**: `STM_RFC_DIR` points to a nonexistent directory (V6) |
| IPFS upload from CONTRRF | **Short-circuited** by the shim (accepts fake CIDs) (V5) |
| CI | **Dead twice**: nested workflow 5 levels deep + `working-directory` pointing at a nonexistent tree (H8/H9) |

### 1.6 Build, tests and release

- **Build**: `dotnet publish -c Release -r win-x64|linux-x64 --self-contained`
  (iteration with `-p:SkipGodotAssets=true`); PCK with `godot --headless --import`
  + `--export-pack`. **Unversioned inputs**: `godot_exe.zip` (86 MB) and
  `wvp3d.pck` (114.6 MB / 114,591,724 B, SHA-256 `ebeff90c…7ae5e14`) — the repo
  versions not even one world texture (H15/D12).
- **Tests**: pytest 98 (~1/3 smoke/grep; no behavioral coverage of the neural
  core, V4) + 5 console selftests of the exe (`--startup` 17/17, `--chat` 26/0,
  `--cuenta` 19/19, `--red` 7/7, `--update`). **No C# suite** (D15/H11).
- **Release**: 100 % manual, script nailed to `E:\` and v2.7.5 (M31);
  `SHA256SUMS` published with a UTF-8 BOM that breaks `sha256sum -c` (M34);
  **no code signing at any layer** (G3); 365 MB viewer (Win) / 207 MB (Linux)
  (issue #15).

---

## 2. Target stack per stage (to-be)

The plan's principle: **add the minimum, demand honesty before ports**. The
only new mandatory runtime/build dependency is **xunit**; everything else is
development tooling or decisions pending from the owner.

| Stage | Stack ADDED or changed | Key IDs |
|---|---|---|
| 0 — Quick wins | Nothing new (surgical fixes + pytest smoke tests) | V3, V6, H1, H4, L20, M33, M34, H15, M35, M38 |
| 1 — P2P security | Nothing new: existing primitives (BCL SHA-256/HMAC, Godot `Crypto`) + a 2-client test rig | V2, H2, H6, H7, M21, M22, G1, G4 |
| 2 — OTA/viewer reliability | Version-pinned cloudflared + verified SHA-256; **artifact signing** (recommended: minisig; Authenticode later) | H3, H5, M16–M19, G3 |
| 3 — Living CI | **GitHub Actions at the root** (checkout, setup-dotnet 8, setup-python 3.10+), **xunit project `Visor3D.Tests`**, hermetic `conftest.py` | H8–H11, M25–M30, V4 |
| 4 — Honest core | `pyproject.toml` at `$SRC` (explicit packages, `voz` extra with digests), `LC_STM/__init__.py`, clean `ruff`; **torch/sklearn NOT added** | V1, V5, M1–M7, M8, M12 |
| 5 — Structure | `CHANGELOG.md`/`ROADMAP`/`CONTRIBUTING.md`; parameterized `publish_release.ps1`; split of `MainWindow.xaml.cs` into partials; assets decision (**Git LFS** / submodule / release-assets-only) | M20, M31, M36–M39, L11, L21, L22, H15 |
| 6 — Product/ecosystem | `gitleaks` + `pre-commit`; `pip-audit` + Dependabot; `THIRD-PARTY_NOTICES.md`; `.resx`/`.po` (i18n) + `AutomationProperties`; island export/import (zip); two-machine validation script | G2, G5–G9, #22 |

### 2.1 Per-stage detail

- **Stage 0**: zero new stack. The SL1–SL10 smoke tests are parameterized
  pytest over the existing harness.
- **Stage 1**: zero new dependencies. Session tokens, possession proof (salted
  hash), private uuid→peer map, trustworthy-proxy `X-Forwarded-For`, LRU in the
  rate limiter, RPC clamps — all with `System.Security.Cryptography` and
  Godot's `Crypto`. New artifact: a small **two-client rig** (legitimate +
  hostile) as integration tests.
- **Stage 2**: verifying `cloudflared` requires publishing/pinning its SHA-256
  (a new distribution requirement, not a dependency). Signing (G3) is an
  **owner decision**: cross-platform minisig first (maintainer key, passphrase
  outside the repo), Authenticode/codesign per RID later; the updater then
  verifies a signature in addition to the digest.
- **Stage 3**: workflow in the root's `.github/workflows/` with real
  `working-directory`, `dotnet build -p:SkipGodotAssets=true`, pytest without
  `continue-on-error`, a separate job for daemon-dependent tests. Only new
  package: **xunit** (`Visor3D.Tests`), porting the existing selftests
  (Update/Cuenta nearly verbatim; Red/Chat with loopback sockets and port 0).
  The full `StartupSelfTest` stays in the release checklist (unversioned assets
  don't fit in CI, M29).
- **Stage 4**: V1's remedy is **honesty** (relabeled *scaffolding*,
  `NotImplementedError`), not porting training: the plan does not bring in
  torch/sklearn. Real packaging (`pip install -e .`) removes the
  `sys.path.insert` calls; the optional `voz` group declares the 6 libraries
  with pinned digests.
- **Stage 5**: no runtime change. Git LFS **only if** the owner decides to
  version the world sources (H15); meanwhile, clean dead scenes from the
  `export_filter` and re-measure the PCK (metric H5).
- **Stage 6**: dev-only tooling (gitleaks, pre-commit, pip-audit, Dependabot
  informative), `THIRD-PARTY_NOTICES.md` (AForge **LGPL-3.0**, NAudio,
  cloudflared Apache-2.0, Godot, Ollama models, PCK provenance — today the MIT
  repo has no NOTICE, G8), i18n via `.resx` (WPF) / `.po` (Godot), and the
  LAN + tunnel script on two real machines (#22, P0).

---

## 3. New dependency matrix (consolidated)

| Dependency | Purpose | Stage | Mandatory | Status |
|---|---|---|---|---|
| `xunit` (NuGet) | C# suite (`Visor3D.Tests`) | 3 | Yes (build/test) | New |
| GitHub Actions (`actions/checkout`, `setup-dotnet`, `setup-python`) | Root CI | 3 | Yes (quality) | New, SaaS with no self-hosted runners |
| minisign / minisig | Signing binaries + `SHA256SUMS`; updater verifies signature | 2 | Recommended | **Pending owner decision** (G3) |
| cloudflared with published digest | Verified tunnels | 2 | Yes (security) | Distribution change, not a package |
| `gitleaks` + `pre-commit` | Local secret scanning | 6 | No | New, dev-only |
| `pip-audit` / Dependabot | CVEs for the Python area | 6 | No | New, informative (needs Stage 4 manifests, G7) |
| Git LFS | Versioning world sources | 5 | No | **Pending decision** (H15: LFS vs submodule vs release-assets-only) |
| `.resx` / `.po` | i18n and accessibility | 6 | No | New capability (G9) |

**What the plan does NOT add**: no `torch`, no `sklearn` (V1 is fixed with
honesty and `NotImplementedError`, not by porting training), no viewer rewrite,
no engine change, no self-hosted runners, no Docker.

---

## 4. Development environment requirements

- .NET SDK 8 (two targets: `net8.0-windows` WPF and `net8.0` Avalonia).
- Godot 4.7.2 + export templates (only to publish/re-export the PCK).
- Python ≥ 3.10 with `numpy`, and in dev `pytest` + `ruff`
  (`pip install -e $SRC/STM_HRTS` or `python $SRC/STMGNRL/mainLCSTM.py`).
- Variables: `OPENROUTER_API_KEY`, `OPENROUTER_VAULT_PW` (LucIA/vault);
  `GODOT_BIN`, `DOTNET_BIN` only if not on PATH (`STM_HRTS/rutas.py`).
- Real publishing: place `godot_exe.zip` (86 MB) and `wvp3d.pck` (114.6 MB) in
  `$SRC/VSC#/` (gitignored); without them only `-p:SkipGodotAssets=true`
  compiles.
- Mixed environments: WSL `/mnt/*` is 9p (very slow I/O);
  `node_modules`/caches installed from Windows break shims — reinstall from
  the side that runs them.
- Public-repo rules: `.env` is never committed; only `.env.example`.

---

## 5. References

- `docs/IMPLEMENTATION_PLAN.md` — full findings catalog (V/H/M/L/G), stages
  0–6 with acceptance criteria and the D1–D16 debt cross-map.
- `README.md` — user manual, release flow (§11), quality (§14) and the F0–F7
  roadmap (§15).
- `CLAUDE.md` / `AGENTS.md` — build/test/environment guide for AI agents.
- `$SRC/STM_DOC/REGLAS_DE_ACTUALIZACION.md` — mandatory release rules.
