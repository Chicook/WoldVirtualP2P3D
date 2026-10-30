# Desarrollo 2.7.4 — el portal embebido vuelve a responder en Linux

Trabajo sobre el árbol del 2026-10-30
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_91883d55`), rama `DevQoderIA`,
commit `b136b50`.
**Estado: release `v2.7.4` preparada en borrador y verificada; pendiente de publicar.**

---

## Objetivo

Que el visor de Linux vuelva a servir su portal embebido y que `--comprobar` sirva para
validar un despliegue. La 2.7.3 ejecutaba el motor y la ventana, pero el portal respondía
`404` y la comprobación sin ventana terminaba siempre con un fallo.

## Síntoma

En un Ubuntu 24.04 real (run 40988015161), con el visor arrancado bajo Xvfb:

```
http://127.0.0.1:3030/                 404  <h1>Not Found (Not Found)</h1>
http://127.0.0.1:3030/api/p2p-status   404  <h1>Not Found (Not Found)</h1>
http://localhost:3030/api/p2p-status   404  <h1>Not Found (Not Found)</h1>
```

y, en las tres pasadas de `./woldvirtual-linux --comprobar`:

```
OK     portal WebNodo en http://localhost:3030/
FALLO  /api/p2p-status no responde
== 1 fallo(s) ==
```

La ventana, la cuenta, el motor headless y la actualización de Linux funcionaban.

## Causa

`WebNodoService` escucha en un puerto interno (`ActivePort + 100`, p. ej. 3130) y delante
pone un proxy TCP en 3030. El proxy existe para los túneles: reescribe la cabecera `Host`
para que http.sys no rechace el nombre público. La reescritura era a `localhost:{interno}`,
pero la conexión se abre a `IPAddress.Loopback` (127.0.0.1).

En Windows http.sys normaliza el prefijo y ambas formas casan. El `HttpListener` gestionado
de .NET (el que se usa fuera de Windows) no:

- `HttpEndPointManager` crea **un endpoint por IP resuelta** del prefijo. En ese equipo
  `localhost` resolvía primero a `::1`, así que el prefijo `http://localhost:3130/` quedó
  registrado en el endpoint `[::1]:3130` y `http://127.0.0.1:3130/` en `127.0.0.1:3130`.
- `HttpEndPointListener.SearchListener` empareja el `Host` de la petición **de forma
  literal**: `if (p.Host != host || p.Port != port) continue;`.
- Al conectar a 127.0.0.1 con `Host: localhost:3130`, el único prefijo del endpoint no
  casaba, `BindContext` devolvía `false` y `HttpConnection` respondía
  `SendError(HttpStatusDescription.Get(404), 404)`, que es exactamente el
  `<h1>Not Found (Not Found)</h1>` observado.

Quedó demostrado con sondas de `Host` explícito contra el puerto interno (run 40988439530):

| Petición | Código |
|---|---|
| `127.0.0.1:3130` + `Host: 127.0.0.1:3130` (`/` y `/api/p2p-status`) | 200 |
| `127.0.0.1:3130` + `Host: localhost:3130` | 404 |
| `http://localhost:3130/api/p2p-status` (curl resuelve `::1`) | 200 |
| `http://127.0.0.1:3030/api/p2p-status` (el proxy) | 404 |

## Arreglo

`Services/WebNodoService.cs`: el proxy reescribe el `Host` a la misma IP a la que conecta
(`127.0.0.1:{_internalPort}`), con una constante `HostInterno` y el comentario del porqué.
Los dos prefijos (`localhost` y `127.0.0.1`) siguen registrados, así que el navegador puede
entrar por cualquiera de los dos nombres; el proxy es el que tiene que ser coherente con el
endpoint al que conecta.

## Planos de versión

| Fichero | Cambio |
|---|---|
| `VSC#/Visor3D.csproj` | `AssemblyName`, `Version`, `AssemblyVersion`, `FileVersion` y `Description` a 2.7.4 |
| `VSC#/VisorLinux/VisorLinux.csproj` | `Version` a 2.7.4 |
| `VSC#/VisorLinux/Linux/RutasLinux.cs` | `Version` a 2.7.4 |
| `VSC#/Services/WebNodoService.cs` | respaldo del portal a `DMWoldVirtualP2P3Dv2.7.4.exe` |
| `VSC#/STM_LBR/*` | README y guiones: paquete, carpeta y rutas de la 2.7.4 |

El mundo no cambia: se reutiliza `wvp3d.pck` de 114.591.724 B
`ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14`, y el motor sigue
siendo `Godot_v4.7.2-stable_linux.x86_64` (`4.7.2.stable.official.ed1daf0bf`).

## Verificación

### Windows (exe 2.7.4, `ProductVersion 2.7.4+b136b50c…`)

Con el visor instalado cerrado (con él abierto, el motor ocupaba el 8911 y la baliza veía
su nodo: 15/17 y 6/7, fallos ambientales):

- `--startup-selftest`: **17/17**, `RESULTADO ARRANQUE: OK` (marcador 2.7.4, PCK íntegro,
  portal en 3030, `/api/p2p-status` 200 sin token, motor desde el PCK con isla y red).
- `--cuenta-selftest`: **OK** (reset total, respaldo, estado global).
- `--chat-selftest`: **0 fallos** (26 comprobaciones, chat por el proxy `/chat` incluido).
- `--red-selftest`: **7 líneas, 0 fallos** (baliza, presencia sin token y `/api/info` 403).

### Ubuntu 24.04.5 real (run 40990210317, release en borrador)

Se descargó el `.tar.gz` **desde la propia release en borrador** (asset id, `sha256sum -c`)
para probar exactamente los bytes que se publican:

- `test -x` de `woldvirtual-linux`, `woldvirtual-linux.sh` y `diagnostico.sh`, tar con 0755.
- `--extraer`: motor 146.414.384 B (0755) y PCK 114.591.724 B con la huella esperada.
- `MOTOR --version` = `4.7.2.stable.official.ed1daf0bf`.
- Motor headless con el mundo: sin `SCRIPT ERROR`/`Parse Error`/`FATAL`.
- `--comprobar` ×3: **`== comprobación correcta ==`** en las tres (es la regresión del 404).
- Ventana real bajo Xvfb: `Wold Virtual P2P 3D — visor Linux 2.7.4`, captura en el artefacto.
- Sondas del portal:

```
http://127.0.0.1:3030/                 200  <!DOCTYPE html>…
http://127.0.0.1:3030/api/p2p-status   200  {"online":false,"tunnel_url":"","timestamp":…}
http://localhost:3030/api/p2p-status   200  {"online":false,"tunnel_url":"","timestamp":…}
http://localhost:3030/api/info         403  {"error":"forbidden"}
```

## Artefactos

En `E:/areadetrabajo/wvp274/`:

| Fichero | Bytes | SHA-256 |
|---|---|---|
| `DMWoldVirtualP2P3Dv2.7.4.exe` | 365.072.249 | `f2dc55e0cb93d2a44e78c80b0b0f3312e7d5bfac7e74be2e01dd3327b0a322f8` |
| `WoldVirtualP2P3Dv2.7.4-linux.tar.gz` | 207.221.630 | `a135571e123379f6444f0ade08e7fcddc2f04dce3462110330716f71d1756916` |
| `release.json` | 215 | `c72ec3c7b50ee5a5b966d7c7f44e625a27f504f78c3b2ae82a9d478cf86771bf` |
| `SHA256SUMS` | 276 (LF) | — |

Los tres `digest` que devuelve la API del borrador coinciden con los locales.

## Deuda y notas

- La batería de Ubuntu vive en `.github/workflows/prueba-linux-real.yml`, en la rama
  temporal `ci/prueba-linux-273`. Descarga el `.tar.gz` de la release **en borrador**
  (con `GH_TOKEN`), así que sirve para verificar cualquier paquete antes de publicarlo.
  Se puede borrar la rama cuando la 2.7.4 esté publicada; el workflow no va a `main`.
- Queda pendiente el OTA real 2.7.3 → 2.7.4 sobre la copia instalada después de publicar.
- El mismo defecto afectaba al túnel: un `Host` público reescrito a `localhost` habría dado
  404 igualmente con el listener interno, de modo que el arreglo cubre también ese camino.
