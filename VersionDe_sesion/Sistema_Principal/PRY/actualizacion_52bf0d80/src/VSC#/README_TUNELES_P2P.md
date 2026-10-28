# Túneles efímeros P2P — Visor 3D (`DMWoldVirtualp2pCNXv0.0.20_p2p`)

Documento de análisis y estado de la gestión automatizada de **túneles públicos efímeros**
(Cloudflare Tunnel / SSH inverso) del visor 3D P2P del metaverso.

> **Estado:** análisis completado. Implementación funcional; ver *Tareas pendientes* al final.

---

## 1. Arquitectura

El sistema publica la isla local en Internet mediante **un túnel HTTP efímero** cuyo tráfico
termina en el `WebNodo` embebido, que a su vez hace de **proxy WebSocket** hacia el motor Godot.

```
Invitado  ──HTTPS/WSS──►  https://xxx.trycloudflare.com   (túnel público)
                                   │
                                   ▼
                    WebNodoService (HttpListener, 3030-3040)
                       ├─ GET  /                  portal de descarga
                       ├─ GET  /descargar         .exe del visor
                       └─ WS   upgrade  ───────►  ws://localhost:8911   (Godot)
                                                        │
                                                        ▼
                                            WebSocketMultiplayerPeer (isla 3D)
```

### Componentes

| Clase | Ubicación | Responsabilidad |
|---|---|---|
| `P2PTunnelManager` | `RedP2P/P2PTunnelManager.cs` | Túnel SSH inverso (localhost.run / serveo.net) para la API P2P local (7890). Bucle asíncrono con **reconexión y backoff exponencial**. |
| `TunnelProcessRegistry` | `RedP2P/TunnelProcessRegistry.cs` | Persiste el PID del proceso de túnel y **barre procesos huérfanos** de ejecuciones anteriores. |
| `EphemeralTunnelRunner` | `p2pipfsCS/EphemeralTunnelRunner.cs` | Arranca un proceso de túnel, escucha `stdout`/`stderr` y extrae la URL pública con **Regex**. |
| `WebNodoService` | `Services/WebNodoService.cs` | Portal HTTP embebido + **proxy WebSocket** `wss://túnel → ws://localhost:8911`. |
| `RedP2PServicio` | `RedP2P/RedP2PServicio.cs` | Coordina nodo local + túnel; eventos `UrlTunnelLista`, `TunelCaido`, `TunelReintentando`. |
| `MainWindow` | `MainWindow.xaml.cs` | Orquesta tras el login, inyecta la URL en la UI y copia al portapapeles. |

---

## 2. Cobertura de los requisitos

### ✅ 1. Automatización del lanzamiento del túnel (async + Regex)
- Se lanza **tras el login correcto** (`IniciarP2P` → `P2PTunnelManager.IniciarAsync` y
  `EstablecerTunelEfimeroAsync`), sin bloquear la UI.
- Extracción de la URL pública leyendo `StandardOutput`/`StandardError` con `Regex`:
  - cloudflared → `https://[\w\-]+\.trycloudflare\.com`
  - serveo.net → `https://[\w\-]+\.serveo\.net`
  - localhost.run → `https?://[^\s]+\.lhr\.life[^\s]*`
- **Nota sobre el puerto:** el requisito menciona el puerto del servidor de la isla (8910).
  El transporte real del metaverso es **WebSocket TCP 8911** (ver §3). El túnel apunta al
  **puerto HTTP del WebNodo** (3030-3040), que hace de proxy al 8911. Tunelizar 8911
  directamente no es posible con proveedores HTTP y no haría falta.

### ✅ 2. Enlace dinámico en la interfaz
- `MostrarEnlacePublico(url)` inyecta la URL en `TxtUrlP2P` (barra superior) en tiempo de ejecución.
- `OnCopiarUrlP2PClicked` copia al portapapeles con `Clipboard.SetText`, ahora con
  **reintentos** (`CopiarAlPortapapeles`) porque el portapapeles puede estar bloqueado por otra app.
- La IP privada LAN ya **no** se muestra como enlace principal; solo como alternativa en el tooltip.

### ✅ 3. Validación de entrada para invitados
- Campo inferior `TxtUrlAmigo` + botón `BtnConectarAmigo` → `OnConectarAmigoClicked`
  valida y hace `PingParAsync` antes de conectar.
- `TryParseConnectionTarget` normaliza `http(s)://`, `woldvirtual://`, host:puerto y mapea
  los puertos HTTP del WebNodo/API al **8911** del motor.
- También se acepta el enlace por **línea de comandos** (`--peer-url`, `--ip`, `--host`, URL directa)
  vía `App.ParseCommandLineArgs`.

### ✅ 4. Limpieza y cierre seguro de procesos
- **Cierre normal (X):** evento `MainWindow.Closing` → `StopGodot()` + `_p2pServicio.Dispose()`
  + `DetenerTunelWebNodo()`.
- **Cierre de sesión:** `MostrarPantallaBienvenida()` llama a `DetenerTunelWebNodo()`.
- **Muerte no controlada** (Finalizar tarea / crash): el PID se persiste en
  `%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel-<slot>.pid` y se **barre al arrancar**,
  validando nombre de proceso (`ssh` / `cloudflared`) y hora de arranque para no matar
  un proceso ajeno con el PID reciclado.
- `Kill(entireProcessTree: true)` en todos los puntos, para no dejar hijos vivos.

---

## 3. Decisiones clave

- **WebSocket (8911) en lugar de ENet/UDP (8910).** Los túneles HTTP (Cloudflare/SSH) no
  transportan UDP; con ENet las islas y avatares solo eran visibles en la red local.
  El proxy WS del `WebNodoService` es lo que hace la conexión remota posible.
- **Dos túneles con slots separados.** `p2p` (API local, 7890) y `webnodo` (portal, 3030-3040),
  cada uno con su PID persistido independiente.
- **Proxy TCP que reescribe la cabecera `Host`.** Evita el `400 Bad Request - Invalid Hostname`
  de HTTP.sys cuando llega tráfico desde el dominio del túnel.

---

## 4. TAREAS PENDIENTES

- [ ] **README:** revisar/validar este documento y trasladarlo al `README` raíz del repositorio.
- [ ] **Verificación E2E real:** probar el flujo completo invitado↔anfitrión con un túnel
  real (cloudflared y serveo) entre dos máquinas en redes distintas.
- [ ] **Reconexión del túnel de WebNodo:** `EstablecerTunelEfimeroAsync` es *one-shot*: si el
  túnel cae, no se reintenta ni se refresca `App.WebNodo.PublicTunnelUrl`. Migrarlo a
  `P2PTunnelManager` (que ya tiene backoff) para unificar el ciclo de vida.
- [ ] **Refresco de URL en UI:** al caer el túnel, el banner puede quedarse con una URL muerta;
  mostrar estado "reconectando" como ya hace el túnel de la API P2P.
- [ ] **cloudflared embebido:** hoy se descarga en caliente a `%LOCALAPPDATA%`; valorar
  empaquetarlo o fijar su hash de verificación.
- [ ] **Evaluar relay UDP (Noray)** solo si en el futuro se necesita tráfico no-HTTP.
