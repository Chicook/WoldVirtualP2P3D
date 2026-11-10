# Desarrollo 2.6.8 — el registro vuelve a estar disponible en equipos con VBS

Trabajo sobre el árbol del 2026-10-28
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c`), rama `DevQoderIA`.
**Estado: publicada como v2.6.8 el 2026-10-28.** Tag `v2.6.8` sobre `cfa6982` de `main`, marcada
*Latest*, con `exe` + `release.json` + `SHA256SUMS` verificados por API. La v2.6.7 sigue publicada
como release anterior.

---

## Objetivo

Publicar con nombre propio la corrección del falso positivo de SMTPLC que la prueba de registro
del 2026-10-28 destapó en la 2.6.7: cualquier PC físico con VBS/Hyper-V/WSL2 activo veía el flag
`HypervisorPresent`, el detector lo puntuaba con 0,50 y el registro quedaba denegado con
`VmDetected`. La 2.6.8 es la 2.6.7 más ese arreglo; no cambia el mundo, ni el motor, ni el chat.

## Qué cambia respecto a la 2.6.7

| Área | Cambio |
|---|---|
| Detección anti-VM | `Seguridad/SMTPLC/VmDetector.cs`: `HypervisorPresent` puntúa **0,25** (antes 0,50) y queda como señal corroborante. `IsVm` exige 0,40 y el umbral de política es 0,50, así que un equipo físico con VBS ya no se bloquea; un invitado real sigue cayendo por modelo/fabricante, BIOS, OUI de MAC, controladores, procesos o registro |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.8`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.8`/`2.6.8.0` (`VSC#/Visor3D.csproj:24,27-29`) |
| Portal | El fallback empotrado anuncia `DMWoldVirtualP2P3Dv2.6.8.exe` y su URL (`Services/WebNodoService.cs:64-66`) |
| Chat, perfiles, reset total, bienvenida, motor y PCK | Sin cambios: mismos ficheros que la 2.6.7 |

## Compilación

```
cd VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c/src/VSC#
"E:/Program Files/dotnet/dotnet.exe" publish -c Release -r win-x64 --self-contained true
```

| Dato | Valor |
|---|---|
| Salida | `bin/Release/net8.0-windows/win-x64/publish/DMWoldVirtualP2P3Dv2.6.8.exe` |
| Tamaño | 788.303.737 B (≈751,8 MiB) |
| SHA-256 | `6ab640d1dd939faec1de83fc922516b7f914c5df04670b9a451e32a8a994b554` |
| `FileVersion` | `2.6.8.0` |
| `ProductVersion` | `2.6.8+f5b205e33d2604850121a9bb74527f79ce519d89` |
| PDB | 158.944 B, junto al exe |

## Autopruebas del binario 2.6.8

Ejecutadas con `WOLD_RUNTIME_DIR=E:/areadetrabajo/wvp268/selftest_runtime` y
`APPDATA=E:/areadetrabajo/wvp268/selftest_appdata` (copia del perfil de prueba, nunca la cuenta real).

| Prueba | Comando | Resultado |
|---|---|---|
| Chat, amigos y franja | `… --chat-selftest` | **0 fallos**, exit 0; `micrófonos=1 webcams=1` |
| Cuenta, reset total y estado global | `… --cuenta-selftest` | **19/19, 0 fallos**, exit 0; `RESULTADO CUENTA: OK` |
| Red y portal | `… --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `… --startup-selftest` | **15/15, 0 fallos**, exit 0; `.extracted` = `2.6.8`; PCK 512,9 MiB íntegro; `isla=True red=True errores=False` |

Registro con SMTPLC: la prueba del 2026-10-28 sobre el código de este mismo árbol dio **11/11**
(aprobación con la política por defecto y denegaciones por cuota, enfriamiento de 72 h, VM y VPN,
sin tocar el libro mayor real). Su detalle y el defecto corregido están en
[`README_desarrollo_20261028_2_6_7.md`](README_desarrollo_20261028_2_6_7.md#prueba-de-registro-con-smtplc-aprobación-y-denegación).

## PCK y motor

No se reexportó el mundo: `wvp3d.pck` sigue siendo el de la 2.6.1–2.6.7 (SHA-256 `9d5c15e7…a69ac94`)
y `godot_exe.zip` no se tocó. La 2.6.8 sólo cambia C# y metadatos.

## Estado de la release

Publicada el 2026-10-28 como *Latest*:

| Dato | Valor |
|---|---|
| Tag | `v2.6.8` sobre `cfa6982` de `main` |
| Release | `https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v2.6.8` |
| `digest` del exe (API) | `sha256:6ab640d1dd939faec1de83fc922516b7f914c5df04670b9a451e32a8a994b554` (coincide con el SHA-256 local) |
| `release.json` | `bb039599a82a5f8d43fc2d7765cb0dee9a517fca4e8e093a2c7bfcedb4bf8641`, 215 B |
| `SHA256SUMS` | `d98c5191a5beca7d67ba64bd186b0db279637c5be7553033516ecf8c0ad30f14`, 174 B |
| Descarga | `200` con `Content-Length` 788.303.737 |

Artefactos en `E:/out_v268/`. `gh release create` ejecutado desde el repo con `-R`: lanzado desde
`E:/out_v268` falla con «not a git repository», y una ruta con `#` (`src/VSC#/…`) se corta en
`VSC`, así que el exe se sube desde una ruta sin `#`.
