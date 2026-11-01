# OpenCode en STM_HRTS (WoldVirtualP2P3D)

Instalación limpia, local y autónoma de **OpenCode** (v1.19.5) desde cero.

---

## 🚀 Formas de Ejecución

Puedes ejecutar OpenCode de cualquiera de las siguientes formas:

1. **Doble clic (Consola interactiva):**
   - Ejecuta [`ejecutar_opencode.bat`](file:///E:/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/STM_HRTS/opencode/ejecutar_opencode.bat).
   - Abre la ventana con codificación UTF-8 e inicia OpenCode directamente.

2. **Desde la línea de comandos / terminal (en esta carpeta):**
   ```powershell
   cd E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\STM_HRTS\opencode
   .\opencode.exe
   ```
   o también:
   ```cmd
   opencode.bat
   ```

3. **Globalmente desde cualquier consola:**
   ```powershell
   opencode
   ```

---

## 🛠️ Errores detectados y soluciones aplicadas

1. **Falta de `npm` y runtime Node.js incompleto:**
   - Previamente sólo existía `node.exe` en `C:\Program Files\nodejs` sin `npm` ni `npx`.
   - Se reinstaló de forma limpia **Node.js LTS (v26.13.0)** con **npm (v11.20.0)**.

2. **Error de directiva de ejecución en PowerShell (`UnauthorizedAccess`):**
   - PowerShell bloqueaba los scripts `.ps1` al tener directiva `Restricted`.
   - Se configuró `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` para permitir la ejecución legítima de scripts de herramientas locales y npm.

3. **Versiones desfasadas de dependencias y plugins de OpenCode:**
   - La configuración en `~/.config/opencode` tenía dependencias obsoletas (`@opencode-ai/plugin 1.18.29` contra el motor 1.19.x) y carpetas temporales corruptas en npm.
   - Se actualizaron a la versión unificada **1.19.5** con compatibilidad OpenAI / Ollama (`@ai-sdk/openai-compatible 3.0.82`).

4. **Entorno local en `STM_HRTS/opencode`:**
   - Se generó `package.json` y `package-lock.json` limpios.
   - Se instalaron las dependencias locales y se copió el binario ejecutable `opencode.exe` (1.19.5) en la raíz de esta carpeta para máxima autonomía.

---

## 🔐 Permisos de edición configurados (2026-10-31)

Todo el bloque vive en [`opencode.jsonc`](file:///E:/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/STM_HRTS/opencode/opencode.jsonc), a nivel de proyecto, y sobreescribe lo que haya en `~/.config/opencode`.

| permiso | valor | efecto |
| --- | --- | --- |
| `edit` | `allow` con `deny` para `*.env`, `.env.*`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `node_modules/*`, `*.exe` | escribe y parchea código **sin pedir aprobación** |
| `read`, `glob`, `grep`, `list`, `lsp`, `skill`, `task`, `todowrite`, `question` | `allow` | explorar el proyecto sin preguntas |
| `bash` | `ask` con lista blanca de lectura/build (`git status`, `ls`, `cat`, `node`, `npm`, `npx`…) | comandos normales sí, el resto pregunta |
| `bash` (deny explícito) | `rm -rf`, `rm -r`, `del`, `erase`, `rd /s`, `git push`, `git reset --hard`, `git clean`, `shutdown`, `format`, `npm publish`, `npm uninstall` | bloqueados aunque se apruebe otra cosa |
| `webfetch`, `websearch` | `ask` | salida a red siempre preguntada |
| `external_directory` | `ask` (sin cambiar del default) | tocar algo fuera del directorio pide permiso |

Reglas de opencode: gana **la última que casa**, por eso los `deny` van detrás de los `allow`.

**Cómo comprobarlas sin lanzar el TUI:**

```powershell
.\opencode.exe debug agent build    # ruleset efectivo (101 reglas al 2026-10-31)
```

### Pruebas ejecutadas (evidencia real)

| prueba | resultado |
| --- | --- |
| `opencode run "Crea PRUEBA_PERMISO.txt…"` | fichero creado, `← Write PRUEBA_PERMISO.txt / Wrote file successfully`, **sin pedir aprobación** |
| escribir `tokens.env` | ✗ bloqueado, opencode devuelve las reglas activas (`edit *.env deny`) |
| bash `del prueba_e2e.log` | ✗ bloqueado (`bash "del *" deny`); el fichero siguió existiendo |
| captura con un proxy temporal en el puerto 11435 (ya retirado) | opencode envía **10 tools** con `tool_choice: "auto"` y un system de **20.050 caracteres** |

---

## 🧩 Lo que impedía editar (no eran los permisos)

1. **Modelos que no existen.** El config global fijaba `ollama/cogito:3b` y `ollama/qwen3:1.7b` en los agentes `build`/`general`/`plan`, y ninguno está descargado en el Ollama de este PC. Se sobrescribieron con el bloque `agent` del config de proyecto.
2. **Contexto de Ollama demasiado pequeño (el bloqueador real).** Opencode manda ~6k tokens de system + schemas de tools, pero Ollama truncaba a `num_ctx` por defecto: se procesaban **2050 tokens** de 5850. Sin las tools en la ventana, el modelo *narraba* el comando en texto (`{"name":"write",…}`) en vez de llamarlo, y decía «no tengo acceso al sistema de archivos».

Mediciones del 2026-10-31 con el mismo payload (system de 20k + 10 tools):

| vía | contexto | tokens de prompt procesados | ¿`tool_calls`? |
| --- | --- | --- | --- |
| `/v1/chat/completions` | default del servidor | 2050 | no |
| `/v1/chat/completions` | `num_ctx: 32768` en el body | 2050 | no (**Ollama lo ignora**) |
| `/api/chat` nativo | `options.num_ctx: 4096` | 2050 | no |
| `/api/chat` nativo | `options.num_ctx: 32768` | 5850 | **sí** (`["write"]`) |
| `/v1/chat/completions` | alias `wvp-opencode` (num_ctx en el modelo) | 5647 | **sí** (`["write"]`) |

Como `/v1` ignora `num_ctx` del body y opencode habla por `/v1`, la solución pasa por subir el contexto **en el modelo**:

```powershell
# Modelfile (esta carpeta): FROM qwen3.5:latest + PARAMETER num_ctx 32768
ollama create wvp-opencode -f Modelfile
node comprobar_ollama.mjs wvp-opencode   # debe decir EDITABLE
```

El alias reutiliza las capas ya descargadas (no duplica los 6,6 GB) y no requiere reiniciar Ollama ni cambiar variables de entorno del sistema.

---

## 🧠 Modelos locales: estado verificado el 2026-10-31

| modelo | instalado | tool calling |
| --- | --- | --- |
| `wvp-opencode` (alias 32k de qwen3.5) | sí | **funciona** → es el modelo por defecto de opencode |
| `qwen3.5:latest` (9,7B) | sí | funciona **sólo con contexto ≥ 32k**; con el default no ve las tools |
| `qwen2.5:7b` | sí | emite `tool_calls` en `/api/chat` con `num_ctx 16384` |
| `qwen2.5-coder:7b` / `:latest` | sí | **no**: su plantilla no produce `tool_calls` (devuelve el JSON como texto incluso con prompt corto) |
| `starcoder2:7b` | sí | sin probar (`/api/tags` lo declara sólo `completion,insert`) |
| `cogito:3b`, `qwen3:1.7b`, `qwen2.5-coder:3b`, `llama3.1`, `gemma2:2b`, `llama3.2:1b`, `qwen2-math:1.5b` | **no** | aparecen en el config pero no están descargados |

LM Studio (`http://localhost:1234/v1`) estaba apagado durante la configuración: su bloque de `provider` no se ha probado.

---

## ⏭️ Pendientes y límites honestos

- La **lista blanca de `bash`** está cargada y evaluada (aparece en los errores de denegación), pero no se ha verificado de forma end-to-end que un comando `allow` se ejecute en modo no interactivo.
- `external_directory` se deja en `ask`: no se ha comprobado cómo clasifica opencode una ruta `../…` dentro del repo pero fuera de esta carpeta.
- Con `opencode --auto` se saltan también los `ask` de bash; no es el modo por defecto de esta carpeta.
- Los ficheros de esta carpeta viven bajo `TLLDCD/src`, que el flujo RFPRMN vacía al actualizar: el `Modelfile`, `comprobar_ollama.mjs` y este README son reproducibles pero conviene revisarlos tras cada actualización.

