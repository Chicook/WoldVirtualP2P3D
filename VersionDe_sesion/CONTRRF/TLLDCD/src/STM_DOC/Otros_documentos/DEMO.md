# Demo local · LucIA anfitriona y la cuenta por bloque

Implementación local de la [discusión #86](https://github.com/Chicook/WoldVirtualP2P3D/discussions/86):
**una cuenta = un bloque = un archivo**. LucIA recibe al jugador en su oficina, la
cadena mina un bloque por alta y el hash de ese bloque **es la cuenta**. No hay
contraseña, ni frase semilla, ni validación de conexión por túnel.

Verificado de punta a punta con `e2e_demo.ps1`: recepción → alta → `.zip` →
carrusel → registro → portal → isla → avatar propio en la cadena.

---

## 1. Arrancar

```powershell
cd E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src
.\demo_local.ps1 -Reset
```

Eso hace tres cosas: deja el demo como primera vez (archiva, no borra), arranca el
servidor de cuentas en `127.0.0.1:8545` con su **propio ledger**, y abre el mundo
en Godot como servidor local (sin red externa).

Sin `-Reset`, respeta la cuenta que ya exista en el PC.

### Guion (3 minutos)

| Paso | Qué se ve |
|---|---|
| 1 | LucIA en su oficina: «Es tu primera vez: yo te acompaño a crear tu cuenta» |
| 2 | Nick de 10 a 15 letras → **Crear mi cuenta** |
| 3 | La cadena mina el bloque: se muestra el hash y se descarga `cuenta_<hash16>.zip` |
| 4 | **Entrar al mundo** → carrusel (24 avatares en 3 turnos) |
| 5 | Registro: el nick ya viene fijado. **Validación 2 de 2**: el botón sigue bloqueado hasta que el avatar se aparta un 12 % del base |
| 6 | Portal → **tu isla** («Isla 0 preparada: 10920 vértices») |
| 7 | Cierras y vuelves: la cuenta se reconoce y se entra directo |

Son **dos validaciones iniciales**, en este orden:

1. **En la oficina de LucIA**: se mina el bloque y nace el hash (la cuenta).
2. **En el registro**: el avatar propio valida el nick. Sin diferencia
   suficiente, el registro no se cierra.

---

## 2. El avatar propio (diseño de LucIA anfitriona)

El avatar se puede personalizar con los 5 tintes y los 18 campos de
`Personalizacion.gd` (cuerpo, rostro y expresiones). El registro mide **cuánto se
aparta del avatar de fábrica** y lo muestra en vivo:

```
Validación 2 de 2 · avatar base · 4% (mínimo 12%)
Sube proporciones del cuerpo o cambia un color para validar tu nick.

Validación 2 de 2 · AVATAR PROPIO · 13% (mínimo 12%) · nick validado
```

Mientras no llegue al umbral, **el botón de confirmar está deshabilitado**: es una
validación, no un adorno.

- La medida vive en [`AvatarFirma.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/AvatarFirma.gd):
  33 dimensiones normalizadas (5 colores × 3 canales + 18 campos), diferencia
  media absoluta en 0..1 y **umbral 0.12**.
- Si supera el umbral, al confirmar el registro se mina un bloque
  **`AVATAR_ORIGINAL`** ligado al hash de cuenta y a la huella comprometida, y la
  misma operación alimenta las **50 neuronas** de LucIA
  (`ACTUALIZACION_SINAPTICA`): el aspecto es el dato de entrenamiento.
- Además se guardan **3 variantes** deterministas en
  `user://avatares_variantes.json`, con su aspecto completo ya resuelto, su firma
  y su diferencia. Son las que alimentan el carrusel: se suman a las 24 plazas
  del catálogo (**27 plazas**) y se presentan como «AVH1 · variante 1».
- Para verlas: al volver a entrar, LucIA ofrece **«Elegir otro avatar»**. Elegir
  una variante guarda su aspecto en el registro y la marca como variante; el
  registro llega ya con la validación 2 superada (≈15 %).
- Si el avatar no llega al umbral, el registro queda bloqueado con el motivo en
  pantalla y no se escribe ningún bloque: el nick no se valida.

> El umbral está duplicado a propósito en los dos lados
> (`AvatarFirma.UMBRAL_ORIGINALIDAD` y `CelebroBlockchain.UMBRAL_ORIGINALIDAD_AVATAR`):
> el cliente avisa y el servidor decide. Si cambias uno, cambia el otro.

---

## 3. Qué hay por dentro

```
Godot 4.7.2 · MTBGT/WoldVirtualP2P3D
  LuciaRecepcion.gd ──POST /alta-cuenta──────────▶ STM_BKCH (Python)
        │              GET  /descargar-cuenta-zip        BKSVCB (cadena)
        │              POST /avatar-original             50 neuronas
        ▼
  user://cuenta.json + cuenta_<hash>.zip
        │
        ▼
  Boot.gd → carrusel → registro → portal → ISLA3Dblock (servidor local)
```

### Ficheros del jugador (`%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\`)

| Fichero | Para qué |
|---|---|
| `cuenta.json` | hash único, nick y fecha. **Es la cuenta** |
| `cuenta_<hash16>.zip` | copia del hash (`cuenta.json` + `metadata.txt`) |
| `registro.cfg` | avatar elegido, personalización, firma y diferencia |
| `avatar_hash.json` | resumen del registro (`avatar_firma`, `avatar_delta`, `avatar_original`) |
| `avatares_variantes.json` | 3 variantes del avatar propio para el carrusel |

### Servidor

| Pieza | Ruta |
|---|---|
| Lanzador del demo | `STM_BKCH/demo_servidor.py` |
| HTTP | `STM_BKCH/bksvcb_net.py` (`/alta-cuenta`, `/descargar-cuenta-zip`, `/avatar-original`, `/status`) |
| Cadena | `STM_BKCH/BKSVCB.py` |
| Ledger del demo | `src/_demo/ledger.json` (nunca el del sistema) |

---

## 4. Comandos

```powershell
# Demo completa (servidor + mundo)
.\demo_local.ps1                 # con la cuenta que ya exista
.\demo_local.ps1 -Reset          # como primera vez
.\demo_local.ps1 -Editor         # abre el PROYECTO en el editor de Godot
.\demo_local.ps1 -SoloServidor   # solo el servidor, en primer plano
.\demo_local.ps1 -SinServidor    # solo el mundo (servidor ya arrancado)

# Prueba automática del flujo completo, sin ventana
.\e2e_demo.ps1

# Contrato del servidor (16 pruebas)
python -m pytest tests/test_bkch_cuentas.py -q

# Firma y variantes del avatar (13 comprobaciones, Godot headless)
& $godot --headless --path MTBGT\WoldVirtualP2P3D --script res://tools/test_avatar_firma.gd

# Las variantes en el carrusel (6 comprobaciones; requiere el flujo anterior)
& $godot --headless --path MTBGT\WoldVirtualP2P3D --script res://tools/e2e_variantes.gd
```

`e2e_demo.ps1` ya ejecuta esa segunda puerta después del flujo principal y antes
de devolver la cuenta del jugador a su sitio.

`demo_local.ps1` busca solo Python (con numpy) y Godot 4.7.2; si no los encuentra,
se le pasan con `-Python` y `-Godot`.

### Jugar o editar

- **Jugar**: `.\demo_local.ps1` (o `-Reset` la primera vez). Abre el juego.
- **Editar**: `.\demo_local.ps1 -Editor`. Abre el **proyecto** en el editor de
  Godot. El `.exe` que se incluye también es editor: si se ejecuta a mano y sin
  argumentos abre el *Project Manager*, y hay que importar el proyecto a mano.

Con `-Editor` el servidor de cuentas queda levantado mientras el editor esté
abierto, así que **F5** dentro del editor ejecuta el mismo flujo de cuenta que el
demo.

---

## 5. Entorno de esta máquina (importante)

En esta máquina el proceso de Godot **solo puede escribir dentro de
`E:\WoldVirtualP2P3D`** (restricción del entorno de ejecución del asistente, no
del proyecto). Como Godot guarda la cuenta en `%APPDATA%`, esa carpeta se ha
redirigido al workspace con una unión de directorios:

```
C:\Users\User\AppData\Roaming\Godot\app_userdata\WoldVirtualP2P3D
    ──▶ E:\WoldVirtualP2P3D\_tmp_tests\userdata_wvp
```

Sin esa unión, el alta mina el bloque pero no puede guardar `cuenta.json` (la
recepción lo detecta y avisa en pantalla). En un escritorio normal no hace falta:
Godot escribe en `%APPDATA%` sin más.

Para deshacerla:

```powershell
cmd /c rmdir "C:\Users\User\AppData\Roaming\Godot\app_userdata\WoldVirtualP2P3D"
Move-Item "E:\WoldVirtualP2P3D\_tmp_tests\userdata_wvp" "C:\Users\User\AppData\Roaming\Godot\app_userdata\WoldVirtualP2P3D"
```

---

## 6. Qué NO hace (a propósito)

- **No hay contraseña ni frase semilla**: si se pierde el `.zip` y `cuenta.json`,
  la cuenta se pierde. Así está diseñado y así se dice en pantalla.
- **No hay migración** de cuentas antiguas en el demo (el servidor conserva el
  endpoint, el cliente no lo usa).
- **No hay validación por túnel SSH**: se entra con la cuenta del PC.
- **No exporta PCK ni publica**: el demo corre desde fuente.
- **No genera mallas nuevas**: las variantes del avatar reutilizan el mismo GLB
  con otro aspecto. El generador de avatares originales es el siguiente paso.
- **No hay IPFS real**: el shim local devuelve `ok=False` a propósito.

---

## 7. Ficheros que forman el demo

| Fichero | Estado |
|---|---|
| `demo_local.ps1` | nuevo |
| `e2e_demo.ps1` | nuevo |
| `STM_BKCH/demo_servidor.py` | nuevo |
| `STM_BKCH/BKSVCB.py` | + `registrar_avatar_original`, `_bloque_por_hash` |
| `STM_BKCH/bksvcb_net.py` | + `POST /avatar-original` |
| `MTBGT/WoldVirtualP2P3D/gdscrip/LuciaRecepcion.gd` | reescrito (sin semilla ni túnel) |
| `MTBGT/WoldVirtualP2P3D/gdscrip/Boot.gd` | nick único, timeout de isla, avatar a la cadena |
| `MTBGT/WoldVirtualP2P3D/gdscrip/AvatarFirma.gd` | nuevo |
| `MTBGT/WoldVirtualP2P3D/.../registro.gd` | nick fijado + originalidad |
| `MTBGT/WoldVirtualP2P3D/tools/e2e_demo.gd` | nuevo |
| `MTBGT/WoldVirtualP2P3D/tools/e2e_variantes.gd` | nuevo |
| `MTBGT/WoldVirtualP2P3D/tools/test_avatar_firma.gd` | nuevo |
| `MTBGT/WoldVirtualP2P3D/gdscrip/SLAV.gd` | plazas extra con las variantes |
| `tests/test_bkch_cuentas.py` | nuevo |
| `MTBGT/_archivo_20261110/` | copias antiguas apartadas |
