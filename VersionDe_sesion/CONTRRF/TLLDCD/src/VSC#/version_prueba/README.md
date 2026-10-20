# Wold Virtual P2P 3D — Version 0.2.0 (version_prueba)

Version limpia sin usuarios de prueba. Lista para probar el flujo completo.

## Flujo completo

```
Inicio
  └─ [Sin cuenta] → "Crear Cuenta"
        ├─ Paso 1: Registrar PC     (RegistroWindow)   → guarda hardware_id.zip
        ├─ Paso 2: Crear usuario    (FormularioUsuario) → user_profile.json
        ├─ Paso 3: Wallet DeFi     (SemillaWallet)     → semilla_wallet.zip (12 palabras)
        ├─ Paso 4: Verificar seed  (VerificarSemilla)  → confirma 3 palabras al azar
        └─ Paso 5: La Llave        (DescargaLlave)     → llave_acceso.json

  └─ [Con cuenta] → "Acceder"
        ├─ Introducir usuario + contrasena
        ├─ Seleccionar llave_acceso.json
        └─ Entra al mundo 3D Godot + Red P2P
              └─ Banner con enlace P2P propio (boton Copiar → portapapeles)
              └─ Campo para pegar enlace de amigo y conectarse
```

## Datos del usuario

Todos los datos se guardan en:
```
%APPDATA%\WoldVirtualP2P3D\usuario\
  ├─ hardware_id.json
  ├─ user_profile.json
  ├─ credentials.json
  ├─ semilla_wallet.json
  ├─ llave_acceso.json
  └─ p2p_session.json
```

> **Sin datos en la carpeta del .exe** — Limpio para distribucion.

## Compilar y ejecutar

```powershell
cd version_prueba
dotnet build -c Release
dotnet run -c Release
```

O con el bat:
```
Lanzar.bat
```

## WebNodo (publicar .exe)

```powershell
cd ..\webnodo
npm install
# Copia el Visor3D.exe compilado a webnodo\descargas\
npm start
# Accede a http://localhost:3030
```

## Movimiento del avatar (Godot)

| Tecla         | Accion              |
|--------------|---------------------|
| W            | Avanzar             |
| S            | Retroceder          |
| A            | Izquierda           |
| D            | Derecha             |
| Espacio      | Saltar              |
| Boton derecho + raton | Girar camara |

## Notas de la version

- Datos de usuario en AppData (no en la carpeta del exe)
- Sin ningun usuario de prueba precargado
- Hash de llave rotado en cada inicio de sesion
- Boton "Copiar enlace P2P" con manejo de error
- GodotConfig apunta al path correcto: CONTRRF/TLLDCD/src/MTBGT/WoldVirtualP2P3D
