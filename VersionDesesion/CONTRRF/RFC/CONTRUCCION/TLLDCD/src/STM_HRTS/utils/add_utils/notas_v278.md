## Wold Virtual P2P 3D {{TAG}}

Release con las novedades de seguridad: subsistema defensivo `STM_DEF` y retirada del vector R-01.b.

| fichero | bytes | SHA-256 |
|---|---|---|
| `{{EXE_NAME}}` (Windows, single-file, motor y mundo embebidos) | {{EXE_SIZE}} | `{{EXE_HASH}}` |
| `{{LINUX_NAME}}` (visor Linux Avalonia, motor y mundo embebidos) | {{LINUX_SIZE}} | `{{LINUX_HASH}}` |

### Novedades de seguridad

- **Escaneo estatico del arbol** (`STM_DEF escanear`) con allowlist `rutas_ignoradas.txt`: 0 hallazgos / LIMPIO.
- **Escaneo del historial de Git** (`STM_DEF historial`): detecta el commit malicioso del dropper EtherHiding.
- **Heuristica de entropia de Shannon** (umbral >= 6.0) para payloads ofuscados.
- **Integridad HMAC** de ficheros sellados y **cuarentena firmada** (nunca borra: conserva evidencia).
- **Arranque fail-closed**: `ArranqueSeguro.cs` invoca `python -m STM_HRTS.STM_DEF arranque` antes de abrir la ventana; fail-open solo si no existe el interprete Python o el arbol de fuentes.
- **Servicio de vigilancia** continuo (hilos daemon) y **firma Ed25519** autocontenida con respaldo puro RFC 8032.
- **Retirada del vector R-01.b**: el `.vscode/settings.json` de la raiz con `task.allowAutomaticTasks` y una tarea `runOn: folderOpen` queda eliminado; la configuracion vive en `STM_HRTS/utils/.vscode`.

Deuda tecnica del desarrollo y fases pendientes (blindaje de red y gobernanza): issue de seguimiento.

### Linux

`{{LINUX_NAME}}` trae el visor completo (Avalonia 11): cuenta local, portal WebNodo, tunel P2P, invitacion, chat de texto, amigos, motor Godot y comprobacion de actualizaciones. El motor `Godot_v4.7.2-stable_linux.x86_64` y `wvp3d.pck` van embebidos en `woldvirtual-linux` y se extraen en el primer arranque. No lleva chat de voz ni webcam (dependen de DirectShow).

SHA-256 (Windows): `{{EXE_HASH}}`
SHA-256 (Linux): `{{LINUX_HASH}}`
