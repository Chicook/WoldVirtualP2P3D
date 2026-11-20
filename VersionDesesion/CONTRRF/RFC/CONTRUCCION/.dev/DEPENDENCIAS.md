# Dependencias — árbol CONTRUCCION

Estado: 2026-11-16 · Origen: análisis de `TLLDCD/src` (tarea R1.4 del plan de
refactorización en `TLLDCD/src/README.md`). Todo lo aquí afirmado fue verificado
por ejecución salvo que se marque como "según documentación".

## 1. Runtime Python — estado real del sistema

| Elemento | Estado | Verificación |
|---|---|---|
| **`.dev\.python` (canónico)** | **Python 3.15.2 completo y funcional**, con los seis paquetes del proyecto instalados. Incluye el instalador `python-3.15.2-amd64.exe`: es el despliegue vendido del taller; el registro PEP 514 viejo apuntaba a una copia anterior de este mismo runtime, movida de sitio | `python.exe -V`, `pip show`, validador ejecutado — 2026-11-16 |
| `.dev\venv` (respaldo) | Entorno virtual del **mismo** Python 3.15.2, con los seis paquetes en las mismas versiones; los lanzadores lo usan como segunda opción | `pip list`, 2026-11-16 |
| Registro PEP 514 (HKLM) Python `3.15` / `3.15t` | **ROTO**: apunta a `E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\LC_STM\python\` que no existe; `py`/`python` globales fallan | `py -0p`, 2026-11-16 |
| Intérprete vendido `LC_STM/python` | **No existe** en ninguna variante de ruta (`VersionDe_sesion`, `VersionDesesion`, con/sin `RFC`) | `Test-Path`, 2026-11-16 |
| `C:\Python314` | **Incompleto**: solo `Lib`, `DLLs`, `Doc` — sin `python.exe` | `Get-ChildItem`, 2026-11-16 |
| `C:\Users\User\AppData\Local\Programs\Python\Python3127` | **Funcional** (`python.exe` 3.12.7) pero sin registro PEP 514 y sin paquetes del proyecto | `pip show`, 2026-11-16 |

Consecuencia: los comandos `python` y `py` fallan en todo el sistema, y la
documentación del proyecto (`lucia3D/README.md` §2) asume `python -u servidor_lucia.py`.

## 2. Paquetes Python requeridos

Fuente: `lucia3D/README.md` §2 («Python 3.14 con: numpy, soundfile, scipy,
pedalboard, gTTS, comtypes»). Verificado con `pip show` (2026-11-16): los seis
están instalados en el intérprete canónico `.dev\.python` (3.15.2); las versiones
de abajo son las reales, ya fijadas en [`requirements.txt`](requirements.txt).

| Paquete | Uso según documentación | Versión en `.dev\.python` |
|---|---|---|
| `numpy` | Núcleo neuronal (PSN 50 neuronas, checkpoint NPZ) | 2.5.4 |
| `soundfile` | E/S de audio PCM para la voz | 0.14.0 |
| `scipy` | DSP de la voz (remuestreo/envolventes) | 1.18.1 |
| `pedalboard` | Cadena de efectos de voz | 0.9.26 |
| `gTTS` | Síntesis de voz principal (depende de red) | 2.5.4 |
| `comtypes` | Respaldo de voz Windows OneCore | 1.5.0 |

Lista canónica lista para `pip install`: [`requirements.txt`](requirements.txt).

## 3. Resolución de R1.4 (2026-11-16)

**Resuelto por despliegue vendido.** El intérprete canónico del taller es:

```
E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\python.exe
```

Python 3.15.2 con los seis paquetes del proyecto (§2). El validador de rutas
(`TLLDCD/src/tests/validar_rutas_json.py`) ejecuta con él sin errores de
lanzamiento. Los scripts del taller deben invocarlo por ruta absoluta o relativa
al árbol; no dar por supuesto que `python`/`py` globales funcionan.

Higiene opcional pendiente (requiere admin): las claves
`HKLM:\SOFTWARE\Python\PythonCore\3.15` y `3.15t` siguen apuntando a la copia
vieja muerta (`VersionDe_sesion/…/LC_STM/python`). Borrarlas o actualizarlas a
`.dev\.python` haría que `py`/`python` globales funcionen de nuevo.

### Política de ejecución del código Python (2026-11-16)

- **Todo el código Python del árbol (`TLLDCD/src`) ejecuta con `.dev\.python`
  (3.15.2)**; `.dev\venv` es respaldo del mismo runtime.
- Compatibilidad verificada: `compileall` sobre todo `src` con 3.15.2 →
  **exit 0**: el árbol completo compila en esta versión.
- Los lanzadores de `VSC#/Visor3Ddesarrollo/HerraMientas/` resuelven el
  intérprete en orden: `.dev\.python` → `.dev\venv` → `LC_STM\python` → legacy.
  Corregidos a ese orden: `Abrir_VistaPrevia.bat`, `Lanzar_Lucia.bat`,
  `Iniciar_Lucia_Visor.bat` e `Iniciar_Lucia_Visor.ps1` (`Reiniciar_Lucia.bat`
  y `Lanzar_PCK_Completo.bat` ya lo cumplían).
- El visor C# además respeta la variable de entorno `WVP_PYTHON`
  (`GodotConfig.cs` → `GetPythonExePath`) por encima de esas rutas.
- `Rutas.json` §runtime incluye ahora `python` → `../../.dev/.python/python.exe`;
  el validador de rutas lo comprueba en cada ejecución.
- Las copias bajo `VSC#/…/Actualizaciones/` son snapshots históricos de
  versiones publicadas: no se modifican.

## 4. Dependencias externas del sistema

| Dependencia | Detalle | Fuente |
|---|---|---|
| Ollama | `http://127.0.0.1:11434`; modelos probados `qwen2.5:7b` (~4,6 GB VRAM) y `qwen2.5:3b` para menos VRAM | `lucia3D/README.md` §2 |
| Godot | 4.7.2 build mono, D3D12, Forward Plus, física Jolt; el proyecto principal es `MTBGT/WoldVirtualP2P3D` | `project.godot`, `lucia3D/README.md` §2 |
| Blender | Headless para regenerar el rig (`rig_lucia.py`); probado con Blender 5 | `lucia3D/README.md` §5.1, §10 |
| Addon `ziva_agent` | **Desactivado**: build oficial godot-cpp 4.2 crashea (0xC0000005) en Godot 4.7.2; sin build compatible publicada | `MTBGT/.../RUTAS_CORREGIDAS.md` |
| Binario IPFS | Necesario para `STMIPFS` (`ipfs_launcher.py`); versión no verificada en este análisis | `Rutas.json` §archivos |
| Red para gTTS | La voz principal depende de red; respaldo local OneCore si falla | `lucia3D/README.md` §1 |

## 5. Notas de mantenimiento

- Este documento es la referencia de dependencias del árbol; el plan general vive
  en `TLLDCD/src/README.md`.
- Cuando se repare el runtime Python, actualizar la tabla §1 y marcar R1.4 como
  hecho en el plan.
- No fijar versiones de paquetes sin ejecutar primero la suite de LucIA/PSN; si se
  fijan, anotar la fecha y el motivo.
