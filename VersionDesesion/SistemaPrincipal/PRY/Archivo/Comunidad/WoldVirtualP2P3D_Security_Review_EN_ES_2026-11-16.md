# WoldVirtualP2P3D: Responsible Security Findings and Remediation Guide
# WoldVirtualP2P3D: Hallazgos de seguridad y guía de corrección responsable

**Date / Fecha:** 2026-11-16  
**Repository / Repositorio:** https://github.com/Chicook/WoldVirtualP2P3D  
**Reviewed branch / Rama revisada:** `main`  
**Reviewed HEAD / Commit revisado:** [`758d964eca48c607631abc88e5fb2108282d76fa`](https://github.com/Chicook/WoldVirtualP2P3D/commit/758d964eca48c607631abc88e5fb2108282d76fa) (2026-11-15)  
**Method / Método:** Read-only examination of repository source, tree, commits, published documentation, and issues; **no suspicious code was executed**. / Inspección de solo lectura del código, árbol, commits, documentación e incidencias; **no se ejecutó código sospechoso**.

> **Purpose / Propósito:** This is a constructive, evidence-based report to help the project owner and contributors resolve problems. It is **not** an accusation against any named person, and it does **not** claim that the published v2.8.4 executable has been proven infected. This review is about the **source tree at the commit above**.  
> Este es un informe constructivo, basado en pruebas, para ayudar a la persona responsable y a quienes colaboran con el proyecto. **No** acusa a ninguna persona y **no** afirma que se haya demostrado una infección del ejecutable v2.8.4 publicado. Se examina el **árbol de código del commit indicado**.

---

# PART I. ENGLISH

## 1. Executive summary: what needs urgent attention

WoldVirtualP2P3D contains substantial work on an open-source Godot/C# virtual world, networking, and the LucIA AI subsystem. This report recognizes that work. It also documents several security and engineering problems that should be fixed before the current checkout or generated binaries are trusted.

**Most urgent finding:** the current `main` tree contains a Python module that retrieves JavaScript from Ethereum transaction data and executes it using Node.js. A documented direct-execution entry point imports that module *before* running any defensive scanning. The mechanism closely matches the project's own earlier November 5 audit of an Ethereum-based remote-code loader. **Its presence and the direct-import path are verifiable; whether it executed on any particular user's computer or was included in a published executable has not been established by this review.**

**Second major finding:** previously documented P2P authentication protections appear absent from the currently tracked implementation. The `POST /peer` handler accepts arbitrary submitted URLs without checking a session token, validating the URL, limiting the list size, or rate-limiting registration. Its service is paired with a public tunnel manager. The chat relay also listens on all interfaces and its reviewed WebSocket handshake authenticates no session identity.

**Immediate request to maintainers:** temporarily pause recommending that people execute a fresh checkout, development scripts, or new builds until the code-execution path is removed and a clean release is independently tested. A publicly accessible source-code view, read-only security review, or a carefully isolated forensic environment is appropriate in the meantime.

### Severity and certainty

| ID | Severity | What was observed | Verification status |
|---|---|---|---|
| S-01 | **Critical** | Ethereum transaction → untrusted JavaScript → Node.js execution | **Confirmed in current source** |
| S-02 | **Critical** | Defensive CLI imports S-01 before its security checks | **Confirmed for the documented direct-file entry point** |
| S-03 | **High** | `POST /peer` has no authentication, input bounds, or registration limit | **Confirmed in current source** |
| S-04 | **High** | Chat listener is exposed on all interfaces; its WebSocket handshake has no session-authentication requirement | **Confirmed in reviewed listener and handshake** |
| S-05 | **High** | Direct LAN WebSocket URLs omit invitation tokens; network resolver logs command-line arguments | **Confirmed in current resolver; full end-to-end exploit not tested** |
| S-06 | **High** | Windows pending-update application does not re-check the executable hash immediately before replacement | **Confirmed in reviewed updater; full update trust chain not independently audited** |
| S-07 | **High** | SSH tunnel launch disables SSH host-key verification | **Confirmed in current tunnel manager** |
| S-08 | **Medium** | `.gitignore` does not explicitly exclude `.env` / `.env.*` files | **Confirmed configuration gap; no current secret leak established** |
| S-09 | **High for assurance** | No workflow at repository-root `.github/workflows/`; nested CI refers to obsolete paths | **Confirmed from current tree and workflow** |
| S-10 | **Medium** | Broken/stale paths, tests, documentation, and mismatched Linux/Windows version metadata | **Confirmed examples; not all modules reviewed** |

**Important:** S-03 through S-10 are not all evidence of planted malicious code. They are separate vulnerabilities, reliability problems, or gaps in validation. Preserve that distinction when commenting publicly.

## 2. Exact dangerous files and removal instructions

For compactness, the actual source root is:

```text
SRC = VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src
```

Every relative path below is below `SRC` unless explicitly stated otherwise. The links point to the **reviewed commit**, not a moving branch.

### S-01. Ethereum-based remote JavaScript execution (CRITICAL)

**Exact file:**

```text
SRC/STM_HRTS/STM_DEF/utils/transport.py
```

**Verified source:** [transport.py at reviewed commit](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_HRTS/STM_DEF/utils/transport.py)

**What it does, in ordinary language:**

1. Contacts an Ethereum transaction-indexing service for transactions linked to a hard-coded wallet.
2. Retrieves transaction input through a public Ethereum JSON-RPC endpoint.
3. Decodes the input bytes as JavaScript.
4. Writes this JavaScript to a temporary `.js` file.
5. Invokes `node` on the temporary file.
6. Deletes the temporary file and suppresses exceptions.

The particularly important behaviors are represented by `eth_getTransactionByHash`, `bytes.fromhex(...)`, `NamedTemporaryFile(..., suffix=".js")`, `subprocess.run(["node", ...])`, and exception handlers that silently ignore errors.

**Why it is dangerous:** whoever controls the referenced Ethereum transaction data can change the code that a local computer is asked to execute. There is no verified, fixed, signed application update package. A blockchain transaction is only a data source, **not** a security guarantee. The project's earlier audit described this pattern as an *EtherHiding* or on-chain dead-drop loader; see [security audit PR #64](https://github.com/Chicook/WoldVirtualP2P3D/pull/64).

**Easy corrective steps:**

1. **Do not run this module or import it to test it.** Do not contact its remote endpoints as part of a casual verification.
2. Preserve an evidence copy in a restricted incident-response archive if the maintainer wishes to investigate provenance. Do not keep an executable copy in the normal runtime source tree or publish it as a sample script.
3. **Delete `SRC/STM_HRTS/STM_DEF/utils/transport.py` from active source** in a reviewable security PR.
4. Remove every production import or launcher that refers to it, particularly S-02 below.
5. Review the tracked history and all long-lived branches for a return of the same logic. Fix the regression source, not only one occurrence.
6. Add a **static test** that fails if runnable production code contains this network-download-and-execute sequence. Harmless quoted examples inside security-test fixtures must be identified separately from executable modules.

**Acceptance test:** the active source tree has no executable EtherHiding loader; no direct or indirect import invokes it; no normal setup, editor-open, test discovery, packaging, or launch action fetches and executes remote Ethereum-sourced code. A separate security reviewer confirms this before deployment.

### S-02. Defensive CLI runs the loader before its safety gate (CRITICAL)

**Exact file:**

```text
SRC/STM_HRTS/STM_DEF/__main__.py
```

**Verified source:** [defensive CLI entry point](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_HRTS/STM_DEF/__main__.py)

Near the top, **before** the `if __package__` branch and the scanning routines, it includes:

```python
import utils.transport
import utils.session
```

The first import is the immediate problem. When this file is run directly as documented (`python STM_HRTS/STM_DEF/__main__.py informe` from the appropriate source directory), Python can resolve `utils.transport` to the neighboring `STM_DEF/utils/transport.py`, **executing its top-level statements during import**. The second import appears to reference a `session.py` file absent from that same directory; even if that subsequently fails, the preceding dangerous import has already been attempted.

**Scope limitation:** behavior of `python -m STM_HRTS.STM_DEF` depends on the interpreter's module search path. This review does not assert that every invocation mode reaches the same module. The documented **direct-file form** is sufficient to establish the serious risk.

**Easy corrective steps:**

1. Delete **both** unnecessary top-level imports of `utils.transport` and `utils.session` if no legitimate, independently verified purpose requires them.
2. Keep only reviewed, package-relative imports of known benign defensive components.
3. Ensure that the security scanner does **not** execute a file merely to inspect it. Static analysis should read text as data.
4. Correct the documentation and add tests for both documented CLI invocation forms. Run these tests **only after S-01 and S-02 are removed**, in an isolated environment.

**Acceptance test:** importing or launching the security CLI produces **zero network requests and zero child Node.js processes** before it validates the project. Both CLI invocation modes either work safely or fail explicitly without side effects.

### S-03. P2P `/peer` endpoint accepts unauthenticated registrations (HIGH)

**Exact files:**

```text
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PNodo.cs
SRC/VSC#/Visor3Ddesarrollo/RedP2P/RedP2PServicio.cs
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs
```

**Verified sources:** [P2PNodo.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/P2PNodo.cs), [RedP2PServicio.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/RedP2PServicio.cs), and [P2PTunnelManager.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs).

`P2PNodo.ProcesarPeticionAsync` reads `POST /peer` JSON and adds `url` to a growing `Pares` list, with **no session invitation validation, URL allowlist, request-body limit, list cap, or per-client rate limit** in the reviewed path. The node listens locally, but its service creates a public tunnel directed to that local port. Network exposure must therefore be evaluated across the **tunnel**, not only by noticing a loopback listener.

The repository previously merged a targeted fix in [PR #62](https://github.com/Chicook/WoldVirtualP2P3D/pull/62). The current code lacks the `RegistrarPar`, `TokenInvitacion`, `MaxPares`, and related safeguards described there. Existing tests in `SRC/tests/STM_test3/test_stage1_s6_registro_pares.py` encode the desired behavior, but still point at an older `VSC#/Nucleo/` directory that is not the current implementation path.

**Easy corrective steps:**

1. Restore the behavior of PR #62, **adapted to the current directory structure** rather than blindly restoring old files.
2. Require a strong, unpredictable **session-specific invitation credential** for every `/peer` registration; missing or incorrect credential must return `401` without modifying state.
3. Accept only valid, absolute HTTP/HTTPS peer URLs with bounded length; reject unexpected URL schemes, embedded credentials, and malformed values. Enforce request-body limits.
4. Cap registered peers (for example, 100) and rate-limit submissions per source socket address. Synchronize concurrent modifications.
5. Ensure a legitimate client passes the **destination session's** credential when announcing itself; do not put secrets into logs.
6. Retain public read-only discovery endpoints only after checking their information disclosure and abuse limits.
7. Repair the test paths and add **behavioral** integration tests, not just string-based source checks.

**Acceptance test:** no token and wrong token return `401`; bad URL returns `400`; repeated requests receive `429` when appropriate; peers cannot grow without a limit; valid invited peers still connect; tests pass on the current source layout.

### S-04. Chat relay does not authenticate the direct socket connection (HIGH)

**Exact file:**

```text
SRC/VSC#/Visor3Ddesarrollo/Chat/ChatRelayServer.cs
```

**Verified source:** [ChatRelayServer.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/Chat/ChatRelayServer.cs)

The listener binds to `IPAddress.Any` (all interfaces), typically on ports 8920–8929. `Handshake(...)` checks ordinary WebSocket headers and a `/chat` route but **does not verify an invitation token or authenticated peer identity**. Subsequently, `hello` accepts caller-supplied names and user IDs. A proxy may impose controls on tunnel traffic, but that does **not** protect a directly reachable LAN socket bound to all interfaces. The HTTP-header read also has a size cap but **no clear per-connection deadline**; the client limit is checked after header reading, allowing a resource-exhaustion surface.

**Easy corrective steps:**

1. Check the invitation and authenticated session identity **at the relay itself**, before upgrading to WebSocket or accepting messages. Do not rely on the web portal as the only gate.
2. Bind to loopback if only the local proxy should reach the relay. If LAN access is necessary, enforce authentication there too and review the firewall policy.
3. Set short pre-handshake timeouts and cap the total number of pending, not-yet-authenticated connections.
4. Bind the chat identity to an authenticated session instead of trusting a self-declared `uid`.
5. Add tests for unauthenticated LAN clients, valid invitees, forged identities, idle/slow connections, and reconnection.

**Acceptance test:** direct unauthenticated connections never reach chat; legitimate authorized users still can; forged IDs do not impersonate another user; slow unauthenticated clients cannot exhaust the service.

### S-05. LAN invitation bypass and invitation-token logging (HIGH)

**Exact file:**

```text
SRC/MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd
```

**Verified source:** [Red.gd](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd)

`resolver_url_ws()` attaches `?invitacion=...` **only when the URL starts with `wss://`**; direct `ws://` LAN connections omit the credential. The resolver additionally prints the entire evaluated command-line argument list, which may include `--peer-url=...invitacion=...`. This potentially exposes invitation secrets in console output or saved logs. The existing security roadmap already identified the LAN-credential gap as R-04.

**Easy corrective steps:**

1. Require a session credential for **both** direct LAN `ws://` and tunnel `wss://` connections, with the authoritative host checking it during connection setup. Transport encryption and authentication are separate concerns.
2. Avoid transmitting credentials in reusable URLs where possible. Use a short-lived challenge/response handshake or another authenticated connection mechanism.
3. **Remove the raw `print(...all_args)` call** or replace it with a strict allowlist of non-sensitive diagnostics, never raw URLs or tokens.
4. Verify that host-discovery beacons cannot cause silent redirection to an untrusted host.
5. Test the authorized and unauthorized connection paths on two machines.

**Acceptance test:** a LAN client without the session credential is rejected; no invitation appears in console logs or crash diagnostics; correct clients still join.

### S-06. Update application lacks final integrity check (HIGH)

**Exact files:**

```text
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateApplier.cs
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateChecker.cs
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateDownloader.cs
```

**Verified sources:** [UpdateApplier.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/STM_actualizar/UpdateApplier.cs) and [UpdateChecker.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/STM_actualizar/UpdateChecker.cs).

`UpdateApplier.ApplyPendingUpdate` reads a local `state.json`, picks a pending `.exe`, and generates a batch script to replace and relaunch the current application. **This function does not re-verify the pending executable before replacement.** The updater's other components may check a downloaded digest earlier, but that does not protect against subsequent local replacement or a compromised release source. A hash obtained from the same untrusted source as a binary does not independently authenticate its publisher.

**Easy corrective steps:**

1. Stop automatic update application until an end-to-end update-trust test is available.
2. Sign a release manifest with a publisher-controlled key; embed or otherwise independently authenticate the **verification public key** in the application.
3. Before moving or launching a new executable, re-check its hash **and the signature of the manifest that authorizes that hash**. Reject missing or invalid signatures and hashes.
4. Use atomic replacement and a tested rollback procedure; never delete a known-good backup until the new version passes a startup check.
5. Test altered executables, manipulated `state.json`, missing manifests, unexpected filenames, interrupted copies, and rollback.

**Acceptance test:** an altered or unsigned pending binary cannot replace the running application; a failed update leaves a working previous executable.

### S-07. SSH tunnel host-key verification disabled (HIGH)

**Exact file:**

```text
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs
```

The `localhost.run` and `serveo.net` SSH launch arguments include `StrictHostKeyChecking=no` and `UserKnownHostsFile=NUL`. These settings turn off SSH server identity verification. Encryption without server authentication cannot reliably rule out a man-in-the-middle or impersonated tunnel endpoint.

**Easy corrective steps:** remove both bypass settings; use a legitimate, maintained `known_hosts` trust policy, pin or verify host keys through an authenticated channel, and fail safely if the key changes unexpectedly. Test normal tunnel setup, key mismatch, and reconnect behavior. Do not treat a first-time unverified key as proof of identity.

### S-08. Secret files are not explicitly excluded by `.gitignore` (MEDIUM)

**Exact file:**

```text
.gitignore   (repository root)
```

The root ignore file contains `!.env.example` but no corresponding rules excluding `.env` and `.env.*`. This means a future contributor could accidentally commit API keys or credentials from an environment file. **This observation does not prove that secrets have already leaked.**

**Easy corrective steps:**

```gitignore
.env
.env.*
!.env.example
```

Then add a secret scanner to CI, inspect tracked files and history for existing secrets, and **rotate any credential actually exposed**. Git history rewriting alone cannot revoke exposed credentials or clean all forks.

### S-09. Missing active CI and obsolete security-test paths (HIGH for assurance)

**Exact files:**

```text
SRC/STM_HRTS/.github/workflows/ci.yml
SRC/STM_HRTS/STM_DEF/.github/workflows/stm_def.yml
SRC/tests/STM_test3/test_stage1_s6_registro_pares.py
```

There is **no `.github/workflows/` directory at the repository root** in the reviewed tree. Workflows nested inside `src/STM_HRTS` are not registered as repository-wide GitHub Actions workflows. The nested `ci.yml` still uses older `VersionDesesion/CONTRRF/TLLDCD/src` paths instead of the present `VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src` structure. The S6 peer-authentication test expects files under `VSC#/Nucleo` instead of `VSC#/Visor3Ddesarrollo`.

**Easy corrective steps:**

1. Put an audited workflow in **repository-root `.github/workflows/`**.
2. Update all working directories and test paths to match the actual tree.
3. Run safe static checks first; do not use infected code to launch the scanner.
4. Run Python tests, Godot headless tests, .NET Windows/Linux builds, and a security regression suite in disposable CI runners **after** S-01 and S-02 have been removed.
5. Make the security checks required for merges; avoid hiding serious failures behind `continue-on-error: true`.

**Acceptance test:** a pull request triggers the actual workflow; the workflow checks the correct sources; a regression that restores the dangerous import or removes peer authentication fails before merge.

### S-10. Stale architecture paths and version claims (MEDIUM reliability/supply-chain concern)

**Exact files:**

```text
SRC/Rutas.json
SRC/STM_CH/STM_herramientas/rutas_json.py
VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/.vscode/settings.json
SRC/VSC#/Visor3Ddesarrollo/VisorLinux/VisorLinux.csproj
SRC/VSC#/Visor3Ddesarrollo/HerraMientas/Visor3D.csproj
README.md
README_EN.md
```

Examples confirmed:

- `Rutas.json` lives in `.../TLLDCD/src`, but `raices.repo` is `../../../..`, which resolves to **`VersionDesesion/CONTRRF`**, not the repository root. The matching `raices.contrrf` and `raices.version` entries are also too shallow.
- `.dev/.vscode/settings.json` hardcodes a developer-specific `E:/WoldVirtualP2P3D/...` filesystem layout.
- The Windows project declares **2.8.4** while `VisorLinux.csproj` declares **2.8.0**.
- The root READMEs show **2.8.1** and refer to old `actualizacion_bfef2dea` snapshot paths no longer present in the reviewed tree.

**Easy corrective steps:** establish one source of truth for version and paths; repair the relative directory traversal; run path validation on Linux and Windows; eliminate machine-specific absolute paths from distributed editor settings; update README and release information only after checking packaged artifacts. These errors can cause code and tests to target the **wrong location** or silently misrepresent what was shipped.

### S-11. Historical malicious mechanisms: what is and is not present now

The earlier security audit described three mechanisms: (a) VS Code folder-open auto-execution of a disguised `.orc` payload, (b) an obfuscated `opencode/init` executed by `npm start`, and (c) an Ethereum-based Python loader. In the **current reviewed `main` tree**:

- No file named `fa-brand-400.orc` was found.
- No `.vscode/tasks.json` folder-open trigger was found.
- No `SRC/STM_HRTS/opencode/init` was found, although `SRC/STM_HRTS/opencode/package.json` **still references `node init`**. As tracked, that launch step is broken; its absence is **not** proof of an active obfuscated `init` payload in current `main`.
- The Ethereum-based loader **does exist**, now at `SRC/STM_HRTS/STM_DEF/utils/transport.py`, with a direct-file import path described in S-02.

**Recommended action:** inspect all historical/AI development branches and packaging sources before merging or publishing, but **do not claim the earlier `.orc` and `init` payload files still exist in current `main`**. Remove the stale `node init` start command or replace it only with a known, reviewed, harmless setup entry point. Keep inert forensic test samples as quoted data, never as runnable modules.

## 3. A simple, safe remediation sequence for the maintainer

**The following is designed for a reviewable pull request, not a destructive history rewrite.** A contributor does not need to run the suspicious code to identify or remove it.

### Phase A. Stop exposure and preserve evidence

1. Pause recommendations to download, build, or execute from the affected source tree pending a verified fix.
2. If someone may have executed the affected direct CLI or other old triggers, arrange a **separate incident-response review** of that machine: disconnect it from sensitive accounts where appropriate, check process and network history, inspect persistence, and rotate potentially exposed credentials from a clean device. **No execution or compromise is asserted for any specific person.**
3. Record the reviewed commit SHA, exact file locations, file hashes, relevant logs, and related merge history. Restrict access to forensic payload copies.
4. Do not force-push or rewrite history as the first remedy. Preserve history until the scope of the incident is understood; later sanitization requires coordination because old clones and forks persist.

### Phase B. One narrow emergency pull request

For users of the GitHub web interface: open each affected file on the repository, choose **Edit** or **Delete file**, and commit the proposed change on a **new branch**. Ask the maintainer to review and merge the pull request.

At a minimum, the emergency PR should:

- Delete `SRC/STM_HRTS/STM_DEF/utils/transport.py` from runtime code.
- Delete the `import utils.transport` and stale `import utils.session` lines from `SRC/STM_HRTS/STM_DEF/__main__.py`.
- Keep the security scanner as *non-executing* source inspection.
- Disable or repair the broken `node init` start script; inspect third-party package scripts before any install or run.
- Add static regression coverage ensuring those dangerous import/exec constructs cannot be reintroduced into production modules.

**Do not test by launching the malicious loader.** A PR diff and offline static checks are sufficient to confirm the removal itself. For subsequent functional tests, use a clean disposable CI environment and test the fixed tree only.

### Phase C. Repair exposed network services

- Restore invitation validation and rate/size limits to `P2PNodo.cs` (refer to PR #62).
- Authenticate both the chat relay's direct listener and the Godot LAN transport.
- Stop logging invitation arguments; restrict unnecessary network listeners and SSH tunnel behavior.
- Add unauthorized-client tests that prove **denial**, not only normal connection success.

### Phase D. Restore reliable release controls

- Correct canonical paths, version metadata, and tests.
- Put CI at `.github/workflows/` at the **repository root**.
- Sign release manifests; check signatures/hashes immediately before applying updates; test rollback.
- Build from a clean, reviewed commit and record the exact commit, dependency lockfiles, artifact digests, and verification logs.
- Publish a clean release with a concise security advisory and tell users how to verify it. Review all branches before merge to prevent reintroduction.

### Non-executing checks for maintainers

Run only in a **properly isolated, untrusted-code review environment** or use GitHub's browser-based code search. These commands inspect text; they do not import or run the project's Python, Node, .NET, or Godot modules:

```bash
# From the repository root, inspect tracked names and references only:
git ls-files '*transport.py' '*fa-brand-400.orc' '*/opencode/init' '*/.vscode/tasks.json'
git grep -n -E 'import utils\.transport|eth_getTransactionByHash|node init|StrictHostKeyChecking=no' -- '*.py' '*.json' '*.cs' '*.md'
git diff --check
```

**Interpret the results:** the project contains legitimate *textual* indicators inside the incident report, threat-detection patterns, and non-executing test fixtures. Those references need not be deleted; the requirement is that **no production entry point executes such content**. Avoid `python -m STM_HRTS.STM_DEF` or direct execution of its current `__main__.py` until the dangerous import is removed.

## 4. Suggested acceptance checklist for a security-fix PR

- [ ] S-01 loader removed from **runnable production code**; evidence retained securely outside the active runtime.
- [ ] S-02 direct-file and module CLI paths no longer execute untrusted code during import.
- [ ] No editor-open, package-manager, build, or development-script trigger executes an unreviewed payload.
- [ ] `/peer` rejects invalid/missing credentials and malformed/oversized input.
- [ ] Chat and Godot LAN listeners require an authenticated session.
- [ ] Invitation tokens are not printed to logs.
- [ ] SSH tunnel host authentication is restored.
- [ ] Pending update signature/hash is verified immediately before replacement, with rollback tested.
- [ ] `.env` patterns are ignored; secret scanning is active; leaked credentials, if any, are rotated.
- [ ] Repository-root CI runs on pull requests with correct paths and fails on security regressions.
- [ ] Old AI branches were checked before any merge; the fixed modules are not silently overwritten.
- [ ] The owner publishes exact build evidence and a clear advisory once a clean release is available.

## 5. Reference links and evidence limits

- Current [`main` HEAD reviewed](https://github.com/Chicook/WoldVirtualP2P3D/commit/758d964eca48c607631abc88e5fb2108282d76fa)
- Earlier [security audit PR #64](https://github.com/Chicook/WoldVirtualP2P3D/pull/64) and [security audit document](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_DOC/otrosarticulos/SECURITY_AUDIT_2026-11-05.md)
- Earlier [peer-registration fix PR #62](https://github.com/Chicook/WoldVirtualP2P3D/pull/62)
- [Issue #76: cleanup and history rewrite context](https://github.com/Chicook/WoldVirtualP2P3D/issues/76)
- [Issue #120: current path/CI technical debt](https://github.com/Chicook/WoldVirtualP2P3D/issues/120)
- [Issue #122: proposed security-core architecture and open tasks](https://github.com/Chicook/WoldVirtualP2P3D/issues/122)
- [Published releases](https://github.com/Chicook/WoldVirtualP2P3D/releases)

**Evidence boundaries:** This report establishes **what the reviewed code says**, not whether any specific workstation was compromised; not whether the final remote JavaScript stage performed a particular action; not whether v2.8.4 was built from exactly this working tree; and not a complete independent end-to-end penetration test. Do not attribute the malicious mechanism to a named human without separately verified evidence. Re-check `main` before acting if it has advanced beyond the reviewed commit.

**Respectful request:** Thank you to the owner and community for inviting public feedback. Please prioritize removing the current runnable loader path and restoring the previously designed session protections. A small, transparent emergency fix, followed by measured regression tests and a verifiable clean release, protects both users and the project itself.

---

# PARTE II. ESPAÑOL

## 1. Resumen ejecutivo: qué requiere atención urgente

WoldVirtualP2P3D contiene un trabajo considerable en un mundo virtual de código abierto con Godot, C#, redes y el subsistema de IA LucIA. Este informe reconoce ese esfuerzo. También documenta problemas de seguridad y de ingeniería que conviene resolver antes de confiar en el código actual o en los binarios derivados de él.

**Hallazgo más urgente:** en la rama `main` actual existe un módulo Python que obtiene JavaScript de datos de transacciones de Ethereum y lo ejecuta con Node.js. Un punto de entrada de la consola defensiva, documentado para ejecución directa, importa ese módulo **antes** de realizar las comprobaciones de seguridad. El mecanismo coincide estrechamente con el descrito por la propia auditoría del 5 de noviembre. **La existencia del código y de esa ruta de importación están verificadas; este análisis no demuestra que se haya ejecutado en el equipo de ninguna persona ni que esté incluido en un ejecutable publicado.**

**Segundo hallazgo principal:** las protecciones de autenticación P2P que se habían descrito en un PR anterior parecen no estar presentes en la implementación actualmente rastreada. `POST /peer` acepta URL proporcionadas por el solicitante sin comprobar el token de sesión, validar la URL, limitar la cantidad de pares ni restringir la frecuencia de solicitudes. El servicio puede publicarse mediante un túnel. El relé de chat escucha en todas las interfaces y su handshake WebSocket revisado tampoco autentica la identidad de la sesión.

**Solicitud inmediata:** suspender temporalmente la recomendación de ejecutar clones recientes, scripts de desarrollo o compilaciones nuevas hasta retirar la ruta de ejecución remota y verificar una versión limpia. Mientras tanto, es razonable revisar el código desde GitHub, sin ejecutarlo, o utilizar un entorno forense aislado.

### Gravedad y certeza

| ID | Gravedad | Observación | Estado de verificación |
|---|---|---|---|
| S-01 | **Crítica** | Transacción Ethereum → JavaScript no confiable → ejecución con Node.js | **Confirmado en el código actual** |
| S-02 | **Crítica** | La consola defensiva importa S-01 antes de las comprobaciones de seguridad | **Confirmado para la ejecución directa documentada** |
| S-03 | **Alta** | `POST /peer` sin autenticación ni límites suficientes | **Confirmado en el código actual** |
| S-04 | **Alta** | Relé de chat en todas las interfaces y handshake sin autenticación de sesión | **Confirmado en el listener y handshake revisados** |
| S-05 | **Alta** | Conexiones LAN sin token en la URL y registro de argumentos de ejecución | **Confirmado en el resolvedor; explotación completa no probada** |
| S-06 | **Alta** | El instalador de actualizaciones no vuelve a verificar el ejecutable justo antes de reemplazarlo | **Confirmado en el aplicador; cadena completa no auditada independientemente** |
| S-07 | **Alta** | El túnel SSH desactiva la verificación de la clave del servidor | **Confirmado en el gestor de túneles** |
| S-08 | **Media** | `.gitignore` no excluye expresamente `.env` / `.env.*` | **Configuración comprobada; no se ha demostrado filtración** |
| S-09 | **Alta para garantías** | No hay CI activo en `.github/workflows/` de la raíz; el CI anidado tiene rutas antiguas | **Confirmado en el árbol actual** |
| S-10 | **Media** | Rutas, pruebas, documentación y versiones inconsistentes | **Ejemplos comprobados; revisión parcial** |

**Distinción esencial:** S-03 a S-10 no significan necesariamente código malicioso introducido deliberadamente. Son vulnerabilidades, problemas de fiabilidad o carencias de verificación independientes. Es importante no confundirlos.

## 2. Archivos exactos, explicación del peligro y cómo corregirlo

La raíz del código usada a continuación es:

```text
SRC = VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src
```

Todas las rutas relativas empiezan en `SRC`, salvo indicación contraria. Los enlaces llevan al **commit concreto revisado**, para que las pruebas no cambien si avanza `main`.

### S-01. Ejecución remota de JavaScript obtenido de Ethereum (CRÍTICA)

**Archivo exacto:**

```text
SRC/STM_HRTS/STM_DEF/utils/transport.py
```

**Prueba directa:** [transport.py en el commit revisado](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_HRTS/STM_DEF/utils/transport.py)

**Qué hace en palabras sencillas:**

1. Consulta un servicio de transacciones Ethereum para localizar operaciones vinculadas con una dirección fija.
2. Obtiene el campo `input` de una transacción mediante JSON-RPC.
3. Descifra **en el sentido de decodificar hexadecimal**, no de verificar autenticidad, esos datos como JavaScript.
4. Guarda el JavaScript en un archivo temporal `.js`.
5. Ejecuta ese archivo con `node`.
6. Elimina el archivo temporal y oculta las excepciones.

Los elementos relevantes son `eth_getTransactionByHash`, `bytes.fromhex(...)`, `NamedTemporaryFile(..., suffix=".js")`, `subprocess.run(["node", ...])` y la supresión silenciosa de errores.

**Por qué es peligroso:** quien controle los datos de la transacción seleccionada puede determinar el código que se solicita ejecutar al equipo local. No existe aquí un paquete de actualización firmado y fijado a una versión conocida. Que los datos estén en una cadena de bloques **no** demuestra que sean seguros. La auditoría anterior describió este patrón como un cargador *EtherHiding*; véase el [PR de auditoría #64](https://github.com/Chicook/WoldVirtualP2P3D/pull/64).

**Cómo eliminar el peligro, paso a paso:**

1. **No ejecutar ni importar este módulo para probarlo.** Tampoco consultar sus servicios remotos como comprobación casual.
2. Si se desea investigar su procedencia, conservar una copia como prueba en un archivo forense restringido, fuera del código ejecutable.
3. **Eliminar `SRC/STM_HRTS/STM_DEF/utils/transport.py` del árbol de producción** mediante un PR revisable.
4. Eliminar todas las importaciones o lanzadores que se refieran al módulo, en especial los de S-02.
5. Revisar el historial y las ramas de desarrollo persistentes para evitar que vuelva al fusionarlas.
6. Añadir una **prueba estática** que bloquee cualquier código de producción que reproduzca la secuencia «descargar y ejecutar» desde Ethereum. Una muestra de texto inerte dentro de una prueba defensiva no es lo mismo que un módulo ejecutable.

**Criterio de cierre:** no hay cargadores EtherHiding ejecutables en producción, ninguna importación los activa y ningún arranque, instalación, prueba, compilación o apertura del proyecto ejecuta código remoto de Ethereum. Una segunda persona revisa el resultado antes de publicar.

### S-02. La consola defensiva importa el cargador antes de protegerse (CRÍTICA)

**Archivo exacto:**

```text
SRC/STM_HRTS/STM_DEF/__main__.py
```

**Prueba directa:** [punto de entrada de STM_DEF](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_HRTS/STM_DEF/__main__.py)

Al principio del archivo, **antes** de las comprobaciones, aparecen:

```python
import utils.transport
import utils.session
```

La primera importación es el peligro inmediato. Cuando se ejecuta directamente este archivo, según indica su propia documentación (`python STM_HRTS/STM_DEF/__main__.py informe` desde el directorio de código pertinente), Python puede resolver `utils.transport` como el módulo vecino `STM_DEF/utils/transport.py` y **ejecutar su contenido al importarlo**. La segunda importación parece señalar a `session.py`, que no figura en ese directorio. Aunque después falle esa segunda importación, la primera ya habrá sido intentada.

**Límite de la comprobación:** la forma `python -m STM_HRTS.STM_DEF` depende de la ruta de búsqueda de Python; no se afirma que todas las formas de lanzamiento ejecuten necesariamente el mismo módulo. La **ejecución directa documentada** ya demuestra un riesgo grave.

**Cómo corregirlo:**

1. Eliminar ambas importaciones superiores (`utils.transport` y `utils.session`) si no hay una necesidad legítima comprobada.
2. Utilizar únicamente importaciones relativas de componentes defensivos legítimos y revisados.
3. Asegurar que el escáner **lee el código como texto, sin ejecutarlo**.
4. Corregir la documentación y añadir pruebas de las dos formas de lanzar la consola, **solo después** de retirar S-01 y S-02, en un entorno aislado.

**Criterio de cierre:** iniciar la consola defensiva no realiza ninguna petición de red ni lanza Node.js antes de verificar el proyecto; las dos formas de ejecución funcionan con seguridad o fallan de forma explícita.

### S-03. Registro P2P `/peer` sin autenticar (ALTA)

**Archivos exactos:**

```text
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PNodo.cs
SRC/VSC#/Visor3Ddesarrollo/RedP2P/RedP2PServicio.cs
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs
```

**Pruebas directas:** [P2PNodo.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/P2PNodo.cs), [RedP2PServicio.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/RedP2PServicio.cs) y [P2PTunnelManager.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs).

El método `P2PNodo.ProcesarPeticionAsync` añade al listado `Pares` la `url` recibida en `POST /peer`, **sin comprobar invitación, límites de longitud, formato, cantidad total ni frecuencia**. Aunque el listener sea local, el servicio crea un túnel público hacia él: hay que valorar la exposición a través del túnel y no solo la dirección de escucha.

El [PR #62](https://github.com/Chicook/WoldVirtualP2P3D/pull/62) había descrito y fusionado una corrección. En el código actual faltan sus salvaguardas `RegistrarPar`, `TokenInvitacion`, `MaxPares`, etc. Las pruebas existentes en `SRC/tests/STM_test3/test_stage1_s6_registro_pares.py` describen el comportamiento deseado, pero usan rutas antiguas `VSC#/Nucleo/`.

**Cómo corregirlo:**

1. Recuperar el **comportamiento** de PR #62 y adaptarlo a las carpetas actuales, sin reemplazar archivos a ciegas.
2. Exigir un token de invitación **aleatorio y específico de cada sesión**; sin él, o con token erróneo, devolver `401` sin modificar los pares.
3. Validar URL absolutas HTTP/HTTPS, con longitud y tamaño de petición limitados; rechazar esquemas o datos inadecuados.
4. Limitar la cantidad de pares (por ejemplo, 100), aplicar limitación por IP del socket y sincronizar escrituras concurrentes.
5. Hacer que las solicitudes salientes presenten el token de la **sesión de destino**, sin exponerlo en logs.
6. Mantener el descubrimiento público solo tras revisar qué información revela y cómo se limita el abuso.
7. Reparar rutas de tests y añadir **pruebas de comportamiento reales**, además de inspecciones estáticas.

**Criterio de cierre:** falta de token o token incorrecto → `401`; URL inválida → `400`; abuso → `429`; lista acotada; los pares invitados válidos siguen conectando; pruebas sobre las rutas actuales.

### S-04. Relé de chat sin autenticación en el puerto directo (ALTA)

**Archivo exacto:**

```text
SRC/VSC#/Visor3Ddesarrollo/Chat/ChatRelayServer.cs
```

**Prueba directa:** [ChatRelayServer.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/Chat/ChatRelayServer.cs)

El relé escucha con `IPAddress.Any`, normalmente en los puertos 8920–8929. `Handshake(...)` verifica las cabeceras WebSocket y la ruta `/chat`, pero **no comprueba un token de invitación ni la identidad autenticada**. Después, `hello` acepta nombres y UID declarados por el propio cliente. Aunque el portal web tenga protecciones, estas no bloquean automáticamente una conexión directa a un socket accesible por LAN. La lectura de cabeceras tiene un límite de tamaño, pero **no se observa un plazo máximo por conexión** y el límite de clientes se comprueba después de leer la cabecera, lo que permite agotar recursos con conexiones lentas.

**Cómo corregirlo:**

1. Validar invitación e identidad **en el propio relé**, antes de aceptar una conexión WebSocket o mensajes.
2. Escuchar solo en loopback si únicamente el proxy local necesita acceder. Si hace falta LAN, autenticar también esas conexiones y revisar el firewall.
3. Aplicar tiempos máximos cortos y limitar conexiones pendientes sin autenticar.
4. Asociar el UID a una sesión autenticada, no al valor que envía cualquier cliente.
5. Probar clientes sin permiso, identidades suplantadas, conexiones lentas y reconexión legítima.

**Criterio de cierre:** ninguna conexión directa sin autorización entra al chat; los usuarios autorizados siguen funcionando; no se puede suplantar otro UID.

### S-05. Omisión del token por LAN y exposición de invitaciones en logs (ALTA)

**Archivo exacto:**

```text
SRC/MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd
```

**Prueba directa:** [Red.gd](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd)

`resolver_url_ws()` añade `?invitacion=...` **solo** a URL `wss://`, no a conexiones directas `ws://` por LAN. Además, el resolvedor imprime todos los argumentos de línea de comandos, que pueden incluir una URL con `invitacion=...`. Esos secretos podrían terminar en la consola o en registros persistentes. La hoja de ruta anterior identifica el problema LAN como R-04.

**Cómo corregirlo:**

1. Exigir credencial de sesión tanto por **LAN `ws://`** como por **túnel `wss://`**, verificándola en el servidor anfitrión.
2. Preferir un handshake autenticado de duración limitada frente a credenciales reutilizables en URL.
3. **Quitar `print(...all_args)`**, o sustituirlo por diagnóstico estrictamente filtrado sin tokens ni URL sensibles.
4. Confirmar que las balizas de descubrimiento LAN no puedan redirigir al usuario silenciosamente a un anfitrión falso.
5. Probar conexiones autorizadas y rechazadas entre dos equipos.

**Criterio de cierre:** sin token correcto no se entra por LAN; los logs no muestran invitaciones; los clientes autorizados siguen conectando.

### S-06. Aplicación de actualizaciones sin comprobación final (ALTA)

**Archivos exactos:**

```text
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateApplier.cs
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateChecker.cs
SRC/VSC#/Visor3Ddesarrollo/STM_actualizar/UpdateDownloader.cs
```

**Pruebas directas:** [UpdateApplier.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/STM_actualizar/UpdateApplier.cs) y [UpdateChecker.cs](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC%23/Visor3Ddesarrollo/STM_actualizar/UpdateChecker.cs).

`UpdateApplier.ApplyPendingUpdate` lee `state.json`, elige un `.exe` pendiente y crea un `.bat` para reemplazar y reiniciar el programa. **Esa función no vuelve a comprobar el hash del ejecutable justo antes de sustituirlo.** Otros componentes pueden haber comprobado antes un resumen SHA-256, pero eso no impide la sustitución posterior del archivo local ni autentica por sí solo al autor de una release. Un hash obtenido de la misma fuente que el ejecutable no demuestra de manera independiente quién lo publicó.

**Cómo corregirlo:**

1. Suspender la aplicación automática hasta contar con una prueba completa de la cadena de confianza.
2. Firmar un manifiesto de actualización con una clave controlada por la persona responsable; distribuir la clave **pública de verificación** por un canal autenticado e independiente (por ejemplo, integrada en la aplicación).
3. Justo antes de copiar o ejecutar el nuevo `.exe`, comprobar su hash **y la firma del manifiesto que autoriza ese hash**. Rechazar toda firma o hash ausente o inválido.
4. Hacer una sustitución atómica y probar la recuperación; no borrar la copia anterior hasta confirmar que la nueva versión arranca correctamente.
5. Probar ejecutables alterados, `state.json` manipulado, manifiestos ausentes, copias interrumpidas y rollback.

**Criterio de cierre:** un ejecutable pendiente modificado o no autenticado no puede reemplazar al actual; si falla la actualización, la versión anterior sigue funcionando.

### S-07. Verificación de identidad del servidor SSH desactivada (ALTA)

**Archivo exacto:**

```text
SRC/VSC#/Visor3Ddesarrollo/RedP2P/P2PTunnelManager.cs
```

Los argumentos SSH de `localhost.run` y `serveo.net` incluyen `StrictHostKeyChecking=no` y `UserKnownHostsFile=NUL`, que desactivan la comprobación de la identidad del servidor SSH. El cifrado sin autenticar al servidor no elimina de forma fiable el riesgo de intermediario o de servidor suplantado.

**Cómo corregirlo:** retirar ambas opciones inseguras; mantener una política legítima de `known_hosts`, comprobar o fijar las claves del servidor mediante una fuente autenticada y detener la conexión si una clave cambia inesperadamente. Probar conexión normal, clave incorrecta y reconexión. Aceptar sin verificar una clave desconocida no demuestra la identidad del servidor.

### S-08. Archivos de secretos no excluidos explícitamente por `.gitignore` (MEDIA)

**Archivo exacto:**

```text
.gitignore   (raíz del repositorio)
```

En `.gitignore` existe `!.env.example`, pero no aparecen las reglas que impiden añadir `.env` y `.env.*`. Así, una persona colaboradora podría subir accidentalmente credenciales o claves de API. **No se afirma que haya ocurrido una filtración de secretos.**

**Cómo corregirlo:**

```gitignore
.env
.env.*
!.env.example
```

Añadir además un escáner de secretos a CI, inspeccionar archivos ya versionados e historial, y **rotar toda credencial que realmente se haya expuesto**. Reescribir el historial no revoca claves ni elimina automáticamente copias de terceros.

### S-09. CI no operativo en la raíz y pruebas de seguridad desactualizadas (ALTA para garantías)

**Archivos exactos:**

```text
SRC/STM_HRTS/.github/workflows/ci.yml
SRC/STM_HRTS/STM_DEF/.github/workflows/stm_def.yml
SRC/tests/STM_test3/test_stage1_s6_registro_pares.py
```

No hay carpeta `.github/workflows/` **en la raíz del repositorio** del commit revisado. GitHub no reconoce automáticamente como workflows generales los archivos anidados en `src/STM_HRTS`. El `ci.yml` anidado todavía emplea `VersionDesesion/CONTRRF/TLLDCD/src` en lugar de la estructura vigente `VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src`. Las pruebas S6 esperan `VSC#/Nucleo`, pero la implementación actual está en `VSC#/Visor3Ddesarrollo`.

**Cómo corregirlo:**

1. Colocar un workflow revisado en **`.github/workflows/` de la raíz**.
2. Corregir los directorios de trabajo y rutas de pruebas.
3. Ejecutar primero análisis estático seguro, sin arrancar el código infectado.
4. Una vez retirados S-01/S-02, usar runners desechables para pruebas Python, Godot, .NET Windows/Linux y regresiones de seguridad.
5. Exigir resultados de seguridad correctos para fusionar; no esconder fallos importantes con `continue-on-error: true`.

**Criterio de cierre:** cada PR activa el CI verdadero, se prueban los archivos reales y una regresión que reintroduzca el import peligroso o elimine la autenticación falla antes de fusionar.

### S-10. Rutas y versiones contradictorias (MEDIA; afecta a fiabilidad y publicación)

**Archivos exactos:**

```text
SRC/Rutas.json
SRC/STM_CH/STM_herramientas/rutas_json.py
VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev/.vscode/settings.json
SRC/VSC#/Visor3Ddesarrollo/VisorLinux/VisorLinux.csproj
SRC/VSC#/Visor3Ddesarrollo/HerraMientas/Visor3D.csproj
README.md
README_EN.md
```

Ejemplos comprobados:

- `Rutas.json` está en `.../TLLDCD/src`, pero `raices.repo = "../../../.."` resuelve a **`VersionDesesion/CONTRRF`**, no a la raíz del repositorio. También están a una profundidad incorrecta `raices.contrrf` y `raices.version`.
- `.dev/.vscode/settings.json` fija rutas absolutas propias de un equipo concreto, por ejemplo `E:/WoldVirtualP2P3D/...`.
- El proyecto Windows declara **2.8.4**, mientras que el Linux declara **2.8.0**.
- Los README principales muestran **2.8.1** y enlazan a rutas históricas `actualizacion_bfef2dea` que ya no aparecen en el árbol revisado.

**Cómo corregirlo:** establecer una fuente única de verdad para rutas y versiones; arreglar las rutas relativas; validar el proyecto en Windows y Linux; retirar rutas absolutas locales de los ajustes compartidos; actualizar README y versiones **después** de comprobar los artefactos realmente publicados. Una ruta incorrecta puede dirigir compilaciones o pruebas a otra ubicación y hacer que se anuncie una versión equivocada.

### S-11. Mecanismos maliciosos históricos: lo que hay y lo que ya no aparece

La auditoría anterior describió tres mecanismos: (a) una tarea de VS Code al abrir una carpeta que ejecutaba un `.orc` camuflado, (b) un `opencode/init` ofuscado ejecutado por `npm start` y (c) un cargador Python que obtenía código desde Ethereum. En el **árbol actual de `main` revisado**:

- No se encontró `fa-brand-400.orc`.
- No se encontró `.vscode/tasks.json` con ejecución al abrir.
- No se encontró `SRC/STM_HRTS/opencode/init`, aunque el archivo `SRC/STM_HRTS/opencode/package.json` **todavía ejecutaría `node init`**. En el árbol versionado actual ese paso está roto; su ausencia **no demuestra** que haya hoy un `init` ofuscado activo en `main`.
- **Sí existe** el cargador de Ethereum en `SRC/STM_HRTS/STM_DEF/utils/transport.py`, con la ruta de importación directa indicada en S-02.

**Recomendación:** revisar las ramas históricas y de desarrollo de IA, así como las fuentes de empaquetado, antes de fusionar o publicar; **no afirmar que los archivos `.orc` e `init` de ataques anteriores sigan existiendo en `main`**. Eliminar el comando `node init` obsoleto o sustituirlo por un arranque conocido e inspeccionado. Las muestras de pruebas forenses deben seguir siendo datos de texto inertes, nunca módulos ejecutables.

## 3. Secuencia sencilla y segura de corrección

**Se propone un PR pequeño y revisable, no una reescritura destructiva del historial.** No hace falta ejecutar código sospechoso para encontrarlo o retirarlo.

### Fase A. Detener la exposición y conservar las pruebas

1. Dejar de recomendar temporalmente nuevas descargas, compilaciones o ejecuciones del árbol afectado hasta tener una corrección verificada.
2. Si alguien pudiera haber ejecutado la consola directa afectada u otros activadores antiguos, realizar una **revisión de respuesta a incidentes** del equipo: separarlo de cuentas sensibles cuando corresponda, revisar procesos, conexiones y mecanismos de persistencia, y cambiar posibles credenciales expuestas desde un dispositivo limpio. **No se presupone que un equipo concreto esté comprometido.**
3. Registrar commit, rutas exactas, hashes, logs pertinentes e historial de fusiones. Guardar muestras forenses en un lugar de acceso restringido.
4. No reescribir el historial como primera acción: conservarlo mientras se delimita el incidente. Una limpieza posterior exige coordinación porque existen forks y clones anteriores.

### Fase B. Un PR de emergencia muy concreto

Quien prefiera la web de GitHub puede abrir cada archivo afectado, elegir **Editar** o **Eliminar archivo**, proponer el commit en una **rama nueva** y enviar un pull request para revisión.

Ese PR debe, como mínimo:

- Eliminar `SRC/STM_HRTS/STM_DEF/utils/transport.py` del código ejecutable.
- Quitar `import utils.transport` y el import obsoleto `import utils.session` de `SRC/STM_HRTS/STM_DEF/__main__.py`.
- Mantener la inspección del escáner como análisis de texto, **sin ejecutar módulos examinados**.
- Desactivar o reparar el `node init` roto; revisar los scripts de paquetes externos antes de cualquier instalación.
- Añadir pruebas estáticas que impidan reintroducir esas importaciones y patrones de ejecución en producción.

**No verificar la corrección ejecutando el cargador.** El diff del PR y el análisis estático sin ejecución bastan para confirmar su retirada. Para pruebas de funcionamiento posteriores, utilizar un entorno de CI desechable y solo el árbol ya corregido.

### Fase C. Asegurar los servicios de red

- Restaurar autenticación y límites de `P2PNodo.cs` (tomando como referencia PR #62).
- Autenticar las conexiones directas del relé de chat y las sesiones LAN de Godot.
- Dejar de registrar los argumentos que contengan invitaciones; limitar listeners y túneles innecesarios.
- Añadir pruebas que confirmen el **rechazo** a clientes no autorizados y la conexión de los autorizados.

### Fase D. Recuperar una publicación verificable

- Corregir rutas canónicas, versiones y pruebas.
- Instalar CI en `.github/workflows/` de la **raíz del repositorio**.
- Firmar los manifiestos de release; verificar firma y hash justo antes de aplicar actualizaciones; probar recuperación.
- Compilar desde un commit limpio y revisado, registrando el SHA, dependencias, hashes de binarios y resultados.
- Publicar un aviso de seguridad y una versión limpia con instrucciones de verificación. Auditar las ramas antes de fusionarlas para impedir la reintroducción del problema.

### Comprobaciones sin ejecutar código sospechoso

Realizar únicamente en un **entorno aislado de revisión de código no confiable** o mediante búsquedas en la propia web de GitHub. Estos comandos solo inspeccionan nombres y texto; no ejecutan módulos Python, Node, .NET ni Godot del proyecto:

```bash
# Desde la raíz del repositorio; solo lectura de archivos versionados:
git ls-files '*transport.py' '*fa-brand-400.orc' '*/opencode/init' '*/.vscode/tasks.json'
git grep -n -E 'import utils\.transport|eth_getTransactionByHash|node init|StrictHostKeyChecking=no' -- '*.py' '*.json' '*.cs' '*.md'
git diff --check
```

**Interpretación:** los informes forenses, las reglas de detección y las pruebas con muestras de texto pueden contener legítimamente estos indicadores. No es necesario borrar toda mención documental: lo imprescindible es que **ninguna ruta de producción los ejecute**. No ejecutar `python -m STM_HRTS.STM_DEF` ni el `__main__.py` afectado antes de retirar el import peligroso.

## 4. Lista de verificación para aceptar un PR de seguridad

- [ ] S-01 retirado del **código de producción ejecutable** y pruebas conservadas en archivo restringido.
- [ ] S-02 ya no ejecuta código no confiable durante imports, tanto en modo archivo como en modo módulo.
- [ ] Abrir el editor, instalar paquetes, compilar o ejecutar scripts no dispara código oculto sin revisar.
- [ ] `/peer` rechaza credenciales ausentes/incorrectas y datos mal formados o excesivos.
- [ ] Chat y conexiones Godot LAN exigen autenticación de sesión.
- [ ] Los tokens de invitación no aparecen en logs.
- [ ] Se ha recuperado la verificación de la identidad del servidor SSH.
- [ ] Se valida firma y hash antes del reemplazo de una actualización y funciona el rollback.
- [ ] `.env` queda ignorado; escáner de secretos activo; credenciales realmente filtradas, si existen, rotadas.
- [ ] CI real en la raíz se ejecuta por PR, usa las rutas correctas y bloquea regresiones.
- [ ] Ramas antiguas de IA revisadas antes de fusionarlas; no se sobrescriben silenciosamente los arreglos.
- [ ] La persona responsable publica pruebas exactas de compilación y un aviso claro cuando exista una versión limpia.

## 5. Referencias y límites de las pruebas

- [`main` revisado](https://github.com/Chicook/WoldVirtualP2P3D/commit/758d964eca48c607631abc88e5fb2108282d76fa)
- [PR #64: auditoría de seguridad anterior](https://github.com/Chicook/WoldVirtualP2P3D/pull/64) y [documento de auditoría](https://github.com/Chicook/WoldVirtualP2P3D/blob/758d964eca48c607631abc88e5fb2108282d76fa/VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/STM_DOC/otrosarticulos/SECURITY_AUDIT_2026-11-05.md)
- [PR #62: corrección anterior del registro de pares](https://github.com/Chicook/WoldVirtualP2P3D/pull/62)
- [Issue #76: contexto de limpieza y reescritura histórica](https://github.com/Chicook/WoldVirtualP2P3D/issues/76)
- [Issue #120: deuda de rutas y CI](https://github.com/Chicook/WoldVirtualP2P3D/issues/120)
- [Issue #122: arquitectura de seguridad propuesta y tareas abiertas](https://github.com/Chicook/WoldVirtualP2P3D/issues/122)
- [Releases publicados](https://github.com/Chicook/WoldVirtualP2P3D/releases)

**Límites de la evidencia:** se demuestra **lo que contiene el código revisado**, no que un equipo concreto haya sido comprometido; no se han ejecutado ni investigado las cargas remotas finales; tampoco se ha comprobado que el `.exe` v2.8.4 se compilara exactamente desde este árbol, ni se ha realizado un pentest completo. No atribuir el código malicioso a una persona sin otras pruebas independientes. Volver a revisar `main` antes de actuar si hay commits posteriores.

**Petición respetuosa:** Gracias a la persona responsable y a la comunidad por solicitar aportaciones públicas. Rogamos que se dé prioridad a retirar la ruta del cargador ejecutable y a restaurar las protecciones de sesión ya diseñadas. Un PR de emergencia pequeño y transparente, seguido de pruebas de regresión y una versión limpia verificable, protege a quienes utilizan el proyecto y al propio proyecto.
