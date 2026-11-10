# Security Fix Roadmap — WoldVirtualP2P3D

**Derived from:** `SECURITY_AUDIT_2026-11-05.md` (read-only audit of commit `c0aaa84e0e97c3ce02f4ada652ad5f2209c6d3c6`, `main`, 2026-11-04)
**Date:** 2026-11-05
**Purpose:** Turn the audit's 74 findings into an ordered, PR-sized fix programme in the style of the collaboration's earlier Stage 1 slices: one branch per slice, one pull request per slice, the repo owner (Chicook) judges and merges. Nothing here is pushed by the audit team.


> ## ⛔ STAGE 0 IS AN ABSOLUTE CRITICAL SHOWSTOPPER — HARMFUL CODE, NOT A FIX-LATER ITEM
>
> The three mechanisms closed by slice **R-01** are **planted harmful code**: the 2026-11-05 provenance trace proved they are **one weapon** — a single byte-identical second-stage loader, fed through an Ethereum dead drop, downloading further unsigned code from **live command infrastructure**. That is a backdoor pattern, **not** a legitimate update method and **not** a legitimate Web3 technique. **Nothing else in this roadmap — and no feature work, cloning, opening, or running of this repository on a trusted machine — comes before R-01.** Machines already exposed to the triggers (VS Code folder-open, `npm start` in `STM_HRTS/opencode`, STM_HRTS console) must be treated as potentially compromised until checked. (Honest limits: the loader's final downloaded stages were never fetched or run; the human who planted the code is not proven.)

## How to read this roadmap

- **Worst first.** Stages are ordered by risk: Stage 0 is incident response (do it before anything else, ideally before the repo is cloned or opened anywhere new); Stages 1–2 finish session security and network robustness; Stage 3 fixes the update/supply chain; Stage 4 the Python data-integrity core; Stage 5 identity-adjacent local protections, CI and scripts.
- **Every slice names the audit findings it closes** (IDs like A1-1, plan IDs like H7 in parentheses), its **dependencies**, a **rough effort** (S ≈ one small PR, a day or less · M ≈ a few days · L ≈ a week or more), and **acceptance tests**.
- **Standing acceptance rule for every slice** (from the established clean-main baseline): `python -m pytest` on a clean checkout reports **94 passed / 2 pre-existing failures / 2 skipped, with no new failures** (delete any stale `.pytest_cache` first — it causes one spurious failure); the C# solutions build with **0 errors / 0 warnings**; `godot4 --headless --import` on the Godot project completes with **zero script errors**; and any behaviour the slice changes gets a **behaviour test**, not a source-text grep (the plan's M25 lesson).
- **Precondition:** slices marked "after #nn merges" assume the open PRs #57–#62 land first, in the owner's chosen order (note the known overlap: #57 and #61 touch neighbouring code — merge them deliberately, not back-to-back blind).

## Sequencing at a glance

| Stage | Theme | Slices | Findings closed |
|---|---|---|---|
| 0 | Incident response & repo hygiene | R-01, R-02, R-03 | 3 Critical payloads, .env leak path, dormant upload surface |
| 1 | Finish session security (plan Stage 1 completion) | R-04 … R-07 | H7, M22, G1/G4 residuals |
| 2 | Network robustness & DoS | R-08 … R-15 | M16, H5, portal token, Godot transfer caps, tunnel fixes |
| 3 | Update chain & supply chain | R-16 … R-20 | H3, H4, G3, G2, M19, dependency hygiene |
| 4 | Python data integrity & local services | R-21 … R-27 | H1, V5, M13, M14, M8, M5, L2, L7 + new Python findings |
| 5 | Local protections, CI, scripts, docs | R-28 … R-33 | M18, H8–H15, M9, M20, M24 |

---

## Stage 0 — Incident response & repo hygiene (immediate)

**⛔ SHOWSTOPPER: Stage 0 is not ordinary incident response — R-01 removes planted, harmful code (see the banner at the top of this document). It is the absolute first work, ahead of every other stage, slice, and feature.**

### R-01 — Remove the three planted-payload execution vectors
- **Closes:** A1-1 (Critical), A5-1 (Critical), A5-2 (Critical)
- **Work:** (1) Delete `.vscode/tasks.json`'s auto-run tasks and the `task.allowAutomaticTasks` / lint-on-open settings from `.vscode/settings.json`; delete the file `…/public/fonts/fa-brand-400.orc`. (2) Restore `STM_HRTS/opencode/init` to its 34-line benign stub (remove the appended line 35) or delete the `start` script from `opencode/package.json`. (3) Delete `STM_HRTS/utils/transport.py` and its import in `STM_HRTS/__main__.py`. Add a short SECURITY note in the PR body: any machine that opened this repo in VS Code, ran `npm start` in `STM_HRTS/opencode`, or ran the STM_HRTS console should be treated as potentially compromised until checked (owner's call how widely to announce).
- **Dependencies:** none. **Do this before any other slice and before further cloning/sharing of the repo.**
- **Effort:** S
- **Acceptance:** repo-wide grep finds no `runOn: folderOpen`, no `allowAutomaticTasks`, no `.orc` file, no `transport.py`; opening the repo in VS Code runs no task; `npm start` (dry inspection) contains no obfuscated line; STM_HRTS console module imports without the transport module (static check — do **not** execute the old code to "test" it); standing acceptance rule passes.
- **Follow-up (owner's decision, not a code slice) — R-01b:** deobfuscate the two JS payloads and inspect the referenced Ethereum transaction's input **in an isolated sandbox with no credentials and no network route back**, to learn what ran on exposed machines; review the introducing commits (`.orc` present by `d510acd`, 2026-11-01) and the opencode folder's provenance.

### R-02 — Close the .env leak path and scrub the committed key fingerprint
- **Closes:** A5-4 (High), A5-14 (Low)
- **Work:** Add `.env` and `.env.*` to `.gitignore` keeping the `!.env.example` exception; verify with `git check-ignore` for `.env`, `.env.local`, `.env.example`. Scrub the masked first4/last4 key fragments from `STM_IA/modelosIAlocal/IALOCAL/uso_ialocal.md` (replace with a wholly synthetic masked value). Add a lightweight secret-scan step (gitleaks config or a grep-based tripwire list) that contributors run pre-commit; document it in the repo.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** `git check-ignore -v .env` reports the new rule; a planted dummy `.env` with a fake key is caught by the scan step and cannot be staged silently; the uso_ialocal.md fragments are gone from the working tree; standing acceptance rule passes.

### R-03 — Delete or gate the dormant P2PWebNode / IpfsManager surface
- **Closes:** A4-17 (Low, dormant), A4-7 (High, latent part)
- **Work:** Remove `VSC#/p2pipfsCS/P2PWebNode.cs` and, if unused after caller search, `IpfsManager.cs`/`IpfsPublisher.cs` from both viewers (the class has no instantiation anywhere in the tree; the live portal is WebNodoService and the live node is RedP2P/P2PNodo). If the owner prefers to keep the code for a future IPFS feature, move it behind an explicit off-by-default build flag **and** strip the anonymous-upload fallbacks (Pixeldrain/GoFile/transfer.sh/0x0.st), the unauthenticated `/visor.zip`, and the wildcard CORS before any re-activation.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** caller search confirms no references; both viewers build 0/0; if the flag route is chosen, a default build contains no P2PWebNode types (verify by assembly inspection or `#if` audit); standing acceptance rule passes.

---

## Stage 1 — Finish session security (completes the plan's Stage 1)

### R-04 — LAN/direct session credential (the missing Stage 1 item)
- **Closes:** A2-4 / H7 (Critical). Also removes the token-in-logs leak noted inside A2-4.
- **Work:** Require the session invitation on **every** transport, not only the tunnel `wss://` path: implement the invitation check in the Godot join handshake (first-message token with a short join window, disconnect on mismatch) so direct `ws://` LAN connections to :8911 are authenticated too; authenticate the LAN beacon (HMAC of the beacon payload with the session token; ignore unsigned beacons) or require the token before connecting to a beacon-discovered host and pin the first host by user confirmation; stop printing raw command-line args in Boot.gd/Red.gd (redact `invitacion`).
- **Dependencies:** after #58 and #61 merge (reuse their token/identity plumbing). **Effort:** M
- **Acceptance (plan Stage 1 hostile-client test, extended):** two test clients on a LAN — one legitimate, one hostile with no token and one with a forged token: the hostile clients cannot join the world or the chat over direct `ws://`, cannot enter via a forged `WOLDVIRTUAL_HOST` beacon (clients ignore it or demand confirmation), and no session credential appears in client logs; legitimate LAN and tunnel joins still work; standing acceptance rule passes.

### R-05 — Host-migration hardening
- **Closes:** A2-9 / M22 (High)
- **Work:** Bind roster addresses to the reporting peer: each peer signs its roster entry with its identity key (from #61); the host validates reported addresses at report time (parse as URL/IP, allow only `wss://` tunnel hosts or RFC1918 IPs, cap lengths, reject embedded credentials/paths and characters that reshape the interpolated `ws://%s:%d` fallback); `_url_candidato` re-validates before dialling; migration targets must present the session invitation and the expected host identity before any state is trusted; never auto-dial non-tunnel LAN addresses for Internet sessions; the UI shows the destination and asks for confirmation when the new host's address differs unexpectedly (plan Stage 1 item 6).
- **Dependencies:** R-04 (credential on all transports) and #61 merged. **Effort:** M
- **Acceptance:** hostile-peer test: a low-order peer reporting an attacker URL does **not** become the migration target (entry rejected or unsigned → ignored); on host death, clients migrate only to a verified candidate and refuse a target that fails the invitation/identity check; the confirmation UI appears on unexpected address change; standing acceptance rule passes.

### R-06 — Chat relay residuals: loopback bind, UID derived server-side
- **Closes:** the residuals of A2-5 / G1 left after #58 (direct-LAN bypass; client-claimed UIDs; UIDs broadcast in peer lists).
- **Work:** Bind ChatRelayServer to loopback only and let the token-checking WebNodo proxy be the sole external entry (including for LAN guests); stop starting a relay for pure guests; inside the relay, derive the session UID server-side from the authenticated account/token instead of trusting the client's `hello` uid; stop including raw UIDs in `welcome`/`join` peer lists (use display names + server-assigned session ids).
- **Dependencies:** after #58 merges. **Effort:** M
- **Acceptance:** from a second machine on the LAN, a direct connection to :8920 is refused/unreachable while chat through the host's portal/tunnel still works; a client that handshakes with a victim's UID cannot claim it (server assigns its own), and DMs route to the authenticated identity; two clients with the same display name no longer collide; standing acceptance rule passes.

### R-07 — Session-file hygiene
- **Closes:** A2-6 residual (invitation persisted with the URLs; three write locations) and A3-12 (Medium).
- **Work:** Stop writing `invitacion` into `p2p_session.json` (store a hash or nothing; the token lives in memory and in the share link only); write the session file to the Godot app_userdata location **only**, with restrictive permissions, and remove the project-root and exe-directory copies from the write set; on the Godot read side, drop the exe-directory fallback paths, validate `remoteIp` as an IP or plausible public hostname, clamp `remotePort` to 1–65535 in the session branch too, and surface the resolved remote host to the user when it changes from the previous session.
- **Dependencies:** after #57 merges (same files). **Effort:** S
- **Acceptance:** after a full session, no file under the project tree or exe directory contains the invitation or any peer LAN IP (grep-verified); a hand-planted `p2p_session.json` next to the exe is ignored; an out-of-range `remotePort` is clamped/rejected; standing acceptance rule passes.

---

## Stage 2 — Network robustness & denial-of-service surface

### R-08 — Chat relay connection lifecycle and media budgets
- **Closes:** A2-11 (High, slow-loris / late MaxClients check), A2-12 (Medium, media amplification + head-of-line blocking)
- **Work:** Add a per-connection handshake timeout (e.g. 10 s via a linked CancellationTokenSource) in `AtenderClienteAsync`; count pending handshakes against a separate cap and check capacity **before** reading headers; cap binary media rates near the design rates (audio 50 fps / video 4–8 fps with per-second byte budgets, replacing the flat 90 fps allowance); make `DifundirAsync` concurrent with per-recipient bounded queues, drop-on-full for media frames, and per-send timeouts that disconnect a stuck recipient instead of blocking the room.
- **Dependencies:** none (complements R-06; do after #58 to avoid merge friction in ChatRelayServer.cs). **Effort:** M
- **Acceptance:** slow-loris test: 100 trickling pre-handshake connections are reaped within the timeout and legitimate clients still connect (backlog never starves); a client flooding 90 fps video is throttled/disconnected without delaying text delivery to others; one dead recipient does not delay media to the rest by more than the send timeout; standing acceptance rule passes.

### R-09 — Proxy connection lifecycle + accept-loop resilience
- **Closes:** A2-7 / M16 (High), A2-3 / H5 (Medium)
- **Work:** In WebNodoService's WS and TCP proxies: link a per-connection CancellationTokenSource to both pumps, cancel when either direction completes, close both WebSockets (CloseAsync with a short timeout) in `finally`, set socket receive/idle timeouts, and cap concurrent proxy connections (global + per-source semaphore in the accept loops). In `ListenerLoop`: log exceptions, continue on non-fatal errors, break only on cancellation/disposal, and add a supervisor that restarts the loop and surfaces an error state instead of silently reporting running.
- **Dependencies:** none. **Effort:** M
- **Acceptance:** churn test: 50 guests connect/disconnect uncleanly (kill client mid-stream) and the host's socket/task counts return to baseline (no leaked pumps); an injected non-fatal listener exception is logged and the portal keeps serving; a slow-loris proxy connection is reaped by the idle timeout; standing acceptance rule passes.

### R-10 — Portal/API token rework
- **Closes:** A2-10 (High, incl. the A4-13 token-in-page and ungated `/descargar` aspects)
- **Work:** Remove the embedded `{{API_TOKEN}}` from the public landing page; derive the API token server-side from the session invitation the guest arrived with (per-session, rotated per session — not a process-static value); make unauthenticated `/api/p2p-status` return only a boolean (no tunnel URL); gate `/descargar` behind the invitation, or record an explicit owner decision that public download is intended and document the token as anti-CSRF only.
- **Dependencies:** none (coordinate with R-04's token plumbing). **Effort:** S–M
- **Acceptance:** fetching `/` as an unauthenticated tunnel visitor yields no usable API token (page source grep); `/api/*` with a token copied from the page is rejected; p2p-status without credentials returns no URL; an invited guest's full flow (portal → status → download → join) still works; standing acceptance rule passes.

### R-11 — Godot state-transfer caps and state-request authorisation
- **Closes:** A3-9 (High, blob reassembly), A3-8 (Medium, `_pedir_estado`), A3-10 (Medium, unbounded island spawn), A3-11 (Medium, unbounded prims deserialisation)
- **Work:** In Construccion.gd's blob transfer: cap `total` (e.g. 4 MiB) and `partes` in `_blob_ini`, reject parts that would exceed the declared compressed size, enforce part sequence numbers, expire incomplete transfers after a few seconds, and limit concurrent inbound blobs per island. Restrict `_pedir_estado` to the island's owner (same `_validar_remitente` check as the editing RPCs) or to peers the host spawned that island for, with a per-peer cooldown and a cached compressed blob per island version. Validate `_spawn_island_for_player` indices against a session maximum (hard cap, e.g. 512) and require the `id` to be a known peer; rate-limit spawns. Enforce the per-island prim cap inside `Prims.deserializar_isla` and stream instantiation across frames for large states.
- **Dependencies:** after #60 merges (same files). **Effort:** M
- **Acceptance:** hostile-host test client: a `_blob_ini` declaring a 1 GB total is rejected without a large allocation; endless `_blob_parte` streams are cut at the cap; abandoned transfers expire; a non-owner's `_pedir_estado` is refused and an owner's repeated requests are cooldown-limited and served from cache; spawn RPCs beyond the island cap are ignored; a prims blob declaring 100k prims is truncated at the cap without a freeze; standing acceptance rule passes.

### R-12 — Sync-path residual validation (pers throttle)
- **Closes:** A3-2 (Medium)
- **Work:** Cap the `pers` string length (~256 chars), cache the last-applied personalisation per peer by hash, and enforce a minimum interval (e.g. 1 s) between `Pers.aplicar` calls per peer in PlayerSync.gd; drop `_net_position` packets from peers exceeding the position-sync rate instead of processing them.
- **Dependencies:** after #60 merges (same handler). **Effort:** S
- **Acceptance:** a test peer alternating two `pers` strings at 50 Hz causes at most one mesh rebuild per second on a receiving client; honest 10 Hz sync (position, avatar, personalisation changes at human pace) is unaffected; standing acceptance rule passes.

### R-13 — Outbound-request guards: friend-URL SSRF + SSH host keys
- **Closes:** A2-14 (Medium), A2-16 (Medium, SSH `StrictHostKeyChecking=no` in all tunnel candidates)
- **Work:** In RedP2PServicio/P2PNodo/DescubrimientoP2P: restrict peer URLs to the expected tunnel domains (trycloudflare.com, serveo.net, lhr.life, etc.) or an explicit user-confirmed host; block private/loopback ranges for the HTTP announce/ping flow; disable redirect-following on those HttpClients. For SSH tunnels: ship the known host keys for serveo.net/localhost.run and launch with `StrictHostKeyChecking=yes` + bundled known_hosts (or, if the owner prefers, drop the SSH fallbacks and keep cloudflared only — see R-19); the floor is `StrictHostKeyChecking=accept-new` so key *changes* are detected.
- **Dependencies:** none. **Effort:** S–M
- **Acceptance:** pasting a friend link pointing at `http://192.168.1.1/…` or a redirecting URL produces no request to the LAN target (verified with a local listener receiving nothing); a tunnel to a host presenting a *changed* SSH key fails closed with a visible error; normal tunnel joins still work; standing acceptance rule passes.

### R-14 — Tunnel startup single-flight
- **Closes:** A2-8 / M17 (Medium)
- **Work:** Make `EstablecerTunelEfimeroAsync` single-flight: one async lock / stored Task that all callers (login flow, IniciarP2P, WebNodo button) await; check-and-set the guard under that lock; run `BarrerHuerfano` only once per app start, before any tunnel of that slot is launched — never inside a retryable start method. Apply the same pattern to the parallel :7890 SSH tunnel manager if it shares the pattern.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** rapid double-start (login + button spam) yields exactly one tunnel process and one stable public URL across 10 trials; killing the tunnel and restarting produces a fresh URL with no orphan sweep killing the new process; standing acceptance rule passes.

### R-15 — Per-guest revocable invitations and replay resistance
- **Closes:** A2-17 (Medium)
- **Work:** Issue per-guest, short-lived invitation tokens the host can revoke individually (replacing the single session-long bearer token adopted unchanged by guests); add per-connection nonces to the chat and game join handshakes and reject replayed handshake frames; document in the README that direct LAN play is unencrypted, or route LAN guests through the TLS-terminating tunnel path as well (owner's product call).
- **Dependencies:** R-04 (handshake credential) and R-06 (server-side UID) merged. **Effort:** M–L
- **Acceptance:** revoking one guest's token disconnects/blocks only that guest; a captured handshake replayed verbatim is rejected; an expired invitation is refused with a clear message; standing acceptance rule passes.

---

## Stage 3 — Update chain & supply chain

### R-16 — OTA apply re-verification, rollback, and resume fix (Windows)
- **Closes:** A4-1 / H3 (High), A4-2 / H4 (Medium)
- **Work:** In `UpdateApplier.ApplyPendingUpdate`: read `asset` + `sha256` from state.json, require the pending file name to match the asset exactly, recompute SHA-256 and abort (current exe untouched) on mismatch. In the generated .bat: check errorlevel after the copy, verify the new file exists with the expected size before deleting state, restore `.old` automatically if the copy or the first launch fails, and keep `.old` until the new version confirms a successful start itself. In `UpdateDownloader`: if the .part length already equals the asset size, skip the HTTP request and go straight to SHA-256 verification; never delete the .part before `EnsureSuccessStatusCode()`; treat a 416 with a full-size .part as "already complete — verify".
- **Dependencies:** none. **Effort:** M
- **Acceptance (plan Stage 2 tests):** manual bricked-apply test — target exe locked during apply → the .bat restores from `.old` and the old version runs; a pending exe whose bytes were swapped after download is refused at apply (hash mismatch, current install untouched); a complete `.part` is reused without re-downloading (log-verified); the existing update selftests stay green; standing acceptance rule passes.

### R-17 — Release signing (the strategic fix)
- **Closes:** A4-8 / G3 (High)
- **Work:** Choose the route (plan Stage 2 item 10): cross-platform minisign/ed25519 detached signatures over a SHA-256 manifest, or Authenticode per RID. Sign the binaries **and** SHA256SUMS in the release process with a key held outside GitHub; pin the public key in both viewers; verify the signature in UpdateDownloader **and** at apply time (R-16) in addition to the digest. Drop UpdateChecker's any-`.exe`/any-`.zip` asset fallback (exact expected asset names only) and require explicit opt-in for prereleases.
- **Dependencies:** R-16 (apply-time verification point). **Effort:** L
- **Acceptance:** an update package with a valid digest but no/invalid signature is rejected on both viewers; a release containing extra arbitrarily-named .exe assets does not change which asset is selected; prereleases are never auto-selected without opt-in; a correctly signed release updates both viewers end-to-end; standing acceptance rule passes.

### R-18 — Linux updater parity
- **Closes:** A4-9 (Medium, digest-optional), A4-10 (Medium, manual apply / no resume)
- **Work:** Mirror the Windows fail-closed policy in `ActualizadorLinux.Verificar`: no valid 64-hex SHA-256 digest → reject the download (if GitHub omits digests for some assets, consume the signed manifest from R-17 instead of weakening the check). Add a real Linux applier: re-verify the stored package immediately before applying, extract to a staging directory with per-entry path containment, swap with a kept backup of the previous version, and roll back on failed first start. Add Range resume with the R-16 semantics (or keep the .part and report restart honestly).
- **Dependencies:** R-16 (shared semantics); signature verification part depends on R-17. **Effort:** M
- **Acceptance:** a package with a missing digest is rejected on Linux exactly as on Windows; a package replaced in the actualizaciones folder after download is refused at apply; a broken package rolls back to the previous working version; an interrupted download resumes instead of restarting (or reports honestly); standing acceptance rule passes.

### R-19 — Verified third-party binaries + asset-name sanitisation
- **Closes:** A4-5 / M19 (High, cloudflared), A4-12 (Medium, asset-name path traversal, both viewers)
- **Work:** Pin a specific cloudflared version; download from the versioned release URL; verify the published SHA-256 (and Authenticode where available) after download and before first execution; cache the verified hash; store the binary only under the app's LocalAppData folder; remove the `%TEMP%` and bare-PATH candidates from the trust list (or verify signatures for found binaries too). (The latent P2PWebNode copy is deleted in R-03; if any Kubo download survives elsewhere, apply the same pin+verify rule and remove the IPFS API wildcard CORS.) In both downloaders: reduce the release asset name to `Path.GetFileName`, reject empty/dot-segment results, require the expected extension, and assert the full destination path stays inside the pending/downloads directory before any I/O.
- **Dependencies:** R-03 (so only the live copy remains). **Effort:** S–M
- **Acceptance:** a cloudflared binary with a modified byte is refused and never executed; a pre-planted `%TEMP%\cloudflared.exe` is ignored (or signature-rejected); a release asset named `../../evil.exe` (or an absolute path) is rejected before any file is written outside the pending dir; a normal first-run tunnel setup still works; standing acceptance rule passes.

### R-20 — Dependency hygiene: lockfiles, servicing bumps, AForge exit path
- **Closes:** A5-12 (Low), A5-10 (Medium), and the unscanned half of plan G7
- **Work:** Commit lockfiles: uv/pip-tools (or equivalent) for Python with per-package manifests for the currently undeclared packages (SBSTM/STMIPFS/STM_BKCH/STM_SGR/STM_IA), and a .NET packages lock file in restore-locked mode. Bump Avalonia/Desktop/Themes.Fluent/Fonts.Inter 11.2.3 → current 11.3.x servicing and System.Management 8.0.0 → current servicing. Add a scheduled vulnerability scan (pip-audit + `dotnet list package --vulnerable`) to the fixed CI (R-29) so the NOT PROVEN gap in the audit closes permanently. Plan the AForge.Video migration (OpenCvSharp / FlashCap / Media Foundation), remove the NU1701 suppression, and add the interim third-party notice (also plan G8 for AForge's LGPL-3.0).
- **Dependencies:** R-29 for the CI scan step (the rest is independent). **Effort:** M (AForge migration itself is a separate later slice if it grows)
- **Acceptance:** clean-machine installs reproduce identical dependency sets from the lockfiles; the vulnerability scan runs in CI and reports zero un-triaged criticals for the pinned set; NU1701 suppression is gone and the build stays 0/0; webcam capture works after the AForge replacement (or the migration is split out with its own PR and the notice lands here); standing acceptance rule passes.

---

## Stage 4 — Python data integrity & local services

### R-21 — Ledger integrity pack
- **Closes:** A1-2 / H1 (High), A1-8 (Medium)
- **Work:** In BKSVCB's load path: on any load/parse error, refuse to start (or start read-only), preserve the bad file as `blockchain_ledger.json.corrupt-<timestamp>`, log at ERROR, and never call `guardar_ledger()` from the recovery path. After a successful load, recompute every block's Merkle root and hash, verify the link chain and PoW prefix, and quarantine the file on the first mismatch. (Interlock the two changes — they share the loader.)
- **Dependencies:** none. **Effort:** M
- **Acceptance (plan Stage 0 pattern):** a hand-corrupted ledger planted in a test → it is renamed/quarantined with a warning, no history is silently replaced, and the service does not mine on top of a forged chain; a ledger with one edited transaction (stored hashes untouched) is rejected at load; a valid ledger loads and `/status` validation agrees with the load-time verification; the H1 containment tests stay green; standing acceptance rule passes.

### R-22 — Honest IPFS receipts (the shim contract)
- **Closes:** A1-3 / V5 (High), A1-4 / M13 (High), A1-11 / M14 (Medium), A1-18 (Low)
- **Work:** Enforce one contract everywhere a shim/manager result is consumed: a receipt counts as success only when `ok is True` and the CID is not `QmLocal*` / `modo == "local-sin-daemon"`. Specifically: `stm_registro._subir_via_manager` checks `ok`; local record files are deleted only after a verified retrieval (download by CID, hash-compare), otherwise an explicit "NOT uploaded" warning is printed; BKSVCB records `cid_ipfs` only on `ok`, else an explicit `ipfs: unavailable` marker; IALOCAL's session close calls the real `almacenar_pesos` API, checks `ok`, and deletes `MODELOS_DIR` only after verified upload or explicit user confirmation, surfacing the shim's `error` verbatim; `ipfs_launcher.descargar_pesos_desde_ipfs` returns the manager's actual result; all CID values placed in IPFS API query strings are URL-quoted. Update the two tests that assert the fake-CID behaviour (`test_sistema.py:69`, `test_h1_contencion.py:105`) to assert the honest contract instead.
- **Dependencies:** none (coordinate with R-21 — same files, different functions). **Effort:** M
- **Acceptance:** with the IPFS daemon stopped, the CONTRRF publish flow keeps the local record and prints NOT uploaded (no deletion, no success message); the ledger records an explicit unavailable marker and mines no `QmLocal*` CID (grep of a test ledger); IALOCAL close with the daemon down keeps the models or asks; the updated tests pass and the suite shows no new failures; standing acceptance rule passes.

### R-23 — BKSVCB HTTP service hardening
- **Closes:** A1-7 (High; network-crew duplicate graded the loopback configuration Low — this slice satisfies both gradings)
- **Work:** Require a per-session random token (header) on all mutating routes of `bksvcb_net.py`; move `/mine` and `/transform` to POST-only; cap request bodies (e.g. 1 MiB → 413) and reject negative/invalid `Content-Length`; keep the loopback default bind and warn loudly on any non-loopback bind.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** unauthenticated POST `/transaction` and GET `/mine` from a test script (and from a browser-origin request) are rejected; an oversize body gets 413 without a handler thread pinning; the legitimate local client flow with the token still works; standing acceptance rule passes.

### R-24 — Vault crypto: remove the seed fallback, adopt AEAD
- **Closes:** A1-5 / M8 (High), A1-6 (Medium)
- **Work:** Remove the `_MASTER_SEED` fallback from `vault_openrouter.py`: require `OPENROUTER_VAULT_PW` (or an OS keychain entry) and refuse to encrypt/decrypt without it. Replace the repeating-XOR construction with a real AEAD (`cryptography` Fernet or AES-GCM/ChaCha20-Poly1305) with a per-blob random nonce; keep a one-time migration path for legacy blobs (decrypt-with-old, re-encrypt-with-new, then drop the legacy decoder). Document prominently: **any OpenRouter key ever stored under the default seed must be rotated** — the seed is in public git history and cannot be un-published.
- **Dependencies:** none. **Effort:** S–M
- **Acceptance:** with the env var unset, encrypt and decrypt both refuse with a clear error (no silent fallback); a vault written by the new code round-trips and fails loudly on a flipped ciphertext byte (AEAD tag); a legacy default-seed vault migrates once and the old seed no longer decrypts new blobs; standing acceptance rule passes.

### R-25 — Python download integrity (voice models + GGUF)
- **Closes:** A1-9 / M5 (Medium), A1-10 / L2 (High)
- **Work:** Piper voice models: pin each model by HF revision (commit hash), download to a `.part`, verify a recorded SHA-256, rename only on verified completion, delete partial files of any size on failure. GGUF downloads (both `IALOCAL/gestor.py` and CONTRRF `stm_modelos.py`): same pattern — `.part` download, verify `bajados == Content-Length` **and** a pinned SHA-256 (HF exposes one per file/revision), atomic rename; treat any pre-existing final file without a matching recorded hash as absent; remove stm_modelos' size-heuristic `.part` adoption.
- **Dependencies:** none. **Effort:** M
- **Acceptance:** killing a download mid-way leaves no "valid" model (next run re-downloads or resumes the .part, never loads the partial); a served file with a wrong digest is rejected; a complete verified download loads in Piper/Ollama exactly as before; standing acceptance rule passes.

### R-26 — Python execution-safety pack
- **Closes:** A1-13 (High, `trust_remote_code=True`), A1-12 / L7 (Medium, runtime pip installs), A1-14 (Medium, pickle loading API)
- **Work:** Drop `trust_remote_code` from the IALOCAL LLM fallback (the Qwen2.5-Coder family is natively supported); if any future model truly needs it, pin `revision=` to an audited commit and document the exception. Move `huggingface_hub` and `llama-cpp-python` into the pinned setup-time requirements (with hashes, coordinating with R-20's lockfile) and replace the runtime `pip install` calls with a clear "dependency missing, run setup" failure. Replace the LC_STM pickle load helpers with a data-only format (JSON + `.npy`/safetensors-style arrays with explicit shapes); mark the pickle helpers deprecated-and-unsafe during the transition and remove them once callers migrate.
- **Dependencies:** R-20 for the lockfile home (can proceed in parallel with a temporary pinned requirements file). **Effort:** M
- **Acceptance:** the fallback LLM loads with `trust_remote_code` absent (grep-verified) and works on the pinned revision; a missing dependency produces the setup message and **no** pip subprocess runs (test with pip blocked); a crafted pickle file offered to the new loader is rejected as data, never unpickled; standing acceptance rule passes.

### R-27 — Python hazard cleanup
- **Closes:** A1-15 / M10 (Medium, machine-wide `taskkill`), A1-16 / M12 (Medium, `split_tool.py`), A1-19 (Low, PowerShell string interpolation)
- **Work:** Replace bat_runner's image-name `taskkill /F /IM ipfs.exe` with PID-targeted termination of the daemon this code started (the `ipfs_launcher` pattern) or the Kubo API shutdown endpoint. Delete `SBSTM/split_tool.py` from the tree. In `voice_engine.py`'s Windows fallback, pass the text to speak out-of-band (temp file / stdin / environment variable read by a fixed text-free script, or the COM path already in the same file) — never interpolate content into a `-Command` string.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** stopping the daemon leaves an unrelated `ipfs.exe` process alive (two-daemon test); `split_tool.py` is absent and nothing imports it (grep); a speech text containing quotes/`$()`/backticks is spoken verbatim with no command execution (test with a canary string); standing acceptance rule passes.

---

## Stage 5 — Local protections, CI, scripts, docs

### R-28 — Access-key rework + Linux parity + honest PC seal
- **Closes:** A4-3 / M18 (High), A4-4 (Medium), A4-15 (Low)
- **Work:** Sign `llave_acceso.json` at issuance with a key the client cannot mint (server-issued signature, or an HMAC whose secret is not derivable from public hardware data); verify the signature at login; replace the model-string hardware hash with the serial-based `MaquinaHuellaDigital` fingerprint (serials + HKDF); **fail closed** when the fingerprint or the `hardware_hash` field is missing/empty, and when WMI is unavailable; verify `seed_hash` against the wallet seed it claims to bind. Implement the same verification in the Linux viewer's `CuentaLinux.Acceder` (account-format parity). For the one-account-per-PC seal: read the UUID only after HMAC verification, and document the seal as tamper-evidence, not enforcement (any real multi-account rule belongs server-side / in the P2P layer).
- **Dependencies:** none. **Effort:** M
- **Acceptance:** a hand-written key file (`{"usuario":"<name>","hardware_hash":""}`) is rejected on both viewers; a genuine key copied to a *different* PC model is rejected; a genuine key on its own machine still logs in; deleting/tampering with the seal is detected (not silently reset) and reported; the Linux viewer performs the same key step as Windows; standing acceptance rule passes.

### R-29 — CI promotion and repair + C# test project seed
- **Closes:** A5-6 / H8 (Medium), A5-7 / H9+H10+H14 (Medium), §5.1 H11 (no C# test project)
- **Work:** Promote `ci.yml` to the root `.github/workflows/` (the plan's Stage 3 shape); rewrite its 9 `working-directory`s to the real tree (`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_aeef1149/src`); remove the `|| pip install` masking fallback (install exactly the manifest from R-20's lockfile); add `-p:SkipGodotAssets=true` to the C# build; remove `continue-on-error: true` once the suite is hermetic (plan M26–M28: a `conftest.py` redirecting ledger/PSNRL/caches to `tmp_path`, IPFS fixture or fake binary, Ollama socket mock, time asserts → recorded metrics or 10× caps); make the summary step reflect actual step outcomes. Seed a `Visor3D.Tests` project (xunit) porting the five console selftests (Update/Cuenta nearly verbatim; Red/Chat with loopback sockets) and wire `dotnet test` into CI. Also add the dependency vulnerability scan from R-20 and the secret-scan tripwire from R-02 as CI steps. (Per the plan, trigger on push/PR to `development` and `main`.)
- **Dependencies:** R-02 (secret scan), R-20 (lockfile + scan). **Effort:** M
- **Acceptance:** the `development` branch shows real checks on GitHub; a push that breaks a genuine behaviour test turns the build red (demonstrated with a throwaway breakage on a test branch); the suite runs twice in a row on a clean runner with no environment- or timing-related failures; `dotnet test` runs the ported selftests; a C# build on a clean clone succeeds with SkipGodotAssets; standing acceptance rule passes.

### R-30 — Dangerous-scripts and launcher hygiene
- **Closes:** A5-8 / H12 (Medium), A5-9 / H13 (Medium), A5-13 / M9 (Low), A5-15 (Low), A5-11 (Medium, opencode auto-allow)
- **Work:** Delete `borrar_packs_viejos.ps1` and document the supported route (`git reflog expire` + `git gc --prune=now` from the repo root). Delete `purgar_repositorio.ps1`, or rewrite it anchored to `git rev-parse --show-toplevel` with a WhatIf/dry-run default, a confirmation flag, per-item reporting, and a success banner only when deletions actually occurred. Remove all hardcoded absolute developer paths (`C:\Users\User\Desktop\…`, E:/F: trees, dead snapshot names) from stm_base.py, GodotConfig.cs, publish_release_v275.ps1 and the .bat launchers; resolve the Godot engine relative to the executable/install dir or via an explicit env var (the Python side's `GODOT_BIN` pattern), never returning a path that was not verified to exist, and never trusting a Desktop location as an executable source ahead of the app folder. Replace the `ExecutionPolicy Bypass` launcher with RemoteSigned/signed scripts or the Godot addon's own cleanup. Tighten `opencode.jsonc`: move `node`/`npm`/`npx` from wildcard-allow back to `ask` (or allow only specific known subcommands/scripts), keeping the existing deny list.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** no script in the repo references a drive-letter user path or a dead snapshot (grep-verified); the purge replacement in dry-run mode lists exactly what it would delete and deletes nothing; `git gc` documentation replaces the pack script; the launcher works without an execution-policy bypass; an agent session with the tightened opencode config prompts before running arbitrary node/npm commands; standing acceptance rule passes.

### R-31 — Documentation truth: PCK rebuild instructions
- **Closes:** H15 (§5.1, coordinator-verified in substance)
- **Work:** Rewrite README §11 per the plan's Stage 0 item 0.7: state plainly that the PCK is **not** rebuilt from this repo and point to the release assets as the only source of the world binary; reconcile §11 with §17 (and, while there, the plan's neighbouring doc items: §18's 41→43 document count and the `src/README_DESARROLLO.md` index entry from Stage 0 item 0.8, if the owner wants them in the same PR).
- **Dependencies:** none. **Effort:** S
- **Acceptance:** a new reader following §11 cannot conclude the PCK is rebuildable from a clone (checklist review against the plan's Stage 0 acceptance criteria); no §11/§17 contradiction remains; standing acceptance rule passes (docs-only).

### R-32 — Local-state and launch hygiene (Godot/C# seam)
- **Closes:** A3-13 / M24 (Low, security angle), A4-16 (Low, Godot argument-string injection)
- **Work:** Write `registro.cfg` atomically (temp file + rename) through a single-writer helper used by all five current writers (ChunkManager, Identidad, Personalizacion, SLAV, registro), and cache the `p2p_session.json` poll behind an mtime check. On the Windows launcher: build the Godot process arguments with `ProcessStartInfo.ArgumentList` (the Linux `LanzadorMundo` pattern) instead of a concatenated Arguments string; validate the parsed target host as a hostname/IP literal (reject whitespace/quotes); construct the peer URL from a parsed `Uri` instead of the raw invitation-link string.
- **Dependencies:** none. **Effort:** S
- **Acceptance:** killing the client mid-save never truncates `registro.cfg` (fault-injection test: repeated kill during the save window, identity/island binding intact on next launch); an invitation link containing quotes/spaces cannot smuggle extra user arguments into the Godot launch (argument list inspected in a test harness); normal launches from link, scheme and command line all still work; standing acceptance rule passes.

### R-33 — (Structural, optional) Extract security logic out of the MainWindow god-class
- **Closes:** A4-18 / M20 (Info, context)
- **Work:** Extract authentication/key verification (R-28), the updater client (R-16/R-17) and tunnel management (R-14/R-19) from `MainWindow.xaml.cs` into the existing service classes, with the window calling them; add focused unit tests for the extracted security decisions (feeding R-29's test project). Best done incrementally as the Stage 3/5 slices touch each area, rather than as one big-bang refactor.
- **Dependencies:** rides along with R-14, R-16, R-19, R-28. **Effort:** M–L (spread across those slices)
- **Acceptance:** the extracted services have direct unit tests for their security decisions (key verification accept/reject, apply-gate hash check, tunnel single-flight); MainWindow contains no direct credential, hash or process-launch logic; standing acceptance rule passes.

---

## What this roadmap deliberately does not do

- **It does not re-litigate the plan's non-security stages.** The Implementation Plan's Stages 0, 2 (non-security items), 4, 5 and 6 (documentary truth beyond H15/R-31, honest neural core V1/V4/V6, repository structure, product/ecosystem) remain the owner's programme; this roadmap covers the security findings only. Plan items the audit did not re-verify (V1, V3, V4, V6, G6, G8, G9, and the M/L items listed in audit §5.3) are accounted for in the audit's mapping section, not silently dropped.
- **It does not schedule the payload investigation (R-01b) as code work** — deobfuscation and any disclosure decision belong to the repo owner.
- **Every slice is a proposal until the owner merges it.** The collaboration's rule stands: per-slice branches + PRs, owner judges, no direct pushes to `main`, no force-pushes.

*— End of roadmap. Companion document: `SECURITY_AUDIT_2026-11-05.md`.*
