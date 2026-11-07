# Hoja de ruta — Wold Virtual P2P 3D (v0.0.20 → v0.1.0)

> Resumen ejecutable del plan. El análisis completo, las evidencias y las medidas están en
> [`README_DESARROLLO.md`](README_DESARROLLO.md).
> **Estado:** propuesta. Ninguna línea de código modificada todavía.
> **Regla del taller:** la zona de trabajo aislada del sistema principal es `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`. **No se sale de esa ruta**: ni builds, ni temporales, ni artefactos, ni cambios en el repo principal.

---

## Objetivo

Convertir la demo actual (`.exe` de 687 MB sin firma, taller sin instantáneas, botón de actualización invisible) en una **v0.1.0 portable, verificable y actualizable** — **un solo `.exe`, sin instalador, sin admin y sin registro** — sin perder nada de lo que ya funciona: mundo Godot, islas P2P, avatares, WebNodo y login por llave, y sin tocar el sistema principal.

## Principios

0. **No se sale de `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`.** Todo vive bajo esa ruta; el sistema principal solo se lee si se pide expresamente.
1. **Primero congelar, luego tocar.** Sin build reproducible no hay forma de saber qué se rompió.
2. **Un solo sitio para la UI flotante: la barra.** El *airspace* del `HwndHost` no se negocia.
3. **Portable de verdad: un `.exe`, cero instalador.** El peso se ataca por dentro (exportar el mundo, quitar caché, deduplicar), no metiendo un MSI. Objetivo: ≤ 450 MB con todo dentro, o ~170 MB + mundo bajo demanda.
4. **Verificar antes de ejecutar.** Hash + firma, siempre.
5. **Cada fase termina en captura + checklist.** Sin captura, no está hecha.

---

## Orden y esfuerzo

| Fase | Entrega | Días | Bloquea a |
|---|---|---:|---|
| **F0** | Congelar el taller + build reproducible | 1–2 | todo |
| **F1** | Botón de actualización en la barra | 1–2 | F4 |
| **F2** | Release < 250 MB, firmada, un tag por versión | 2–3 | F3 |
| **F3** | Updater con hash, reanudación y errores claros | 2–3 | — |
| **F4** | Puente Godot/WPF sin controles invisibles | 3–5 | F6 |
| **F5** | Identidad PBKDF2/BIP-39 + DPAPI | 3–5 | F6 |
| **F6** | LucIA/WebNodo/observabilidad | 5–8 | — |

**Total: ~4–5 semanas** de una persona a tiempo completo, en ese orden.

---

## F0 · Congelar el taller — *hoy*

- [ ] Crear `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\` con `snapshots\`, `out\`, `logs\`, `tmp\`, `localappdata\` y su `.gitignore` local.
- [ ] `snapshot.ps1`: copia fechada de `VSC#\`, `MTBGT\WoldVirtualP2P3D\` y los dos ZIP + `manifest.sha256`.
- [ ] `build.ps1`: publish con `-o "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\out\<fecha>\"` + SHA-256 + `release.json`. **Nada fuera de `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`.**
- [ ] `run.ps1`: lanzar el visor con `LOCALAPPDATA=E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\localappdata` (la extracción de 761 MB no sale del taller).
- [ ] Congelar el binario actual como baseline (`_taller\baseline\`: hash + captura; el `.exe` si hay espacio).
- [ ] **No** hacer `git add` al repo de `E:\WoldVirtualP2P3D` ni copiar a `Sistema_Principal/PRY/…`.
- [x] **Hecho:** reglas de exclusión en el `.gitignore` de la raíz (`_taller/`, credenciales, `update-pending`, `webnodo/descargas`, `.ipfs/`, certificados/secretos).
- [ ] **Hecho cuando:** snapshot + ZIP → `build.ps1` reproduce el tamaño/hash en `_taller\out\` y no se ha escrito nada fuera de `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`.

> Si no se hace F0, no hay vuelta atrás si una edición sale mal: el taller no tiene historial y los ZIP son el único insumo del build.

---

## F1 · Botón de actualización en la barra — *lo pedido*

**Objetivo:** el botón vive dentro de la barra de 42 px, en el hueco de ~165 px entre «WebNodo» y «Llave:» (x ≈ 75 %), y su progreso se ve siempre.

**Estado: implementado y compilado el 2026-10-21** (capturas en `_taller\preview\out\`).

- [x] Sacar `BtnActualizar` de la capa flotante (`Grid.RowSpan="3"`, `ZIndex=999`, `Margin="0,52,20,0"`).
- [x] Colocarlo como primer hijo de la columna derecha, antes de `TxtSesionLlave`, `Margin="0,0,10,0"`, alto 26.
- [x] Convertirlo en `Button` con plantilla (teclado, foco y hover nativos).
- [x] Estados: `Buscando` · `Al día` · `Actualizar vX.Y.Z` · `Descargando %` · `Reiniciando` · `Error/Reintentar`.
- [x] Barra de progreso de **2 px en el borde inferior de la barra** (nunca sobre el viewport 3D).
- [x] Eliminar el `PanelProgreso` flotante y el *glow* sobre el `HwndHost`.
- [x] Tooltip: versión, tamaño y enlace a *release notes*.
- [x] Responsive: a < 1360 px la llave se acorta (`🔑 hash…`) y el enlace pasa a «enlace listo» (URL completa en tooltip y portapapeles).
- [ ] Probar 1280×720 y DPI 125/150 % en una sesión real (pendiente).
- [x] **Hecho:** capturas a 1120×630 y 1916×1000 con el *pill* entre «WebNodo» y «Llave», sin solapes; `Tab` + `Enter` funcionan por ser `Button`; el progreso se ve sin tapar el 3D.

**Medida de referencia (captura 1916 px):** flecha en x = 1436 px (74,9 %), 1 px bajo la barra; hueco 1297–1462 px.

---

## F2 · Release ligera, firmada y portable

**Medido el 2026-10-21** (motor y proyecto extraídos en `_taller\work`, PCK en `_taller\out`):

| Empaquetado | Tamaño | Nota |
|---|---:|---|
| ZIP del proyecto (actual) | 448,9 MB | 580 MB en crudo, con `.godot` |
| **PCK exportado** | **299,5 MB** | 6,9 s de export, sin *export templates*, arranca |
| **PCK con 8 texturas a 2K** | **171,5 MB** | −128 MB (−43 %); arranca |
| **`.exe` final** | **409,5 MB** | host 155,8 + motor 86,2 + PCK 171,5 (medido) |

- [x] Exportar el mundo a `.pck` (sin `.godot` ni `.blend`): válido y arrancable con `--main-pack`.
- [x] Bajar a 2K las 8 texturas grandes (7 difusas de avatar + terreno): PCK 299,5 → 171,5 MB.
- [x] Integrar el PCK en el visor: `AppExtractor` extrae `wvp3d.pck` y `GodotHwndHost` lanza con `--main-pack`. **Build final: 409,5 MB**; extracción 344 MB en 3,3 s; arranque del PCK `exit=0`.
- [x] Firmar el `.exe` (Authenticode, SHA-256) + `SHA256SUMS` + `release.json`; un tag por versión. **Firma de desarrollo** (autofirmada); falta certificado real para distribución.
- [x] Quitar de `WebNodoService.cs` el nombre y la URL cableados: lee `release.json` (con *fallback* a v0.1.0).
- [x] Renombrar el binario a `DMWoldVirtualp2pCNXv0.1.0_p2p.exe` (`Version` 0.1.0).
- [x] **Hecho:** `.exe` 409,5 MB ✔, arranca con el PCK ✔, firma presente (dev) y portal dinámico ✔.
- [x] **Publicada:** https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v.0.1.0 — `.exe` + `release.json` + `SHA256SUMS`; el digest de GitHub coincide con el local.

---

## F3 · Updater robusto

- [x] Verificar el SHA-256 del asset contra el digest de la API **antes** de aplicar.
- [x] Descarga reanudable por `Range` (conserva `.part`) y botón cancelar durante la descarga.
- [x] Aplicar solo en carpeta escribible; comprobación temprana con mensaje claro.
- [x] `state.json` con escritura atómica y borrado al iniciar un intento nuevo.
- [ ] Canal estable/beta y *changelog* en el tooltip.
- [x] **Probado (2026-10-21):** hash correcto → OK; hash manipulado → aborta sin estado; reanudación 1 MB + 2 MB con `206` → fichero íntegro.
- [ ] **Hecho cuando:** red cortada al 50 % → reanuda ✔; hash manipulado → aborta ✔; carpeta de solo lectura → mensaje claro ✔.

---

## F4 · Puente Godot/WPF

- [x] Auditar lo que cae sobre el `HwndHost`: botón y progreso ya están en la barra; el HUD inferior era invisible y se retiró.
- [x] Regla escrita en el código: **la barra es el único sitio para overlays**; el contenedor de Godot no admite hijos WPF.
- [x] DPI (`OnDpiChanged`) y redimensionado recalculan el viewport en píxeles físicos.
- [x] Si Godot muere: estado «Motor 3D detenido» + botón **⟳ Reiniciar 3D** sin cerrar el visor.
- [x] Comentarios ENet 8910 eliminados; documentado WebSocket 8911.
- [ ] **Pendiente:** medir 60 fps y probar DPI 125/150 % en sesión real.

---

## F5 · Identidad y seguridad

- [x] `PBKDF2-SHA256` (210.000 iteraciones) con *salt* por usuario y formato versionado.
- [x] BIP-39 real: lista oficial de 2048 palabras embebida, 12 palabras con checksum.
- [ ] DPAPI para `llave_acceso.json`: **descartado** (fichero portable; la semilla no se guarda).
- [x] Migración transparente al iniciar sesión (SHA-256 → PBKDF2, `hashVersion: 2`).
- [x] **Probado:** 10/10 en `_taller\sectest` (PBKDF2, legado, BIP-39 y checksum).
- [ ] Rotación de llave con escritura atómica (pendiente).

---

## F6 · LucIA, WebNodo y observabilidad

- [x] Portal sin mojibake (12 secuencias corregidas; HTML verificado).
- [x] Token por sesión en `/api/*` (403 sin token; el JS lo envía).
- [x] Log con rotación de 7 días (`VisorLog`) y descargas del portal registradas.
- [x] Botón **ⓘ Copiar diagnóstico** en la barra (versión, rutas, estado y últimas 40 líneas).
- [x] LucIA se mantiene como proyecto separado y documentado.
- [x] Límite por IP: `/api/*` 120/min y `/descargar` 3/min + 1 simultánea; **la página y los estáticos no se limitan**.
- [ ] Empaquetado propio de LucIA y límite global de ancho de banda.

---

## F7 · Continuidad de sesión (implementado; falta prueba real)

> Si el anfitrión se va, los demás no deben caerse ni partirse en mundos separados.

- [x] Roster replicado: `peer_id`, orden, nick, IP LAN y URL pública del WebNodo.
- [x] Elección determinista del nuevo anfitrión (menor orden) con reintentos; nadie más se proclama host.
- [x] Reconexión por `wss://` a la URL del elegido; fallback a IP LAN.
- [x] Re-rooting del enlace (`?host=`) vía `session_host.txt` leído por el visor.
- [x] Islas: reconstrucción desde `TeleportManager` + reclamación de `my_own_index` (sin duplicar).
- [ ] **Pendiente:** prueba con 3 instancias headless + muerte del host (no ejecutada aquí).

---

## Pendiente — LucIA (no se publica)

> Avatar femenino 3D interactivo + IA conversacional en RAM + entrenamiento de su red profunda + pesos en IPFS. **Fuera de GitHub y de la release.**

- [ ] **L1** Avatar glTF femenino con rig y animaciones (`idle`, `walk`, `talk`, `gesture`, `listen`).
- [ ] **L2** IA conversacional ligera cargada en RAM (GGUF/ONNX), API local.
- [ ] **L3** Puente LucIA ↔ visor ↔ Godot (texto, voz y animación sincronizada).
- [ ] **L4** Registro de turnos y job de entrenamiento de `LC_STM`.
- [ ] **L5** Pesos a IPFS: `add --pin`, CID puntero y restauración al arrancar.
- [ ] **L6** Exclusión del repo/release + licencia y consentimiento.

---

## Métricas de éxito de la v0.1.0

| Métrica | Hoy | Objetivo |
|---|---:|---:|
| Formato | 1 `.exe` (portable) | **1 `.exe` (portable), sin instalador** |
| Tamaño del `.exe` | 687 MB | **≤ 450 MB** (medido 409,5) |
| Primera extracción | 761 MB | **≤ 350 MB** (motor 172,5 + PCK 171,5) |
| Actualización | 687 MB, sin reanudar | **< 50 MB** o reanudable |
| Firma | Ninguna | **Authenticode + SHA-256** |
| Botón de actualización | Invisible | **Visible y clicable a 1120×630** |
| Texto del portal | Mojibake | **UTF-8 limpio** |
| Build reproducible | No hay snapshot | **1 comando, dentro de `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`** |
| Tests del visor | 0 | **humo + updater** |

---

## Decisiones pendientes (bloquean F0)

1. **Alcance:** ¿trabajamos solo sobre esta copia (recomendado) o quieres que en algún momento prepare un parche para el sistema principal?
2. **Distribución (portable):** ¿**A)** un solo `.exe` con todo dentro (~400-450 MB, funciona sin internet) o **B)** `.exe` ~170 MB + mundo (~120-150 MB) descargado la primera vez? En ambos casos, sin instalador.
3. **Botón:** ¿dentro de la barra (recomendado) o 1 px más abajo con overlay?
4. **LucIA:** ¿producto aparte o parte del visor?

---

## Primer paso, en concreto

```powershell
# 1. Comprobar que los dos ZIP del build están aquí (insumo del taller)
Get-ChildItem .\VSC#\*.zip | Select-Object Name, Length

# 2. Crear la carpeta de trabajo efímera en E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller
New-Item -ItemType Directory -Force "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\snapshots", "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\out", "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\logs", "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\tmp", "E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\_taller\localappdata" | Out-Null
```

Si confirmas el alcance, el siguiente paso es `snapshot.ps1` + `build.ps1` (F0) y, justo después, **F1** (el botón), que es lo único que toca la interfaz que ya estás viendo. Nada de esto escribe fuera de `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src`.

---

*Documento de trabajo del taller. No modifica el sistema principal.*
