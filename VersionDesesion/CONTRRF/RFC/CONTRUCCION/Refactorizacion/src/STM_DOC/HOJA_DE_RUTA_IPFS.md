# Hoja de ruta — IPFS real para el estado neuronal de Lucía

**Fecha:** 2026-11-13
**Ámbito:** `STMIPFS/`, `SBSTM/`, `STM_BKCH/`, `STM_RFPRMN_stmDL/`
**Estado:** el "IPFS" actual es un nodo Kubo en `127.0.0.1` con el repo dentro del proyecto. Funciona, pero no es duradero ni compartible: si se borra la carpeta, se borra la memoria.
**Objetivo:** que el estado neuronal se publique en IPFS **al cerrar sesión en el metaverso** y se recupere **al iniciar**, con el CID como fuente única de verdad y la copia local degradada a caché.

---

## 0. Principio rector

> Nada se anuncia como guardado hasta que **un segundo nodo independiente** confirma que tiene el contenido.

Todo lo demás (gateway, cifrado, linaje, reintentos) está al servicio de esa frase. Hoy el sistema anuncia "Pesos actualizados en caliente" sin que exista esa confirmación.

Y una corrección de expectativa: **no se puede eliminar la copia local**, solo degradarla. Sin caché local no hay arranque offline, ni latencia aceptable, ni recuperación si la red falla. El cambio real es que lo local deja de ser la verdad y pasa a ser un espejo.

---

## 1. Punto de partida verificado

Ya hay mucho más hecho de lo que parece. Inventario real:

| Pieza | Dónde | Qué hace hoy | Sirve |
|---|---|---|---|
| Cliente API v0 | `STMIPFS/nodo/cliente.py` | `add`, `cat`, `pin`, `id`, `swarm/peers`; endpoint por `WOLD_IPFS_API` | Sí, es la base correcta |
| Daemon gestionado | `STMIPFS/nodo/daemon.py` | arranca/para Kubo con `IPFS_PATH` y PID | Sí |
| Repo y rutas | `STMIPFS/nodo/rutas.py` | repo en `STMIPFS/.ipfs`, datos en `datos/` | Sí, pero aísla el nodo |
| Paquete de pesos | `STMIPFS/nodo/pesos.py` | `.zip` + `indice.json` con SHA-256 por archivo; `publicar`/`recuperar` | Sí, formato aprovechable |
| Puente CLI | `STMIPFS/SBSTMPYIPFS/pesos_ipfs.py` | `ipfs add --pin`, puntero en `STM_CH/lucia_pesos.cid` | Duplica al anterior |
| Subida en 4 niveles | `STM_RFPRMN_stmDL/stm_ipfs.py` | manager → API → CLI → **CID sintético `QmLocal…`** | El nivel 4 hay que eliminarlo |
| Cierre de sesión | `STM_BKCH/BKSVCB.py:638` `cerrar_sesion_y_subir_ipfs()` | empaqueta ledger y PSNRL; no borra (H1) | Sí, es el hook correcto |
| Llamadas al cierre | `STMGNRL/mainLCSTM.py:438`, `SBSTM/snsbstnprb_utils.py:124` | invocan el hook | Sí |
| Arranque | `STM_RFPRMN_stmDL/stm_pesos_ipfs.py:165` `sincronizar_al_iniciar()`, `orquestador_lucia.py:46` | restaura solo si faltan los pesos locales | Parcial: no reanuda ni compara |
| Snapshot de entrenamiento | `SBSTM/subsistema_neural.py:401` `guardar_pesos_runtime()` | escribe en `LCtrabajando` y `PSNRL` | Aún no toca IPFS |

**Conclusión del inventario:** hay tres punteros distintos para "el último estado" (`datos/pesos.json`, `STM_CH/lucia_pesos.cid`, `.modelos/ipfs_pesos.json`) y dos empaquetadores. Antes de añadir IPFS remoto hay que **unificar**.

---

## 2. Por qué lo actual no es IPFS "de verdad"

1. **Es loopback.** `cliente.API = "http://127.0.0.1:5001"`. Si el nodo no anuncia providers al DHT ni tiene pins remotos, el contenido solo existe en ese disco. Borrar `STMIPFS/.ipfs` equivale a borrar el cerebro — exactamente el fallo que ya ocurrió al limpiar `LCtrabajando`.
2. **No hay réplica.** Un `pin add` en un nodo local no garantiza disponibilidad: no hay segundo proveedor, ni `ipfs-cluster`, ni servicio de pinning.
3. **CID sintético.** `stm_ipfs._cid_sintetico()` devuelve `QmLocal…` cuando no hay daemon. Es honesto en el log, pero cualquier consumidor que guarde ese CID cree tener un respaldo que no existe.
4. **Un solo snapshot, sin linaje.** Cada cierre sobrescribe el puntero. No hay historia, no hay `parent`, no se puede volver a un estado anterior ni demostrar progreso.
5. **Sin cifrado y sin control de acceso.** En IPFS el contenido es público para quien tenga el CID. Pesos de Lucía, ledger y memoria conversacional no pueden ir en claro.
6. **No hay "confirmado".** `publicar()` devuelve `ok=True` en cuanto el `add` local responde; nadie comprueba que el bloque sea recuperable desde fuera.

---

## 3. Decisión de arquitectura

Tres caminos. Recomiendo **C** (nodo propio + pinning remoto), porque da soberanía y a la vez garantía externa.

| Opción | Coste | Durabilidad | Complejidad | Cuándo |
|---|---|---|---|---|
| A. Solo nodo local | 0 € | Nula (un disco) | Baja | Solo desarrollo |
| B. Solo pinning remoto (Pinata / Filebase / Octopin) | 0-20 €/mes | Alta | Baja | Prototipo rápido |
| **C. Nodo propio (VPS) + pinning remoto + gateway** | ~5-15 €/mes | **Alta + soberanía** | Media | **Recomendada** |
| **C-bis. Nodo propio en free tier + pinning free** | **0 €** | **Alta** | Media | **Arranque real sin coste** |

**Reparto de responsabilidades en C:**

- **Nodo local (Kubo en el PC):** añade, cachea, sirve el gateway local para latencia baja. Efímero, reconstruible.
- **Nodo propio (VPS con IPFS + `ipfs-cluster` o Kubo con swarm público):** pin permanente, siempre encendido, "segundo nodo" que confirma.
- **Servicio de pinning remoto:** tercera copia, barata, protege del fallo del VPS.
- **Gateway público (uno propio con dominio, o uno dedicado del proveedor):** lectura desde cualquier dispositivo sin depender de que el PC esté encendido. Ojo: `ipfs.io` ya responde `429` a scripts y servidores y redirige navegadores; no lo uses como backend de sincronización.

Regla operativa: **se publica cuando `pin` local + `pin` remoto han confirmado**. Si solo hay local, el estado es `PENDIENTE`, no `GUARDADO`.

### 3.1 ¿Y gratis? Sí, pero separa tres cosas

"Gratis" en IPFS significa tres cosas distintas, y conviene no mezclarlas:

1. **El protocolo es gratis.** Kubo, el swarm y los CIDs no cuestan nada. Lo que cuesta es la máquina encendida que guarda los bloques.
2. **Los free tiers existen y para este proyecto sobran.** Un snapshot de Lucía pesa 50-800 KB; 50 retenidos son < 40 MB. Cualquier free tier es 100-1.000 veces mayor que la necesidad real:

   | Servicio | Free tier | Límite que sí aprieta |
   |---|---|---|
   | Filebase | 5 GB, 10 GB egress, 500 archivos | los 500 objetos |
   | Pinata | 1 GB, 10 GB bandwidth, 500 archivos | los 500 objetos |
   | Octopin | 1 GB, 500 archivos | los 500 objetos |
   | AIOZ Pin | pay-as-you-go, primeros 40.000 archivos | exige monedero AIOZ |

   Con ~500 objetos y un cierre por sesión, hablamos de ~500 sesiones antes de tocar la cuota; con la política de retención de F4 (50 vivos) no se llega nunca. El ancho de banda es irrelevante aquí: unos pocos MB por sesión.

3. **Infraestructura gratis de verdad.** Oracle Cloud "Always Free" da 4 núcleos ARM Ampere y 24 GB de RAM (dentro de las 3.000 OCPU-horas/mes), 200 GB de bloque y ~10 TB de salida. Kubo pide 6 GB de RAM y 2 vCPU como mínimo, así que **entra holgado y es gratis de forma indefinida**. Eso convierte la opción C en C-bis: nodo propio permanente a 0 € + un free tier como tercera copia.

**El precio real de lo gratis es el mantenimiento**: actualizar Kubo, vigilar disco, y que el día que el proveedor cierre la puerta no te lleve por delante. Ya pasó: Storacha (antes web3.storage) retiró su gateway público en mayo de 2026 y el free tier de NFT.Storage se apagó con él; por eso la opción B ya no la lista. De ahí la regla de diseño de F4: **proveedor-agnóstico + exportación CAR**. Si puedes sacar tus CIDs en un `.car`, cambiar de proveedor es una tarde, no una migración.

### 3.2 El `.exe` ya es el nodo: lo que falta es la segunda máquina

`ipfs.exe` (Kubo) **es** el nodo. No es un cliente que necesite un servicio detrás: hace `add`, calcula el CID, anuncia el contenido en el DHT, lo sirve por Bitswap y levanta el gateway. Un servicio de pinning no es más que alguien ejecutando ese mismo binario, con su disco y su uptime, y cobrándote por ello.

Lo que el binario **no** aporta es lo único que da durabilidad: **otra máquina ejecutándolo a la vez**. Con un solo `.exe` hay un solo repo, un solo disco y una sola IP. Si el PC se apaga o se borra `STMIPFS/.ipfs`, el CID deja de ser alcanzable.

Por tanto la versión mínima de C-bis no necesita ningún proveedor:

```bash
# En el VPS (mismo Kubo, binario linux-arm64)
ipfs init
ipfs config Addresses.API /ip4/127.0.0.1/tcp/5001
ipfs daemon &

# Desde el PC, tras publicar el snapshot
ipfs swarm connect /ip4/<IP_VPS>/tcp/4001/p2p/<PEER_ID_VPS>
ipfs pin remote add --service=local --name=lucia <CID>   # o simplemente: en el VPS → ipfs pin add <CID>
```

Con eso, el pin del VPS es la copia que sobrevive al cierre del portátil. `ipfs-cluster` solo hace falta cuando hay más de dos nodos o quieres reconciliación automática.

Tres avisos de operación:

- El `.exe` de Windows no corre en Linux: en el VPS va el binario de Kubo para `linux-arm64`. No copies el repo entero; basta con que el VPS haga `pin add` tras conectar.
- El API (`5001`) **no se expone**: Kubo no autentica. Solo `127.0.0.1` o túnel. El swarm (`4001`) sí puede ser público.
- Un pin no caduca: si no hay política de retención y `repo gc`, el repo crece para siempre. Eso es F4, no un problema del `.exe`.



---

## 4. Modelo de datos

### 4.1 Un snapshot = un CID

```
snapshot/
├── manifest.json      # identidad, linaje, hashes
├── pesos.npz          # tensor real (float32) + paso + deriva
├── estado.json        # contadores, hiperparámetros, versión de esquema
└── (opcional) ledger.json, memoria.json
```

`manifest.json`:

```json
{
  "esquema": "lucia.brain/1",
  "avatar_id": "lucia",
  "sesion_id": "2026-11-13T01:26:55Z-7f3a",
  "creado": "2026-11-13T01:26:55Z",
  "paso": 63,
  "padre_cid": "bafy...anterior",
  "archivos": {
    "pesos.npz": {"sha256": "...", "bytes": 794},
    "estado.json": {"sha256": "...", "bytes": 412}
  },
  "dispositivo": "pc-casa",
  "cifrado": {"algoritmo": "xchacha20poly1305", "kdf": "argon2id"},
  "firma": "ed25519:..."
}
```

### 4.2 Linaje inmutable + cabeza mutable

- **Linaje:** cada `manifest` apunta a `padre_cid`. La historia completa es una cadena de CIDs, verificable y sin reescrituras.
- **Cabeza (head):** un CID es inmutable, así que "el último" necesita un puntero mutable. Opciones, de más a menos recomendable:
  1. **Un bloque del ledger propio** (`BKSVCB` ya es una cadena con hashes y Merkle). El cierre añade un bloque con `cid_estado`. Esto encaja con lo que ya existe y da prueba de autoría.
  2. DNSLink (`_dnslink.lucia.dominio`) si hay dominio.
  3. IPNS (funciona, pero lento y con NAT).
  4. Tabla en una BD remota (simple, pero vuelve a depender de un servicio central).

  Recomendación: **1 como verdad + 4 como caché de arranque rápido**.

### 4.3 Empaquetado determinista

Si el contenido no cambia, el CID debe ser el mismo (deduplicación y detección de "no hubo progreso"). Para eso, al construir el `.zip`/CAR:

- nombres ordenados alfabéticamente,
- `date_time=(1980,1,1,0,0,0)` en cada entrada,
- sin rutas absolutas ni timestamps en el `manifest` que cambien sin cambios reales.

---

## 5. Ciclo de sesión

```
INICIO
  ├─ leer head (ledger → caché local → pinning service)
  ├─ GET manifest por gateway  ──fallo──► usar snapshot local + marcar DEGRADADO
  ├─ verificar sha256 + descifrar + validar esquema
  ├─ cargar pesos (fast-forward desde el último paso conocido)
  └─ abrir sesión
DURANTE
  └─ checkpoint local cada N min / cada M pasos  (nunca a IPFS: latencia)
CIERRE
  ├─ flush de pesos, deriva y contadores
  ├─ construir snapshot + manifest (padre = head actual)
  ├─ cifrar
  ├─ add local → pin local
  ├─ pin remoto (VPS + servicio)  ──fallo──► encolar en OUTBOX y salir sin bloquear
  ├─ verificar recuperabilidad (cat por gateway externo o pin ls remoto)
  ├─ escribir head en ledger
  └─ informar CID real (o "PENDIENTE", nunca un CID inventado)
```

**Nada de esto puede bloquear el cierre del metaverso.** El cierre debe tardar < 2 s percibidos: se encola y un worker publica. Si el usuario cierra el portátil, la outbox se reintenta al siguiente arranque.

---

## 6. Fases

### F0 — Verdad y limpieza (1 día)

- [ ] Eliminar `_cid_sintetico()` y el modo `local-sin-daemon` de `stm_ipfs.py`; devolver `ok=False` explícito.
- [ ] Elegir **un** empaquetador y **un** puntero. Propuesta: `STMIPFS/nodo/pesos.py` + `datos/estado.json`; `pesos_ipfs.py` y `stm_pesos_ipfs.py` pasan a adaptadores finos.
- [ ] Instrumentar: cada operación devuelve `{ok, cid, proveedores, verificado, motivo}`.

**Aceptación:** ningún camino del código puede producir un CID sin bloque real; `grep -r "QmLocal"` no devuelve nada.

### F1 — Nodo alcanzable y duradero (2-3 días)

- [ ] Kubo en VPS con `Swarm.EnableRelayHop` desactivado, `Addresses.Swarm` en TCP/QUIC, `AutoNAT`/`Relay` configurados.
- [ ] Servicio de pinning remoto con token en variable de entorno (nunca en repo): `IPFS_PINNING_ENDPOINT`, `IPFS_PINNING_TOKEN`.
- [ ] `cliente.py`: añadir `pin_remoto(cid)` y `proveedores(cid)` (`/api/v0/routing/findprovs`), soportando `WOLD_IPFS_API` remoto con Basic Auth o túnel.
- [ ] Gateway propio con TLS (Caddy + `gateway` de Kubo), o el gateway dedicado del proveedor de pinning. No `ipfs.io` (da 429 a scripts).

**Aceptación:** un CID publicado desde el PC se descarga desde otra máquina con el nodo del PC apagado, en < 15 s, y `pin ls` lo confirma en ≥ 2 proveedores.

### F2 — Snapshot, manifiesto y linaje (2-3 días)

- [ ] Implementar `manifest.json` y la cadena `padre_cid` (apartado 4).
- [ ] Empaquetado determinista + deduplicación (mismo estado ⇒ mismo CID, no se publica nada).
- [ ] Cifrado obligatorio (apartado 7) y verificación de `sha256` **antes** de descifrar.
- [ ] `head` en el ledger: nuevo campo `cid_estado` en el bloque de cierre.
- [ ] `recuperar()` acepta `cid` explícito, no solo el puntero: permite "vuelve al estado del día X".

**Aceptación:** dos cierres seguidos producen dos CIDs enlazados; `recuperar(cid_antiguo)` restaura exactamente ese estado y las métricas coinciden.

### F3 — Hooks de sesión endurecidos (2 días)

- [ ] `BKSVCB.cerrar_sesion_y_subir_ipfs()` → solo encola (`outbox/*.json`) y devuelve el `job_id`.
- [ ] Worker de publicación con reintentos exponenciales, idempotencia por `sha256` y límite de intentos.
- [ ] `sincronizar_al_iniciar()` reescrito: no solo "si faltan pesos", sino **fast-forward** comparando `paso` local vs `paso` del head.
- [ ] `subsistema_neural.guardar_pesos_runtime()` deja de escribir snapshot en `LCtrabajando` como si fuera definitivo: escribe caché y encola publicación.
- [ ] Latencia de cierre medida y acotada.

**Aceptación:** matar el proceso a mitad de cierre no pierde la sesión; al siguiente arranque se publica lo pendiente y el paso continúa (63 → 148, no 63 → 63).

### F4 — Multidispositivo y política de pins (2 días)

- [ ] `avatar_id` + `dispositivo` en el manifiesto; resolución de conflicto: gana la cadena más larga, la otra se conserva como rama (nunca se borra).
- [ ] Política de retención: pin permanente de los últimos N cierres (p. ej. 50) + hitos diarios/semanales; el resto `unpin` (el contenido sigue direccionable si alguien lo tiene, y se puede re-pinnear).
- [ ] `ipfs dag export` (CAR) semanal a almacenamiento frío como seguro independiente de la red.
- [ ] GC programado con ventana y verificación previa de pins.

**Aceptación:** coste de almacenamiento acotado y previsible; restaurar un estado de hace un mes desde CAR funciona.

### F5 — Operación y pruebas (2-3 días)

- [ ] Observabilidad: `snapshots_publicados`, `snapshots_pendientes`, `latencia_publicacion{proveedor}`, `fallos_verificacion`, `bytes_pinneados`.
- [ ] SLOs: publicar p95 < 10 s (asíncrono), restaurar p95 < 15 s, **0 sesiones perdidas**, ≥ 2 proveedores por snapshot.
- [ ] Batería de caos (apartado 9).
- [ ] Runbook: qué hacer si se pierde la clave, si el VPS cae, si el servicio de pinning caduca.

---

## 7. Seguridad y claves

IPFS es una red pública: **el CID es la capability**. Quien lo tiene, lee.

- **Cifrado en origen**, antes de `add`: XChaCha20-Poly1305 (libsodium) o `age`. Nunca pesos en claro.
- **Clave fuera de IPFS**: derivada de la semilla del usuario (Argon2id) o guardada en el gestor de secretos del dispositivo. Si la clave vive en el mismo snapshot, el cifrado no sirve de nada.
- **Firma Ed25519** del manifiesto para demostrar autoría y evitar que un tercero publique un "estado de Lucía" falso con tu `avatar_id`.
- **Pérdida de clave = pérdida irreversible.** Hay que decirlo en la UI y ofrecer exportación de la clave en papel/QR antes del primer cierre.
- **Metadatos**: el `manifest` no debe contener rutas locales, nombres de usuario ni texto de conversación en claro (va dentro del paquete cifrado).
- **Repositorio IPFS**: no expongas el API (`5001`) a Internet. API solo en `127.0.0.1` o tras túnel autenticado; el swarm sí puede ser público.

---

## 8. Coste y cuotas (orden de magnitud)

| Recurso | Supuesto | Coste |
|---|---|---|
| VPS 2 vCPU / 4 GB | nodo + cluster | 5-12 €/mes |
| Pinning remoto | 5-20 GB | 0-20 €/mes |
| Tráfico gateway | uso personal | 0 € (gateway público) |
| Almacenamiento por snapshot | 50-500 KB cifrado | despreciable |

Un cerebro de 50-500 KB por cierre, 50 retenidos: < 25 MB. El coste real es el nodo siempre encendido, no el almacenamiento.

**Modo 0 € (C-bis):** Oracle Cloud Always Free (4 vCPU ARM / 24 GB / 200 GB) como nodo permanente + Filebase Free o Pinata Free (1-5 GB) como tercera copia + gateway del propio nodo tras Caddy. Cubre el proyecto entero y su crecimiento durante años. Lo que no compras con 0 € es SLA ni soporte: si el VPS gratuito se degrada o el free tier cambia de condiciones, el deber de reaccionar es tuyo. Por eso el CAR semanal de F4 no es opcional en este modo: es tu seguro.

---

## 9. Pruebas de caos (obligatorias antes de decir "hecho")

| Escenario | Resultado esperado |
|---|---|
| Daemon apagado al cerrar | Cierre en < 2 s, job en outbox, aviso "PENDIENTE"; se publica al siguiente arranque |
| Daemon apagado al iniciar | Carga snapshot local, estado `DEGRADADO`, aviso claro |
| Bloque corrupto / SHA distinto | Se rechaza el snapshot, se conserva el local, error legible |
| CID inexistente o no pinneado | Error explícito; nunca "restaurado" falso |
| Gateway caído, pinning OK | Reintento por segundo gateway; si no, `PENDIENTE` |
| Dos dispositivos cierran a la vez | Dos ramas; se elige la más larga y se registra la otra |
| Clave incorrecta | Fallo de descifrado controlado, sin sobrescribir el estado bueno |
| Corte de luz a mitad de escritura | Escrituras atómicas: no queda snapshot a medias |

---

## 10. Migración desde el código actual

1. **Se depreca** `STMIPFS/SBSTMPYIPFS/pesos_ipfs.py` (CLI + JSON suelto) → adaptador sobre `nodo/pesos.py`.
2. **Se depreca** el nivel 4 de `stm_ipfs.py` (CID sintético).
3. **Se unifican** los punteros: `datos/estado.json` como cabeza local, ledger como cabeza de verdad.
4. **`LCtrabajando` deja de ser destino final**: pasa a ser caché de trabajo (se puede borrar sin pérdida, que es justo lo que falló).
5. **`PSNRL` se mantiene** como caché local de lectura rápida, no como archivo.

Nada de esto rompe la API pública: `cerrar_sesion_y_subir_ipfs()` y `sincronizar_al_iniciar()` siguen existiendo con el mismo nombre y firma; cambia lo que hacen por dentro.

---

## 11. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Pérdida de la clave de cifrado | Media | **Crítico** | Exportación obligatoria + copia en papel; aviso en UI |
| Servicio de pinning caduca / sube precio | Media | Alto | Nodo propio como proveedor primario; el servicio es tercera copia |
| VPS cae y nadie más tiene el pin | Baja | Alto | Pinning remoto + CAR semanal |
| Cierre bloqueado esperando red | Alta sin diseño | Medio | Outbox asíncrona + timeout duro |
| Snapshot crece sin control | Media | Medio | Retención + `unpin` + compresión |
| Contenido público por CID filtrado | Media | Alto | Cifrado en origen + no indexar + gateways propios |
| Deriva de esquema entre versiones | Media | Medio | Campo `esquema` y migrador con rechazo explícito |

---

## 12. Definición de "hecho"

Se puede cerrar esta hoja de ruta cuando, en una máquina limpia:

1. Se inicia sesión y Lucía arranca con el estado del último cierre **sin copia local previa**.
2. Se cierra sesión, se apaga el PC, y desde otro dispositivo se recupera ese mismo estado por CID.
3. Se borra `PSNRL`, `LCtrabajando` y `STMIPFS/.ipfs`, y **no se pierde nada**.
4. El ledger contiene el `cid_estado` de cada cierre y la cadena de manifiestos se verifica.
5. `estado()` responde con ≥ 2 proveedores confirmados y el `paso` continúa (no reinicia).

Ese punto 3 es la prueba real: hoy borrar esas carpetas borra la memoria; después, solo borra caché.

---

## Anexo A — Variables de entorno

```text
WOLD_IPFS_API=http://127.0.0.1:5001     # API local (nunca expuesta)
WOLD_IPFS_GATEWAY=http://127.0.0.1:8080 # gateway local
WOLD_IPFS_GATEWAY_PUBLIC=https://gw.lucia.example
WOLD_IPFS_BIN=.../ipfs.exe
IPFS_PATH=.../STMIPFS/.ipfs
IPFS_PINNING_ENDPOINT=https://api.pinata.cloud
IPFS_PINNING_TOKEN=***                  # solo en gestor de secretos
LUCIA_BRAIN_KEY_ID=...                  # referencia a la clave, no la clave
LUCIA_BRAIN_RETENCION=50                # snapshots pinneados
```

## Anexo B — Estados de un cierre

| Estado | Significado | UI |
|---|---|---|
| `PUBLICADO` | ≥ 2 proveedores confirman | "Guardado en IPFS · `bafy…`" |
| `PENDIENTE` | En outbox, sin red | "Se guardará al reconectar" |
| `FALLIDO` | Reintentos agotados | "No se pudo guardar; copia local intacta" |
| `DEGRADADO` (arranque) | Se usó caché local | "Modo local; el estado puede no ser el último" |

Nunca existe un estado "guardado" sin CID verificable. Esa es toda la diferencia entre el sistema actual y el que describe este documento.
