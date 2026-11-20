# PROMPT — Intermittent instability of the ephemeral SSH tunnel
## (why does it drop after downloading from GitHub, but not when run from my local folder?)

> **Intended use of this document.**
> It is a self-contained *prompt* to submit for debate (branch `DevOpenCodeIA`, peer review, or an AI agent).
> It contains: context, symptom, evidence in the code with exact paths, hypotheses ordered by likelihood,
> a verification plan, and open questions. **It is not an implementation plan**: the goal of the debate is
> to decide the true root cause and which mitigation to adopt.

---

## 0. Instruction for the recipient

Analyze the problem described, contrast each hypothesis against the cited code evidence, and answer the
**Questions for debate (§6)**. If possible, provide objective proof (command, log, `netstat` capture,
firewall/Defender configuration) that confirms or rules out each hypothesis. Do not propose code yet.

---

## 1. System context

- Product: **Wold Virtual P2P 3D**, a 3D viewer (WPF + Godot 4.7.2) with a P2P network and a DAO, distributed as
  a **single self-contained executable** (`PublishSingleFile`, `SelfContained=true`,
  `IncludeNativeLibrariesForSelfExtract=true`). Current version **v2.9.5**,
  `AssemblyName = DAOLCDMWoldVirtualP2P3Dv2.9.5`.
- The viewer publishes local services to the outside through an **outbound ephemeral tunnel** (no inbound port needed):
  1. **Cloudflare Quick Tunnel** (`cloudflared.exe`) — HTTPS, no warning page.
  2. **Reverse SSH** against free providers: `localhost.run` (`nokey@localhost.run`) and `serveo.net`.
  3. (variants, depending on the code path) `serveo.net:443`.
- The tunnel must **start after login** and close when the session ends, with **orphan-process control
  via a PID persisted to disk**.
- Involved engines: `P2PWebNode`, `P2PTunnelManager`, `EphemeralTunnelRunner`, `TunnelModule` (modular server),
  `LucIAValidacionManager` (LucIA/DAO tunnels).

## 2. Symptom

> "The tunnel is **unstable** when the viewer is **downloaded from GitHub** (it drops, is slow, reconnects,
> sometimes never publishes a URL), whereas running it **from my local development folder** it almost never drops."

It is **intermittent**: it does not always fail, nor with the same pattern. This points to an **environment
difference** (which binaries exist, which environment variables are inherited, which permissions the process runs
under) rather than a pure logic bug.

---

## 3. Evidence in the code

Source base path:
`VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC#/Visor3Ddesarrollo/`

### 3.1 Provider selection: the environment decides, and decides differently

`RedP2P/P2PTunnelManager.cs` (`ObtenerCandidatos`, `EncontrarCloudflared`):

```csharp
string preferencia = Environment.GetEnvironmentVariable("WVP_TUNNEL_PROVIDER") ?? "";
var cloudflare = ("Cloudflare Quick Tunnel", "tunnel --no-autoupdate --url http://127.0.0.1:{0}", ...);
if (preferencia.Equals("cloudflare", ...)) return new[] { cloudflare }.Concat(ssh).ToArray();
if (preferencia.Equals("ssh", ...))        return ssh;
return (EncontrarCloudflared() is not null ? new[] { cloudflare } : Array.Empty<...>())
        .Concat(ssh).ToArray();
```

- If there is **no** `WVP_TUNNEL_PROVIDER` and `cloudflared.exe` is **not** found → **only** the free
  SSH providers are attempted.
- `EncontrarCloudflared()` searches: `CLOUDFLARED_EXE`, `AppContext.BaseDirectory/cloudflared.exe`, and `"cloudflared"` on PATH.

### 3.2 The local launcher DOES configure the environment; the distribution one does NOT

- `HerraMientas/Abrir_VistaPrevia.bat` (local preview) sets:
  ```bat
  set "CLOUDFLARED=%CS%\runtime\cloudflared\cloudflared.exe"
  set "WVP_TUNNEL_PROVIDER=cloudflare"
  set "CLOUDFLARED_EXE=%CLOUDFLARED%"
  ```
- `WoldVirtual3DP2P3D/Lanzar_VistaPrevia.ps1` sets `$env:CLOUDFLARED_EXE` and `$env:WVP_TUNNEL_PROVIDER`.
- **`WoldVirtual3DP2P3D/Lanzar_v2.9.5.bat` (the one that ships with the download) sets NEITHER variable.**
  It only runs `start "" "%~dp0DAOLCDMWoldVirtualP2P3Dv2.9.5.exe" %*`.

### 3.3 `cloudflared.exe` does not travel in the download

`.gitignore` (root) contains:

```
*.exe
*.pck
*.zip
godot_exe.zip
wvp3d.pck
```

A `WoldVirtual3DP2P3D/cloudflared.exe` exists in the working tree, but since `*.exe` is ignored it is **not versioned**
nor packaged into the release. The `.csproj` (`HerraMientas/Visor3D.csproj`) does **not embed it** as an embedded
resource (it embeds `godot_exe.zip`, `wvp3d.pck`, `lucia_runtime.zip`, etc., but **not** `cloudflared.exe`).

### 3.4 Runtime download fallback (can fail on the user's machine)

- `HerraMientas/MainWindow.xaml.cs` → `BuscarODescargarCloudflaredAsync()`: searches 9 paths and, if not found,
  **downloads it** from `.../cloudflare/cloudflared/releases/latest/...` and writes it to
  `Path.Combine(appBase, "cloudflared.exe")`.
- `p2pipfsCS/P2PWebNode.cs` → `FindOrDownloadCloudflaredAsync()`: same pattern, writes to
  `Path.Combine(appBase, "cloudflared.exe")`.
- `appBase = AppDomain.CurrentDomain.BaseDirectory`. If the exe was downloaded to a **read-only folder**
  (Program Files, a synced folder, etc.), **the write fails** → `null` → falls back to SSH.

### 3.5 SSH fallback chain (far less stable)

- `MainWindow.xaml.cs` (~lines 4394-4432): first `localhost.run` (pattern `https://[\w\-]+\.lhr\.life`),
  then `serveo.net`. Arguments per attempt:
  `-o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{port}`
  — **without** `ServerAliveCountMax` and **without** `ExitOnForwardFailure=yes`.
- `P2PTunnelManager.cs` (CandidatosSsh): does include `ServerAliveCountMax=3` and `ExitOnForwardFailure=yes`.
- `P2PWebNode.cs` (SSH candidates, ~lines 217-234): different order (serveo first) and the localhost.run pattern
  written as `@"https://[\w\-]+\.lhr\\.rocks"` → a double backslash in the regex **and** an outdated TLD
  (`lhr.rocks` vs `lhr.life`). Probable result: `localhost.run` **never matches** on that path.

### 3.6 The WebNodo tunnel has no watchdog

- `MainWindow.xaml.cs` → `EstablecerTunelEfimeroAsync` is **idempotent but one-shot**: it only checks
  `_tunnelProcess.HasExited` when it is invoked again. There is **no reconnection loop** for the WebNodo tunnel.
- `EphemeralTunnelRunner.StartAsync` (`p2pipfsCS/EphemeralTunnelRunner.cs`) returns the `Process` and launches two
  *fire-and-forget* tasks to drain stdout/stderr; it **does not monitor process exit**.
- In contrast, `P2PTunnelManager.BucleAsync` **does** reconnect with backoff (max 30 s) → only the
  LucIA/DAO tunnels self-recover.

### 3.7 Limited observability in the release

Most tunnel telemetry uses `System.Diagnostics.Debug.WriteLine` (invisible without an attached debugger) or
`Console.WriteLine`. In the distribution `.exe` (WinExe, no console) those messages **are lost** → the user
only sees "it went down", with no cause.

---

## 4. Hypotheses ordered by likelihood

| # | Hypothesis | Evidence | Likelihood |
|---|------------|----------|------------|
| **H1** | **Provider switch due to environment difference.** Locally, `cloudflared.exe` exists (and the launchers set `CLOUDFLARED_EXE`/`WVP_TUNNEL_PROVIDER`), so the tunnel uses **Cloudflare Quick Tunnel** (production infrastructure, stable). In the download there is no `cloudflared.exe`, the download fallback may fail, and the system falls back to **free SSH** (localhost.run / serveo.net), intrinsically fragile, with session limits and subdomain rotation. | §3.1–§3.5 | **High** |
| **H2** | **Mark-of-the-Web + Defender/SmartScreen.** Files downloaded from GitHub carry the `Zone.Identifier` ADS. Windows treats them as untrusted: network and child-process inspection, and the `cloudflared.exe` the app *itself* downloads inherits that mark → it can be silently blocked/quarantined → SSH fallback. | §3.4 | **Medium-high** |
| **H3** | **Writing `cloudflared.exe` to a non-writable folder.** `appBase` may be Program Files/OneDrive/etc.; `File.Create(localCf)` throws → `null` → SSH. | §3.4 | **Medium** |
| **H4** | **Regex/provider-order regression in `P2PWebNode`.** Pattern `lhr\\.rocks` (double escape + old TLD) → `localhost.run` never matches on that path → reconnections and an appearance of instability. | §3.5 | **Medium** |
| **H5** | **Missing watchdog on the WebNodo tunnel.** If the process dies, it is not relaunched; the state stays "down" until restart. Locally, frequent restarts mask the effect; in the download (long session) it is more noticeable. | §3.6 | **Medium** |
| **H6** | **Weaker SSH options on one of the paths.** Missing `ServerAliveCountMax` and `ExitOnForwardFailure=yes`: if remote port 80 is taken, SSH stays "connected" but **with no forwarding** (a silent dead tunnel). Same if the network degrades without an effective keepalive. | §3.5 | **Medium-low** |
| **H7** | **First-run I/O contention.** The download extracts the Godot engine + PCK (~500 MB) on first use; disk/CPU *thrashing* can cause timeouts within the 23–35 s URL-publishing window. | §3.4 (extraction) | **Low** |

### Ruled-out hypotheses (for the debate record)

- **H8 — "`STM_DEF` kills the tunnel process".** Reviewed `src/STM_HRTS/STM_DEF/`: it uses `psutil`/`netstat` to
  **observe** connections and `subprocess` for `git` commands; it contains **no** logic that terminates
  `ssh.exe`/`cloudflared.exe`. **Ruled out** (absent a watchdog external to the repository).

---

## 5. Verification plan (how to confirm/rule out)

Run **on the machine where the viewer was downloaded** and **in the local folder**, and compare.

1. **Mark of origin (MOTW)**
   ```powershell
   Get-Item ".\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe" -Stream * -ErrorAction SilentlyContinue
   ```
   Presence of `Zone.Identifier` ⇒ H2 active. Try `Unblock-File .\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe` and retry.

2. **Does cloudflared exist and where?**
   ```powershell
   Get-ChildItem "$env:LOCALAPPDATA\WoldVirtualP2P3D\cloudflared.exe",
                 "$env:TEMP\cloudflared.exe",
                 ".\cloudflared.exe" -ErrorAction SilentlyContinue |
     Select-Object FullName, Length, LastWriteTime
   ```

3. **Which provider is actually being used?** Force the provider to isolate H1:
   ```powershell
   $env:WVP_TUNNEL_PROVIDER = "cloudflare"   # and separately "ssh"
   $env:CLOUDFLARED_EXE = "C:\path\to\cloudflared.exe"
   .\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe
   ```
   If forcing `cloudflare` **stabilizes it**, H1 is confirmed.

4. **Processes and connections during the drop**
   ```powershell
   Get-Process ssh,cloudflared -ErrorAction SilentlyContinue |
     Select-Object Id, ProcessName, StartTime
   netstat -ano | Select-String ":22|:443"   # filters the tunnel's ESTABLISHED sockets
   ```
   Compare the process lifetime in each environment.

5. **Persisted PID of the WebNodo tunnel**
   ```powershell
   Get-Content "$env:LOCALAPPDATA\WoldVirtualP2P3D\tunnel-webnodo.pid" -ErrorAction SilentlyContinue
   ```

6. **Release versioning**: check which asset was published and whether its size/hash differs from the local build
   (was `cloudflared.exe` packaged? were the `*.zip`/`*.pck` included?).

7. **Logs**: since messages go to `Debug.WriteLine`, attach a debugger (DebugView) or add file logging on a
   diagnostic branch to capture the exact reason for the fallback.

---

## 6. Questions for debate

1. Is the root cause **functional** (design: relying on free providers) or **packaging-related**
   (`cloudflared.exe` missing from the release)? Or both?
2. Should we **embed `cloudflared.exe`** as an embedded resource (like `godot_exe.zip`/`wvp3d.pck`) so the
   tunnel is deterministic between local and download? What are the risks (size, license, updates)?
3. Is it acceptable for the **free-SSH fallback** to exist? Or should it be treated as an **explicit degraded
   state** with a user warning, instead of a silent degradation?
4. Should the **reconnection watchdog** be single and shared across *all* tunnel paths
   (WebNodo included), instead of existing only in `P2PTunnelManager`?
5. How do we **unify** the SSH arguments (currently they diverge between `MainWindow`, `P2PTunnelManager`, and
   `P2PWebNode`)? Should `ExitOnForwardFailure=yes` + `ServerAliveCountMax` be mandatory?
6. Do we fix the **`localhost.run` regex** (`lhr\\.rocks`) or simply drop that provider as obsolete?
7. How do we **observe** the tunnel in production without a debugger (file log, the existing status endpoint
   `/api/tunnel/status`)? A diagnostic panel in the UI?
8. Does **MOTW/Defender** justify code-signing the executable to reduce first-run friction?

---

## 7. Candidate mitigations (to be decided in the debate, not yet implemented)

**Short term**
- Embed/pin `cloudflared.exe` in the release and/or write the download fallback to
  `%LOCALAPPDATA%\WoldVirtualP2P3D\` (a guaranteed writable path) instead of `appBase`.
- Document/run `Unblock-File` after download, or code-sign the `.exe`.
- Unify the SSH arguments and add `ExitOnForwardFailure=yes` + `ServerAliveCountMax=3` on all paths.

**Medium term**
- A **single tunnel manager** with a shared reconnection watchdog, for all slots (`p2p`, `webnodo`, DAO).
- File logging (`%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel.log`) + expose status in the UI.
- Replace `Debug.WriteLine` with a leveled logger.

**Structural**
- Define a **provider contract** (order, health criteria, timeouts) and an **explicit degraded mode**
  when only free SSH is available.

---

## 8. Missing data (needed to close the case)

- [ ] Confirm on the affected machine whether `cloudflared.exe` exists and at which path.
- [ ] Confirm whether the downloaded `.exe` has a `Zone.Identifier`.
- [ ] Confirm whether `WVP_TUNNEL_PROVIDER`/`CLOUDFLARED_EXE` are defined on that machine.
- [ ] Capture the exact reason for the fallback (requires file logging; it does not exist in the release today).
- [ ] Confirm exactly which asset was uploaded to the GitHub v2.9.5 release (name, size, hash).
- [ ] Reproduce with `WVP_TUNNEL_PROVIDER=cloudflare` forced and compare stability.

---

### Executive summary (one sentence)

**Most likely it is not "the SSH tunnel" that is failing, but *which tunnel gets chosen*: in your local folder
there is a `cloudflared.exe` and the launchers force Cloudflare (stable); when downloaded from GitHub that binary
does not travel along, the download fallback may fail, and the system falls back to the free SSH providers, which
are intermittent by design — compounded by the missing watchdog on the WebNodo tunnel, an outdated regex, and the
lower observability of the distributed `.exe`.**
