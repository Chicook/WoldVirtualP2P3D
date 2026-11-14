# CLAUDE.md — AI Assistant Guide for WoldVirtualP2P3D

## Project Overview

Decentralized P2P 3D metaverse project (v2.7.5, 2026-11-01). A single C#/.NET 8 codebase
produces two autonomous viewers — **Windows (WPF)** and **Linux (Avalonia, `VisorLinux/`)** —
that embed **Godot 4.7.2** as the world engine. Multiplayer runs over the project's own
WebSocket relay plus UDP-beacon LAN discovery (beacon port 8912; data port taken from the
beacon payload, 8911 only as fallback), with a public web portal through ephemeral tunnels
(WebNodo). Updates arrive via an OTA updater that is **SHA-256 fail-closed** (a package
without a valid digest is rejected before extraction; extraction normalizes paths against
Zip Slip). **LucIA** is a Python cognitive subsystem (distributed neural net, PoNL ledger,
planned IPFS/blockchain integration) — implemented as packages, not yet integrated in the
viewer. Account ledger + neural weights persist on close.

Language: **the project is Spanish** — docs, comments, and commit messages are in Spanish.
Match that. Internal acronyms (`STM_*`, `MTBGT`, `LC_STM`, `SBSTM`…) are project names;
do not rename or expand them.

Upstream is `Chicook/WoldVirtualP2P3D` (issues and releases live there); this repository
(`CesarChaMal/WoldVirtualP2P3D`) is the development fork. `main` mirrors upstream snapshots;
**`development` is the working branch**.

## Key Documents

| Document | Content |
|---|---|
| `README.md` / `README_EN.md` | Product and usage manual (Spanish canonical / English) |
| `docs/IMPLEMENTATION_PLAN.md` / `docs/IMPLEMENTATION_PLAN_EN.md` | Findings catalog (V/H/M/L/G), Stages 0–6, D1–D16 debt cross-map |
| `docs/STACK.md` / `docs/STACK_EN.md` | Current (as-is) vs target (to-be) technology stack |

## Directory Structure

All source lives five levels deep under one snapshot directory:

```
SRC = VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src
```

```
$SRC/
  VSC#/                     C# solution (the product)
    MainWindow.xaml.cs      viewer UI: world panel, chat, voice/webcam, construction UI
    AppExtractor.cs         self-extraction + .extracted marker + Zip-Slip guard
    STM_actualizar/         OTA: UpdateDownloader, UpdateChecker, UpdateSelfTest
    Services/               DescubrimientoP2P (UDP beacons), WebNodoService (tunnels)
    Seguridad/              bip39 identity, session, machine fingerprint
    VisorLinux/             Avalonia Linux viewer (shares identity/portal/net/chat/updater)
  MTBGT/WoldVirtualP2P3D/   Godot 4.7.2 project: gdscrip/Red.gd (P2P), islands, avatars,
                            construction; export_presets.cfg is versioned
  STM_HRTS/                 LucIA manifest: pyproject.toml, rutas.py, utils/ (see WARNING)
  LC_STM/                   red_neuronal/ — distributed neural net
  SBSTM/                    LucIA modules: voice_engine.py, IAFREE.py (reads OPENROUTER_API_KEY)
  STM_SGR/                  vault_openrouter.py (reads OPENROUTER_VAULT_PW)
  STM_DOC/                  per-release dev docs + REGLAS_DE_ACTUALIZACION.md (release rules)
  STM_IA/ STMIPFS/ STM_BKCH/ STM_JSON/ STM_CH/ STMGNRL/ STM_SGR/   LucIA subsystems;
                            STMGNRL/mainLCSTM.py is the LucIA entry point
  tests/                    pytest regression harness (13 files, 98 collected tests)
  pytest.ini
VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/    separate Python refactor tool (not part of build)
docs/img/                                       README screenshots
```

`$SRC` is a long path — set it once per shell: `SRC=VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src`.

## Build

```bash
cd "$SRC/VSC#"
dotnet publish -c Release -r win-x64 --self-contained true                    # Windows viewer (WPF)
dotnet publish VisorLinux/VisorLinux.csproj -c Release -r linux-x64 \
  --self-contained true -p:IncludeNativeLibrariesForSelfExtract=true          # Linux viewer (Avalonia)
# dev iteration: add -p:SkipGodotAssets=true  (UI only, no engine/world — light binary)
```

**Non-versioned build inputs:** `.gitignore` excludes `*.zip`/`*.pck`, so two inputs must be
placed manually in `$SRC/VSC#/` before a real publish: `godot_exe.zip` (86 MB, Godot 4.7.2
win64 official) and `wvp3d.pck` (114.6 MB, exported from the MTBGT project: `godot
--headless --path . --import` then `--export-pack "Windows Desktop"`). Without them only
`SkipGodotAssets` builds work.

## Test

```bash
cd "$SRC" && python -m pytest            # 98-test Python regression harness
```

C# has **no unit suite** (upstream debt D15); instead the built exe carries selftests that
must pass before any release:

```bash
./<built-exe> --startup-selftest         # 17/17 expected
./<built-exe> --chat-selftest            # 26/0 expected
./<built-exe> --cuenta-selftest          # 19/19 expected
./<built-exe> --red-selftest             # 7/7 expected
./<built-exe> --update-selftest          # OTA fail-closed check
```

## Python / LucIA

Package manifest: `$SRC/STM_HRTS/pyproject.toml` (`lucia-woldvirtualp2p3d`, Python ≥ 3.10,
runtime dep `numpy>=1.24`, dev deps `pytest` + `ruff`). Run: `python
$SRC/STMGNRL/mainLCSTM.py`, or `pip install -e .` then the `lucia` command.

## Release Process

**Read `$SRC/STM_DOC/REGLAS_DE_ACTUALIZACION.md` before any release work** — the
Godot → PCK → version → build → release → OTA flow is mandatory and has a checklist.
The published `SHA256SUMS` currently carries a UTF-8 BOM that breaks `sha256sum -c` on
Linux — a known open defect.

## Environment Variables

The code reads (see `.env.example`): `OPENROUTER_API_KEY`, `OPENROUTER_VAULT_PW`
(LucIA LLM access / key vault), `GODOT_BIN`, `DOTNET_BIN` (tool paths, `$SRC/STM_HRTS/rutas.py`).
This repo is **PUBLIC** — `.env` is gitignored and must never be committed; values are
never printed or committed, key names only.

## ⚠️ Dangerous Scripts

`$SRC/STM_HRTS/utils/` contains personal maintenance scripts — `purgar_repositorio.ps1`,
`borrar_packs_viejos.ps1`, `limpiar_cache_godot.ps1`, `Godot_abrir_y_limpiar_al_cerrar.bat` —
with **hardcoded machine paths and snapshot IDs that delete data**. Never run them without
explicit user confirmation in the conversation, and read them first.

## Known Issues / Gotchas

- **No real two-machine session test** (upstream P0, issue #22): chat, voice/webcam, and
  construction sync are validated by local selftests only, never between two machines on
  LAN/tunnel. Any networking change needs at minimum the full selftest set afterward.
- Milestones **H5 (footprint metrics)** and **H6 (product caps)** are open; viewer weight
  is upstream issue #15 (365 MB Windows / 207 MB Linux).
- **No GitHub Actions**: there is no `.github/workflows/` at the repo root (a ci.yml exists
  nested in STM_HRTS but GitHub only triggers from the root), so nothing CI-runs here today.
- Upstream issues referenced from the README (#15, #22, #23, #38…) live in
  `Chicook/WoldVirtualP2P3D`, not in this fork.
- `/mnt/f` is WSL 9p — very slow I/O. Big `ls`/`find` time out; use `git ls-files` +
  targeted reads. Timed-out installs/commands: **re-run, never delete caches**. Prefer
  explicit `cd` in git commands.

## Best Practices for AI Assistants

- Never print or commit secret **values** (API keys, vault passwords). Key names only.
- `.env` is never committed (public repo); `.env.example` carries placeholders only.
- Stage **named files** (`git add <file>`), never `git add -A`. Before committing, verify
  the staged list contains nothing matching
  `\.env$|successful_repos|\.tfvars|backend\.hcl|out\.terraform|\.tfstate|mykey|ghp_`.
- Never run the maintenance scripts above, `dotnet publish` with real assets, or any
  release/OTA action without explicit user confirmation.
- Match existing code style: Spanish comments, 4-space indent for `.cs`/`.py`, **tabs for
  `.gd`** (Godot 4 convention), LF endings except `*.bat`/`*.ps1` (CRLF, see .gitattributes).
- `main` tracks upstream snapshots — do not commit to it. All work goes on `development`.
- When you finish implementing or changing something, commit and push it.

## Quick Reference

```bash
SRC=VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src
cd "$SRC" && python -m pytest                          # regression harness (98 tests)
python "$SRC/STMGNRL/mainLCSTM.py"                     # run LucIA
git ls-files | wc -l                                   # repo shape without slow ls
python3 -m py_compile "$SRC"/{SBSTM,STM_HRTS}/*.py     # fast syntax check
```

## Status check

Baseline = `main` at v2.7.5 (`19cc65e`). Regression harness green (98 collected), selftest
expectations as listed under Test. Anything that changes networking, OTA, or extraction
must re-run the full selftest set.
