# DevCodexIA

Estado actual del proyecto y plan de desarrollo para la rama `DevCodexIA`.

## Estado actual

- Rama activa: `DevCodexIA`.
- Proyecto principal: `WoldVirtual P2P 3D`.
- Estado del repositorio: hay artefactos de compilación generados en `Capa3_Visor/ServidorVirtualCS/bin` y `obj` tras la verificación de build.
- Verificación realizada:
  - `dotnet build D:\WCVcoinMTB\Capa3_Visor\ServidorVirtualCS\ServidorVirtualCS.csproj -c Debug`
  - Resultado: compilación correcta, `0 errores` y `0 advertencias`.

## Qué hay hoy

- Un visor WPF en .NET 8 funcionando como núcleo de orquestación.
- Integración con Godot, estado JSON local, UDP local, webcam, voz, IPFS/Kubo y túneles públicos.
- Documentación de trabajo previa en `PLANDEVCODEX.md`.
- No existía un `README.md` dedicado dentro de `IAs/DevCodexIA` antes de esta actualización.

## Lectura rápida del estado técnico

El proyecto está en un punto de prototipo funcional local. La base compila y el flujo principal está vivo, pero todavía mezcla fuente, binarios, caches, estado local y artefactos de build dentro del repositorio. Eso hace que el mantenimiento sea más difícil de lo necesario y que los cambios reales se mezclen con ruido.

Los riesgos principales siguen siendo:

- higiene del repositorio;
- contrato de estado P2P;
- validación de identidad y wallet;
- separación de responsabilidades en WPF y en el nodo P2P;
- ausencia de pruebas automáticas mínimas.

## Objetivo de desarrollo

Consolidar el prototipo para que pase de una integración funcional, pero pesada, a una base mantenible y verificable.

## Plan de desarrollo

### Fase 0: higiene del repositorio

- Crear y aplicar reglas de exclusión para `bin`, `obj`, caches y estado local que no deba versionarse.
- Definir qué binarios se mantienen por necesidad funcional y cuáles deben salir del control de versiones.
- Evitar que una build normal ensucie el árbol de trabajo.

### Fase 1: contrato de estado P2P

- Definir un esquema versionado para los `peer_*.json`.
- Validar el contenido antes de escribirlo a disco.
- Sanear identificadores para evitar rutas inseguras o nombres inválidos.

### Fase 2: identidad y wallet

- Verificar criptográficamente la firma recibida.
- Separar el modo demo del modo real.
- Mover secretos y datos sensibles fuera de rutas del proyecto.

### Fase 3: refactor del visor WPF

- Reducir la carga de `MainWindow.xaml.cs`.
- Extraer servicios para launcher, chat, voz, webcam y sesión.
- Mantener la ventana principal como coordinadora de UI.

### Fase 4: refactor del nodo P2P/IPFS

- Separar servidor local, túneles, publicación ZIP y proxy IPFS.
- Añadir validación de descargas externas.
- Hacer opt-in explícito para exposición pública.

### Fase 5: pruebas y verificación

- Crear pruebas unitarias para validación de estado y saneamiento.
- Automatizar un script de verificación local.
- Dejar una ruta clara para CI cuando se necesite.

### Fase 6: beta LAN

- Priorizar la experiencia LAN antes que la exposición pública.
- Mejorar mensajes de error y telemetría local.
- Documentar instalación offline y recuperación de identidad.

## Prioridades

1. Higiene del repositorio.
2. Contrato de estado P2P.
3. Seguridad de identidad y wallet.
4. Refactor de WPF y del nodo P2P.
5. Pruebas automáticas.
6. Beta LAN estable.

## Referencia

El documento histórico y más detallado sigue estando en [`PLANDEVCODEX.md`](./PLANDEVCODEX.md).

