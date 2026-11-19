# ⚠️ Informe de Deuda Técnica Generada — v2.9.4 (DAO & Túneles Efímeros)

## Resumen Ejecutivo

Durante el ciclo de desarrollo de las versiones **v2.9.3 y v2.9.4**, se priorizó la estabilización inmediata de los túneles efímeros SSH, la comunicación entre el visor C# y el motor Godot, y la reconexión automática de la sede DAO (`IslaUnicaLucIA.gd`). Si bien estas soluciones restauraron la conectividad y la experiencia de usuario, introdujeron compromisos arquitectónicos y deuda técnica que deben ser subsanados en versiones futuras.

---

## 1. IPC Basado en Sistema de Archivos (`user://*.json`)

### Descripción:
La comunicación entre el host C# (`LucIAValidacionManager.cs`, `P2PTunnelManager.cs`) y los scripts de Godot (`IslaUnicaLucIA.gd`, `LuciaRecepcion.gd`, `TeleportPanel.gd`) se realiza mediante lectura y escritura de archivos JSON en el directorio de usuario:
* `user://tunel_solicitud.json`
* `user://tunel_lucia_url.json`
* `user://tunel_dao_url.json`
* `user://validacion_resultado.json`

### Riesgos y Deuda:
* **Polling Periódico Ineficiente:** Godot utiliza Timers de polling (ej. cada 0.5s en `_poll_dao`) consumiendo ciclos de CPU y generando I/O continuo sobre disco.
* **Race Conditions en Windows:** A pesar de utilizar el patrón `.tmp` → `rename_absolute`, Windows en ocasiones bloquea archivos durante lectura/escritura concurrente (`EPERM` o `SharingViolation`), requiriendo reintentos o silenciamiento de errores.
* **Falta de Validación de Esquema:** No existe validación de tipos fuerte (JSON Schema / Protobuf). Si un campo cambia de nombre o tipo, la falla se propaga silenciosamente dejando la UI en espera indefinida.

---

## 2. Dependencia de Timeouts Fijos en GDScript

### Descripción:
Tanto en `Sonda.gd` como en `IslaUnicaLucIA.gd`, las esperas de respuesta del túnel o del servicio modular emplean bucles de tiempo fijos con timeouts duros:
* Timeout de 8.000 ms esperando `validacion_resultado.json`
* Timeout de 20.000 ms en `Sonda.gd` para peticiones modulares

### Riesgos y Deuda:
* En conexiones lentas o bajo alta carga de CPU, las peticiones pueden expirar artificialmente aunque el túnel SSH termine estableciéndose unos milisegundos después.
* Ausencia de un mecanismo de "backoff exponencial" o cancelación cooperativa con cancellation tokens.

---

## 3. Fragmentación y Duplicidad de Versiones de Código

### Descripción:
Existen múltiples copias y ramas de scripts distribuidas a lo largo del árbol del proyecto:
* `Actualizaciones/DAOLCDMWoldVirtualP2P3Dv2.9.3`
* `Actualizaciones/DAOLCDMWoldVirtualP2P3Dv2.9.4`
* `CONTRRF/RFC/CONTRUCCION/TLLDCD/src/MTBGT/WoldVirtualP2P3D/gdscrip/`
* Carpetas auxiliares en `.dev/`

### Riesgos y Deuda:
* Riesgo de deriva de código (code drift): un desarrollador puede corregir un bug en `src/MTBGT/` sin sincronizarlo a la carpeta de `Actualizaciones/`, o viceversa.
* Dificultad para mantener una única fuente de verdad (Single Source of Truth).

---

## 4. Estado de Conexión DAO Acoplado al Teletransporte

### Descripción:
En `TeleportPanel.gd`, la invalidación del estado DAO se dispara observando el cambio de índice de isla (`_current_island == INDICE_DAO` vs `anterior == INDICE_DAO`).

### Riesgos y Deuda:
* Si el jugador se desconecta, se cae el proceso o se teletransporta por un método alternativo (ej. comandos de consola o respawn forzado por caída al mar), el hook de salida puede no dispararse, dejando `tunel_dao_url.json` en un estado inconsistente.
* Debería existir una máquina de estados finita (FSM) formal para el ciclo de vida de la conexión DAO desacoplada del panel de teletransporte.

---

## 5. Limpieza y Persistencia de Artefactos Temporales

### Descripción:
Archivos como `tunel_solicitud.json`, `tunel_dao_url.json` y flags transitorios permanecen en `user://` indefinidamente tras cerrar la aplicación.

### Riesgos y Deuda:
* Al volver a arrancar el juego en una sesión posterior, Godot puede leer datos obsoletos de túneles caídos de la sesión anterior antes de que el host C# inicialice.

---

## Plan de Remediación Propuesto (v3.0)

1. **Migración a IPC Basado en Sockets / Named Pipes:**
   * Sustituir el intercambio de archivos JSON en disco por un servidor de Named Pipes local (`\\.\pipe\WoldVirtualIPC`) o WebSocket local loopback (`127.0.0.1:puerto`).
2. **Máquina de Estados de Red Unificada:**
   * Centralizar los estados (`Desconectado`, `Conectando`, `TúnelActivo`, `Error`, `Reconectando`) en un Singleton de red con eventos/señales reactivas.
3. **Pipeline Automatizado de Empaquetado:**
   * Generar las carpetas de release mediante scripts automatizados desde una única carpeta canónica de fuentes, eliminando copias manuales.
