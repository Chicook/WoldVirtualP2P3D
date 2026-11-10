## Wold Virtual P2P 3D v2.7.7

Binario de Windows autocontenido (single-file, con el PCK embebido). Motor Godot **4.7.2**.

| dato | valor |
|---|---|
| fichero | `DMWoldVirtualP2P3Dv2.7.7.exe` |
| tamaño | 365.114.325 B (348,19 MiB) |
| SHA-256 | `a8ddf7b6d04d71c3f9ec5521ff6adf22ad3f1df4d05074c66f581fd516150c80` |
| PCK embebido | `ebeff90c752e4680dbd1f3763b1869643f1980316a44523990ec25fb97ae5e14` · 114.591.724 B |

El número, el motor y el anclaje del PCK salen de un único fichero (`VERSION.json`); el `FileVersion` del `.exe` se
contrasta contra esa tabla antes de subir nada.

---

## ⚠️ Aviso de seguridad: se publica con la Etapa 0 sin cerrar

Los tres mecanismos de código dañino plantado que describe
[`docs/SECURITY_AUDIT_2026-11-05_ES.md`](https://github.com/Chicook/WoldVirtualP2P3D/blob/main/docs/SECURITY_AUDIT_2026-11-05_ES.md)
(A1-1, A5-1 y A5-2, un mismo cargador de segunda etapa) **no se han eliminado todavía**: la entrega **R-01 (Etapa 0)**
sigue abierta. Esto afecta al *repositorio y a las máquinas que abran la carpeta*, no a este `.exe`, pero la hoja de
ruta pide tratar cualquier máquina expuesta como potencialmente comprometida hasta comprobarla.

Mecanismos que siguen vivos en `main` en el momento de publicar:

- `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_aeef1149/src/STM_HRTS/utils/transport.py` (A1-1, RCE en tiempo
  de importación al ejecutar `python -m STM_HRTS`).
- `STM_HRTS/opencode/init` con su línea 35 ofuscada y `"start": "node init && ./opencode.bat"` (A5-2).
- `…/public/fonts/fa-brand-400.orc` (A5-1); el `tasks.json` que lo disparaba ya fue borrado en `7d60ceb`.

Tratamiento de las máquinas expuestas y desofuscado de las cargas útiles: decisión pendiente del propietario (R-01b).

## ⚠️ Qué commit anuncia esta release

El tag está anclado a `DevQoderIA` (`294a72a`, 2026-10-30). **El árbol que construyó este binario no está commiteado**
(es la zona de trabajo del ciclo de refactorización, que se versiona como snapshot aparte), así que fuente y binario no
son el mismo árbol. Se publica aun así por decisión del propietario; la promoción del árbol canónico a `main` queda
registrada como deuda en el issue de seguimiento.

---

## Qué trae

**Núcleo C# común (U3).** La duplicación WPF/Avalonia se acaba con `VSC#/Nucleo`: `ConfigRed` pasa a ser la única
fuente de configuración de red y `MainWindow.xaml.cs` y `LanzadorMundo.cs` delegan en `ConfigRed.ProbarDestino`.
Defectos de parseo medidos y cerrados: `ws://ip:puerto` devolvía host `"ws"`; un roster con `https://host` producía
`wss://https://host`; `woldvirtual://` tenía un off-by-one; y `resolver_url_ws` tiraba el puerto explícito.

**Red y puertos (U4).** Las banderas de comando de `Red.gd` se extraen a `analizar_args()` pura y los puertos dejan de
estar cableados: cinco constantes hermanas en un solo sitio, con comprobación const a const entre C# y GDScript.

**Versión única (U5).** `VERSION.json` manda sobre `Version`/`AssemblyVersion`/`FileVersion`/`AssemblyName` de los
cuatro csproj y sobre el `WoldInfoVersion` del visor de Linux. No hay valor por defecto: si la tabla falta o el árbol
vuelve a cablear un número, el build para. `--comprobar` es puerta también en CI, y `--registrar-pck` ancla el PCK real
tras cada reexport.

**Puerta headless de Godot (DT-05).** 22 pruebas de GDScript corriendo con el motor real desde CI, con veredicto,
recuento de evidencia y `xfail` estricto para los defectos conocidos; `user://` aislado y timeout de 120 s.

## Verificación medida de este artefacto

- `dotnet build` 0 errores / 0 advertencias · xUnit **67/67**.
- pytest **215 aprobadas + 4 `xfail` estrictas**, 0 fallos · puerta de Godot **18 aprobadas + 4 `xfail`** con PCK y
  **12 + 1 `xfail` con 9 omitidas** en el escenario del runner (sin PCK).
- Los seis selftests sobre este mismo `.exe`, cada uno con runtime y log temporales, en salida 0: `--startup-selftest`,
  `--red-selftest` (7 líneas / 0 fallos), `--cuenta-selftest`, `--update-selftest` (0 fallos, con reanudación de la
  descarga truncada en 10/53 B), `--chat-selftest` y `--webnodo-selftest` (23 líneas / 0 fallos).

## Límites honestos de esta release

- **No hay asset de Linux** (la 2.7.5 sí lo publicó).
- El PCK embebido sigue siendo el de la 2.7.6: los cambios de U3/U4 en GDScript no llegan al binario hasta reexportar
  (regla **RU5** abierta).
- Cuatro defectos quedan a la vista con `xfail(strict=True)`: `SCRIPT ERROR` en `Personalizacion.gd:952` (sale 0
  igualmente, en `probar_registro` y `probar_flujo_portal`) y los dos verdes sin fixture (`validar_anim_glb`,
  `validar_personalizacion`).
- El workflow de CI existe con cuatro jobs pero **no se ejecuta**: sigue anidado en `src/STM_HRTS/.github/workflows/` y
  GitHub no lo lee hasta promocionarlo a la raíz.

Deuda técnica completa y tareas pendientes: issue de seguimiento de esta release.
