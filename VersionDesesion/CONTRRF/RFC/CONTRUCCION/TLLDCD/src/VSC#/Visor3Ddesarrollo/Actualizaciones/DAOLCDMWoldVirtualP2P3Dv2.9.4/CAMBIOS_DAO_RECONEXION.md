# DAOLCDMWoldVirtualP2P3D v2.9.4 — Reconexión Automática DAO

## Problema resuelto

En v2.9.3 el túnel DAO **funcionaba al entrar por primera vez**, pero al **volver a la isla DAO** después de salir:

- `tunel_dao_url.json` no existía → `LuciaRecepcion._poll_dao()` nunca disparaba
- El botón "🏛 DAO" seguía mostrando el estado desconectado
- La reconexión automática (`_auto_conectar_dao`) sí llamaba a `conectar_dao_al_metaverso()` pero el resultado nunca se persistía en disco

## Causa raíz

`IslaUnicaLucIA._realizar_conexion_dao()` obtenía correctamente el `tunel_url` de `tunel_lucia_url.json` (escrito por C#) pero **nunca escribía `tunel_dao_url.json`** — el fichero que `LuciaRecepcion._poll_dao()` necesita para actualizar la UI y el estado de la DAO.

## Solución v2.9.4

### Arquitectura del flujo DAO

```
[Usuario entra a isla DAO]
       ↓
TeleportPanel._refresh_location() detecta INDICE_DAO
       ↓
_auto_conectar_dao() → IslaUnicaLucIA.conectar_dao_al_metaverso()
       ↓
_realizar_conexion_dao():
  1. Lee tunel_lucia_url.json  ← URL del túnel ya activo (Lucía como HOST)
  2. Conecta ServicioConexionModular (sesión modular P2P)
  3. ✅ NUEVO: Escribe user://tunel_dao_url.json
       ↓
LuciaRecepcion._poll_dao() (cada 0.5 s)
  → detecta tunel_dao_url.json
  → muestra "✅ DAO activa: https://..."
  → botón "🏛 DAO CONECTADA"

[Usuario sale de la DAO]
       ↓
TeleportPanel._refresh_location() detecta salida de INDICE_DAO
       ↓
✅ NUEVO: _invalidar_tunel_dao()
  → resetea _dao_conectada = false en IslaUnicaLucIA
  → escribe tunel_dao_url.json con exito=false
       ↓
[Usuario vuelve a la DAO]
       ↓
_auto_conectar_dao() lanza reconexión fresca → escribe JSON nuevo → UI ✅
```

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `lucia3D/IslaUnicaLucIA/IslaUnicaLucIA.gd` | Al finalizar `_realizar_conexion_dao()`, escribe `user://tunel_dao_url.json` con esquema `{exito, url, enlace, mensaje, dao_modular, timestamp}`. Escritura atómica: `.tmp` → rename. |
| `gdscrip/TeleportPanel.gd` | Al salir de la isla DAO (`anterior == INDICE_DAO` → otra isla), llama a `_invalidar_tunel_dao()`. Nueva función que resetea el flag en la isla y escribe `tunel_dao_url.json` con `exito=false` para forzar reconexión limpia al volver. |

### Esquema de `user://tunel_dao_url.json`

```json
{
  "exito": true,
  "url": "https://abc123.lhr.life",
  "enlace": "https://abc123.lhr.life",
  "mensaje": "DAO activa: https://abc123.lhr.life",
  "dao_modular": true,
  "timestamp": "2026-11-18T06:10:00"
}
```

### Comportamiento esperado

| Acción | Resultado |
|--------|-----------|
| Entrar a DAO por 1ª vez | Auto-reconexión → JSON escrito → UI: ✅ DAO activa |
| Pulsar "Conectar DAO" manualmente | Mismo flujo → JSON escrito → UI actualizada |
| Salir de la DAO a otra isla | JSON invalidado (`exito=false`), flag reseteado |
| **Volver a la DAO** | Auto-reconexión → JSON nuevo → UI: ✅ DAO activa |
| Acercarse al Terminal DAO 3D | `body_entered` → `conectar_dao_al_metaverso()` → JSON escrito |

## Compatibilidad

- ✅ No rompe v2.9.3: misma arquitectura de ficheros IPC
- ✅ No modifica C#: el C# sigue escribiendo solo `tunel_lucia_url.json`
- ✅ El GDScript lee `tunel_lucia_url.json` como fallback si `validacion_resultado.json` no llega
- ✅ `LuciaRecepcion._poll_dao()` sin cambios: ya estaba preparado para leer el nuevo JSON

## Instrucciones de actualización

1. Reemplazar `gdscrip/TeleportPanel.gd` en el proyecto Godot.
2. Reemplazar `lucia3D/IslaUnicaLucIA/IslaUnicaLucIA.gd` en el proyecto Godot.
3. No es necesario recompilar C# ni modificar el WebNodo.
4. Al ejecutar: entrar a la isla DAO y verificar en los logs de Godot:
   ```
   [IslaUnicaLucIA] tunel_dao_url.json escrito (exito=true, url=https://...)
   ```
