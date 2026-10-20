# WoldVirtualP2P3D 🌐

> **Metaverso 3D P2P Descentralizado & Visor Autónomo C# / Godot**  
> Prototipo jugable avanzado desarrollado con arquitectura desacoplada: **Visor C# (.NET 8 WPF)**, motor gráfico **Godot Engine 4** incrustado, topología de red **P2P distribuida** y portal **WebNodo con túnel efímero Cloudflare**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![.NET 8](https://img.shields.io/badge/.NET-8.0%20WPF-512bd4?logo=dotnet&logoColor=white)](https://dotnet.microsoft.com)
[![Godot Engine](https://img.shields.io/badge/Godot-Engine%204-478cbf?logo=godot-engine&logoColor=white)](https://godotengine.org)
[![Cloudflare Tunnel](https://img.shields.io/badge/Tunnel-Cloudflare%20Quick-f38020?logo=cloudflare&logoColor=white)](https://www.cloudflare.com)
[![Version](https://img.shields.io/badge/Release-v0.0.012__actualizacion__049ac229-green.svg)](https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v0.0.012_actualizacion_049ac229)

---

## 🌌 Visión General del Proyecto

**WoldVirtualP2P3D** es una plataforma y prototipo técnico avanzado de metaverso 3D descentralizado. A diferencia de las plataformas virtuales tradicionales que dependen de servidores centrales propietarios, este ecosistema combina:
- **Visor C# / WPF (.NET 8):** Control de acceso local, autenticación criptográfica de hardware, monedero DeFi (12 palabras semilla), rotación dinámica de llaves maestras e incrustación de bajo nivel Win32 del motor 3D.
- **Motor 3D Godot 4 Incrustado:** Renderizado 3D de alta fidelidad, carrusel interactivo de avatares, hangar cyberpunk, portal dimensional y archipiélago de islas procedurales.
- **Red P2P & WebNodo Autónomo:** Servidor HTTP embebido en C# con proxy TCP local transparente y túnel público efímero Cloudflare (`*.trycloudflare.com`), permitiendo invitar a amigos y compartir el visor directamente desde la propia máquina del usuario sin intermediarios.

---

## 🎮 Descarga y Puesta en Marcha

### 1. Descarga del Visor Portable (Recomendado)
No requiere instalación ni dependencias de Node.js o librerías adicionales:
* 📥 **Descarga directa:** [DMWoldVirtualp2pCNXv0.0.012_actualizacion_049ac229.exe](https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v0.0.012_actualizacion_049ac229/DMWoldVirtualp2pCNXv0.0.012_actualizacion_049ac229.exe) *(~687 MB, ejecutable portable 64-bit)*
* 📦 **Release oficial:** [GitHub Releases v0.0.012_actualizacion_049ac229](https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v0.0.012_actualizacion_049ac229)

### 2. Flujo de Acceso en el Primer Inicio
1. **Registro de Identidad & Hardware:** Al abrir por primera vez, el visor extrae la huella digital criptográfica de tu hardware (CPU, Placa Base, BIOS).
2. **Frase Semilla DeFi:** Se generan 12 palabras mnemónicas que debes respaldar de forma segura.
3. **Generación de «La Llave»:** Se crea tu archivo maestro `llave_acceso.json`.
4. **Acceso y Rotación:** Cada vez que inicias sesión, el visor valida la llave y rota su hash SHA-256 único, impidiendo duplicidad o suplantación.
5. **Entrada al Mundo 3D:** El visor incrusta el motor Godot y activa en segundo plano la red P2P y el túnel WebNodo.

---

## 🌐 WebNodo Efímero & Compartición PC-a-PC

Durante la sesión 3D, el visor dispone del botón **`🌐 WebNodo`** en la barra superior del HUD:

```
[Visor 3D Anfitrión]
       │
       ├─► WebNodo C# Local (http://localhost:3030/)
       │         ▲
       │         │ (Proxy TCP Loopback + Reescritura Host Header)
       │         ▼
       └─► Túnel Efímero Cloudflare (https://xxx.trycloudflare.com/) ──► Amigos / Invitados
```

* **Cero configuración de puertos:** Gracias a Cloudflare Quick Tunnel (`cloudflared`) y alternativas SSH (Serveo / localhost.run), no se requiere abrir puertos en el router ni configurar DDNS.
* **Proxy TCP Anti-Error 400:** El servidor embebido en C# integra un proxy TCP transparente que reescribe en tiempo real las cabeceras `Host`, garantizando que `HTTP.sys` nunca rechace las solicitudes con errores `Bad Request - Invalid Hostname`.
* **Portal de Invitado Autónomo:** Tus amigos pueden abrir tu enlace efímero en cualquier navegador web, visualizar el estado en línea de tu nodo y descargar el visor para unirse a tu misma isla virtual.

---

## 🚀 Experiencia Jugable: Fases de la Simulación

```
[1. Selector 3D de Avatares] ──► [2. Registro de Nick] ──► [3. Hangar Cyberpunk]
                                                                  │
                                                      [4. Portal Dimensional]
                                                                  │
                                                                  ▼
[7. Panel de Islas y Teletransporte] ◄── [6. Réplica P2P] ◄── [5. Isla Procedural]
```

1. **Selector 3D de Ocho Avatares:** Carrusel interactivo circular con 8 modelos antropomórficos animados (4 femeninos `AVMJ1..4` y 4 masculinos `AVH1..4`).
2. **Registro de Identidad:** Previsualización dinámica sobre pedestal mediante `SubViewport` 3D y guardado de perfil.
3. **Hangar Espacial Cyberpunk:** Estación interestelar industrial con suelo metálico, bruma volumétrica y área de control inicial con físicas de colisión.
4. **Portal Dimensional:** Estructura anular de energía que activa la transición fluida hacia el archipiélago virtual.
5. **Isla Procedural y Océano:** Generación de parcela en rejilla serpentina (chunks de 199.5 m) con shader de agua dinámico, atmósfera con dispersión y cámara orbital con amortiguación suave.
6. **Sincronización P2P:** Visualización en tiempo real de nodos remotos, placas de nombre (*nametags*) y locomoción compartida.
7. **Panel de Islas [T]:** Menú HUD interactivo para teletransporte instantáneo entre parcelas del archipiélago.

---

## ⌨️ Controles de Navegación

| Acción | Control / Tecla |
|---|---|
| **Caminar / Desplazamiento** | <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> o Flechas de dirección |
| **Correr (Sprint)** | <kbd>Shift</kbd> o <kbd>AltGr</kbd> + <kbd>↑</kbd> |
| **Órbita de Cámara** | Movimiento del ratón |
| **Portal WebNodo** | Clic en botón superior **`🌐 WebNodo`** (Abre navegador y copia URL pública) |
| **Panel de Islas** | Tecla <kbd>T</kbd> o botón **Islas [T]** |
| **Teletransporte** | Abrir panel (<kbd>T</kbd>), seleccionar destino y pulsar para saltar |

---

## 🏗️ Estructura del Repositorio y Arquitectura

```
WoldVirtualP2P3D/
├── VersionDe_sesion/
│   └── Sistema_Principal/
│       └── PRY/
│           └── actualizacion_049ac229/
│               └── src/
│                   ├── VSC#/                  # Proyecto Visor C# (.NET 8 WPF)
│                   │   ├── App.xaml / .cs      # Arranque y orquestación
│                   │   ├── MainWindow.xaml/.cs # HUD 3D, sesión y túnel WebNodo
│                   │   ├── GodotHwndHost.cs    # Incrustación Win32 de Godot
│                   │   ├── Services/           # WebNodoService con Proxy TCP
│                   │   ├── RedP2P/             # Nodos P2P y túneles
│                   │   ├── p2pipfsCS/          # EphemeralTunnelRunner y DHT
│                   │   ├── STM_actualizar/     # Sistema de actualización
│                   │   ├── godot_project.zip   # Runtime 3D incrustado
│                   │   └── godot_exe.zip       # Motor Godot 4 incrustado
│                   ├── MTBGT/                 # Proyecto Fuente 3D Godot
│                   │   └── WoldVirtualP2P3D/   # Escenas, modelos glTF, texturas y shaders
│                   ├── STMIPFS/               # Subsistema IPFS distribuido
│                   ├── STM_DOC/               # Documentación y diagramas
│                   └── tests/                 # Pruebas automatizadas y diagnósticos
├── AGENTS.md                                  # Directivas del entorno Disco E:
├── GEMINI.md                                  # Reglas de desarrollo Antigravity
└── README.md                                  # Este documento
```

---

## 🧹 Estado de Optimización del Repositorio (~0.98 GB)

El repositorio se encuentra optimizado en su tamaño mínimo esencial sin binarios huérfanos ni cachés acumuladas:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPOSICIÓN DEL REPOSITORIO (~0.98 GB TOTAL)                    │
├───────────────────────────────────────────────────────┬────────────┬───────────────────┤
│ Módulo / Componente                                   │ Tamaño     │ Rol Técnico       │
├───────────────────────────────────────────────────────┼────────────┼───────────────────┤
│ 📦 src/VSC#/godot_project.zip                         │   448,9 MB │ Runtime 3D Visor  │
│ 🎮 src/MTBGT/WoldVirtualP2P3D (Fuentes 3D Godot)      │   250,1 MB │ Modelos y Shaders │
│ 🗄️ .git/ (Historial limpio y compactado)              │   215,5 MB │ Control versiones │
│ ⚙️ src/VSC#/godot_exe.zip                             │    82,2 MB │ Motor Godot Win64 │
│ 📄 Resto del código (C#, Python, Docs, Tests)         │    ~7,0 MB │ Código fuente     │
│ ❌ Carpetas temporales (bin/, obj/, publish/)         │     0,0 MB │ Purgadas (0 MB)   │
└───────────────────────────────────────────────────────┴────────────┴───────────────────┘
```

> **Política de almacenamiento:** Los ejecutables generados (`*.exe`), librerías (`*.dll`) y salidas de compilación (`bin/`, `obj/`, `publish/`) se mantienen estrictamente fuera del control de versiones mediante `.gitignore`. Los binarios finales se distribuyen exclusivamente a través de [GitHub Releases](https://github.com/Chicook/WoldVirtualP2P3D/releases).

---

## 🧠 Núcleo Cognitivo LucIA (Subsistema de Inteligencia)

El ecosistema integra de forma paralela el subsistema cognitivo **LucIA**:
- **Red Neuronal Distribuida:** 50 neuronas activas (`ENRN`, `RF_SL`, `RF_EN`, `RNP`, `SLRN`) con cálculo de tensores y entropía.
- **Blockchain PoNL:** Registro inmutable de transacciones y estados de sesión (`BKSVCB.py`).
- **Inferencia Híbrida:** Soporte para modelos locales (Ollama/LM Studio) y catálogo remoto gratuito mediante `IAFREE` / OpenRouter.
- **Voz Neuronal:** Motor de síntesis con modulación DSP integrado en `voice_engine.py`.

---

## 📜 Licencia

Distribuido bajo la Licencia **MIT**. Consulta el archivo `LICENSE` para más información.
