# Peso del repositorio y de las copias locales — informe del 2026-10-30

**Estado:** investigación cerrada; **fases 1 (P1–P3) ejecutadas el 2026-10-30** con el resultado de §9.
**Alcance:** `Chicook/WoldVirtualP2P3D` (GitHub), el clon `E:\WoldVirtualP2P3D`, la copia
instalada `E:\WoldVirtual_3DP2P`, el perfil local `%LOCALAPPDATA%\WoldVirtualP2P3D` y el
directorio de trabajo `E:\areadetrabajo`.
**Decisión del dueño que ordena el informe:** las 20 releases y sus assets **se conservan
como historial de evolución**; el informe no propone borrar ninguna release.

---

## 1. Resumen

| Ámbito | Peso | Qué contiene |
|---|---:|---|
| GitHub, código del repo | **163,7 MiB** (`size` de la API = 167.645 KB) | 4.020 objetos alcanzables; el mayor fichero de `HEAD` es `metaverso.jpg` (1,1 MiB) |
| GitHub, assets de las 20 releases | **29,7 GB** (27,7 GiB) | exe de Windows + tar de Linux + `release.json` + `SHA256SUMS` por release |
| `E:\WoldVirtualP2P3D` (clon completo) | **5,0 GiB** | 1,1 GiB `.git` + 3,9 GiB árbol de trabajo |
| · basura de `.git` | **831,6 MiB** | 132 objetos sueltos inalcanzables de un commit huérfano |
| · artefactos de compilación | **2,7 GiB** | `bin/`, `obj/`, `VisorLinux/{bin,obj,publish}` |
| · respaldo del PCK 4K | **1,0 GiB** | `wvp3d.pck.bak.4k`, anterior a la compactación 1K |
| · insumos de build | **0,27 GiB** | `wvp3d.pck` (110 MiB) + `godot_exe.zip` + `godot_linux.zip` |
| `E:\WoldVirtual_3DP2P` (instalada) | **697 MiB** | exe 2.7.4 + `.old` (2.7.3) |
| `%LOCALAPPDATA%\WoldVirtualP2P3D` (perfil) | **617 MiB** | runtime 2.7.3 + 2.7.4 (282 MiB cada uno), `cloudflared.exe` 53 MiB, perfil |
| `E:\areadetrabajo` (fuera del repo) | **63 GB** | artefactos de release (~45 GB) y fuentes de assets (~18 GB) |

Conclusiones:

1. **El repositorio de GitHub no pesa demasiado**: 163,7 MiB de código. Lo que pesa son los
   assets de las releases (29,7 GB), que por decisión del dueño se quedan.
2. **La copia local sí está inflada**: 5,0 GiB, de los que **4,55 GiB son recuperables**
   (basura de Git 0,83 GiB + artefactos de build 2,7 GiB + respaldo 4K 1,0 GiB) sin tocar
   ni una fuente ni un asset publicado.
3. **Nada de lo borrable afecta al visor**: la actualización, el portal y el arranque solo
   dependen de la release más reciente, del runtime extraído y del perfil; ninguno de los
   tres vive en las carpetas propuestas para limpieza.
4. **El directorio de 63 GB es el mayor desperdicio**, pero está fuera del repositorio y
   contiene la única copia del árbol de exportación (`wvp270/godot`, 2,9 GB) y las fuentes
   de avatares, que **no** se pueden borrar.

---

## 2. Qué pesa en GitHub

### 2.1 Código (no es el problema)

`gh api repos/Chicook/WoldVirtualP2P3D` → `size = 167.645 KB` (163,7 MiB).

- 4.020 objetos alcanzables desde ramas y etiquetas.
- El fichero más grande en `HEAD` es
  `src/VSC#/webnodo/public/metaverso.jpg` (1.144.808 B). El resto de `HEAD` no pasa de
  1,0 MiB por fichero.
- `wvp3d.pck`, `godot_*.zip`, `bin/`, `obj/`, `*.pck.bak*` están en `.gitignore`
  (líneas 17, 18, 36, 37, 38 y 39), así que **no viajan en el clon remoto**.

Queda muy por debajo de los umbrales de GitHub (aviso a partir de ~1 GB, bloqueo a 5 GB).
No hay LFS ni ficheros grandes rastreados.

### 2.2 Assets de las releases (lo que pesa, y se conserva)

| Release | Assets | Peso | Comentario |
|---|---:|---:|---|
| v2.7.4 | 4 | 572.294.370 B | *Latest*: exe 365,1 MB + tar 207,2 MB + 2 metadatos |
| v2.7.3 | 4 | 574.192.990 B | |
| v2.7.2 | 4 | 574.193.171 B | |
| v2.7.1 | 4 | 2.413.863.359 B | exe y tar de 1,3 GB / 1,1 GB (PCK 4K) |
| v2.7.0 | 4 | 2.381.721.864 B | ídem |
| v2.6.9 | 4 | 1.341.044.122 B | primer tar de Linux con motor |
| v2.6.0 – v2.6.8 | 3 c/u | 8.433.699.064 B | exe ≈788 MB + metadatos |
| v2.5.4 – v2.5.9 | 3–22 | 14.775.607.261 B | **v2.5.4 sola: 10,8 GB en 22 assets** |
| **Total (20 releases)** | **74** | **29.725.572.079 B** | 27,7 GiB |

Reparto: v2.7.x = 6,5 GB (22 %), v2.6.x = 8,4 GB (28 %), v2.5.x = 14,8 GB (50 %), de los
cuales 10,8 GB son solo de la v2.5.4 (36,5 % del total).

**No se proponen borrados aquí.** Se dejan como historial, tal como pidió el dueño. Nota
técnica: aunque algún día se quisiera aligerar, el actualizador solo usa la release de
mayor versión (ver §3), así que los assets antiguos nunca se descargan; su valor es
histórico y de descarga manual.

---

## 3. De qué depende realmente el visor (evidencia de código)

### 3.1 Actualización en Windows — `src/VSC#/STM_actualizar/`

- `UpdateChecker.FetchReleasesAsync()` (`UpdateChecker.cs:157`):
  `https://api.github.com/repos/Chicook/WoldVirtualP2P3D/releases?per_page=30` — pide **las
  30 releases más recientes** (la API las devuelve de más nueva a más vieja).
- `SeleccionarMejorRelease()` (`:102-149`): descarta borradores, exige un asset con URL,
  calcula la versión efectiva (máximo entre la del tag y la del nombre del fichero), y se
  queda con la mayor versión publicada. **Nunca consulta releases antiguas por nombre ni
  por URL.**
- `ElegirAsset()` (`:204-224`): dentro de la release elegida prefiere el `.exe` con mayor
  versión en el nombre; si no, cualquier `.exe`; si no, un `.zip`.
- `UpdateDownloader.DownloadAsync()`: descarga `browser_download_url`, comprueba tamaño y
  **verifica el `digest` SHA-256 que publica la API** antes de mover el fichero a
  `STM_actualizar\update-pending\` y escribir `state.json`.
- `UpdateApplier`: sustituye el exe y **conserva la versión anterior como `…exe.old`**.

Consecuencia: el OTA solo necesita **la release más reciente y sus assets**. Hoy hay 20
releases y el límite de la consulta es 30; aun superándolo, las 30 más nuevas siguen siendo
las que interesan.

### 3.2 Actualización en Linux — `src/VSC#/VisorLinux/Linux/ActualizadorLinux.cs`

- Misma API (`:246`), mismo criterio de versión.
- `ElegirPaqueteLinux()` (`:225-235`): se queda con el `.tar.gz`/`.tgz` cuyo nombre
  contiene `linux`, el de mayor versión. Depende del tar de la release más reciente.

### 3.3 Portal WebNodo — `src/VSC#/Services/WebNodoService.cs`

- Lee `release.json` **junto al exe** al arrancar (`:167-186`); si falta o está corrupto usa
  el fallback compilado `ExeNameFallback` / `ExeUrlFallback` = `v2.7.4` (`:70-72`).
- Después lo sustituye por la release vigente real consultando GitHub con el mismo criterio
  que el actualizador (`RefrescarReleaseVigente`, `:98-147`, 3 intentos con espera
  creciente).
- `GET /descargar` **redirige** a la `browser_download_url` de la release vigente
  (`:726-767`); no copia binarios ni guarda assets en disco.

### 3.4 Motor y mundo embebidos

- El `.exe` y el ELF llevan dentro `godot_exe.zip` / `godot_linux.zip` + `wvp3d.pck` como
  recursos embebidos; al arrancar se extraen a
  `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\` con marcador `.extracted`.
- `RuntimeCleaner` conserva la versión vigente y la anterior. Hoy conviven `2.7.3` y
  `2.7.4` (282 MiB cada una).

### 3.5 Dependencias externas que no son del repo

- `cloudflared.exe` (53 MiB) se descarga de
  `github.com/cloudflare/cloudflared/releases/latest/...` y se guarda en el perfil.
- Gateways IPFS para el chat/archivos (`ipfs.io`, `w3s.link`, `dweb.link`, etc.).
- Las URLs `raw.githubusercontent.com/.../b136b50…` que aparecen en `obj/` y `bin/` son
  metadatos **SourceLink de los PDB**, no peticiones en tiempo de ejecución.

**Ningún componente lee un tag, un asset ni un commit antiguo.** El historial de releases
es prescindible técnicamente; se conserva por decisión del dueño, no por dependencia.

---

## 4. Qué NO se puede borrar

| Elemento | Dónde | Por qué |
|---|---|---|
| Release v2.7.4 completa (4 assets) | GitHub | Es la que descargan el OTA de Windows, el de Linux y `/descargar` del portal |
| Resto de releases y sus assets | GitHub | Historial pedido por el dueño; además son la vía de vuelta atrás manual |
| Etiquetas `v2.5.4`…`v2.7.4` | GitHub | Anclan el código publicado; los enlaces del `README.md` (badge de la 2.6.4, enlaces a 2.6–2.7.0) apuntan a ellas |
| `wvp3d.pck` (110 MiB) | `src/VSC#/` | Se embebe en el exe y en el ELF; sin él no se puede compilar el binario de distribución |
| `godot_exe.zip`, `godot_linux.zip` (159 MiB) | `src/VSC#/` | Motores embebidos; sin ellos la build `SkipGodotAssets` no produce un visor funcional |
| Fuentes de `src/` (`VSC#`, Godot, scripts `STM_LBR`) | repo | Cualquier borrado rompe la compilación o el paquete de Linux |
| `Seguridad/bip39-english.txt`, `webnodo/public/index.html`, `metaverso.jpg` | repo | Recursos embebidos en el exe |
| Runtime extraído vigente y anterior | `%LOCALAPPDATA%\…\runtime\{2.7.3,2.7.4}` | Si se borra, el siguiente arranque vuelve a extraer ~282 MiB (no falla, pero tarda) |
| `user/`, `Seguridad/pc_sello.json`, `credentials.json`, `llave_acceso.json` | perfil | Identidad, semilla de wallet y sellado del equipo; borrarlos obliga a registrarse de nuevo |
| `cloudflared.exe` | perfil | Túnel del portal; si falta se vuelve a descargar (53 MiB) |
| `release.json` junto al exe | instalación | Fallback del portal si GitHub no responde (la instalación lo trae) |
| `E:\areadetrabajo\wvp270\godot` (2,9 GB) | disco | **Único árbol de exportación con `project.godot`, `export_presets.cfg` y 26 `.glb`/`.gltf`**; el repo no contiene assets 3D |
| Fuentes de avatares (`UserAnimados`, `AVATARESCONANIMACION`, `AvataresParaSelector`, `selector_avatar`, `AVMN`) | disco | Originales de texturas/esqueletos; no están en Git ni en los PCK publicados en 4K |
| `respaldo/*`, `backup/*`, historial de ramas | `.git` | Única copia del trabajo previo a la limpieza (decisión ya registrada) |

---

## 5. Qué SÍ se puede borrar sin que el visor dé errores

Ordenado por ganancia. **Nada de esto se ha ejecutado.**

### P1 · Basura de Git: 831,6 MiB (`.git` de 1,1 GiB → ~0,25 GiB)

`git fsck --unreachable --no-reflogs` encuentra **132 objetos sueltos inalcanzables**
(102 blobs, 29 árboles y **1 commit**) que suman **831,6 MiB**. Los mayores son PNG 4K de
20–30 MB cada uno del snapshot retirado `actualizacion_f7bfd9ba`.

El commit huérfano es `b5527f0` (2026-10-22, «fix: el visor anuncia e instala siempre la
release vigente tras un OTA»). Su cambio ya está vivo en el código actual
(`WebNodoService.RefrescarReleaseVigente`), y su árbol es el snapshot antiguo que se retiró
a propósito al unificar ramas. Está referenciado por el reflog (2 entradas), así que un
`git gc` normal aún no lo tocaría.

- **Riesgo:** bajo; solo se pierde ese commit huérfano y su árbol.
- **Ganancia:** ~0,83 GiB y un `.git` mucho más manejable.
- **Cómo medirlo/ejecutarlo cuando se decida:**
  ```bash
  git count-objects -vH                       # antes: size 843 MiB, pack 215 MiB
  git bundle create /ruta/b5527f0.bundle b5527f0   # opcional: conserva el huérfano
  git reflog expire --expire-unreachable=now --all
  git gc --prune=now --aggressive
  git count-objects -vH                       # después: sin objetos sueltos
  ```
- **Alternativa conservadora:** `git bundle` del huérfano y, si nunca se usa, borrar el
  bundle más adelante.

### P2 · Artefactos de compilación del clon: 2,7 GiB

| Carpeta | Peso | Contenido |
|---|---:|---|
| `src/VSC#/VisorLinux/publish/linux-x64/` | 1,2 GiB | `woldvirtual-linux` self-contained de la 2.7.4 |
| `src/VSC#/VisorLinux/bin/Release/` | 571 MiB | salida intermedia |
| `src/VSC#/VisorLinux/obj/` | 384 MiB | intermedios de MSBuild |
| `src/VSC#/bin/Release/` | 360 MiB | exe 2.7.4 y dependencias |
| `src/VSC#/obj/` | 208 MiB | intermedios de MSBuild |

Todo está en `.gitignore`, el árbol está limpio (`git status` sin cambios) y se regenera con
`dotnet publish`. Los binarios que importan ya están publicados (release v2.7.4 y copia en
`E:\areadetrabajo\wvp274`).

- **Riesgo:** nulo para el visor instalado; solo obliga a recompilar (~3–5 min).
- **Ganancia:** ~2,7 GiB.

### P3 · Respaldo del PCK 4K: 1,0 GiB

`src/VSC#/wvp3d.pck.bak.4k` (1.005 MiB) es el PCK anterior a la compactación 1K de la 2.7.2.

- No lo usa ninguna build (`Visor3D.csproj` embebe `wvp3d.pck`, no el `.bak`).
- Está ignorado por Git (`*.pck.bak*`).
- El PCK 4K **sigue dentro de los assets publicados de la 2.7.0 y la 2.7.1** (exe de
  1,3 GB y tar de 1,1 GB), y además es reconstruible desde `E:\areadetrabajo\wvp270\godot`.
- **Riesgo:** bajo. Solo se pierde la copia cómoda para volver a texturas 4K; no la
  posibilidad, que sigue en la release y en el árbol de exportación.
- **Ganancia:** ~1,0 GiB.

### P4 · Directorio de trabajo: ~45 de los 63 GB

`E:\areadetrabajo` no es el repositorio, pero es lo que más ocupa en disco:

| Carpeta | Peso | Veredicto |
|---|---:|---|
| `wvp271` | 13 GB | **Borrable**: artefactos de la 2.7.1; exe y tar publicados; PCK 4K embebido en ellos |
| `wvp270` | 12 GB | **Borrable salvo `godot/`**: conservar `wvp270/godot` (2,9 GB, árbol de exportación con 26 `.glb`) |
| `wvp269` | 4,7 GB | **Borrable**: PCK 2.6.9 (537 MiB) ×4 copias + bundles de la 2.6.9 |
| `wvp273`, `wvp272`, `wvp274`, `wvp267`, `wvp268`, `prueba_ota_263_264`, `builds`, `versiones` | ~9 GB | **Borrables**: duplicados locales de assets ya publicados |
| `UserAnimados`, `AVATARESCONANIMACION`, `AvataresParaSelector`, `selector_avatar`, `AVMN`, `wvp_shapekeys_real`, `MTBGT` | ~10 GB | **Conservar**: fuentes de assets, únicas |
| `AreaDeTrabajo` | 7,3 GB | **Revisar antes**: mezcla de proyectos; no se ha auditado |
| `nvidia`, `NVIDIA Corporation`, `suno`, `aTube Catcher`, `antygrabity`, `opensimactualizacion` | ~3,7 GB | Ajenos al visor; decisión del dueño |

Copias duplicadas que justifican el borrado (medidas):

- PCK 4K de 1.053.081.932 B: 4 copias (`wvp271/runtime271`, `wvp271/selftest_runtime`,
  `wvp270/wvp3d-2.7.1.pck`, `wvp273/wvp3d-4k.pck`) = **4,2 GB en 4 ficheros idénticos**.
- PCK 2.6.9 de 537.836.524 B: 5 copias (`wvp270/wvp3d-2.6.9.pck`, y los `selftest_runtime`
  de `wvp267`, `wvp268`, `wvp269` + `prueba_ota_263_264`) = **2,7 GB**.
- Exe de la 2.7.1 (1.303.560.057 B): 2 copias; tar 2.7.0: 2 copias; tar 2.7.1: 3 copias.

- **Ganancia:** ~45 GB, dejando intactos el árbol de exportación y las fuentes de avatares.

### P5 · Instalada: `.old` de 349 MiB

`E:\WoldVirtual_3DP2P\DMWoldVirtualP2P3Dv2.7.2.exe.old` es la 2.7.3 (SHA-256
`555fc9fb…b93caa`), respaldo automático que dejó el OTA al instalar la 2.7.4.

- **Borrable**: la 2.7.3 sigue publicada y descargable.
- **Recomendación:** conservarlo hasta validar el uso normal de la 2.7.4; es la vuelta atrás
  inmediata sin red.

### P6 · Cachés y runtimes (pequeño, opcional)

- `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.7.3` (282 MiB): versión anterior; el
  `RuntimeCleaner` la purgará sola en la próxima actualización. Si se borra a mano, no falla
  nada (solo se pierde la vuelta atrás instantánea).
- `%LOCALAPPDATA%\Godot` (46 MiB) y `%APPDATA%\Godot` (39 MiB): cachés del editor,
  regenerables.
- `logs/` y `update_debug.log`: evidencia; conviene conservar los últimos.

---

## 6. Verificación de que lo borrable no rompe el visor

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿El OTA necesita releases antiguas? | No | `UpdateChecker` pide `per_page=30` y elige la mayor versión (`:102-149`) |
| ¿El portal necesita assets antiguos? | No | `/descargar` redirige a la release vigente (`WebNodoService.cs:726-767`) |
| ¿Algo apunta a un tag concreto? | Solo el fallback compilado a `v2.7.4` (`:70-72`) | `grep releases/download` en `src/` |
| ¿El arranque depende de `bin/`, `obj/` o `publish/`? | No | el exe se distribuye autocontenido; el runtime se extrae del propio exe |
| ¿El arranque depende de `wvp3d.pck.bak.4k`? | No | `.csproj` embebe `wvp3d.pck`; el `.bak` está en `.gitignore` |
| ¿Borrar la basura de Git afecta a ramas o etiquetas? | No | son objetos inalcanzables; `respaldo/*` y tags quedan referenciados |
| ¿Se pierde algún asset publicado? | No | el informe no toca releases |

Límite del informe: **no se ha ejecutado ningún borrado**, así que las cifras «después» son
estimaciones a partir de `du`/`git count-objects`; la comprobación real se hará midiendo
antes y después si el dueño lo autoriza.

---

## 7. Hallazgo colateral (corrige lo pendiente del issue #43)

Mientras se medía la instalación se comprobó que **la OTA 2.7.3 → 2.7.4 ya se aplicó sola**,
con el visor en marcha:

| Evidencia | Dato |
|---|---|
| Detección | `update_debug.log` 03:36:03: «Actualización disponible: v2.7.4 (DMWoldVirtualP2P3Dv2.7.4.exe)» |
| Sustitución | `DMWoldVirtualP2P3Dv2.7.2.exe` mtime 03:36:34, SHA-256 `f2dc55e0…b0a322f8` = **digest de la 2.7.4 publicada** |
| Respaldo | `.old` SHA-256 `555fc9fb…b93caa` = **2.7.3 publicada**, `FileVersion 2.7.3.0` |
| Relanzamiento | 03:36:41 «Versión local: 2.7.4»; `STM_actualizar` vacío |
| Runtime | `runtime\2.7.4\wvp3d.pck` = 114.591.724 B `ebeff90c…7ae5e14` = PCK de la 2.7.4 |
| Perfil | `user\*` y `Seguridad\pc_sello.json` con fechas del 2026-10-29, intactos; `estado.json` = equipo `completo` |
| Botón «Actualizar» | A las 13:03 de hoy consulta, ve la v2.7.4 y responde «Sistema al día» (ya está instalada) |

Es decir: **el botón sí detecta la 2.7.4** desde que se publicó (02:29:34Z); lo que ocurría
antes era que la release estaba en borrador y la API anónima no devuelve borradores. Los
dos puntos pendientes del issue #43 («OTA 2.7.3→2.7.4» y «botón no detecta») quedan
verificados con esta evidencia.

---

## 8. Recomendación, por fases

1. **Fase 1 — sin riesgo (4,55 GiB en el clon):** P1 (basura de Git) + P2 (artefactos) +
   P3 (respaldo 4K). Deja el repo en ~0,45 GiB.
2. **Fase 2 — instalación (349 MiB):** P5 (`.old`) cuando la 2.7.4 lleve unos días en uso.
3. **Fase 3 — disco (≈45 GB):** P4, conservando `wvp270/godot` y las fuentes de avatares;
   auditar antes `AreaDeTrabajo`.
4. **No tocar:** releases, etiquetas, `wvp3d.pck`, `godot_*.zip`, fuentes, perfil y runtime
   vigente.

Cada fase se mide antes/después y se documenta aquí mismo.

---

## 9. Ejecutado el 2026-10-30 (fases 1 del §5: P1, P2 y P3)

Antes: **5.278.859.002 B (4,91 GB en el Explorador)**.
Después: **535.917.546 B (511 MiB)**. **Liberados 4.742.941.456 B (−89,8 %).**

| Acción | Antes | Después |
|---|---:|---:|
| P1 · `git reflog expire --expire-unreachable=now --all` + `git gc --prune=now` | `.git` 1,10 GiB (1.445 sueltos, 843 MiB; pack 215 MiB) | `.git` **231 MiB** (0 sueltos; pack 224 MiB) |
| P2 · borrado de `VSC#/bin`, `VSC#/obj`, `VisorLinux/{bin,obj,publish}` | 2,7 GiB | 0 |
| P3 · borrado de `wvp3d.pck.bak.4k` | 1.005 MiB | 0 |
| PCK vigente `wvp3d.pck` | 114.591.724 B `ebeff90c…7ae5e14` | **idéntico** |
| `godot_exe.zip` / `godot_linux.zip` | 86.155.888 / 79.135.021 B | **intactos** |

Comprobaciones posteriores:

- `git fsck --full` sin errores; `git fsck --unreachable` sin objetos.
- `HEAD` sigue en `558d64b` (`DevQoderIA`), 17 ramas locales y 34 etiquetas intactas.
- `git status` limpio salvo este informe y el parche de evidencia.
- El diff del commit huérfano se conserva en
  `STM_DOC/evidencia_commit_huerfano_b5527f0.patch` (28.857 B) antes de purgarlo; su
  corrección ya vive en el código actual.
- **Compilación de humo** tras el borrado, con salidas fuera del repo
  (`-p:BaseIntermediateOutputPath` / `-p:BaseOutputPath` a una carpeta temporal):
  `VisorLinux.csproj` **0 errores en 13 s** y `Visor3D.csproj` (`SkipGodotAssets`)
  **0 errores en 5 s**. Las carpetas temporales se borraron después.
- No hay ninguna referencia a `wvp3d.pck.bak.4k` en guiones, proyectos ni workflows.

Suelo alcanzado: **513 MiB**, que son el historial de Git (231 MiB, con todas las ramas y
etiquetas), los tres insumos de build (`wvp3d.pck` 110 MiB + zips de motor 159 MiB) y las
fuentes y documentos (~13 MiB). Para bajar de ahí habría que reescribir el historial
(prohibido) o renunciar a recompilar el visor sin volver a descargar el motor.

Pendiente de decisión del dueño: P5 (`.old` de la instalación, 349 MiB) y P4
(`E:\areadetrabajo`, ~45 GB borrables de 63 GB).
