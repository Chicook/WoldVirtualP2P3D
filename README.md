# ⬢ WoldVirtual P2P 3D — Metaverso Cripto Descentralizado

> **🎯 Estado del Proyecto:** Prototipo Funcional de Alta Fidelidad y Visor Estético Completado.
> Integración fluida del motor 3D de Godot incrustado en un visor WPF moderno y descentralizado de 3 Capas.

---

## 🔍 Arquitectura de 3 Capas Implementada

La arquitectura actual del proyecto conecta de forma segura el motor de renderizado 3D, la lógica de red local P2P y la persistencia criptográfica en el sistema de la siguiente manera:

```mermaid
graph TD
    A[Capa 3: Visor Singularity WPF] -->|Enlace Criptográfico / IPC| B[Capa 2: Motor Godot 3D]
    A -->|Persistencia Local SQL / Hardware| C[Capa 1: Estado Global & Firma]
    B -->|Sincronización de Coordenadas| D[Protocolo P2P - Red de Islas]
```

1. **Capa 1: Persistencia y Firma (Estado Global):**
   * **Base de Datos SQLite:** Almacenamiento local seguro de identidades vinculadas a firmas de hardware.
   * **Criptografía de Hardware (Fingerprint):** Algoritmo de hash SHA-256 generado a partir de IDs únicos de CPU, Placa Base y Sistema Operativo obtenidos mediante WMI.
   * **Firma Digital Cuántica:** Exportación e importación segura de claves en un paquete `.zip` comprimido que resguarda la llave cuántica local.

2. **Capa 2: Motor Gráfico (Godot Engine):**
   * **Godot 4.6.2 Stable (Mono / C# / OpenGL3):** Renderizado en caliente embebido directamente mediante controladores nativos.
   * **Lógica del Mundo P2P:** Teletransporte P2P, gestión de físicas del avatar, renderizado de islas y shaders integrados.

3. **Capa 3: Visor Singularity (WPF / .NET 8):**
   * **Flujo del Wizard en 4 Pasos:** Registro guiado, generación automática de firma, validación de MetaMask y asignación de coordenadas de islas.
   * **Puente HTTP Local (Puerto 8080):** Pasarela de comunicación segura que intercepta la firma de MetaMask desde el navegador para transferirla directamente al Visor WPF.

---

## 🚀 Logros y Hitos Completados (Sesión de Rediseño)

### 💎 Rediseño Estético desde Cero del Visor WPF (`MainWindow.xaml`)
Se ha implementado una interfaz visual de altísima calidad inspirada en las mejores prácticas de la estética cyberpunk e interfaces tácticas de ciencia ficción:
* **Glow & Glassmorphism:** Paneles de cristal esmerilado con fondo translúcido (`#F2080E1C`), bordes cian muy sutiles y efectos de resplandor mediante sombras difusas y desenfocadas de neón.
* **Control Chrome Personalizado:** Ventana fija a `1600x950` sin barra nativa de Windows (`WindowStyle="None"`, `NoResize`) para evitar deformaciones físicas en el avatar, incorporando controles minimalistas de Minimizar y Cerrar con respuestas visuales interactivas.
* **Visuales y Inputs Premium:** Campos de entrada iluminados con transiciones de color en hover/foco y botones de acción dinámicos en neón cian, verde esmeralda y magenta.
* **HTTP Bridge Wait Overlay:** Alerta premium de validación de MetaMask con una barra animada que pulsa de forma infinita mientras escucha el puerto local.

### 🎮 Integración Total de Godot e Inmersión del Viewport 3D
* **Solución de Vibración del Avatar:** Fijación del visor nativo a coordenadas exactas y estiramiento por GPU, eliminando la vibración del avatar causada por constantes cambios de escala y recálculos en el `HwndHost`.
* **Modo Inmersivo 100%:** Al arrancar el metaverso, el `PanViewportContainer` se expande ocupando el **100% de la ventana** (`Grid.RowSpan="3"`, `Panel.ZIndex="99"`, `Stretch`).
* **Visualización Perfecta de Godot UI:** El panel interno de control de Godot ("RED P2P") y sus menús superiores ya no se solapan ni se ven obstruidos por barras laterales de WPF, disfrutando de toda la resolución de pantalla.
* **Desacoplamiento de Cierre Seguro (Cerrar Sesión):** Implementación de una bandera de exclusión (`_ignoreGodotExit`) que previene que WPF aborte el proceso global del visor al apagar Godot durante el teletransporte o el retorno al menú de inicio de sesión.
* **Dummy Controller de Retrocompatibilidad:** Todos los componentes requeridos por el código-detrás (`MainWindow.xaml.cs`) para su lógica interna (como la barra lateral antigua `PanSidebar`, anchos `ColSidebar` y etiquetas de islas) se mantuvieron encapsulados en un Grid oculto (`Visibility="Collapsed"`). Esto garantiza **cero errores de compilación y cero NullReferenceException** en tiempo de ejecución.

---

## 📅 Próximos Pasos en el Prototipo

1. **Pruebas de Concurrencia Multijugador:**
   * Iniciar dos instancias del Visor Singularity simulando diferentes firmas digitales y comprobar la sincronización del estado espacial 3D y la presencia del avatar.
2. **Refinamiento del Cierre de Sesión (Cerrar Sesión):**
   * Refinar el retorno y limpieza total de la memoria e hilos de ejecución de sockets tras múltiples cierres e inicios de sesión consecutivos en el visor P2P.
3. **Refinamiento de Assets P2P:**
   * Continuar optimizando el renderizado gráfico de las islas y la sincronización de archivos JSON en tiempo real sin dependencias externas o servidores centralizados.

## ☀️ Verano de IAs: Roadmap Estratégico de Desarrollo (Core P2P)

**Período:** 25 de junio al 31 de agosto (67 días de desarrollo intensivo).
**Capacidad:** 4 horas/día = 268 horas totales.
**Metodología de Desarrollo AI-Assisted:** Asignación de 67 horas dedicadas a cada entorno/agente (Antigravity, Cursor, Trae, VS Code), maximizando el paralelismo cognitivo para construir la infraestructura de red descentralizada del metaverso.

---

### 📅 Fase 1: Criptografía de Hardware, Identidad y Sockets Base (Días 1 a 20)

*   **Objetivo Maestro:** Establecimiento de la capa de transporte segura y generación de identidades únicas irrefutables vinculadas al hardware físico, fundamentales para la soberanía del usuario en un metaverso DeFi.
*   **Hito Técnico:** Dos nodos pueden descubrirse mutuamente en la red local e intercambiar un *handshake* criptográfico sin depender de servidores DNS o intermediarios centrales, garantizando una verdadera descentralización.

*   **Distribución del Flujo de Trabajo (4 Horas/Día):**
    *   ⏱️ **Hora 1 (Antigravity - Arquitectura & Diseño):** Análisis algorítmico y viabilidad de los modelos de Hash. Diseño del esquema de seguridad (SHA-256 + Salts aleatorios) para extraer IDs de hardware (CPU, Placa Base, OS) garantizando colisiones nulas y mitigando vectores de ataque de suplantación de identidad en el juego. **Mejores Prácticas DeFi:** Implementar una arquitectura de "confianza cero" (zero-trust) y soluciones de identidad descentralizada (DID) para devolver el control de los datos personales al usuario, previniendo la suplantación de avatares y el acceso no autorizado. Considerar la resistencia a la computación cuántica para la criptografía a largo plazo. <cite data-cite="1"></cite><cite data-cite="5"></cite>
    *   ⏱️ **Hora 2 (Cursor - Desarrollo Core C#):** Implementación exhaustiva de la lógica de identidad (`HardwareFingerprint.cs`). Programación de las consultas WMI (Windows Management Instrumentation) seguras y la serialización para encapsular la firma digital en paquetes comprimidos y encriptados de exportación (`.zip`). **Mejores Prácticas DeFi:** Asegurar el almacenamiento de claves privadas mediante hardware wallets, almacenamiento offline o técnicas de fragmentación de claves (Shamir's Secret Sharing). Implementar mecanismos de rotación de claves y procesos seguros para la generación y firma de transacciones en un entorno aislado. <cite data-cite="2"></cite><cite data-cite="3"></cite>
    *   ⏱️ **Hora 3 (Trae - Implementación de Red):** Programación del servidor TCP/IP asíncrono y los *listeners* de red (`TcpListener`). Creación de los pools de hilos de alto rendimiento y las rutinas de *heartbeat* (latidos) para mantener vivos los sockets P2P y manejar las desconexiones súbitas de los jugadores. **Mejores Prácticas DeFi:** Implementar protocolos de comunicación P2P robustos y cifrados de extremo a extremo. Asegurar la autenticación mutua entre nodos para prevenir ataques de intermediario (man-in-the-middle) y garantizar la integridad de la red.
    *   ⏱️ **Hora 4 (VS Code - QA, Refactor y Testing):** Consolidación estructural del código. Ejecución de pruebas de humo (*smoke testing*) levantando múltiples instancias simultáneas en bucle local (loopback `127.0.0.1`), comprobando la persistencia en SQLite y validando que no se generen fugas de sockets no cerrados. **Mejores Prácticas DeFi:** Realizar auditorías de seguridad de código regulares, pruebas de penetración y fuzzing para identificar vulnerabilidades. Implementar monitoreo continuo de la red para detectar actividades anómalas y posibles ataques.

*   **Entregable:** Librería Core de enlace de red que permite conectar dos Visores Singularity directamente de igual a igual (P2P) y validar la sesión mediante firmas, sentando las bases para una economía digital segura.

---

### 📅 Fase 2: Motor de Tráfico, Throttling y Distribución Descentralizada (Días 21 a 40)

*   **Objetivo Maestro:** Implementación del sistema de distribución de archivos (*file-sharing* P2P) con control estricto de recursos físicos del jugador, crucial para la sostenibilidad y equidad en un metaverso DeFi.
*   **Hito Técnico:** Capacidad de compartir el cliente/visor (.zip del juego base) y los *assets* 3D de las islas sin superar jamás el límite estricto *hard-coded* de **300 MB** de subida por nodo, optimizando el uso de recursos de red.

*   **Distribución del Flujo de Trabajo (4 Horas/Día):**
    *   ⏱️ **Hora 1 (Antigravity - Arquitectura & Diseño):** Diseño del algoritmo *Token Bucket* o *Leaky Bucket* para la modelación del ancho de banda (Throttling). Análisis de la fragmentación óptima de paquetes y prevención de interbloqueos ante congestiones de red en enrutadores domésticos. **Mejores Prácticas DeFi:** Diseñar mecanismos de throttling que sean resistentes a ataques de denegación de servicio (DoS/DDoS) y que garanticen un acceso justo a los recursos de la red para todos los participantes.
    *   ⏱️ **Hora 2 (Cursor - Desarrollo Core C#):** Codificación del motor de transferencia por *chunks* (fragmentos asíncronos en RAM). Implementación de los limitadores de subida mediante `Task.Delay` dinámicos, que calibran milisegundo a milisegundo los *bytes-per-second* en el torrente de transmisión. **Mejores Prácticas DeFi:** Asegurar la integridad de los datos transferidos mediante sumas de verificación criptográficas y firmas digitales. Implementar mecanismos de retransmisión robustos para garantizar la entrega de datos en redes inestables.
    *   ⏱️ **Hora 3 (Trae - Implementación de Red):** Gestión multiplexada de conexiones masivas concurrentes. Asegurar que si 10 usuarios solicitan archivos simultáneamente de un solo jugador, el límite total de salida se reparta matemáticamente de forma justa (ej. max. 30 MB por conexión simultánea), evitando estrangular la línea del anfitrión. **Mejores Prácticas DeFi:** Implementar algoritmos de equidad en la distribución de ancho de banda para prevenir que un solo nodo monopolice los recursos. Considerar el uso de redes de entrega de contenido (CDN) descentralizadas para activos populares.
    *   ⏱️ **Hora 4 (VS Code - QA, Refactor y Testing):** Profiling de estrés en entornos simulados de red con altas latencias. Monitoreo automatizado para certificar frente al *Administrador de Tareas* de Windows que el consumo de ancho de banda jamás supera el umbral máximo exigido. **Mejores Prácticas DeFi:** Realizar pruebas de carga y estrés exhaustivas para asegurar la estabilidad de la red bajo condiciones extremas. Monitorear métricas de rendimiento y seguridad en tiempo real para identificar cuellos de botella o vulnerabilidades.

*   **Entregable:** Motor de transferencia modular capaz de actuar como un ecosistema "BitTorrent" encriptado privado, asegurando que el instalador de WoldVirtual se auto-distribuya de manera viral y sostenible entre la comunidad, fomentando la resiliencia y la descentralización.

---

### 📅 Fase 3: Estado Global, Sincronización JSON y "Cero Absoluto" (Días 41 a 60)

*   **Objetivo Maestro:** Sincronización descentralizada del estado universal del metaverso (las miles de islas generadas) garantizando la consistencia eventual y descentralizada de los datos, esencial para la interoperabilidad y la confianza en un entorno DeFi.
*   **Hito Técnico:** Todo nodo es capaz de asimilar, fusionar y persistir su archivo `estado_metaverso.json` maestro de forma atómica y sin pisarse con los avances de otros jugadores en la red, manteniendo la integridad del estado global.

*   **Distribución del Flujo de Trabajo (4 Horas/Día):**
    *   ⏱️ **Hora 1 (Antigravity - Arquitectura & Diseño):** Modelado estructural de base de datos JSON en esquemas CRDT (*Conflict-free Replicated Data Types*). Estrategia heurística basada en marcas de tiempo (Relojes de Lamport) para dictaminar automáticamente el estado final si dos jugadores plantan una isla en la misma hora exacta. **Mejores Prácticas DeFi:** Utilizar CRDTs para garantizar la consistencia eventual y la resolución automática de conflictos en un entorno distribuido. Implementar mecanismos de consenso ligeros para la validación de estados críticos.
    *   ⏱️ **Hora 2 (Cursor - Desarrollo Core C#):** Implementación de la directiva algorítmica del "Cero Absoluto" `(0, 0, 0)`. Lógica genética: cuando un nodo arranca y no detecta pares en la red (o pierde el contacto total con la DHT), inicia su tabla vacía y genera la coordenada base Génesis de inmediato. **Mejores Prácticas DeFi:** Asegurar que el estado inicial (génesis) sea inmutable y verificable criptográficamente. Implementar mecanismos de recuperación de estado robustos para nodos que se unen o reconectan a la red.
    *   ⏱️ **Hora 3 (Trae - Implementación de Red):** Sincronización diferencial extrema (*Delta Syncing*). En lugar de enviar un archivo gigantesco con todo el universo cada segundo, se programan rutinas de comparación que extraen únicamente los registros de islas modificados o creados en los últimos minutos (Deltas), reduciendo el consumo de red a ínfimos *Kilobytes*. **Mejores Prácticas DeFi:** Implementar firmas digitales en los deltas de estado para asegurar su autenticidad e integridad. Utilizar técnicas de compresión y optimización de red para minimizar el ancho de banda.
    *   ⏱️ **Hora 4 (VS Code - QA, Refactor y Testing):** Simulaciones intensivas de "Cerebro Dividido" (*Split-brain network partitioning*). Aislar dos grupos de nodos intencionadamente, poblar de islas sus redes y reconectarlos posteriormente para comprobar la curación automática del estado mediante la fusión inteligente y fluida del JSON. **Mejores Prácticas DeFi:** Realizar pruebas de resiliencia de la red ante particiones y fallos. Implementar mecanismos de monitoreo de la consistencia del estado global y alertas para desviaciones.

*   **Entregable:** Matriz de almacenamiento inmutable y distribuida. Un cosmos virtual cuyo "recuerdo" de todas las construcciones perdurará mientras haya un nodo encendido, garantizando la persistencia y la historia del metaverso.

---

### 📅 Fase 4: Integración 3D en Godot, Desacoplamiento y Cierre Open Source (Días 61 a 67)

*   **Objetivo Maestro:** Enlazar el poderoso y asíncrono puente C# P2P con el contexto gráfico, el sistema de físicas y el renderizado interno de Godot 4.6.2, asegurando una experiencia de usuario fluida y segura en el metaverso DeFi.
*   **Hito Técnico:** Representar visualmente las transacciones P2P en pantalla 3D; donde cada avatar e isla reaccione instantáneamente al paso de paquetes TCP/UDP sin causar *Stuttering* o caída de FPS, manteniendo la inmersión.

*   **Distribución del Flujo de Trabajo (4 Horas/Día):**
    *   ⏱️ **Hora 1 (Antigravity - Arquitectura & Diseño):** Profiling final de paralelismo multihilo. Revisión pormenorizada para extirpar *Deadlocks* (cuellos de botella por esperas de hilos compartidos) en la comunicación IPC (Inter-Process) entre el entorno WPF de .NET 8 y la instancia nativa del motor de Godot. **Mejores Prácticas DeFi:** Implementar mecanismos de comunicación entre procesos (IPC) seguros y auditables. Asegurar que la interacción entre el motor 3D y la lógica de la blockchain sea atómica y resistente a fallos.
    *   ⏱️ **Hora 2 (Cursor - Desarrollo Core C#):** Transpositor universal de coordenadas espaciales. Algoritmo crítico para concatenar la posición general macro: `(Posición Matemática Real = Eje de la Isla Macro + Posición de Avatar Micro)`. Resolución y refactorización orientada a dobles (`double precision`) previniendo colapsos de cálculo flotante al explorar los límites más lejanos del Metaverso 3D. **Mejores Prácticas DeFi:** Utilizar tipos de datos de alta precisión para coordenadas y cálculos económicos para evitar errores de redondeo que podrían ser explotados. Implementar validación de límites y rangos para todas las operaciones espaciales.
    *   ⏱️ **Hora 3 (Trae - Implementación de Red):** Enrutamiento predictivo y "Co-Seeding" preventivo de assets (Modelos, texturas). El nodo inteligente precarga fragmentos de mapa en segundo plano extrapolando el trayecto del avatar, dotando a la experiencia inmersiva de cero pantallas de carga. **Mejores Prácticas DeFi:** Implementar mecanismos de verificación criptográfica para todos los activos precargados para prevenir la inyección de activos maliciosos. Asegurar que el enrutamiento predictivo no revele información sensible del usuario.
    *   ⏱️ **Hora 4 (VS Code - QA, Refactor y Testing):** Pulido terminal del árbol de ramas en Github, incorporación integral de XML Docs en interfaces C# y formateo general con linting. Cierre absoluto de incidencias residuales para garantizar que el compilador refleje **cero errores y cero advertencias** en la solución Release final. **Mejores Prácticas DeFi:** Mantener un control de versiones riguroso y realizar revisiones de código por pares. Publicar documentación técnica clara y completa, incluyendo especificaciones de seguridad y auditorías. Fomentar la participación de la comunidad en la identificación de vulnerabilidades.

*   **Entregable:** El lanzamiento definitivo (*v1.0.0 Alpha*) del core distribuido WoldVirtual; un ecosistema documentado, seguro y abierto, capacitado para que cualquier usuario instale la semilla tecnológica y propague el juego libremente, promoviendo la adopción y la innovación en el metaverso DeFi.

---

## 📋 **SESIÓN ACTUAL - RAMA: DevTraeIA**

### 🚀 **LO DESARROLLADO HOY (20 de mayo de 2026)**

#### **1. Sistema de Cierre de Sesión Mejorado**
- **Implementación completa** del evento `BtnCerrarSesion_Click` en [MainWindow.xaml.cs](file:///d:/WCVcoinMTB/WoldVirtual/WoldVirtual3Dp2p/Capa3_Visor/MainWindow.xaml.cs)
- **Instrumentación de depuración** con 10 puntos de instrumentación para rastrear la ejecución
- **Manejo robusto de errores** con try-catch-finally completo
- **Timeout controlado** para limpieza de recursos de Godot
- **Terminación forzada** de procesos residuales de Godot

#### **2. Modificación con Dispatcher.BeginInvoke**
- **Solución implementada** en la función `HideDashboardShowWizard()`
- **Retraso de la ocultación** del panel `PanLeftSidebar` hasta que el evento click se complete
- **Prioridad Background** para asegurar que la interfaz no se bloquee

#### **3. Sistema de Logging Avanzado**
- **Archivo de logs específico**: `debug_logout_trace.log`
- **Envío de logs** a servidor de depuración local (puerto 3001)
- **Registro local** para diagnóstico inmediato
- **Múltiples puntos de instrumentación** en todo el flujo de cierre de sesión

#### **4. Análisis Científico del Problema**
- **Creación de documentación** en [debug-visor-logout-failure.md](file:///d:/WCVcoinMTB/debug-visor-logout-failure.md)
- **Hipótesis H6 identificada**: "El botón 'CERRAR SESIÓN' está en un panel que se oculta inmediatamente al hacer clic, interrumpiendo la ejecución del evento"
- **Evidencia recopilada** de logs de tiempo de ejecución

#### **5. Guía de Instrucciones**
- **Creación de** [INSTRUCCIONES_CIERRE_SESION.md](file:///d:/WCVcoinMTB/INSTRUCCIONES_CIERRE_SESION.md)
- **Pasos detallados** para probar el cierre de sesión
- **Recopilación de evidencia** para diagnóstico

### ⚠️ **PROBLEMA PERSISTENTE: BOTÓN "CERRAR SESIÓN"**

#### **Estado Actual**
- **El botón no cierra el visor** a pesar de todas las implementaciones
- **No hay registros** del evento `BtnCerrarSesion_Click` en los logs
- **El código está correctamente implementado** pero el evento no se dispara

#### **Causa Raíz Identificada**
1. **El botón no está siendo clickeado** (posiblemente deshabilitado, cubierto o no interactivo)
2. **Problema con la vinculación del evento** en tiempo de ejecución
3. **El panel `PanLeftSidebar`** tiene `Visibility="Collapsed"` inicialmente y puede no estar visible cuando el usuario intenta hacer clic

#### **Evidencia Clave**
- ✅ **XAML correcto**: `Click="BtnCerrarSesion_Click"`
- ✅ **Código implementado**: Función con instrumentación completa
- ❌ **Logs vacíos**: No hay registros del evento
- 🔍 **Panel oculto**: `PanLeftSidebar.Visibility="Collapsed"` inicial

### 📝 **LO PENDIENTE PARA RESOLVER**

#### **1. Diagnóstico del Problema Real**
- **Verificar si el botón es clickeable** en tiempo de ejecución
- **Comprobar la visibilidad del panel** `PanLeftSidebar` durante el clic
- **Añadir logging adicional** para diagnóstico del estado del botón

#### **2. Soluciones a Implementar**
- **Añadir manejador de eventos alternativo** para verificar la interactividad
- **Verificar el estado `IsEnabled`** del botón en tiempo de ejecución
- **Comprobar si hay elementos superpuestos** que bloqueen el clic
- **Implementar solución definitiva** basada en evidencia de tiempo de ejecución

#### **3. Pruebas Requeridas**
- **Ejecutar el visor** con las modificaciones implementadas
- **Hacer clic en "Cerrar Sesión"** y recopilar logs
- **Analizar evidencia** para confirmar la causa raíz
- **Implementar fix definitivo** y verificar funcionamiento

### 🔧 **POSIBLE SOLUCIÓN Y PRÓXIMOS PASOS RECOMENDADOS**

Para abordar el problema de que el botón "CERRAR SESIÓN" no dispara su evento, se propone el siguiente plan de acción:

1.  **Instrumentación Adicional en `MainWindow.xaml.cs`**:
    *   **Verificar `IsEnabled` del botón**: Añadir un `LogDebug` al inicio de `BtnCerrarSesion_Click` para registrar el valor de `((Button)sender).IsEnabled`. Esto confirmará si el botón está deshabilitado por alguna razón.
    *   **Verificar `Visibility` del `PanLeftSidebar`**: Antes de llamar a `HideDashboardShowWizard()`, añadir un `LogDebug` para registrar el `Visibility` actual de `PanLeftSidebar`.
    *   **Añadir un manejador de eventos `PreviewMouseDown`**: En el XAML, añadir `PreviewMouseDown="BtnCerrarSesion_PreviewMouseDown"` al botón. En el code-behind, implementar este evento para registrar un `LogDebug` y ver si este evento de bajo nivel se dispara. Si se dispara, pero `Click` no, sugiere un problema de enrutamiento de eventos o un elemento superpuesto.

2.  **Revisión de Superposiciones en XAML**:
    *   Examinar el `MainWindow.xaml` para identificar cualquier elemento (como `Grid`, `Border`, `Canvas`) que pueda estar superponiéndose al `PanLeftSidebar` o al botón "CERRAR SESIÓN" y capturando los eventos de clic. Esto puede requerir ajustar `ZIndex` o `Background` de los paneles.

3.  **Pruebas de Ejecución y Recopilación de Logs**:
    *   **Compilar el visor**: `dotnet build "d:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\VisorSingularity.csproj"`
    *   **Ejecutar el visor** y navegar hasta el dashboard.
    *   **Hacer clic en "Cerrar Sesión"**.
    *   **Compartir el contenido actualizado** del archivo `debug_logout_trace.log`.

4.  **Análisis de Evidencia**:
    *   Con los nuevos logs, se podrá determinar si el botón está habilitado, si el panel es visible, y si los eventos de bajo nivel (`PreviewMouseDown`) se están disparando. Esto ayudará a identificar si el problema es de interactividad, visibilidad o enrutamiento de eventos.

5.  **Implementación del Fix Definitivo**:
    *   Basado en el análisis de los logs, se implementará la solución específica (ej. ajustar `ZIndex`, eliminar superposiciones, forzar `IsEnabled`, etc.).

---

## 🐛 **DEBUG Y DIAGNÓSTICO DEL CIERRE DE SESIÓN**

### 📋 **INFORMACIÓN DE LA SESIÓN DE DEBUG**
- **Session ID**: visor-logout-failure
- **Start Time**: 2026-05-20
- **Issue**: Botón de cerrar sesión no funciona en el visor
- **User Report**: "nada no funciona el boton de cerrar sesion nada de lo que hiciste afecto en lo mas minimo al visor"

### 🎯 **DESCRIPCIÓN DEL PROBLEMA**
El usuario reporta que el botón de cerrar sesión en el visor no funciona. A pesar de las modificaciones implementadas anteriormente (mejoras en el manejo de eventos, desuscripción de eventos Exited, mejor logging), el problema persiste completamente.

### 🔍 **HIPÓTESIS (Falsables)**
1. **H1: El botón no está correctamente vinculado al evento click** - El manejador de eventos `BtnCerrarSesion_Click` no se está ejecutando cuando se hace clic en el botón
2. **H2: El proceso Godot no se está terminando correctamente** - Los métodos `Kill()` o `WaitForExit()` no están funcionando como se espera
3. **H3: Hay múltiples instancias de Godot ejecutándose** - Solo se está terminando una instancia pero hay otras en segundo plano
4. **H4: El flag `_ignoreGodotExit` no se está manejando correctamente** - Hay una condición de carrera o el valor no se está propagando correctamente
5. **H5: Problemas de sincronización entre hilos** - El dispatcher de WPF no está manejando correctamente las llamadas entre hilos

### 📊 **PLAN DE RECOPILACIÓN DE EVIDENCIA**
1. **Instrumentar `BtnCerrarSesion_Click`** para verificar si se ejecuta
2. **Instrumentar `CleanupWithTimeout`** para verificar el flujo de limpieza
3. **Instrumentar `ForceKillGodotProcesses`** para verificar la terminación de procesos
4. **Instrumentar el evento `Exited`** para verificar si se dispara
5. **Verificar estado del flag `_ignoreGodotExit`** en diferentes puntos

### 🔧 **PUNTOS DE INSTRUMENTACIÓN**
- [x] Punto 1: Entrada a `BtnCerrarSesion_Click` (logout-1)
- [x] Punto 2: Establecimiento de `_ignoreGodotExit = true` (logout-2, logout-3)
- [x] Punto 3: Llamada a `CleanupWithTimeout` (cleanup-timeout-1 a cleanup-timeout-4)
- [x] Punto 4: Llamada a `ForceKillGodotProcesses` (ya instrumentada)
- [x] Punto 5: Evento `Exited` del proceso Godot (manejado en LaunchGodot)
- [x] Punto 6: Restablecimiento de `_ignoreGodotExit = false` (logout-8)

### 📝 **ANÁLISIS DE LOGS**
**NUEVO DESCUBRIMIENTO CRÍTICO**: He identificado un problema fundamental en la arquitectura del visor.

### 🔍 **Análisis del código:**
1. **El botón "CERRAR SESIÓN" está correctamente vinculado** en el XAML (línea 405):
   ```xml
   <Button Content="✕ CERRAR SESIÓN" Style="{StaticResource MagentaButton}" Height="35" Margin="0,15,0,0" Padding="0" Click="BtnCerrarSesion_Click"/>
   ```

2. **El panel `PanLeftSidebar` está OCULTO por defecto** (línea 365):
   ```xml
   <Border x:Name="PanLeftSidebar" Grid.Column="0" Width="240" Style="{StaticResource GlassPanel}" Margin="15,15,5,15" Visibility="Collapsed">
   ```

3. **El panel se muestra cuando el usuario inicia sesión** (línea 507):
   ```csharp
   PanLeftSidebar.Visibility = Visibility.Visible;
   ```

4. **El panel se oculta cuando se cierra sesión** (línea 751):
   ```csharp
   PanLeftSidebar.Visibility = Visibility.Collapsed;
   ```

### 🎯 **HIPÓTESIS REVISADA:**
**H6: El botón "CERRAR SESIÓN" está en un panel que se oculta inmediatamente al hacer clic, interrumpiendo la ejecución del evento**

**Evidencia**:
- El botón está dentro de `PanLeftSidebar`
- `HideDashboardShowWizard()` se llama en `BtnCerrarSesion_Click`
- `HideDashboardShowWizard()` establece `PanLeftSidebar.Visibility = Visibility.Collapsed`
- **Si el panel se oculta antes de que complete el evento click, la ejecución podría interrumpirse**

### 🚨 **PROBLEMA IDENTIFICADO**:
El flujo actual es:
1. Usuario hace clic en "CERRAR SESIÓN"
2. Se ejecuta `BtnCerrarSesion_Click`
3. Se llama a `HideDashboardShowWizard()`
4. `HideDashboardShowWizard()` oculta `PanLeftSidebar`
5. **El botón (que está dentro del panel) podría dejar de recibir eventos**

### 🔧 **SOLUCIÓN PROPUESTA**:
**Retrasar la ocultación del panel** hasta que el evento click se complete completamente.

**Próximo paso**: Modificar `HideDashboardShowWizard()` para usar `Dispatcher.BeginInvoke` y retrasar la ocultación del panel.

## 🛠️ **IMPLEMENTACIÓN DEL FIX**
*Dependerá de la evidencia recopilada*

**Posibles soluciones basadas en hipótesis:**
- **H1 (botón no vinculado)**: Corregir XAML del botón
- **H2 (proceso no termina)**: Mejorar método Kill() o usar API nativa
- **H3 (múltiples instancias)**: Búsqueda más exhaustiva de procesos
- **H4 (flag mal manejado)**: Mejor sincronización del flag
- **H5 (problemas de hilos)**: Usar Dispatcher.Invoke correctamente

## ✅ **VERIFICACIÓN**
*Después de implementar el fix*

**Pasos de verificación:**
1. Ejecutar visor con fix
2. Probar cierre de sesión
3. Verificar logs post-fix
4. Confirmar que la interfaz vuelve al Wizard

## 🧹 **RESUMEN DE LIMPIEZA**
*Después de confirmar que el fix funciona*

**Acciones de limpieza:**
1. Remover regiones de depuración (`#region debug-point`)
2. Simplificar función `SendDebugLog` (remover logging local extra)
3. Remover archivos de depuración temporales
4. Actualizar documentación si es necesario

---

## 🚦 **ESTADO DE LA SESIÓN: [ABIERTA]**
**Próxima Acción**: Instrumentar puntos de observación para recopilar evidencia de tiempo de ejecución

---

## 🚀 **INSTRUCCIONES PARA DIAGNOSTICAR EL CIERRE DE SESIÓN**

### 📋 **PROBLEMA ACTUAL**
El botón "Cerrar Sesión" en el visor no funciona según el usuario. Las modificaciones anteriores no han tenido efecto.

### 🔧 **CAMBIO IMPLEMENTADO**
He agregado **instrumentación de depuración detallada** en el código para entender exactamente qué está sucediendo cuando se hace clic en "Cerrar Sesión".

### 🚀 **PASOS PARA PROBAR**

#### **1. Compilar el proyecto**
```bash
dotnet build "d:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\VisorSingularity.csproj"
```

#### **2. Ejecutar el visor**
- Ejecuta el visor normalmente desde Visual Studio o el ejecutable
- Inicia sesión como lo haces habitualmente

#### **3. Probar el cierre de sesión**
1. **Haz clic en el botón "Cerrar Sesión"** en la interfaz del visor
2. **Observa cuidadosamente** qué sucede:
   - ¿La interfaz cambia?
   - ¿Aparece algún mensaje de error?
   - ¿El visor se congela o se cierra?
   - ¿Qué dice el texto en la parte inferior (TxtFooterStatus)?

#### **4. Recopilar evidencia**
**Después de hacer clic**, busca estos archivos:

##### **Archivo principal de logs:**
```
[Directorio del ejecutable]\debug_logout_trace.log
```

##### **Archivo de logs local original:**
```
[Directorio del ejecutable]\visor_debug_overlap.log
```

#### **5. Compartir resultados**
Por favor, comparte **TODA** esta información:

1. **¿Qué viste exactamente después de hacer clic?**
   - Ejemplo: "Nada cambió, todo sigue igual"
   - Ejemplo: "Apareció un mensaje de error: 'Error al cerrar sesión: ...'"
   - Ejemplo: "El visor se congeló por 5 segundos y luego volvió a la normalidad"

2. **El contenido COMPLETO de `debug_logout_trace.log`** (si existe)

3. **Cualquier mensaje de error** que aparezca en la interfaz

4. **¿El botón se deshabilitó temporalmente?** (debería deshabilitarse por 1 segundo)

### 🔍 **QUÉ ESTAMOS BUSCANDO**

### **Secuencia esperada de logs:**
```
[HH:mm:ss.fff] 🚀 BtnCerrarSesion_Click INICIADO - Punto de instrumentación 1
[HH:mm:ss.fff] 📌 Parámetros: sender=Button, e=RoutedEventArgs
[HH:mm:ss.fff] 🔄 Estableciendo _ignoreGodotExit = true
[HH:mm:ss.fff] ✅ Set _ignoreGodotExit = true for logout (valor actual: True)
[HH:mm:ss.fff] 🔧 Llamando a CleanupWithTimeout()
[HH:mm:ss.fff] ⏱️ CleanupWithTimeout INICIADO - Punto de instrumentación 11
... más logs de Cleanup y ForceKillGodotProcesses ...
[HH:mm:ss.fff] 🎉 Cierre de sesión completado exitosamente
```

### **Posibles escenarios:**

#### **Escenario A: No se ven logs**
- **Significado**: El botón no está vinculado al evento `BtnCerrarSesion_Click`
- **Solución**: Verificar el XAML del botón

#### **Escenario B: Logs se detienen en algún punto**
- **Significado**: Hay una excepción que no se está manejando
- **Solución**: Revisar el stack trace en los logs

#### **Escenario C: Logs completos pero interfaz no cambia**
- **Significado**: Las funciones `HideDashboardShowWizard()` o `UpdateInterfaceAfterLogout()` no funcionan
- **Solución**: Instrumentar esas funciones específicamente

### ⚠️ **SI NO HAY LOGS**

1. **Verifica la compilación**: Asegúrate de ejecutar la versión más reciente
2. **Busca el archivo**: Revisa el directorio donde está el ejecutable `.exe`
3. **Prueba múltiples veces**: Haz clic en "Cerrar Sesión" 2-3 veces
4. **Revisa permisos**: Asegúrate de que la aplicación puede escribir archivos

### 📞 **INFORMACIÓN CRÍTICA QUE NECESITO**

Por favor, responde con **TODOS** estos detalles:

1. **¿Hiciste clic en el botón?** (Sí/No)
2. **¿Qué sucedió inmediatamente después?**
3. **¿Apareció algún mensaje en la parte inferior de la ventana?**
4. **¿Pudiste encontrar el archivo `debug_logout_trace.log`?**
5. **Si existe el archivo, ¿puedes compartir su contenido COMPLETO?**

### 🎯 **OBJETIVO**
Entender **exactamente** en qué punto falla el cierre de sesión para implementar una solución precisa y efectiva.