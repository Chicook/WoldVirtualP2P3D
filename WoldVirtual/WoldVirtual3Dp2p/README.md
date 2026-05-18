# WoldVirtual P2P 3D — Plan Ejecutivo (Prototipo)

> **🎯 Meta:** Crear un metaverso cripto 3D descentralizado de código abierto, optimizando recursos mediante el reciclaje inteligente de código de la versión `v001`.

---

## 🔍 Análisis de Referencia (v001)
Tras analizar el directorio `C:\Users\Usuario\Desktop\WoldVirtualv001\docs` y sus archivos principales, se extrae la siguiente arquitectura base para reciclar:

1. **Arquitectura de 3 Capas:**
   - **Capa 1 (Estado Global):** Persistencia C# y gestión P2P (JSON).
   - **Capa 2 (Godot):** Motor 3D, lógica de mundo y shaders (Océano).
   - **Capa 3 (Visor3D):** Host WinForms que embebe Godot.
2. **Estado Estable:** Teletransporte funcional, carga de islas/avatares y comunicación IPC (Godot <-> C#).
3. **P2P:** Descentralizado por archivos locales (Peer JSON).

---

## 🚀 Plan de Ejecución Directo (Sin Desvíos)

El objetivo es llegar a un prototipo funcional lo antes posible, reciclando el 100% de lo que funciona.

### Fase 1: Cimentación y Reciclaje (Días 1-3)
* **Objetivo:** Levantar la estructura base del nuevo repositorio.
* **Acciones:**
  - Crear estructura de carpetas: `/Capa1_Estado`, `/Capa2_Godot`, `/Capa3_Visor`.
  - Copiar y limpiar el código de `v001` (manteniendo el Zero-Config ya logrado).
  - Validar que el Visor C# levanta la escena de Godot básica.

### Fase 2: Integración Cripto y P2P (Días 4-6)
* **Objetivo:** Asegurar la identidad y la red.
* **Acciones:**
  - Integrar el flujo de registro (MetaMask/Wallet) en el Visor WinForms (Capa 3).
  - Activar el sincronizador P2P (`IslandStateSync.gd`) en Godot (Capa 2) para que lea los estados de red compartidos.
  - Asegurar la comunicación IPC mediante JSON entre el visor y el motor.

### Fase 3: Validación del Prototipo (Día 7)
* **Objetivo:** Probar el entorno compartido.
* **Acciones:**
  - Simular dos nodos (usuarios) en la red compartiendo la misma carpeta de estado o vía P2P.
  - Verificar que el teletransporte y la presencia funcionan.

---
> [!IMPORTANT]
> **Regla de Oro:** No añadir nuevas características (como lucIA o renderizado premium) hasta que la Fase 3 esté completada y validada.
