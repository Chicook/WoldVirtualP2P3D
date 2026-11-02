# Implementation plan — WoldVirtualP2P3D

**Code analysis and improvement roadmap** · Branch `development` · 2026-11-02

> Analyzed baseline: `main` @ `19cc65e` (v2.7.5, 2026-11-01). Repository: 514 tracked
> files (≈130 Python / 80 C# / 65 GDScript), a README of 891 lines / 118.9 KB,
> `SRC = VersionDe_sesion/Sistema_Principal/PRY/actualizacion_aeef1149/src`.
>
> This document condenses an exhaustive analysis of the entire repository:
> **82 findings** (6 adversarially verified + 76 from the catalog) and **9 completeness
> gaps**, organized into a staged work plan. It does not replace
> `README_DESARROLLO.md` or `STM_DOC/HOJA_DE_RUTA.md`: it complements them with a
> holistic, prioritized view.
>
> **English version of [`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)** — the
> Spanish file is the canonical one and prevails on any divergence. Current vs target
> technology stack: [`docs/STACK.md`](STACK.md) / [`docs/STACK_EN.md`](STACK_EN.md).

---

## 0. How to read this plan

**Identifier convention:**

| Prefix | Meaning | Count |
|---|---|---|
| `V1–V6` | **Verified** findings (adversarial cross-check against the source code; severity adjusted after verification) | 6 |
| `H1–H15` | **HIGH** catalog findings | 15 |
| `M1–M39` | **MEDIUM** catalog findings | 39 |
| `L1–L22` | **LOW** catalog findings | 22 |
| `G1–G9` | **Gaps** detected by the completeness pass (topics that no finding covered) | 9 |

**Estimated effort:** `S` = surgical (hours, one or two files) · `M` = medium
(days, several files or coordination) · `L` = large (weeks or a design decision).

**Branch convention:** all work is done in `development`; `main` only mirrors
upstream snapshots (`Chicook/WoldVirtualP2P3D`). Publishing releases, merging into
`main`, or closing upstream issues requires the owner's confirmation.

**Note on stages:** the project already uses `F0–F7` (phases from README §15) and `P0–P2`
(priorities from §16.4). To avoid collisions, the stages of this plan are named
**Stage 0 … Stage 6** and are mapped against the existing ones in section 6.

---

## 1. Executive summary

WoldVirtualP2P3D is a real product and, in several stretches, well built: the C#
.NET 8 dual-target viewer (WPF + Avalonia), the integrated Godot 4.7.2 engine, the
chat relay, the OTA updater with SHA-256 *fail-closed* download, the local chain with
double-SHA-256 PoW on `127.0.0.1:8545`, and the Kubo orchestration are genuine. The
analysis found not a single `eval`/`exec`/`pickle` or bare `except:` in the Python
periphery, and the extractor correctly blocks Zip Slip.

The problems are concentrated in six themes:

1. **Truthfulness of the neural core (V1).** The ~24,500 lines of
   `LC_STM/red_neuronal` **do not learn**: the epoch loops fabricate `loss` and
   `accuracy` with `np.random.rand()` and never invoke an optimizer. There is no torch
   or sklearn in the manifest. Today the network is **disconnected from the viewer**
   (the runtime uses a local shim), but the documentation —including debt D1 itself
   and `STM_IA/conocimiento/red_neuronal.md`— describes it as 50 "active" neurons.
2. **P2P session security (V2, H7, G1, G4, M22).** There is no peer authentication:
   self-asserted UUIDs, LAN/direct `ws://` with no credentials whatsoever, a chat
   relay open to anyone (including through the public tunnel), a spoofable
   X-Forwarded-For that nullifies the rate-limit, and the home IPs of all participants
   are disseminated and persisted. The README §3.4 promise ("only the island owner
   edits") is bypassable under the current design.
3. **Updater and viewer reliability (H3, H4, H5, M16–M19).** The OTA *apply* stage
   does not re-verify the downloaded package and can leave the installation unusable
   with no rollback; the "resume without downloading again" path destroys the entire
   `.part`; the portal's accept loop dies silently on any exception;
   `cloudflared.exe` is downloaded and executed without verifying digest or signature.
4. **Dead CI and tests without behavior (H8–H11, V4, M25–M30).** The only `ci.yml`
   is nested 5 levels deep and GitHub never runs it; even if it were promoted, its
   `working-directory` settings point to a tree that does not exist. 87 of the 98
   regression tests are *advisory* in CI (`continue-on-error`), ~1/3 of the suite are
   greps of source strings or environment-coupled tests, and the neural core
   completely lacks behavior tests: the harness is green while `SL10.optimize_weights()`
   blows up with `AttributeError` on its first real call.
5. **Repository structure working against itself (M36–M39, H15).** The renamed
   `actualizacion_<hex>` cycle (8 historical names) breaks 72 README links per cycle;
   the 118.9 KB README is at once manual, changelog, roadmap, and logbook; the PCK
   rebuild instructions (§11) are impossible from a clean clone because the world
   assets are not versioned (D12).
6. **Supply chain and user data (G3, G5, G8).** Nothing is signed at any layer (the
   OTA SHA-256 comes from the same release JSON as the asset URL); there is no backup
   or export of worlds or of the ledger; an MIT repo with LGPL-3.0/Apache-2.0
   dependencies and a 114.6 MB PCK without provenance has no NOTICE or
   THIRD-PARTY_NOTICES.

**What to do this week (Stage 0):** eleven surgical fixes of effort `S` (including
`import math` in `_sl_math.py`, re-pointing `STM_RFC_DIR`, and the anti-genesis ledger
save) plus three honesty corrections to documentation. Details in section 8.

**Figures from the analysis:** 82 findings (15 high / 39 medium / 22 low in the
catalog, plus 2 verified ones that dropped from critical→high and 1 from high→medium)
+ 9 gaps. The project's own tracking system (D1–D16, DT-01..DT-10 from issue #45,
§16.4 P0–P2, milestones H5/H6, issues #15/#22) already recognizes part of this debt:
the exact mapping is in section 6.

---

## 2. Status by subsystem

### 2.1 Python core (LucIA): `STM_HRTS`, `LC_STM/red_neuronal`, `STM_IA`

`STM_HRTS` is well designed: path utilities, H1 containment with strict tests,
tools with a catalog. The problem is `red_neuronal`: 60 files across five
families (RNP, SLRN, ENRN, RF_EN, RF_SL) that replicate the same structure with
~24,700 lines whose training is simulated (see V1). Aggravating patterns: 126
`except Exception` blocks that swallow failures and return zero metrics,
import-time side effects (global numpy reseed, `logging.basicConfig` in
libraries, eager loading of the 10 modules per family), mathematically
incorrect "orthogonal/spectral" initializers exported in `RF_EN/__init__.py`
while the correct ones live in `_rfen_base.py`, and LLM model keys embedded in
the neuron layer. Packaging does not exist as such: the only `pyproject.toml`
is in `STM_HRTS/` and cannot package its sibling packages; the entire runtime
depends on `sys.path.insert`.

### 2.2 Python periphery: `STMIPFS`, `STM_BKCH`, `SBSTM`, `STM_SGR`, `STM_JSON`, `STM_CH`, `STMGNRL`, CONTRRF

The best of the analysis came out here: the Kubo orchestration is real
(startup, API wait, retries), the local blockchain actually works
(double-SHA-256 PoW difficulty 2, Merkle, tmp+replace atomic write),
CONTRRF/RFPRMN is a well-built refactoring tool (verification by count,
submission bookkeeping), and there are **zero** bare `except:`, `eval`, `exec`
or `pickle`. The real defects: the ledger silently resets to genesis on any
read error (H1), the shutdown flow of `IALOCAL.py` calls methods that do not
exist in the shim (M14), the shim's fake CIDs get mined into immutable blocks
(M13), the vault master seed is hardcoded in a public repo (M8), there are
dead modules (M12), three duplications of the Kubo wrapper (M11) and two
`C:\Users\User\Desktop` paths in `stm_base.py` (M9).

### 2.3 C# WPF viewer (Windows), `VSC#/`

v2.7.5 hardened the OTA half of the download well: *fail-closed* SHA-256
verification before extracting (`UpdateDownloader.cs:157-183`) and path
normalization against Zip Slip (`AppExtractor.cs:179-181`). `ChatClient.cs` is
remarkably solid (timeout-based shutdown, reconnection). But: the *apply*
stage does not re-verify and can brick without rollback (H3), resume destroys
the entire `.part` (H4), the accept loop shuts down silently (H5), the tunnel
proxy leaks tasks and discards sockets in use without cancellation or
keepalive (M16), the ephemeral tunnel is launched twice in the login flow
(M17), the rate limit is voided with a forged XFF because all public traffic
arrives through the local loopback proxy (H2), `MainWindow.xaml.cs` is a
3,420-line god-class (M20), and the sizes served in JSON use `CurrentCulture`
(L8). The beacon's dynamic ports are only respected on the LAN join path (L9).

### 2.4 Godot world (`MTBGT`, 156 files, ~10.2k lines of GDScript)

The "the host is in charge" trust model is well conceived: ownership
validation on the server, clamps on deserialization, editable terrain with a
bounded step. The decisive weakness is identity (V2): without authentication,
all "the sender is the owner" validations rest on a self-asserted UUID that
anyone can forge. Added to that are unvalidated `any_peer` entries
(`_net_position` accepts NaN and unbounded nicks, H6; the editing RPCs pass
radii and scales without clamps, M21), a host migration whose target is
chosen by the first to join (M22), disk I/O inside `_process` (M24), a loading
screen with no timeout or way out (M23), and dead scenes that travel in the
114.6 MB PCK (L11).

### 2.5 Tests and CI

CI is dead twice over: the workflow is nested 5 directories deep (GitHub only
runs from the root, H8) and, once promoted, its `working-directory` entries
point to `VersionDe_sesion/CONTRRF/TLLDCD/src`, a nonexistent tree (H9);
moreover the full suite runs with `continue-on-error: true` (H10). The Python
harness (98 tests) is real but ~1/3 of it is smoke/grep: 4/4 tests in
`test_h2_h3_red.py` are greps of exact strings from the source (M25), there
are environment-coupled tests (real IPFS repo, probe to `localhost:11434`,
M26), timing asserts that fail on loaded machines (M27), and tests that mutate
the user's real directories (M28). No C# test project exists (D15, H11) —
although `UpdateSelfTest.cs` demonstrates that hermetic testing is viable in
this code. `StartupSelfTest`, the strongest end-to-end verification, cannot
run in CI because of unversioned assets (M29). There is no validation between
two real machines at all (upstream #22, P0; G6).

### 2.6 Build/automation scripts (6 .bat, 5 .ps1, 3 .sh, `herramientas.py`)

The Linux .sh scripts are high quality. The rest: `purgar_repositorio.ps1`
points to a nonexistent root and snapshot, deletes nothing, and still prints
"Purge completed successfully!" (H12); `borrar_packs_viejos.ps1` deletes packs
from `.git/objects/pack` by hardcoded name with 2-minute retries — a real
risk of corrupting the repo (H13); the publish script is pinned to `E:\` and
version 2.7.5 (M31); four duplicated opencode launchers already divergent
(M32); the header of `woldvirtual-linux.sh` documents a PCK size/SHA that
contradicts the constants the script itself enforces (M33);
`herramientas.py` builds cmd/powershell/sh argv without platform gating
(L16); two .ps1 files with accents and no BOM that Windows PowerShell 5.1
decodes as ANSI (L17); one .bat with another user's desktop as the first path
(L18); and `arrancar_daemon.bat` looks for a `STMIPFSCOMFIG` directory (L20).

### 2.7 Documentation and repository hygiene

The README is collapsing under its own weight: 891 lines that are at once a
user manual, a changelog with SHA-256 per release, an F0–F7/H roadmap, a dated
P0–P2 logbook, and a versioning policy (M37). 72 links embed the snapshot
name and break on every RFPRMN cycle (M36). §11 orders rebuilding the PCK
with `--import` when the repo does not version a single texture or model —
impossible from a clone (H15). There are internal contradictions (§18 says 41
documents, §4 says 43, and 43 is correct, M38) and §17 describes the shape of
the upstream repo, not this fork's (M35). Hygiene: 7.3 MB of duplicated
screenshots with identical blobs in `docs/img` and `STM_DOC/docs/img` (L21);
`CONTRIBUTING.md`, `CHANGELOG.md` and a root `.editorconfig` are missing (L22
— the latter already added on this branch). 43 documents, all in Spanish
only, with no real contribution guide (M39).

---

## 3. Verified findings (V1–V6)

Each finding went through an independent adversarial verifier with access to
the code; the "final severity" reflects the verdict, not the initial
estimate.

### V1 — The "distributed neural network" does not learn · **HIGH** (adjusted from critical)

- **Evidence.** `_rn_base.py:205` returns `np.random.rand()` as `loss` **and**
  as `accuracy`. RN1's epoch loops (`:61,63-64,86,189-192`) never invoke an
  optimizer and return the model unchanged. The pattern replicates in
  RN2:61, RN3:58, RN4:59, RN5:55, SL2:188, SL4:185, SL5:176, SL6:178, SL7:170,
  SL8:171, SL9:178 — all of them fabricate `epoch_loss`. No `torch`/`sklearn`
  in the manifest (numpy only).
- **Mitigating factors that lower the severity.** The network is currently
  unreachable from the viewer (zero references to LucIA in the viewer; the
  runtime uses the `STM_BKCH/compat_local.py` shim) and README §12/debt D1
  partially admits it.
- **New fact from the verification.** The remedy written in D1 — "port to
  LC_STM/red_neuronal (50 REAL neurons)" — is a false budget: the port's
  destination is also simulated. The modules record "success" and export
  fabricated scores (RN1:319, RN10:290, SL3:376), and
  `STM_IA/conocimiento/red_neuronal.md` tells LucIA that its neurons are
  "active".
- **Proposed fix.** Relabel the whole package as *scaffolding*: replace the
  random bodies with `NotImplementedError` (the current tests only import, so
  they stay green), fix the text of D1 and of `red_neuronal.md`, and leave
  real training as an explicit future project. Stage 4.

### V2 — No peer authentication: self-asserted UUIDs · **HIGH** (adjusted from critical)

- **Evidence.** `Identidad.gd:30-31` only validates format.
  `ChunkManager.gd:443-451` exposes `_claim_island` as `any_peer`;
  `_puede_reclamar_isla` (517-530) only blocks **connected** holders, so a
  disconnected owner's island can be claimed by anyone; `_adoptar_isla`
  (537-550) leaves the real owner out. `Construccion.gd:290-301`
  `_validar_remitente` protects the six editing RPCs solely by comparing the
  declared UUID vs. the holder.
- **Partial mitigating factor.** The WebNodo portal has an invitation-token
  handshake (`WebNodoService.cs:633-640`), but it is a single shared secret
  and the LAN/direct `ws://` connection does not ask for it
  (`Red.gd:217-243`).
- **Not admitted anywhere.** README §3.4 promises "only the island's owner
  edits" — it is bypassable with the current design.
- **Proposed fix.** Host-private uuid→peer map, proof of possession with a
  salted hash, claim queue for islands with absent owners; domino effect to
  revalidate: `_es_mi_isla` (`Construccion.gd:254-262`). Stage 1.

### V3 — `_sl_math.py` missing `import math` · **MEDIUM** (adjusted from high)

- **Evidence.** `NameError` reproduced at runtime: it breaks SL2
  (`cosine_warm_restart`, `_sl_math.py:153`), SL3 (`adaptive_epsilon`,
  `SL3.py:94`), SL4's default path, and SL5.
- **Second defect found during verification.** `cosine_decay` is left dead
  after a nested `return` in `centered_rms_update` (`_sl_math.py:130-134`) →
  `SL10.py:67` throws `AttributeError`.
- **Latent** (today nobody calls the optimizers at runtime), but it blocks
  any future use and voids the "green suite" signal (see V4).
- **Fix.** One line of `import math` + re-indent `cosine_decay` + one smoke
  test per optimizer. **Stage 0** (validated quick win).

### V4 — The neural core has zero behavior coverage · **HIGH** (confirmed)

- **Evidence.** `tests/test_regresion.py:11-23` (`PAQUETES`) does not include
  `LC_STM`; 24,478 lines of Python verified without a single test that feeds
  data to a neuron. The harness is green while `SL10.optimize_weights()` blows
  up on its first real call. The "98 tests" figure is exact but mostly
  import-level.
- **Fix.** Smoke tests with numpy fixtures asserting "no exception / success"
  — **not** "the loss goes down", because SL1:209 and SL10:166 synthesize the
  curves; plus lazy initialization of `pesos` in EN1. Stage 3/4.

### V5 — CONTRRF's IPFS upload short-circuits with the shim's fake CID and then deletes the local record · **MEDIUM** (adjusted from high)

- **Evidence.** `stm_registro.py:262-263` accepts any receipt with a `cid` and
  ignores `ok`/`simulado` (violating the contract of
  `compat_local.py:13-14,155-156`); `publicar_registro_actualizar`
  unconditionally deletes `envios.json`/`registro.md`/`registro_pesos.json`
  (`:435,439-440`), prints success and a nonexistent gateway URL
  (`:444-446`).
- **Why it drops to medium.** Marginal path: the canonical flow empties `RFC`
  before publishing and level 1 already blows up with `ModuleNotFoundError`;
  and the tool's README (§1.4) documents a success with a real CID
  (`QmQ5bjYVr6…`), so the short-circuit is not the norm. Moreover the level-4
  fallback has the same destruction and the "clean directory" is documented
  design → **maintainer's decision**.
- **Fix.** Require `ok is True` / treat `simulado` as failure. Stage 4.

### V6 — The RFPRMN integration is dead: `STM_RFC_DIR` points to a nonexistent directory · **HIGH** (confirmed)

- **Evidence.** `mainLCSTM.py:20` sets `CONTRRF_DIR = parents[3]` (= `PRY`)
  and `:26` `STM_RFC_DIR = actualizacion_aeef1149/STM_RFC` — neither on disk
  nor in git. The only real `RFPRMN.py` is in
  `VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/`. `_imports.py:26` does a
  bare import → `RFPRMN_DISPONIBLE = False` always; 6 of the 11 advertised
  LucIA console commands are silent no-ops (even `cerrar` returns `True`).
  README §13 marks them "Implemented" and `STM_DOC/README.md:20`
  "Operational" — both wrong.
- **Validated fix.** Point `STM_RFC_DIR` at
  `CURRENT_FILE.parents[5]/CONTRRF/STM_RFC/STM_RFPRMN` (`RFPRMN.py:17-20`
  locates itself). **Stage 0** (validated quick win).

---

## 4. Findings catalog by severity

### 4.1 High (H1–H15)

| ID | Finding | Where | Eff. |
|---|---|---|---|
| H1 | The ledger silently resets to genesis on any read error (`except Exception: pass` → `_crear_bloque_genesis()`, with no warning or backup) | `BKSVCB.py:132-153` (also `:251,268`) | S |
| H2 | Bypassable rate limit: all public traffic arrives through the local (loopback) proxy, so `CF-Connecting-IP`/`X-Forwarded-For` — controlled by the client — define the "client IP"; unbounded limiter memory | `WebNodoService.cs:829-848,686-701` | M |
| H3 | The OTA *apply* stage does not re-verify the SHA of the pending file (TOCTOU vs. the fail-closed policy) and the .bat can leave the installer without an exe if the copy fails (no rollback from `.old`) | `UpdateApplier.cs:38-52,113-141` | S-M |
| H4 | "Resume without re-downloading" destroys the already-complete `.part`: there is no early exit, a `Range` is sent from the final size → 416 → the whole file gets deleted | `UpdateDownloader.cs:103-129` | S |
| H5 | The HTTP accept loop dies silently on any unexpected exception (`catch { break; }` with no log or restart): the portal goes dark until restart | `WebNodoService.cs:552-557` (+`519,811-814`) | S |
| H6 | `_net_position` (`any_peer`) applies values unvalidated: NaN positions replicated to the scene graph, unbounded nick, and per-packet `avatar_path` changes that force rebuilding the remote clone up to 10×/s | `PlayerSync.gd:142-160,86-131` | S-M |
| H7 | LAN/direct sessions with no credential at all: the invitation token is only added to `wss://` and nothing validates it on the Godot side; the beacon joins any host that broadcasts on 8912 | `Red.gd:166-169,217-243` | M |
| H8 | The only CI workflow is nested 5 directories deep — GitHub Actions never runs it (and the file itself admits it) | `$SRC/STM_HRTS/.github/workflows/ci.yml:5-8` | S |
| H9 | All of ci.yml's `working-directory` entries point to `VersionDe_sesion/CONTRRF/TLLDCD/...` — a nonexistent tree; moreover `pip install … \|\| pip install …` masks manifest failures | `ci.yml:38,44,55,64,95,99,103,107,111` | S |
| H10 | The full suite runs with `continue-on-error: true`: only the 11 H1 tests can turn the build red; the other 87 are advisory | `ci.yml:63-73` | M |
| H11 | No C# test project exists (debt D15): ~20,700 lines in 80 files covered only by 5 console selftests; `UpdateSelfTest.cs` demonstrates that hermetic testing is viable | `VSC#/` (no xunit/nunit/mstest) | M-L |
| H12 | `purgar_repositorio.ps1` anchors to the wrong root and snapshot, deletes nothing, swallows errors, and still prints "Purge completed successfully!" | `purgar_repositorio.ps1:8,14,83` | S |
| H13 | `borrar_packs_viejos.ps1` deletes packs from `.git/objects/pack` by hardcoded name with 2-min retries — deleting packs by hand can corrupt the object store; the git-native way is `git gc`/`git repack` | `borrar_packs_viejos.ps1:3-31` | S |
| H14 | CI variant of H8/H9: additionally, the workflow's C# build lacks `-p:SkipGodotAssets=true` and would fail on a clean clone | `ci.yml:96` | S |
| H15 | README §11 gives instructions to rebuild the PCK that are impossible from a clone: not a single texture/model is versioned (D12) — §11 contradicts §17 | `README.md:576` vs `git ls-files` of MTBGT | S(doc) |

### 4.2 Medium (M1–M39)

**Python core (M1–M7):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M1 | 126 `except Exception` blocks (plus one bare `except:`) that swallow failures and substitute fabricated zeros/fallbacks — it is what turns the SL3/SL4/SL5 NameError into a silent "quality 0" | `LC_STM`+`STM_IA` (e.g. `SLRN/__init__.py:237-261`) | L |
| M2 | `RF_EN/__init__.py` exports mathematically wrong "orthogonal/spectral" initializers (they return scaled noise); the correct ones (QR/SVD) live in `_rfen_base.py`; `get_optimizer` returns the *string* `'Adam'` | `RF_EN/__init__.py:29-40,116-118` vs `_rfen_base.py:94,101` | S |
| M3 | Massive structural duplication: base classes, He/Xavier/LeCun initializers and Config/Metrics/Result hierarchies re-implemented per family (and 2× within RF_EN, and 10 identical "self-contained" fallbacks) | ENRN/RF_EN/RNP/SLRN | L |
| M4 | Not pip-installable as a set: the only manifest is in `STM_HRTS/` and cannot package its siblings; the runtime depends on 5 `sys.path.insert` calls and `LC_STM` does not even have an `__init__.py` | `STM_HRTS/pyproject.toml`, `mainLCSTM.py:27-29` | M |
| M5 | The "neural voice" module uses no neural network at all (it re-delegates to DSP) and imports 6 undeclared libraries; the singleton downloads models from huggingface without verifying the digest | `SLRN/procesador_voz_neuronal.py:94-95,162-164` | S |
| M6 | Import-time side effects: global `np.random.seed`, `logging.basicConfig` reconfiguring the host's logger, eager loading of the 10 modules per family (defeats the lazy design) | `ENRN/__init__.py:78,359`, `RF_EN/__init__.py:388-389` | M |
| M7 | The ENRN input neurons make outgoing LLM calls with embedded model keys (`nemotron_nano_9b`, `lyria_pro`, `gemma4`); model selection should live in SBSTM/config | `ENRN/__init__.py:165-172` | S-M |

**Python periphery (M8–M15):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M8 | Vault master seed hardcoded in a public repo → `vault.enc` is obfuscation, not encryption (mitigated: vault gitignored + path via env + key masking) | `vault_openrouter.py:18,33` | S |
| M9 | The only two `C:\Users\User\Desktop\...` paths in the area (personal usernames in a public repo) | `CONTRRF/…/stm_base.py:274-275` | S |
| M10 | Windows-biased `ipfs.exe` discovery + `taskkill /F /IM ipfs.exe` that kills every daemon on the machine; `ipfs_launcher.py` is cross-platform and should be the only path | `SBSTMPYIPFS/bat_runner.py:36,45` | S |
| M11 | Triple duplication of the Kubo wrapper + atomic write re-implemented per package (all correct, none shared) | `STMIPFS/SBSTMPYIPFS/__init__.py` vs `ipfs_utils.py` vs `ipfs_launcher.py` | M |
| M12 | Dead modules with no importers — incl. `split_tool.py`, which **would corrupt files if run today** | `SBSTM/split_tool.py`, `config_catalogo.py`, `bat_runner.py` | S |
| M13 | Misleading status labels (`__status__ = "Production / Optimized"` in an admitted shim) and fake `QmLocal…` CIDs mined into immutable blocks | `STMIPFS/__init__.py:21`, `BKSVCB.py:193-213` | S |
| M14 | `IALOCAL.py`'s shutdown calls methods that do not exist in the shim (`mgr.add`) → the "weights → IPFS" step can never upload by construction; dormant today | `IALOCAL.py:239-243` vs `compat_local.py:146-203` | S |
| M15 | `logging.basicConfig(CRITICAL)` at import time (silences the host process's logger, 3rd copy) and `sys.path` computed from the wrong parent | `BKSVCB.py:19-21`, `STM_BKCH/__init__.py:37-49` | S |

**C# viewer (M16–M20):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M16 | WS proxy pumping: `Task.WhenAny` leaves the losing pump running unobserved, disposes a socket still in use, with no CancellationToken or KeepAlive → half-open tunnels blocked forever | `WebNodoService.cs:864-906` | S-M |
| M17 | The ephemeral tunnel is launched twice concurrently in the login flow (up to 3 call sites) and the orphan sweep can kill the tunnel that does work | `MainWindow.xaml.cs:847-848,1404,3214,3236-3240` | S |
| M18 | The hardware binding of `llave_acceso.json` is bypassable: unsigned JSON, an empty hash skips the check, WMI down → empty string → skipped; the "rotation" binds nothing secret | `MainWindow.xaml.cs:780-794,3128-3148` | S |
| M19 | `cloudflared.exe` is downloaded and executed without verifying digest or signature — exactly the pattern the project itself rejects for its OTA binaries | `MainWindow.xaml.cs:3395-3411`, `P2PWebNode.cs:300` | S-M |
| M20 | God-class `MainWindow.xaml.cs` (3,420 lines, 68 unbound `x:Name`s) mixing OTA, P2P, tunnels, chat, friends, webcam and auth; the Avalonia side already uses `VentanaPrincipal.*.cs` partials as a natural seam | `MainWindow.xaml.cs` | M-L |

**Godot world (M21–M24):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M21 | The relayed editing RPCs pass parameters without clamps or bounds: NaN centers, giant radii, unbounded scales, with no cap on prims per island or rate per peer | `Construccion.gd:567-584,728-751,762-773` | M |
| M22 | The host-migration target comes from URLs self-reported by peers: the first to join decides where everyone reconnects (combinable with V2/H7 to capture the session) | `ChunkManager.gd:454-464,763-789` | M |
| M23 | A guest whose connection fails hangs on the loading screen forever: no timeout, no retry, no error UI | `Boot.gd:169-179,209-211`, `ChunkManager.gd:417-424` | S |
| M24 | Sustained disk I/O inside `_process`: re-reading `p2p_session.json` every 2 s and writing `registro.cfg` every 1 s on the main thread, whether or not anything changed | `ChunkManager.gd:1026-1039,1066-1120` | S-M |

**Tests and CI (M25–M30):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M25 | `test_h2_h3_red.py` is 4/4 greps of exact strings from the source and `test_h1_contencion.py` repeats the pattern for C#: they assert that the text exists, not that the behavior works | `tests/test_h2_h3_red.py:22+`, `test_h1_contencion.py:218-230` | M |
| M26 | Environment-coupled tests: a real pre-initialized IPFS repo, a network probe to `localhost:11434`, and an inverted assert that only passes on machines without a daemon | `tests/test_sistema.py:63,83-99,193-213` | M |
| M27 | Strict time-budget asserts (<15 ms, <100 ms probabilistic PoW, <5 ms on average) — flaky on loaded machines and on CI runners | `test_sistema.py:206,213,243,282`, `test_emocion.py` | S |
| M28 | Non-hermetic tests that mutate real user state (caches, PSNRL) and reach-ins into private attributes; `test_h1_contencion.py` already demonstrates the correct pattern (tmp_path + patching) | `test_sistema.py:273-282`, `test_perfil.py:34-44` | M |
| M29 | `StartupSelfTest` — the only end-to-end extraction+startup check — cannot run in CI because of unversioned assets (86 MB + 114.6 MB gitignored) | `Services/StartupSelfTest.cs` | M |
| M30 | Large uncovered surface: most LC_STM modules are only imported, several SBSTM modules unreferenced, GDScript and C# largely untested | `tests/` | L |

**Scripts, build and docs (M31–M39):**

| ID | Finding | Where | Eff. |
|---|---|---|---|
| M31 | 100% manual release: no CI, unversioned inputs, and the only publish script pinned to `E:\`, version 2.7.5 and one RID | `publish_release_v275.ps1:4-7` | S(param)/L(CI) |
| M32 | Four opencode launchers with the same fallback chain, already divergent (`lanzar_opencode.bat` lost the node_modules branch) | `opencode/*.bat|*.ps1`, `utils/lanzar_opencode.bat` | S |
| M33 | The header of `woldvirtual-linux.sh` documents a PCK size/SHA that contradicts the constants the script itself enforces — the user would conclude that a genuine world is invalid | `woldvirtual-linux.sh:24` vs `:48-49` | S |
| M34 | The published SHA256SUMS carries a UTF-8 BOM + CR and breaks `sha256sum -c` on Linux — a defect documented in every release but never fixed | release v2.7.5, README §2/§5/§16.4 | S |
| M35 | §17 describes the shape of the upstream repo (34 tags/21 releases/9 branches), not this fork's (only `main`, 0 tags) — misleading for any reader of this repo | `README.md` §17 | S |
| M36 | The `actualizacion_<hex>` rename cycle (8 historical names) breaks 72 README links per cycle and leaves fossil rules in .gitignore and `REGLAS_DE_ACTUALIZACION.md` anchored to the previous snapshot | repo-wide | L |
| M37 | A 118.9 KB README that is simultaneously manual/changelog/roadmap/logbook/policy — with no split into CHANGELOG/ROADMAP | `README.md` §2,§15,§16,§17 | M |
| M38 | Internal contradictions: §18 "41 documents" vs §4 "43" (43 is correct); the most recent development plan (`src/README_DESARROLLO.md`) is missing from the index and its header still says "not tracked by Git" and anchors TLLDCD | `README.md:853` vs `:241` | S |
| M39 | 43 documents in Spanish only and with no real contribution guide (§19 is five bullets, with no prerequisites or paths) | `README.md` §19 | S-M |

### 4.3 Low (L1–L22)

| ID | Finding | Where |
|---|---|---|
| L1 | Windows-only assumptions in portable Python: `E:/`/`C:/Program Files/dotnet` fallbacks and `ram_gb()` which on Linux throws and returns an assumed 8.0 (affects the GGUF model cap) | `rutas.py:127-128`, `IALOCAL/gestor.py:82-92` |
| L2 | Interrupted GGUF downloads accepted as valid (no `.part` or Content-Length verification) | `IALOCAL/gestor.py:166-181` |
| L3 | Dataclass/annotation hygiene: metrics via `locals()`, implicit Optionals, false return annotations, `__autor__` for `__author__` | `_rn_base.py`, `RF_EN/__init__.py:86-118`, `ENRN/__init__.py:328` |
| L4 | CONTRRF debt confirmed in code: shadowed duplicate method (`def ejecutar` twice), re-exports swallowed with `except Exception: pass`, unused imports | `stm_flujo.py:161-163`, `STM_RFPRMN_stmDL/__init__.py:320-375` |
| L5 | Dead JSON registry entries (files nobody writes) and an unreachable cleanup branch | `registro_json.py:41-44`, `STM_CH/rutas.py:98-100` |
| L6 | CONTRRF (the tool that purges versions) with no automated tests at all; verification by count only (debt D5) | `CONTRRF/STM_RFC` |
| L7 | Two runtime `pip install`s hidden inside library functions | `SBSTM/IALOCAL.py:88-89,152-155` |
| L8 | Partial culture handling: the `tamano_mb` served in JSON uses `CurrentCulture` ("412,3" in es-ES breaks parsers) | `WebNodoService.cs:136,192` |
| L9 | Dynamic ports only on LAN join: chat (8920), session config (8911/7890) and relays remain hardcoded (~30 literals) | `MainWindow.xaml.cs:1592,1316-1317`, `ChatRelayServer.cs:40,62` |
| L10 | UI hygiene: `Thread.Sleep` on the UI thread, `async void` without try/catch, swallowed diagnostics | `MainWindow.xaml.cs:2987,2993`, `VisorLinux/Vistas/*.cs` |
| L11 | Dead scenes inside the 114.6 MB PCK (`export_filter="all_resources"` also exports unreferenced resources) | `export_presets.cfg:9`, `MNCNT.tscn`, `SLTRTN.tscn` |
| L12 | Multiplayer signals connected in `_ready` and never disconnected (Sonda.gd does show the correct pattern) | `ChunkManager.gd:297-302`, `PlayerSync.gd:26-30` |
| L13 | Two files inside `tests/` are not tests: one plays 90 s of audio via Windows MCI, the other calls gTTS (network) — pytest collects them anyway | `tests/test_voz_lucia.py`, `tests/diag_voz.py` |
| L14 | Selftests with a fixed port (18920), instantiated WPF controls, and `Task.Delay`-based synchronization — collision-prone exactly where CI would run | `ChatSelfTest.cs`, `RedSelfTest.cs` |
| L15 | Fragile asserts: hardcoded manifest version and line-count policing (≤450) inside the regression harness | `test_sistema.py:221`, `test_perfil.py:70-72` |
| L16 | `herramientas.py` builds cmd/powershell/sh argv without platform gating: on Linux, `FileNotFoundError` with a traceback | `herramientas.py:224-229` |
| L17 | Two .ps1 files with UTF-8 accents and no BOM: Windows PowerShell 5.1 decodes them as ANSI (mojibake) | `limpiar_cache_godot.ps1`, `purgar_repositorio.ps1` |
| L18 | One .bat hardcodes another user's desktop (`C:\Users\User\Desktop\Godot…`) ahead of the PATH fallback | `Godot_abrir_y_limpiar_al_cerrar.bat:7-8` |
| L19 | `limpiar_cache_godot.ps1` counts orphans as deleted before knowing whether the deletion succeeded (a metric that feeds H5) | `limpiar_cache_godot.ps1:30-35` |
| L20 | `arrancar_daemon.bat`: misspelled directory (`STMIPFSCOMFIG`) and no reporting of the daemon's exit code | `arrancar_daemon.bat:16-17,36-37` |
| L21 | 7.3 MB of duplicated screenshots (identical blobs) between `docs/img` and `STM_DOC/docs/img` + one orphan image (`08_construccion_prims.png`) | `docs/img/`, `STM_DOC/docs/img/` |
| L22 | Standard root files missing: `.github/`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig` (⇒ **.editorconfig already added on this branch**) and there is a dead `*.gltf` rule in .gitattributes | repo root |

---

## 5. Completeness-critic gaps (G1–G9)

Topics that the area-by-area analysis had not covered and that the critical pass considered
indispensable:

| ID | Gap | Key evidence |
|---|---|---|
| G1 | **Unauthenticated chat relay, deliberately exposed on all interfaces and through the public tunnel.** `IPAddress.Any` "to serve both the public tunnel and the LAN"; the proxy hands tunnel clients directly to the chat; after the RFC6455 handshake the client is registered with no token, origin, or identity — anyone (LAN or internet) can read and inject messages | `ChatRelayServer.cs:17-20,50,106-144`, `WebNodoService.cs:654` |
| G2 | **The Linux/Avalonia viewer (VisorLinux) was left unexamined.** Second standalone .NET 8 product (22 files, Avalonia 11.2.3, zero .axaml — the entire UI in C#) with its own OTA (`ActualizadorLinux.cs`, 300 lines, on-the-fly package replacement), portal, chat, accounts, and machine registration. Unknown whether it shares the WPF's apply/no-rollback/resume defects | `VSC#/VisorLinux/` |
| G3 | **No code signing at any layer.** The SHA-256 the updater demands comes from the same release JSON as the asset URL: a compromised release (or account) silently auto-updates everyone; SmartScreen/AV interfere with an unsigned self-updater, and a quarantine mid-apply aggravates the already-found brick bug | `UpdateChecker.cs:160`, publish scripts |
| G4 | **Peers' IPs are harvested, broadcast, and persisted.** Each client reports its URL+LAN IP to the host; the roster stores `{url, ip, nick}` per peer, serializes it, and retains it in `user://p2p_session.json`. In tunneled sessions, every stranger receives the others' real home IP | `ChunkManager.gd:367,412,437,463,771` |
| G5 | **No backup, export, or recovery for worlds or the ledger.** `registro.cfg`, `islas_registro.cfg`, `p2p_session.json` with no export/snapshot/schema versioning; STM_BKCH contains no backup implementation. Combined with the genesis reset (H1) and island theft (V2), the built world is unrecoverable | `ChunkManager.gd:18,126,1067`, `STM_BKCH/` |
| G6 | **No two-machine validation of the core P2P product** (upstream #22, P0) and no cross-check of the project's own P0s against the findings; milestones H5 (footprint metrics) and H6 (product caps) open; viewer weight = issue #15 (365 MB Win / 207 MB Linux) | `CLAUDE.md` Known Issues, README §15/§18 |
| G7 | **Python dependency surface undeclared and unscanned.** Only `STM_HRTS/pyproject.toml` exists; SBSTM/STMIPFS/STM_BKCH/STM_SGR/STM_IA have no manifest or lockfile → pip-audit/Dependabot have nothing to consume; no gitleaks/pre-commit (the vault seed was caught by hand) | `src/STM_HRTS/pyproject.toml` |
| G8 | **Third-party licenses/attribution missing in an MIT repo.** AForge.Video 2.2.5 is LGPL-3.0, NAudio, cloudflared Apache-2.0, Godot and Ollama models embedded/downloaded, a 114.6 MB PCK with no provenance — and no NOTICE/THIRD-PARTY_NOTICES exists | `LICENSE`, `Visor3D.csproj`, README §19 |
| G9 | **Accessibility and i18n absent at the code level.** A single `AutomationProperties` in the entire WPF, zero in Avalonia, no .resx/.po/.translation: every string is hardcoded in Spanish — no screen-reader support and no path to a second language without full extraction | `MainWindow.xaml`, `VisorLinux/Vistas/*.cs`, `gdscrip/` |

---

## 6. Mapping onto the project's existing debt

The project already tracks part of this debt. Correspondence map (to be completed with
DT-01..DT-10 from upstream issue #45 as this plan's first adoption action):

| This plan | Existing record | Note |
|---|---|---|
| V1 (fabricated network) | **Debt D1** + README §12 + `red_neuronal.md` | D1 must be corrected: its remedy assumes the port's destination is real, and it is not |
| M13 (fake CIDs mined) | **Debt D2** | The shim is acknowledged; what is missing is not mining synthetic CIDs or labeling them "Production" |
| L4 (swallowed re-exports in CONTRRF) | **Debt D4** | Confirmed in code |
| L6 (CONTRRF without tests) | **Debt D5** | Confirmed: 10 files, 0 tests |
| H15/M36 (unversioned assets, broken links) | **Debt D12** + §11/§17 | §11 is misleading today; fixing the text is S, versioning assets is L |
| H11 (no C# suite) | **Debt D15** | README §14 admits it; `UpdateSelfTest` is the base for migrating to xunit |
| M34 (SHA256SUMS with BOM) | **§16.4 pending** + §2/§5 | Documented in every release and never fixed; fixing it is one pipeline line |
| G6 (2-machine validation) | **Issue #22 (P0)** | Requires hardware; blocks any claim of "validated multiplayer" |
| L11 + M29 (viewer/PCK weight) | **Issue #15** + milestones **H5/H6** | Dead scenes out of the PCK = the first measurable reduction |
| M31 (manual release) | §11/§16.4 | Parameterizing publish + a hashing CI is the minimum |
| M35/M36/M37/M38 (README) | §14–§18 | The CHANGELOG/ROADMAP split lowers the cost of each release |
| V6, H8–H10, M25–M30 | §14 ("CI: Broken") | The CI can be revived in one afternoon (Stage 3) |
| — | **DT-01..DT-10 (issue #45)** | Cross-check pending: nobody on the analysis read their contents in detail |
| — | Issues **#23, #38** | Referenced by the README; cross-check contents when adopting this plan |
| — | Phases **F0–F7** (§15) | The Stages 0–6 below must be merged into F0–F7 when planning sprints |

---

## 7. Stage plan

Order by value: first the surgical work and documentary truth (Stage 0), then product
risk (P2P security), then viewer reliability, then the safety net (CI/tests) that
protects everything else, and afterwards structure, core, and ecosystem.

### Stage 0 — Immediate wins and documentary truth (effort S; ~1 week)

**Goal:** close the single-line/single-area defects and eliminate the false documentary
claims, without touching design.

| Item | Action | IDs |
|---|---|---|
| 0.1 | `import math` in `_sl_math.py` + re-indent `cosine_decay` (dead after `return`) + a smoke test per optimizer | V3 |
| 0.2 | `STM_RFC_DIR` → `CURRENT_FILE.parents[5]/CONTRRF/STM_RFC/STM_RFPRMN` and reactivate the 6 console commands; update README §13 and STM_DOC | V6 |
| 0.3 | Genesis-proof ledger: on load error, rename to `blockchain_ledger.corrupt-<ts>.json`, warn, and only then decide; narrow the `except`s at `:251/:268` | H1 |
| 0.4 | Early exit in `UpdateDownloader` when the `.part` already has the final size → straight to digest verification | H4 |
| 0.5 | Fix `STMIPFSCOMFIG`→`STMIPFSCONFIG` and report the daemon's ERRORLEVEL | L20 |
| 0.6 | Header of `woldvirtual-linux.sh` → 114.591.724 B / `ebeff90c…7ae5e14` (or generate it from the constants) | M33 |
| 0.7 | Rewrite §11: the PCK is not rebuilt from the repo (point to release assets as the only source) | H15 |
| 0.8 | §18: 41→43 + index `src/README_DESARROLLO.md` + fix its header ("untracked", TLLDCD) | M38 |
| 0.9 | §17: name both repos (fork = main only; tags/releases/issues upstream) | M35 |
| 0.10 | `__status__ = "Prototype"` in STMIPFS/STM_BKCH; delete the dead `def ejecutar`; `__autor__`→`__author__`; dead `*.gltf` rule out | M13, L4, L3, L22 |
| 0.11 | Decision on `purgar_repositorio.ps1` and `borrar_packs_viejos.ps1` (proposal: replace the second with a documented `git gc --prune=now`; delete or rewrite the first by anchoring it to `git rev-parse --show-toplevel` + a confirmation flag + a banner only if something was deleted) — **requires the owner's decision** | H12, H13 |

**Acceptance criteria:**
- `python -m pytest` green (98) and clean `py_compile` in the touched modules.
- New smoke tests for the SL1–SL10 optimizers green (no exception, success
  reported).
- Start `mainLCSTM.py` and run `ayuda` + the 6 RFPRMN commands: they respond (no longer
  no-ops).
- A corrupted ledger planted by hand → it is renamed, a warning is raised, no history
  is lost.
- A new reader of the README cannot conclude that (a) the PCK is rebuilt, (b) the
  neural network trains, (c) this fork has releases.

### Stage 1 — P2P session security (M–L; the biggest product risk)

**Goal:** make "only the owner edits" and "private session" true even with hostile peers
on the LAN or behind the tunnel.

1. **Peer identity (V2):** host-private uuid→peer_id map; proof of possession
   (salted hash of the secret uuid) on connection; a claim queue for islands of
   disconnected owners with deferred confirmation instead of immediate adoption;
   revalidate `_es_mi_isla`.
2. **LAN/direct session credential (H7):** the host's random token required as the
   first message (or URL parameter) also on `ws://`; reject peers without a token in
   `peer_connected`; opt-in LAN beacon.
3. **Chat relay authentication (G1):** the host generates a per-session token and
   injects it into both local clients and connections arriving through the tunnel
   proxy; close unauthenticated clients after the handshake.
4. **Trustworthy client IP (H2):** the TCP proxy writes the real IP into
   `X-Forwarded-For` and `ObtenerIpCliente` ignores the header except for a
   trusted-proxy marker; cap with LRU eviction in `RateLimiter`.
5. **`any_peer` input validation (H6, M21):** reject non-finite values, clamps on
   radius/scale/tool, nick cap, ignore avatar changes <2 s, per-island prim cap and
   per-peer token bucket.
6. **Reliable host migration (M22):** candidates only among peers verified by the
   host (or by accumulated connected time + agreement of N peers); show the destination
   in the UI before connecting.
7. **IP privacy (G4):** do not broadcast the IP to the general roster or persist it in
   `p2p_session.json` (the tunnel URL suffices); the host uses it in memory and nothing
   more.

**Acceptance criteria:** two test clients (one legitimate, one hostile with a forged
uuid) on a LAN: the hostile one cannot edit others' islands, cannot enter the chat
without a token, cannot force migration, and cannot see anyone's IP in any persisted
file; a client sending NaN positions/absurd radii is ignored or kicked.

### Stage 2 — Viewer, OTA, and data reliability (S–M)

1. **Safe apply (H3):** re-hash the pending item against `state.json` (sha256 + asset
   name) before generating the .bat; fallback `if not exist "%EXE%" move /Y "%EXE%.old"
   "%EXE%"` after exhausting retries; delete `state.json` only on success.
2. **Resilient accept loop (H5):** `break` only for `ObjectDisposed`/stopping;
   any other exception → `VisorLog.Error` + continue with backoff; log the 500
   in `ProcessRequest` and in `HandleProxyClientAsync`.
3. **Correct WS proxy (M16):** `CancellationTokenSource` cancelled in `finally`,
   observe both pumps before disposing, `KeepAliveInterval`, close with
   timeout (the `ChatClient.CerrarSocketAsync` pattern).
4. **Single tunnel (M17):** `SemaphoreSlim` around `EstablecerTunelEfimeroAsync`
   with a re-check of the guard inside; `BarrerHuerfano` only when no attempt is in
   progress.
5. **Verified cloudflared (M19):** pinned version + SHA-256 (or verify
   Authenticode with `X509Chain`) and fail-closed.
6. **Honest session close (M14):** `mgr.almacenar_pesos(...)` + branch on
   `ok`/`simulado` printing the shim's real error; `simulado` CIDs are not
   mined (M13b).
7. **Connection UX (M23):** 20–30 s timeout in `Boot._entrar_a_isla` with a
   retry/back dialog; `conexion_imposible` signal from `ChunkManager`.
8. **I/O outside `_process` (M24):** `get_modified_time` before re-reading the
   session; position saved with debounce; persistence on a `Timer`.
9. **Details:** `InvariantCulture` in `tamano_mb` (L8); centralize the port
   constants and thread the beacon port through to chat/config (L9); try/catch in
   `async void` and `Thread.Sleep` off the UI thread (L10); hardware binding as
   HMAC and empty hash = failure (M18).
10. **Artifact signing (G3, L — strategic):** decide the route (cross-platform
    minisig or Authenticode+codesign per RID), sign the binaries and SHA256SUMS in the
    pipeline, and have the updater verify the signature in addition to the digest.
    It reduces what today is "a compromised release = a compromised fleet" to a
    key-management problem.

**Acceptance criteria:** selftests 17/26/19/7/update green after each change;
manual bricked-apply test (target exe locked) → the .bat restores from `.old`;
a complete `.part` reused without re-downloading (log); the portal survives an
exception injected into the listener.

### Stage 3 — Living CI and behavior tests (S–M, one afternoon + iteration)

1. **Promote the CI (H8, H9, H14):** copy `ci.yml` to `.github/workflows/` at the
   root, rewrite the 9 `working-directory`s to the real tree, `-p:SkipGodotAssets=true`
   on the build, remove the masking `|| pip install`. Trigger: push/PR to `development`
   and `main`.
2. **De-advisory (H10):** remove `continue-on-error` once the suite is hermetic;
   meanwhile, split the daemon tests into their own named job.
3. **Hermeticity (M26, M27, M28):** a `conftest.py` that redirects LEDGER/PSNRL/caches
   to `tmp_path` before the import; IPFS repo initialized in a fixture or a fake
   binary; mock of the Ollama socket; time asserts → recorded metrics or 10× caps.
4. **Behavior over grep (M25):** keep a single grep as a tripwire and port the
   rest (the C# cases already exist in `UpdateSelfTest` — invoke or port them).
5. **C# suite (H11):** a `Visor3D.Tests` project (xunit); port the five
   selftests (Update/Cuenta nearly verbatim; Red/Chat with loopback sockets);
   `dotnet test` in CI.
6. **Minimal neural coverage (V4):** add `LC_STM` to `PAQUETES`; one parameterized
  smoke test per family (forward/backward without exception) — already started in 0.1.
7. **Harness hygiene:** `test_voz_lucia.py`/`diag_voz.py` out of testpaths (L13);
   port 0 in selftests (L14); version checked against pyproject and line-count rule
   out of the gate (L15); `StartupSelfTest` split into an assets-free part (CI) and a
   real startup (release checklist) (M29).

**Acceptance criteria:** the `development` branch shows green checks on GitHub; a
`git push` that breaks a real test (not a grep) turns the build red; the suite runs
twice in a row on a clean runner with no environment- or timing-related failures.

### Stage 4 — Honest neural core (M–L)

1. **Relabel (V1):** random bodies → `NotImplementedError`; fix D1 and
   `red_neuronal.md`; the fabricated "successes" stop being exported (RN1:319,
   RN10:290, SL3:376).
2. **Shim contract (V5):** `stm_registro.py` requires `ok is True`; `simulado` =
   explicit failure; decide with the maintainer on unconditionally deleting the
   local registry (the "clean directory" is documented design).
3. **Swallow less (M1):** narrow the 126 `except Exception`s around math/IO;
   a strict mode that re-raises in the optimization loops so CI sees breakage.
4. **Correct surface (M2, M5, M6, M7):** re-export `_rfen_base` from
   `RF_EN/__init__` and delete the wrong copies; declare the optional `voz` group +
   pinned digest for the ONNX downloads; remove seed/basicConfig/eager-load at
   import; move the LLM keys out of ENRN into SBSTM/config.
5. **Packaging (M4):** `pyproject.toml` in `$SRC` with explicit packages;
   `LC_STM/__init__.py`; remove the `sys.path.insert`s once imports resolve through
   the installed package.
6. **Cleanup (M12, M8, L1, L2, L3, L7):** delete dead modules (split_tool
   —dangerous if executed—, config_catalogo, bat_runner); vault: refuse to decrypt
   "usuario" vaults without `OPENROUTER_VAULT_PW`; `ram_gb()` Linux;
   `.part`+Content-Length in GGUF; `ruff check` with the existing config; pip
   runtime → declared extra.
7. **Structural dedup (M3, L — optional/gradual):** a `_common` module (base
   neuron, initializers, dataclasses) shared by the five families; converge RNP/SLRN
   on one optimizer interface.

**Acceptance criteria:** `pip install -e .` in a clean venv and `lucia` starts
without `sys.path`; no green test claims training; the README/§12/D1 describe
scaffolding; `ruff check` clean across the three packages.

### Stage 5 — Repository structure (M–L)

1. **Stable path (M36):** remove the `actualizacion_<hex>` rename from the
   directory name (move the snapshot id into a manifest); rewrite the 72 links;
   purge fossil rules from .gitignore and `REGLAS_DE_ACTUALIZACION.md`. Coordinated
   with RFPRMN (the tool is what does the renaming).
2. **README split (M37, M39, L22):** §2 → `CHANGELOG.md`; §15–§16 → ROADMAP; §17 →
   its own policy; `CONTRIBUTING.md` with prerequisites (Godot 4.7.2, .NET 8,
   SkipGodotAssets, 98 tests, REGLAS_DE_ACTUALIZACION) — the root `.editorconfig`
   already exists.
3. **Scripts (M31, M32, L16–L19):** parameterized `publish_release.ps1` (`-Version`,
   `-PublishDir` derived from the root); a single opencode launcher; platform
   gating in `herramientas.py`; BOM in the two .ps1s; someone else's desktop out of
   the .bat; count only successful deletions.
4. **Viewer (M20, L9):** split `MainWindow.xaml.cs` along the Avalonia seam
   (`VentanaPrincipal.*.cs`): UpdateViewModel, TunnelController, chat/friends
   UserControl — with no behavior change.
5. **Hygiene (L5, L21):** dead registry entries out; delete the duplicated
   `STM_DOC/docs/img` (or link relatively) and the orphan image; §4 measures
   unique content again.
6. **Assets (H15-real, L11, L — tied to #15/H5):** decide the fate of the world's
   sources (version/LFS/submodule or declare release-assets-only); meanwhile, dead
   scenes out of the export and re-measure the PCK.

**Acceptance criteria:** a grep for `actualizacion_` in docs/ returns only
history/changelog; the README drops from ~890 to <300 lines; clean clone +
`dotnet build -p:SkipGodotAssets=true` + `python -m pytest` work with no hidden
steps; the PCK weight after cleaning scenes is published as the H5 metric.

### Stage 6 — Product and ecosystem (M–L)

1. **Two-machine validation (G6, #22):** a LAN + tunnel test script (chat,
   voice/webcam, building, host migration, reconnection) executed and documented;
   until then, no release note claims validated multiplayer.
2. **Backup/export (G5):** island export/import (terrain chunk + prims + owner
   record) and ledger snapshot; at minimum, an automatic pre-genesis copy
   (complements 0.3).
3. **VisorLinux (G2):** targeted audit of `ActualizadorLinux.cs` and company
   against the known WPF defects (apply/rollback/resume/XFF) with fixes in
   parallel.
4. **Supply chain (G7, G8):** per-package manifests (or Stage 4's pyproject with
   extras) + pre-commit with gitleaks + pip-audit/Dependabot;
   `THIRD-PARTY_NOTICES.md` (AForge LGPL-3.0, NAudio, cloudflared Apache-2.0,
   Godot, Ollama, PCK provenance).
5. **Accessibility/i18n (G9):** minimal base — `AutomationProperties` on key
   controls, keyboard navigation, and UI strings extracted to .resx/.po so that a
   second language is possible without a rewrite.

**Acceptance criteria:** a real session between two machines with the script
green; a restorable `islas_export.zip` exists; Dependabot/gitleaks active with
informative findings; the NOTICE covers every dependency in the csproj.

---

## 8. Quick-wins checklist (already prioritized)

In that order, each item is effort `S` and delivers visible value this week:

- [ ] `import math` + re-indented `cosine_decay` + SL1–SL10 smoke tests (V3)
- [ ] `STM_RFC_DIR` re-pointed; 6 LucIA commands operational (V6)
- [ ] Anti-genesis ledger with `.corrupt-<ts>` (H1)
- [ ] Complete `.part` → verification without re-download (H4)
- [ ] `STMIPFSCONFIG` + daemon ERRORLEVEL (L20)
- [ ] `woldvirtual-linux.sh` header to 114.591.724 B / `ebeff90c…` (M33)
- [ ] SHA256SUMS regenerated without BOM/CR in the pipeline + corrected re-upload of
      v2.7.5 (M34 — **release action: requires the owner's confirmation**)
- [ ] Honest README §11/§17/§18 (H15, M35, M38)
- [ ] `__status__ = "Prototype"`; dead `def ejecutar` out; `__author__`; gltf rule (0.10)
- [ ] Owner decision on `purgar_repositorio.ps1`/`borrar_packs_viejos.ps1` (H12/H13)
- [ ] `.github/workflows/ci.yml` at the root with real working-dirs (H8/H9/H14 — can
      be pulled forward from Stage 3: it is copy + rewrite paths)

## 9. Plan success criteria

1. **Truth:** no documentation claims capabilities the code does not have
   (training, PCK reconstruction, operational commands, "Production" status).
2. **Trust:** the P2P session withstands a hostile peer (identity, chat, migration,
   inputs) and users' IPs are not broadcast.
3. **Recovery:** no disk/network/parser failure deletes history (ledger) or causes
   an inability to start up (OTA with rollback).
4. **Safety net:** CI at the root that turns the build red with real behavior
   tests; hermetic, non-flaky suite; first C# xunit project.
5. **Sustainability:** split README, stable path without renames, real pip
   packaging, declared dependencies and licenses.
6. **Product:** two-machine validation executed; H5 metrics published; viewer/PCK
   weight measured and trending down.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| The identity/token changes (Stage 1) break compatibility with already-deployed 2.7.5 clients | Version the handshake; dual-mode period (optional→mandatory token) coordinated with the release cycle |
| Relabeling the neural network (V1) "removes" functionality announced upstream | It is documentation + `NotImplementedError` on already-dead paths; propose it upstream as an honesty PR, not as a divergent fork |
| The stable path (M36) clashes with the existing RFPRMN flow | Prototype in `development` + manifest; coordinate with the tool before the first real cycle |
| Unversioned assets (H15) make any release build irreproducible | Explicit owner decision: LFS/submodule vs. release-assets-only; document it either way |
| Deleting dead modules/scenes removes something upstream still uses | Each individual deletion in its own reversible commit; verify with a grep of importers/references first |
| Behavior tests uncover more breakage than expected (normal after V3/V4) | That is the goal: report them as new findings and prioritize them by severity, do not revert the test |
| Signatures (G3) introduce key management the project does not have today | Start with minisig (key in the maintainer's repo, passphrase outside) and leave Authenticode as a later step |
| The work scatters across stages | Adopt the 0→3 order first (quick wins + security + reliability + CI): Stage 3 protects all the others |

## 11. Appendix — analysis method

Comprehensive repository analysis executed on 2026-11-02 over `main` @ `19cc65e`
through multi-agent review (14 agents: 7 areas + adversarial verification of the 6
main findings + completeness critique), 459 tool calls across the 514 tracked
files. Each finding includes `fichero:línea` evidence. This document condenses the
resulting 82 findings and 9 gaps; the severities of V1–V6 reflect the verification
verdict (two criticals adjusted to high, one from high to medium, three
confirmed). Line citations correspond to the `actualizacion_aeef1149` snapshot and
may shift with future commits.
