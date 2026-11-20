# PROMPT — Inestabilidad intermitente del túnel SSH efímero
## (¿por qué al descargar desde GitHub se cae y desde la carpeta local no?)

> **Uso previsto de este documento.**
> Es un *prompt* autocontenido para someter a debate (rama `DevOpenCodeIA`, revisión por pares, o un agente de IA).
> Contiene: contexto, síntoma, evidencia en el código con rutas exactas, hipótesis ordenadas por probabilidad,
> plan de verificación y preguntas abiertas. **No es un plan de implementación**: el objetivo del debate es
> decidir cuál es la causa raíz real y qué mitigación se adopta.

---

## 0. Instrucción para el receptor

Analiza el problema descrito, contrasta cada hipótesis con la evidencia de código citada y responde a las
**Preguntas para el debate (§6)**. Si puedes, aporta una prueba objetiva (comando, log, captura de `netstat`,
configuración del firewall/Defender) que confirme o descarte cada hipótesis. No propongas código todavía.

---

## 1. Contexto del sistema

- Producto: **Wold Virtual P2P 3D**, visor 3D (WPF + Godot 4.7.2) con red P2P y una DAO, distribuido como
  **un único ejecutable autocontenido** (`PublishSingleFile`, `SelfContained=true`,
  `IncludeNativeLibrariesForSelfExtract=true`). Versión actual **v2.9.5**,
  `AssemblyName = DAOLCDMWoldVirtualP2P3Dv2.9.5`.
- El visor publica servicios locales al exterior mediante un **túnel efímero saliente** (no requiere abrir puertos):
  1. **Cloudflare Quick Tunnel** (`cloudflared.exe`) — HTTPS, sin página de advertencia.
  2. **SSH reverso** contra proveedores gratuitos: `localhost.run` (`nokey@localhost.run`) y `serveo.net`.
  3. (variantes, según la ruta de código) `serveo.net:443`.
- El túnel debe **iniciarse tras el login** y cerrarse al terminar la sesión, con **control de procesos huérfanos
  por PID persistido en disco**.
- Motores implicados: `P2PWebNode`, `P2PTunnelManager`, `EphemeralTunnelRunner`, `TunnelModule` (servidor modular),
  `LucIAValidacionManager` (túneles de LucIA/DAO).

## 2. Síntoma

> «El túnel es **inestable** cuando el visor se **descarga desde GitHub** (se cae, tarda, reconecta, a veces no
> publica URL), mientras que ejecutándolo **desde mi carpeta local de desarrollo** casi nunca se cae.»

Es **intermitente**: no falla siempre, ni con el mismo patrón. Sugiere una **diferencia de entorno**
(qué binarios existen, qué variables de entorno se heredan, con qué permisos se ejecuta) más que un error de lógica puro.

---

## 3. Evidencia en el código

Ruta base de los fuentes:
`VersionDesesion/CONTRRF/RFC/CONTRUCCION/TLLDCD/src/VSC#/Visor3Ddesarrollo/`

### 3.1 Selección de proveedor: el entorno decide, y decide distinto

`RedP2P/P2PTunnelManager.cs` (`ObtenerCandidatos`, `EncontrarCloudflared`):

```csharp
string preferencia = Environment.GetEnvironmentVariable("WVP_TUNNEL_PROVIDER") ?? "";
var cloudflare = ("Cloudflare Quick Tunnel", "tunnel --no-autoupdate --url http://127.0.0.1:{0}", ...);
if (preferencia.Equals("cloudflare", ...)) return new[] { cloudflare }.Concat(ssh).ToArray();
if (preferencia.Equals("ssh", ...))        return ssh;
return (EncontrarCloudflared() is not null ? new[] { cloudflare } : Array.Empty<...>())
        .Concat(ssh).ToArray();
```

- Si **no** hay `WVP_TUNNEL_PROVIDER` y **no** se encuentra `cloudflared.exe` → **solo** se intentan los
  proveedores SSH gratuitos.
- `EncontrarCloudflared()` busca: `CLOUDFLARED_EXE`, `AppContext.BaseDirectory/cloudflared.exe`, y `"cloudflared"` en el PATH.

### 3.2 El lanzador local SÍ configura el entorno; el de distribución NO

- `HerraMientas/Abrir_VistaPrevia.bat` (vista previa local) fija:
  ```bat
  set "CLOUDFLARED=%CS%\runtime\cloudflared\cloudflared.exe"
  set "WVP_TUNNEL_PROVIDER=cloudflare"
  set "CLOUDFLARED_EXE=%CLOUDFLARED%"
  ```
- `WoldVirtual3DP2P3D/Lanzar_VistaPrevia.ps1` fija `$env:CLOUDFLARED_EXE` y `$env:WVP_TUNNEL_PROVIDER`.
- **`WoldVirtual3DP2P3D/Lanzar_v2.9.5.bat` (el que acompaña a la descarga) NO fija ninguna de las dos variables.**
  Solo hace `start "" "%~dp0DAOLCDMWoldVirtualP2P3Dv2.9.5.exe" %*`.

### 3.3 `cloudflared.exe` no viaja en la descarga

`.gitignore` (raíz) contiene:

```
*.exe
*.pck
*.zip
godot_exe.zip
wvp3d.pck
```

En el árbol de trabajo existe `WoldVirtual3DP2P3D/cloudflared.exe`, pero al estar `*.exe` ignorado **no se versiona**
ni se empaqueta en la release. El `.csproj` (`HerraMientas/Visor3D.csproj`) **no lo incrusta** como recurso embebido
(embebe `godot_exe.zip`, `wvp3d.pck`, `lucia_runtime.zip`, etc., pero **no** `cloudflared.exe`).

### 3.4 Fallback de descarga en runtime (puede fallar en la máquina del usuario)

- `HerraMientas/MainWindow.xaml.cs` → `BuscarODescargarCloudflaredAsync()`: busca en 9 rutas y, si no lo halla,
  **lo descarga** desde `.../cloudflare/cloudflared/releases/latest/...` y lo escribe en
  `Path.Combine(appBase, "cloudflared.exe")`.
- `p2pipfsCS/P2PWebNode.cs` → `FindOrDownloadCloudflaredAsync()`: mismo patrón, escribe en
  `Path.Combine(appBase, "cloudflared.exe")`.
- `appBase = AppDomain.CurrentDomain.BaseDirectory`. Si el exe se descargó a una carpeta **de solo lectura**
  (Program Files, carpeta sincronizada, etc.), **la escritura falla** → `null` → cae a SSH.

### 3.5 Cadena de fallback a SSH (mucho menos estable)

- `MainWindow.xaml.cs` (~línea 4394-4432): primero `localhost.run` (patrón `https://[\w\-]+\.lhr\.life`),
  luego `serveo.net`. Argumentos por intento:
  `-o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{port}`
  — **sin** `ServerAliveCountMax` y **sin** `ExitOnForwardFailure=yes`.
- `P2PTunnelManager.cs` (CandidatosSsh): sí incluye `ServerAliveCountMax=3` y `ExitOnForwardFailure=yes`.
- `P2PWebNode.cs` (candidatos SSH, ~línea 217-234): orden distinto (serveo primero) y patrón de localhost.run
  escrito como `@"https://[\w\-]+\.lhr\\.rocks"` → doble barra invertida en la regex **y** TLD obsoleto
  (`lhr.rocks` vs `lhr.life`). Resultado probable: `localhost.run` **nunca coincide** en esa ruta.

### 3.6 El túnel del WebNodo no tiene vigilancia (watchdog)

- `MainWindow.xaml.cs` → `EstablecerTunelEfimeroAsync` es **idempotente pero de un solo disparo**: solo comprueba
  `_tunnelProcess.HasExited` cuando se vuelve a invocar. **No hay bucle de reconexión** para el túnel del WebNodo.
- `EphemeralTunnelRunner.StartAsync` (`p2pipfsCS/EphemeralTunnelRunner.cs`) devuelve el `Process` y lanza dos tareas
  *fire-and-forget* para drenar stdout/stderr; **no monitoriza la salida del proceso**.
- En cambio `P2PTunnelManager.BucleAsync` **sí** reconecta con backoff (máx. 30 s) → solo los túneles de
  LucIA/DAO se auto-recuperan.

### 3.7 Observabilidad limitada en la release

La mayoría de la telemetría del túnel usa `System.Diagnostics.Debug.WriteLine` (invisible sin depurador adjunto) o
`Console.WriteLine`. En el `.exe` de distribución (WinExe, sin consola), esos mensajes **se pierden** → el usuario
solo ve «se cayó», sin causa.

---

## 4. Hipótesis ordenadas por probabilidad

| # | Hipótesis | Evidencia | Probabilidad |
|---|-----------|-----------|--------------|
| **H1** | **Cambio de proveedor por diferencia de entorno.** En local existe `cloudflared.exe` (y los launchers fijan `CLOUDFLARED_EXE`/`WVP_TUNNEL_PROVIDER`), así que el túnel usa **Cloudflare Quick Tunnel** (infra de producción, estable). En la descarga no hay `cloudflared.exe`, el fallback de descarga puede fallar y el sistema cae a **SSH gratuito** (localhost.run / serveo.net), intrínsecamente frágil, con límites de sesión y rotación de subdominios. | §3.1–§3.5 | **Alta** |
| **H2** | **Mark-of-the-Web + Defender/SmartScreen.** Los ficheros descargados de GitHub llevan ADS `Zone.Identifier`. Windows los trata como no confiables: inspección de red y de procesos hijos, y el `cloudflared.exe` que la app descarga *a su vez* hereda esa marca → puede ser bloqueado/cuarentenado en silencio → fallback a SSH. | §3.4 | **Media-alta** |
| **H3** | **Escritura de `cloudflared.exe` en carpeta no escribible.** `appBase` puede ser Program Files/OneDrive/etc.; `File.Create(localCf)` lanza excepción → `null` → SSH. | §3.4 | **Media** |
| **H4** | **Regresión de regex / orden de proveedores en `P2PWebNode`.** Patrón `lhr\\.rocks` (doble escape + TLD viejo) → `localhost.run` nunca casa en esa ruta → reconexiones y apariencia de inestabilidad. | §3.5 | **Media** |
| **H5** | **Ausencia de watchdog en el túnel del WebNodo.** Si el proceso muere, no se relanza; el estado queda «caído» hasta reinicio. En local, al reiniciar a menudo, el efecto se enmascara; en la descarga (sesión larga) se nota más. | §3.6 | **Media** |
| **H6** | **Opciones SSH más débiles en una de las rutas.** Falta `ServerAliveCountMax` y `ExitOnForwardFailure=yes`: si el puerto remoto 80 está ocupado, SSH sigue «conectado» pero **sin reenvío** (túnel muerto silencioso). Idem si la red se degrada sin keepalive efectivo. | §3.5 | **Media-baja** |
| **H7** | **Contención de E/S al primer arranque.** La descarga extrae motor Godot + PCK (~500 MB) en el primer uso; el *thrashing* de disco/CPU puede provocar timeouts en la ventana de 23–35 s de publicación de URL. | §3.4 (extracción) | **Baja** |

### Hipótesis descartadas (para el registro del debate)

- **H8 — «`STM_DEF` mata el proceso del túnel».** Revisado `src/STM_HRTS/STM_DEF/`: usa `psutil`/`netstat` para
  **observar** conexiones y `subprocess` para comandos de `git`; **no** contiene lógica que termine procesos
  `ssh.exe`/`cloudflared.exe`. **Descartada** (a falta de una vigilancia externa al repositorio).

---

## 5. Plan de verificación (cómo confirmar/descartar)

Ejecutar **en la máquina donde el visor se descargó** y **en la carpeta local**, y comparar.

1. **Marca de origen (MOTW)**
   ```powershell
   Get-Item ".\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe" -Stream * -ErrorAction SilentlyContinue
   ```
   Presencia de `Zone.Identifier` ⇒ H2 activa. Probar `Unblock-File .\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe` y repetir.

2. **¿Existe cloudflared y dónde?**
   ```powershell
   Get-ChildItem "$env:LOCALAPPDATA\WoldVirtualP2P3D\cloudflared.exe",
                 "$env:TEMP\cloudflared.exe",
                 ".\cloudflared.exe" -ErrorAction SilentlyContinue |
     Select-Object FullName, Length, LastWriteTime
   ```

3. **¿Qué proveedor se está usando realmente?** Forzar el proveedor para aislar H1:
   ```powershell
   $env:WVP_TUNNEL_PROVIDER = "cloudflare"   # y por separado "ssh"
   $env:CLOUDFLARED_EXE = "C:\ruta\a\cloudflared.exe"
   .\DAOLCDMWoldVirtualP2P3Dv2.9.5.exe
   ```
   Si forzar `cloudflare` **estabiliza**, H1 confirmada.

4. **Procesos y conexiones durante la caída**
   ```powershell
   Get-Process ssh,cloudflared -ErrorAction SilentlyContinue |
     Select-Object Id, ProcessName, StartTime
   netstat -ano | Select-String ":22|:443"   # filtra ESTABLISHED del túnel
   ```
   Comparar la vida media del proceso en cada entorno.

5. **PID persistido del túnel del WebNodo**
   ```powershell
   Get-Content "$env:LOCALAPPDATA\WoldVirtualP2P3D\tunnel-webnodo.pid" -ErrorAction SilentlyContinue
   ```

6. **Versionado de la release**: verificar qué asset se publicó y si su tamaño/hash difiere del build local
   (¿se empaquetó `cloudflared.exe`? ¿se incluyeron los `*.zip`/`*.pck`?).

7. **Logs**: como los mensajes van a `Debug.WriteLine`, adjuntar un depurador (DebugView) o añadir un log a fichero
   en una rama de diagnóstico para capturar el motivo exacto del fallback.

---

## 6. Preguntas para el debate

1. ¿La causa raíz es **funcional** (diseño: se depende de proveedores gratuitos) o **de empaquetado**
   (falta `cloudflared.exe` en la release)? ¿O ambas?
2. ¿Debemos **incrustar `cloudflared.exe`** como recurso embebido (como `godot_exe.zip`/`wvp3d.pck`) para que el
   túnel sea determinista entre local y descarga? ¿Riesgos (tamaño, licencia, actualización)?
3. ¿Es aceptable que el **fallback a SSH gratuito** exista? ¿O debe considerarse un **estado degradado explícito**
   con aviso al usuario, en lugar de una degradación silenciosa?
4. ¿El **watchdog de reconexión** debe ser único y compartido por *todas* las rutas de túnel
   (WebNodo incluido), en vez de existir solo en `P2PTunnelManager`?
5. ¿Cómo **unificamos** los argumentos SSH (hoy divergen entre `MainWindow`, `P2PTunnelManager` y `P2PWebNode`)?
   ¿`ExitOnForwardFailure=yes` + `ServerAliveCountMax` deberían ser obligatorios?
6. ¿Corregimos la **regex de `localhost.run`** (`lhr\\.rocks`) o directamente eliminamos ese proveedor por obsoleto?
7. ¿Cómo **observamos** el túnel en producción sin depurador (log a fichero, endpoint de estado ya existente
   `/api/tunnel/status`)? ¿Un panel de diagnóstico en la UI?
8. ¿El **MOTW/Defender** justifica firmar el ejecutable (code signing) para reducir la fricción en la primera ejecución?

---

## 7. Mitigaciones candidatas (a decidir en el debate, no a implementar aún)

**Corto plazo**
- Incrustar/fijar `cloudflared.exe` en la release y/o escribir el fallback de descarga en
  `%LOCALAPPDATA%\WoldVirtualP2P3D\` (ruta escribible garantizada) en lugar de `appBase`.
- Documentar/ejecutar `Unblock-File` tras la descarga, o firmar el `.exe`.
- Unificar los argumentos SSH y añadir `ExitOnForwardFailure=yes` + `ServerAliveCountMax=3` en todas las rutas.

**Medio plazo**
- Un **único gestor de túnel** con watchdog de reconexión compartido, para todos los slots (`p2p`, `webnodo`, DAO).
- Log a fichero (`%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel.log`) + exponer estado en la UI.
- Sustituir el `Debug.WriteLine` por un logger con niveles.

**Estructural**
- Definir un **contrato de proveedores** (orden, criterios de salud, timeouts) y un **modo degradado explícito**
  cuando solo haya SSH gratuito disponible.

---

## 8. Datos que faltan (necesarios para cerrar el caso)

- [ ] Confirmar en la máquina afectada si existe `cloudflared.exe` y en qué ruta.
- [ ] Confirmar si el `.exe` descargado tiene `Zone.Identifier`.
- [ ] Confirmar si `WVP_TUNNEL_PROVIDER`/`CLOUDFLARED_EXE` están definidas en esa máquina.
- [ ] Capturar el motivo exacto del fallback (requiere log a fichero; hoy no existe en la release).
- [ ] Confirmar qué asset exacto se subió a la release de GitHub v2.9.5 (nombre, tamaño, hash).
- [ ] Reproducir con `WVP_TUNNEL_PROVIDER=cloudflare` forzado y comparar estabilidad.

---

### Resumen ejecutivo (una frase)

**Lo más probable es que no sea «el túnel SSH» lo que falla, sino *qué túnel se elige*: en tu carpeta local hay
`cloudflared.exe` y los lanzadores fuerzan Cloudflare (estable); al descargar desde GitHub ese binario no viaja,
el fallback de descarga puede fallar y el sistema cae a los proveedores SSH gratuitos, que son intermitentes por
diseño — agravado por la falta de watchdog en el túnel del WebNodo, una regex obsoleta y la menor observabilidad
del `.exe` distribuido.**
