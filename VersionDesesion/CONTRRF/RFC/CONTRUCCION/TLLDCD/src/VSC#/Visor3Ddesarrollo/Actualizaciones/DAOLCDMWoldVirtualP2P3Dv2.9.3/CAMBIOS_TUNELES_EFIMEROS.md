# DAOLCDMWoldVirtualP2P3D v2.9.3 — Corrección Túneles Efímeros

## Problema

En v2.8.7 los túneles efímeros SSH **no estaban bien cableados**:

- `LuciaRecepcion.gd` escribía `tunel_solicitud.json` al pulsar "CONECTAR"
- `LucIAValidacionManager.cs` monitoreaba `validacion_conexion.json` → **nunca lo recibía**
- El túnel SSH nunca arrancaba desde Godot
- Godot monitoreaba `validacion_resultado.json` → **siempre vacío**

## Solución v2.9.3 — Lucía como HOST

### Arquitectura correcta

```
[C# Visor arranca]
       ↓
LucIAValidacionManager.Iniciar()
       ↓
P2PTunnelManager.IniciarAsync()   ← Lucía es el HOST del túnel
       ↓
SSH → localhost.run / serveo.net
       ↓
Túnel obtiene URL pública
       ↓
Escribe user://tunel_lucia_url.json
       ↓
[Godot - LuciaRecepcion.gd]
       ↓
Timer _poll_conexion() lee tunel_lucia_url.json
       ↓
Usuario pulsa "CONECTAR"
       ↓
Muestra: "✅ Túnel WebNodo activo: https://abc.lhr.life"
       ↓
Botón cambia a "CONECTADO"
```

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `RedP2P/LucIAValidacionManager.cs` | Arranca el túnel SSH automáticamente al `Iniciar()`. Escribe `tunel_lucia_url.json` |
| `gdscrip/LuciaRecepcion.gd` | Monitorea `tunel_lucia_url.json`. Botón "CONECTAR" lee el resultado ya listo |

### Archivo de comunicación nuevo

**`user://tunel_lucia_url.json`** — escrito por C#, leído por Godot:

```json
{
  "exito": true,
  "url": "https://abc123.lhr.life",
  "mensaje": "Túnel WebNodo activo: https://abc123.lhr.life",
  "timestamp": 1700000000
}
```

### Comportamiento del botón CONECTAR

| Estado | Botón | Mensaje |
|--------|-------|---------|
| Inicial | `CONECTAR` (azul) | "Esperando túnel de LucIA…" |
| Al pulsar (túnel listo) | `CONECTADO` (verde) | "✅ Túnel WebNodo activo: https://..." |
| Al pulsar (túnel no listo) | `REINTENTAR` | "⏳ LucIA está iniciando el túnel…" |
| Túnel caído | `REINTENTAR` | "⚠️ Túnel desconectado" |

## Referencia visual

La UI debe mostrar algo similar a:

```
                           WoldVirtualP2P3D
                     ┌────────────────────────┐
                     │       CONECTADO        │
                     └────────────────────────┘
  ✅ Túnel WebNodo activo: https://abc123.lhr.life
```
