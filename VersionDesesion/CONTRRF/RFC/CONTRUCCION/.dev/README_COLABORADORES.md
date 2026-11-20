# `.dev` — Guía rápida para colaboradores

Este documento explica qué es la carpeta `.dev`, para qué sirve cada pieza y
cómo trabajar en ella sin romper el entorno del resto del equipo. El detalle
completo está en [`README.md`](README.md); aquí va lo imprescindible.

## Qué es `.dev`

`.dev` es el **taller de desarrollo aislado** de WoldVirtualP2P3D. No forma
parte del producto que recibe el usuario final: contiene el intérprete Python
privado, el entorno virtual, las dependencias, las pruebas y los scripts de
arranque de los servicios (blockchain y LucIA).

Su objetivo es que cualquier colaborador ejecute el mismo Python y las mismas
herramientas, sin depender de lo que tenga instalado en su sistema.

## Tres reglas de oro

1. **Usa siempre el Python privado**: `.dev/.python/python.exe`.
   Nunca `python`, `py` ni `python3` del PATH del sistema.
2. **No subas artefactos al repositorio**: `venv/`, `.python/`, `__pycache__/`,
   `.pytest_cache/`, `_tmp_*` y logs son locales. Si `git status` los muestra,
   añádelos a tu exclusión local; no los subas.
3. **No muevas ni renombres carpetas de `.dev`** sin actualizar a la vez
   `gestor_entorno.py`: es la fuente de verdad de las rutas del proyecto.

## Estructura

```
.dev/
├── .python/python.exe      Intérprete canónico (portátil, privado)
├── venv/                   Entorno virtual de respaldo para pip
├── gestor_entorno.py       Gestor de rutas, servicios y compilación
├── gestor.bat              Lanzador del gestor en Windows
├── run_pytest.bat|.ps1     Ejecuta la suite con el gestor
├── requirements.txt        Dependencias Python del proyecto
├── pytest.ini              Rutas y patrón de pruebas
├── reconstruir_visor.bat   Compila el visor WPF
├── global.json             SDK de .NET fijado (8.0.400, rollForward latestFeature)
├── modulos/                Recursos y piezas auxiliares
├── docs/                   Documentación interna del taller
├── _tmp_*/                 Espacio temporal de pruebas y empaquetado
└── _backup_renombrado/     Copia de seguridad de una reorganización previa
```

## Primeros pasos

```bat
:: desde la carpeta .dev
gestor.bat                       :: diagnóstico completo del entorno
gestor.bat sincronizar           :: aplica rutas y configuración de VS Code
```

Al terminar, abre el proyecto en VS Code: el intérprete ya estará apuntando a
`.dev/.python/python.exe`.

Para trabajar desde bash:

```bash
cd VersionDesesion/CONTRRF/RFC/CONTRUCCION/.dev
./.python/python.exe gestor_entorno.py dependencias
```

## Comandos del gestor

| Comando | Qué hace |
| --- | --- |
| `sincronizar` | Aplica variables de entorno y configuración de VS Code |
| `dependencias` | Verifica .NET, DLL nativas, Python y Godot |
| `validar-frontera` | Comprueba que nada sale de `E:\WoldVirtualP2P3D` |
| `blockchain [iniciar\|detener\|reiniciar\|estado]` | Gestiona el nodo STM_BKCH (8545) |
| `lucia [iniciar\|detener\|reiniciar\|estado]` | Gestiona el cerebro de LucIA (8765) |
| `reconstruir-visor` | Compila el visor C# con dotnet |
| `pytest` | Ejecuta la suite completa |
| `todo` | Sincroniza, arranca servicios y compila el visor |

Sin argumentos, el gestor imprime un diagnóstico con el estado de las rutas,
del nodo blockchain, del puente de LucIA y del visor.

## Pruebas

```bat
run_pytest.bat
run_pytest.bat TLLDCD/src/tests/STM_test3/test_stm_def.py -k iocs
```

`pytest.ini` apunta a `TLLDCD/src/tests` y `STM_RFC/STM_RFPRMN/tests` y añade
ambos árboles al `PYTHONPATH`; no hace falta configurar nada más.

## Servicios que arranca el taller

- **STM_BKCH** — nodo blockchain local en `127.0.0.1:8545`.
- **LucIA** — puente TCP en `127.0.0.1:8765` que conecta Godot con Ollama
  (`127.0.0.1:11434`). Si Ollama no está activo, LucIA arranca igual pero no
  puede generar respuestas.
- **Visor WPF** — compilado por `reconstruir-visor` y `todo`.

Los logs de estos servicios se escriben en `.dev/_tmp_tests/logs/` o en
`%LOCALAPPDATA%\WoldVirtualP2P3D\logs\`, según el lanzador.

## Notas y problemas conocidos

- **`global.json` fija el SDK 8.0.400** con `rollForward: latestFeature`.
  Un SDK de .NET 10/11 no lo satisface. Usa Visual Studio/dotnet 8 o compila
  fuera del árbol `.dev` si necesitas validar algo puntual.
- El registro PEP 514 de Windows puede estar roto en algunas máquinas: por eso
  existe `.python/python.exe`.
- `_tmp_tests/` contiene restos de pruebas automáticas. Puedes vaciarlo, pero
  no lo interpretes como parte del producto.
- Los scripts `Iniciar_Lucia_Visor.bat/.ps1` viven junto al visor; `.dev` solo
  aporta el intérprete y las dependencias.

## Seguridad

- No guardes credenciales, semillas ni tokens en `.dev`.
- No ejecutes cargadores remotos ni scripts descargados de la red para
  "probar": el subsistema `STM_DEF` existe precisamente para detectarlos.
- El módulo de refuerzo criptográfico del proyecto está en
  `Refactorizacion/src/VSC#/Visor3Ddesarrollo/Seguridad/Seguridad_sesion_unica/SeguridadReforzada.cs`
  y no requiere paquetes externos.

## Para colaboradores nuevos: ruta recomendada

1. Ejecuta `gestor.bat` y revisa que todas las rutas estén en `[OK]`.
2. Ejecuta `run_pytest.bat` para confirmar que la base está sana.
3. Trabaja solo en tu rama feature; no hagas merge ni push sin acordarlo.
4. Antes de entregar: `validar-frontera`, `pytest` y una prueba visual real.
