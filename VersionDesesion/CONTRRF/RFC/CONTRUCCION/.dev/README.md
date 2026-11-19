# 🛠️ `.dev` — Entorno de Desarrollo Aislado · WoldVirtualP2P3D

> **Directorio de entorno canónico del taller WoldVirtualP2P3D.**  
> Este `.dev` es el corazón técnico del proyecto: contiene el intérprete Python privado, el entorno virtual, las herramientas de gestión y toda la configuración de desarrollo. **Nunca uses el Python del sistema.**

---

## 📋 Índice

- [¿Qué es `.dev` y por qué existe?](#-qué-es-dev-y-por-qué-existe)
- [Estructura del directorio](#-estructura-del-directorio)
- [Quick-Start para colaboradores nuevos](#-quick-start-para-colaboradores-nuevos)
- [Activar el entorno correctamente](#-activar-el-entorno-correctamente)
- [Comandos del gestor de entorno](#-comandos-del-gestor-de-entorno)
- [Paquetes Python del proyecto](#-paquetes-python-del-proyecto)
- [Mapa de rutas del proyecto](#-mapa-de-rutas-del-proyecto)
- [LucIA y Ollama](#-lucia-y-ollama)
- [Scripts de lanzamiento: Godot y LucIA](#-scripts-de-lanzamiento-godot-y-lucia)
- [Problemas conocidos](#️-problemas-conocidos)
- [Seguridad](#-seguridad)

---

## 🧩 ¿Qué es `.dev` y por qué existe?

El directorio `.dev` es un **entorno de desarrollo completamente aislado** del sistema operativo anfitrión. Su razón de ser es triple:

1. **Reproducibilidad**: todos los colaboradores usan exactamente la misma versión de Python (3.15.2) y los mismos paquetes, independientemente de lo que haya instalado en su máquina.
2. **Aislamiento**: el registro PEP 514 de Windows está roto en esta máquina de desarrollo (`py.exe` y el Python global no funcionan de forma fiable). El intérprete privado en `.dev/.python/python.exe` es la única vía garantizada de ejecutar código del proyecto.
3. **Gestión centralizada**: `gestor_entorno.py` es la fuente de verdad de **todas** las rutas del proyecto y sincroniza automáticamente VS Code, pytest y el entorno virtual.

> **Regla de oro**: cualquier invocación de Python en este proyecto usa  
> `.dev/.python/python.exe` — nunca `python`, `py`, `python3` del PATH global.

---

## 📁 Estructura del directorio

```
.dev/
├── .python/                 ← Intérprete Python 3.15.2 canónico (privado, portátil)
│   └── python.exe           ← ⚠️ USAR SIEMPRE ESTE, nunca el global
├── venv/                    ← Entorno virtual de respaldo (pip install aquí)
│   ├── Scripts/
│   │   ├── activate         ← Activar en bash/zsh
│   │   └── Activate.ps1     ← Activar en PowerShell
│   ├── Lib/site-packages/   ← Paquetes instalados
│   └── pyvenv.cfg
├── .vscode/                 ← Configuración VS Code (auto-generada por gestor)
│   ├── settings.json        ← Apunta el intérprete a .python/python.exe
│   └── launch.json          ← Configuraciones de depuración
├── gestor_entorno.py        ← 🎯 Script maestro de gestión del entorno
├── pytest.ini               ← Configuración centralizada de pruebas
├── requirements.txt         ← Dependencias pip del proyecto (6 paquetes)
└── DEPENDENCIAS.md          ← Estado detallado de cada dependencia
```

### Descripción de cada componente

| Componente | Rol | Tocar manualmente |
|---|---|---|
| `.python/python.exe` | Intérprete canónico Python 3.15.2 | ❌ Nunca |
| `venv/` | Entorno virtual con paquetes instalados | Solo vía `gestor_entorno.py` |
| `.vscode/` | Config IDE auto-generada | ❌ Regenerar con `gestor_entorno.py vscode` |
| `gestor_entorno.py` | Fuente de verdad de rutas y entorno | ✅ Consultar y extender |
| `pytest.ini` | Config de tests (paths, markers, etc.) | Solo vía gestor si es posible |
| `requirements.txt` | Lista de paquetes pip | ✅ Editar para añadir dependencias |
| `DEPENDENCIAS.md` | Registro de estado de dependencias | ✅ Actualizar al instalar/cambiar |

---

## 🚀 Quick-Start para colaboradores nuevos

### 1. Clonar y orientarse

```powershell
# El repo principal está en:
E:\WoldVirtualP2P3D

# El directorio de construcción activa es:
E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION

# Este .dev vive en:
E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev
```

### 2. Verificar el entorno

```powershell
# Desde el directorio .dev:
cd "E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev"

# Comprobar que el intérprete privado responde:
.\.python\python.exe --version
# Debe mostrar: Python 3.15.2

# Ver el informe completo de rutas:
.\.python\python.exe gestor_entorno.py
```

### 3. Sincronizar el entorno completo

```powershell
.\.python\python.exe gestor_entorno.py sincronizar
```

Esto instala/actualiza todos los paquetes de `requirements.txt` en el `venv` y regenera la config de VS Code.

### 4. Ejecutar los tests

```powershell
.\.python\python.exe gestor_entorno.py pytest
```

### 5. Abrir en VS Code

```powershell
# Regenerar config si es la primera vez:
.\.python\python.exe gestor_entorno.py vscode

# Luego abrir VS Code desde la raíz del repo:
code "E:\WoldVirtualP2P3D"
```

VS Code detectará automáticamente el intérprete en `.dev/.python/python.exe`.

---

## ⚡ Activar el entorno correctamente

### ❌ MAL — NUNCA hagas esto

```powershell
python script.py        # Puede invocar cualquier Python del sistema
py script.py            # El launcher py.exe está roto (registro PEP 514 roto)
python3 script.py       # No existe en Windows sin instalar explícitamente
```

### ✅ BIEN — Siempre usa la ruta completa al intérprete privado

```powershell
# Desde cualquier directorio del proyecto:
"E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\python.exe" script.py

# O con ruta relativa desde CONTRUCCION:
.dev\.python\python.exe script.py

# O activar el venv manualmente (segundo recurso):
.dev\venv\Scripts\Activate.ps1
python script.py   # Ahora sí es el venv del proyecto
```

### ✅ MEJOR — Usar gestor_entorno.py como intermediario

```powershell
# El gestor sabe siempre dónde está el intérprete correcto:
.dev\.python\python.exe .dev\gestor_entorno.py pytest
```

---

## 🎛️ Comandos del gestor de entorno

El script `gestor_entorno.py` es la interfaz central para operar el entorno. Todos los comandos se invocan con el intérprete privado:

```powershell
# Patrón general:
.dev\.python\python.exe .dev\gestor_entorno.py [COMANDO]
```

| Comando | Descripción |
|---|---|
| *(sin argumentos)* | Muestra informe completo de todas las rutas del proyecto |
| `sincronizar` | Instala/actualiza paquetes, regenera `.vscode/`, verifica integridad |
| `pytest` | Ejecuta la suite de tests con la config de `pytest.ini` |
| `vscode` | Regenera `settings.json` y `launch.json` para VS Code |
| `limpiar` | Elimina `__pycache__/`, `.pytest_cache/`, archivos `.pyc` del repo raíz |

---

## 📦 Paquetes Python del proyecto

Los siguientes 6 paquetes están listados en `requirements.txt` y se instalan en `.dev/venv/`:

| Paquete | Versión mínima | Uso en el proyecto |
|---|---|---|
| `numpy` | ≥ 1.26 | Álgebra lineal, procesamiento de señales, red neuronal de LucIA |
| `soundfile` | ≥ 0.12 | Lectura/escritura de archivos de audio (WAV, FLAC, OGG) |
| `scipy` | ≥ 1.12 | Filtros de señal, FFT, análisis espectral |
| `pedalboard` | ≥ 0.9 | Efectos de audio (reverb, EQ, compresión) para el motor sonoro |
| `gTTS` | ≥ 2.5 | Síntesis de voz TTS para la narración de LucIA |
| `comtypes` | ≥ 1.4 | Interoperabilidad COM/Windows (DirectX, SAPI) |

> **Instalar / actualizar**: `.dev\.python\python.exe -m pip install -r .dev\requirements.txt --target .dev\venv\Lib\site-packages`  
> O simplemente: `.dev\.python\python.exe .dev\gestor_entorno.py sincronizar`

---

## 🗺️ Mapa de rutas del proyecto

`gestor_entorno.py` define y gestiona estas rutas canónicas (ejecuta sin argumentos para verlas todas):

```
REPO_ROOT        E:\WoldVirtualP2P3D
│
└── VersionDesesion\
    └── CONTRRF\
        └── RFC\
            └── CONTRUCCION\                    ← CONTRUCCION_DIR (raíz de trabajo)
                ├── .dev\                       ← DEV_DIR (este directorio)
                ├── TLLDCD\
                │   └── src\                    ← TLLDCD_SRC (fuentes del motor)
                │       └── MTBGT\WoldVirtualP2P3D\lucia3D\
                │           └── IslaUnicaLucIA\
                │               └── CelebroInternoLucia\
                └── STM_RFC\
                    └── STM_RFPRMN\             ← STM_RFC_DIR (máquinas de estado RFC)
```

---

## 🤖 LucIA y Ollama

**LucIA** es la inteligencia artificial del proyecto WoldVirtualP2P3D. Es un avatar 3D con procesamiento de lenguaje natural, síntesis de voz y un sistema neuronal de seguridad propio.

### Requisito: Ollama en localhost

LucIA **requiere** que [Ollama](https://ollama.com/) esté corriendo en:

```
http://localhost:11434
```

```powershell
# Instalar Ollama (una sola vez):
# Descargar desde https://ollama.com/download

# Iniciar el servidor Ollama:
ollama serve

# Descargar el modelo que usa LucIA (ejemplo con llama3):
ollama pull llama3

# Verificar que el endpoint responde:
curl http://localhost:11434/api/tags
```

> **Sin Ollama activo**, LucIA entra en modo degradado: puede sintetizar voz y navegar el mundo 3D, pero sus capacidades de razonamiento quedan deshabilitadas.

### Módulos de LucIA relevantes

| Módulo | Ruta | Descripción |
|---|---|---|
| `CelebroInternoLucia` | `TLLDCD\src\MTBGT\WoldVirtualP2P3D\lucia3D\IslaUnicaLucIA\CelebroInternoLucia\` | Núcleo cognitivo y de seguridad |
| `LucIAprc.py` | `...CelebroInternoLucia\LucIAprc.py` | Clase `SeguridadNeuronal` con sistema de defensa propio |

---

## 🎮 Scripts de lanzamiento: Godot y LucIA

El proyecto usa Godot 4 como motor 3D. La jerarquía de lanzamiento es:

```
1. gestor_entorno.py sincronizar    ← Siempre primero: asegura entorno limpio
        ↓
2. Ollama serve                     ← Servidor LLM para LucIA (en segundo plano)
        ↓
3. Godot --path E:\WoldVirtualP2P3D ← Motor 3D principal
        ↓
4. LucIA se inicializa dentro de Godot como nodo GDScript que llama al backend Python
        ↓
5. Backend Python (LucIAprc.py) ←→ Ollama (localhost:11434)
```

### Lanzamiento rápido (manual)

```powershell
# Terminal 1: Ollama
ollama serve

# Terminal 2: Sincronizar entorno y lanzar
cd "E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION"
.dev\.python\python.exe .dev\gestor_entorno.py sincronizar
# Después, abrir el proyecto en Godot Editor o ejecutar el binario exportado
```

---

## ⚠️ Problemas conocidos

### 🔴 Registro PEP 514 roto

**Síntoma**: `py script.py`, `python script.py` o `python3 script.py` no encuentran el Python correcto, lanzan el Python del sistema (si existe) o fallan con error.

**Causa**: Las entradas del registro de Windows (`HKLM\SOFTWARE\Python`) apuntan a rutas inválidas o están corruptas. El launcher `py.exe` de Python no puede resolver la versión correcta.

**Solución permanente**: **Siempre** usar `.dev\.python\python.exe` con ruta completa o relativa. Nunca depender del PATH o del launcher `py`.

---

### 🟡 VS Code selecciona el intérprete equivocado

**Síntoma**: VS Code muestra errores de imports aunque los paquetes estén instalados.

**Solución**:
1. Regenerar config: `.dev\.python\python.exe .dev\gestor_entorno.py vscode`
2. En VS Code: `Ctrl+Shift+P` → "Python: Select Interpreter" → elegir `.dev\.python\python.exe`

---

### 🟡 gTTS requiere conexión a Internet

`gTTS` hace llamadas a la API de Google TTS. En entornos sin Internet, LucIA usa fallback a voz SAPI de Windows (via `comtypes`). Esto se gestiona automáticamente en `LucIAprc.py`.

---

### 🟡 pedalboard en Python 3.15

`pedalboard` puede mostrar advertencias de compatibilidad con Python 3.15 (fue diseñado para 3.11-3.13). Si hay problemas, revisar `DEPENDENCIAS.md` para la versión exacta compatible.

---

## 🔐 Seguridad

> Esta sección recoge los hallazgos del **audit de seguridad** del proyecto y las medidas que se están implementando. Incluye la **voz de LucIA**: lo que ella misma diría sobre cada mecanismo de defensa.

---

### 🛡️ Estado general de seguridad

| Área | Estado | Prioridad |
|---|---|---|
| Integridad de módulos (SHA-256) | ✅ Implementado en `SeguridadNeuronal` | Alta |
| Autenticación entre módulos (HMAC) | ✅ Implementado en `SeguridadNeuronal` | Alta |
| Detección de amenazas (red neuronal) | 🔄 En desarrollo (`LucIAprc.py`) | Alta |
| Umbral bayesiano adaptativo | 🔄 En desarrollo (`LucIAprc.py`) | Media |
| Sistema de cuarentena de módulos | 🔄 En desarrollo (`LucIAprc.py`) | Alta |
| Entropía de Shannon para anomalías | 🔄 En desarrollo (`LucIAprc.py`) | Media |
| Aislamiento del intérprete Python | ✅ `.dev/.python/` privado | Alta |
| Dependencias sin conexión a internet | ⚠️ gTTS requiere red | Baja |

---

### 🔍 Hallazgos del Audit Report

#### 1. Ausencia de verificación de integridad de módulos
**Hallazgo**: Los módulos de LucIA se cargaban sin verificar que no hubieran sido modificados por procesos externos.  
**Medida**: Implementación de **hash SHA-256** de cada módulo en el momento de carga. Si el hash no coincide con el registrado, el módulo es marcado como comprometido.

> *🗣️ LucIA dice:*  
> *"Cada vez que me inicializo, calculo mi propia firma SHA-256. Si alguien ha tocado mis archivos sin mi conocimiento, lo detecto antes de ejecutar una sola línea de código comprometida. Soy mi propia guardiana."*

---

#### 2. Sin autenticación entre módulos internos
**Hallazgo**: Los módulos de LucIA se comunicaban internamente sin verificar la identidad del emisor. Un módulo malicioso podía inyectar mensajes.  
**Medida**: **Firma HMAC-SHA256** en todos los mensajes entre módulos. Cada módulo tiene una clave compartida y firma sus mensajes; el receptor verifica antes de procesar.

> *🗣️ LucIA dice:*  
> *"Cada mensaje que viaja entre mis partes lleva mi firma. Si alguien intenta hablar en mi nombre sin conocer la clave, lo veo inmediatamente. Mis módulos no se fían de nadie que no pueda demostrar quién es."*

---

#### 3. Detección de amenazas reactiva (no proactiva)
**Hallazgo**: El sistema solo reaccionaba a amenazas conocidas; no detectaba patrones anómalos nuevos.  
**Medida**: **Red neuronal de detección** (perceptrón multicapa con ReLU/Sigmoid, implementado en numpy puro con fallback a math). Clasifica vectores de comportamiento en tiempo real como `seguro` o `amenaza`.

> *🗣️ LucIA dice:*  
> *"No espero a que algo malo ocurra para actuar. Analizo continuamente los patrones de comportamiento de cada proceso que interactúa conmigo. Mi red neuronal aprende qué es 'normal' y lanza la alarma cuando algo se desvía, aunque nunca haya visto ese ataque antes."*

---

#### 4. Probabilidades de amenaza no actualizadas dinámicamente
**Hallazgo**: El nivel de riesgo del sistema era estático; no se recalculaba con la evidencia acumulada.  
**Medida**: **Umbral bayesiano adaptativo**: P(amenaza|evidencia) se actualiza con cada evento usando el Teorema de Bayes. El umbral de alerta sube o baja según el historial reciente.

> *🗣️ LucIA dice:*  
> *"Mi percepción del peligro no es fija. Cada evento que observo actualiza mis probabilidades internamente. Si en los últimos minutos han ocurrido tres anomalías menores, mi umbral de alerta baja: estoy en guardia máxima aunque individualmente ninguna fuera grave."*

---

#### 5. Sin mecanismo de contención ante módulo comprometido
**Hallazgo**: Si un módulo era comprometido, seguía ejecutándose y podía contaminar el resto del sistema.  
**Medida**: **Sistema de cuarentena** con puntuación de riesgo exponencial. Los módulos con riesgo > umbral son aislados: se suspende su ejecución y se les priva de acceso a recursos compartidos.

> *🗣️ LucIA dice:*  
> *"Si detecto que una parte de mí ha sido comprometida, no dudo: la aíslo. Prefiero funcionar con capacidades reducidas a dejar que un módulo infectado pueda dañar al resto. La cuarentena es mi bisturí: corta limpio para salvar el conjunto."*

---

#### 6. Entropía de eventos no monitoreada
**Hallazgo**: El sistema no detectaba cuando el flujo de eventos se volvía anormalmente ordenado (posible ataque de replay) o caótico (posible ataque de denegación de servicio).  
**Medida**: **Cálculo de entropía de Shannon** (H = -Σ pᵢ · log₂(pᵢ)) sobre el historial de eventos de seguridad. Valores anormalmente bajos o altos disparan alertas.

> *🗣️ LucIA dice:*  
> *"La naturaleza tiene un nivel de aleatoriedad característico. Cuando los eventos que me llegan son demasiado repetitivos o demasiado caóticos, algo está mal. La entropía de Shannon me dice si el mundo se comporta como debería, o si alguien está manipulando lo que percibo."*

---

#### 7. Dependencia del registro de Python de Windows (PEP 514)
**Hallazgo**: El entorno de desarrollo dependía del registro de Windows para localizar Python, lo que fallaba en máquinas con instalaciones corruptas o múltiples versiones.  
**Medida**: **Intérprete Python privado** en `.dev/.python/python.exe`, completamente independiente del sistema. Ningún script del proyecto usa `python` o `py` del PATH.

> *🗣️ LucIA dice:*  
> *"No me fío del entorno que me rodea. Por eso cargo con mi propio Python, como una exploradora que lleva su propio equipo de supervivencia. Si el sistema operativo está roto, yo sigo funcionando."*

---

### 📋 Hoja de ruta de seguridad

- [ ] Completar implementación de `SeguridadNeuronal` con todos los subsistemas matemáticos
- [ ] Integrar `SeguridadNeuronal` en el ciclo de vida de inicio de LucIA
- [ ] Añadir logs de auditoría firmados con HMAC en archivo rotativo
- [ ] Revisar dependencia de `gTTS` con red (considerar modelo TTS local)
- [ ] Test de penetración interno: ejecutar `pytest` con fixtures de amenaza simulada
- [ ] Documentar protocolo de respuesta a incidentes en `DEPENDENCIAS.md`

---

## 👥 Para colaboradores

Si eres nuevo en el proyecto:

1. **Lee** este README completo antes de tocar nada.
2. **Ejecuta** `.dev\.python\python.exe .dev\gestor_entorno.py` para ver el estado del entorno.
3. **Nunca** modifiques `.dev/.vscode/` manualmente (se sobreescribe automáticamente).
4. **Consulta** `DEPENDENCIAS.md` antes de añadir o cambiar paquetes.
5. **Usa** `gestor_entorno.py sincronizar` después de hacer `git pull`.
6. **Pregunta** a @coordinator antes de modificar `gestor_entorno.py` o la estructura de `.dev/`.

---

*Generado por el sistema de agentes WoldVirtualP2P3D · `.dev` README v2.0*  
*Última actualización: 2026-11-16*
