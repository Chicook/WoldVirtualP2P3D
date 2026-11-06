# AGENTS.md — Rules for AI coding agents (any tool: Claude, Codex, Copilot, Cursor…)

**Read `CLAUDE.md` first** — it has the full project map, build/test commands, and the
release process. The rules below are the non-negotiable subset; they apply no matter which
agent you are.

## What this project is

Decentralized P2P 3D metaverse: C#/.NET 8 viewers (Windows WPF + Linux Avalonia) embedding
Godot 4.7.2, WebSocket multiplayer + UDP-beacon discovery, SHA-256 fail-closed OTA updater,
and LucIA, a Python cognitive subsystem. Upstream: `Chicook/WoldVirtualP2P3D`. All source
lives under `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_cae205a3/src/` (call it
`$SRC`).

## Hard rules

1. **Language**: docs, comments, and commit messages are in **Spanish** — match the
   existing style. Internal acronyms (`STM_*`, `MTBGT`, `LC_STM`…) are names, never rename.
2. **Never run destructive scripts** — `$SRC/STM_HRTS/utils/purgar_repositorio.ps1`,
   `borrar_packs_viejos.ps1`, `limpiar_cache_godot.ps1`, `Godot_abrir_y_limpiar_al_cerrar.bat`
   contain hardcoded paths and delete data. Read + explicit user confirmation first.
3. **No secrets, ever**: this repo is PUBLIC. Never commit or print API keys, vault
   passwords, or `.env` contents — key names only. `.env` is gitignored; `.env.example`
   holds placeholders.
4. **No releases without confirmation**: publishing (`dotnet publish` with real assets,
   GitHub releases, anything OTA) follows `$SRC/STM_DOC/REGLAS_DE_ACTUALIZACION.md` and
   needs explicit user approval in the conversation.
5. **Branch model**: `main` mirrors upstream snapshots — never commit to it. Work happens
   on `development`. When you finish a change, commit and push it.
6. **Stage named files only** (`git add <file>`, never `-A`); before committing, check the
   staged list is free of `\.env$|successful_repos|\.tfvars|backend\.hcl|out\.terraform|\.tfstate|mykey|ghp_`.

## Verify before declaring done

```bash
cd "$SRC" && python -m pytest        # 98-test regression harness must pass
python3 -m py_compile ...            # for touched Python modules
```

C# has no unit suite: after touching viewer code, run the built exe's selftests
(`--startup-selftest --chat-selftest --cuenta-selftest --red-selftest --update-selftest`)
before calling it done. After touching networking, OTA, or extraction code, the full
selftest set is mandatory — those paths ship to users fail-closed.

## Environment quirks

- `/mnt/f` is WSL 9p — very slow I/O. Use `git ls-files` + targeted reads; big `ls`/`find`
  time out. Timed-out commands: re-run, never delete caches.
- Indentation: 4 spaces for `.cs`/`.py`, **tabs for `.gd`** (Godot 4), LF everywhere except
  `*.bat`/`*.ps1` (CRLF) — see `.gitattributes` / `.editorconfig`.
