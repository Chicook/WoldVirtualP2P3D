# 🚀 Reglas de Antigravity — Entorno Disco E:

Este archivo define las directivas y configuraciones del entorno para el asistente Antigravity en este espacio de trabajo.

---

## 1. Configuración de Rutas y Disco E:
- **Espacio de Trabajo / Repositorio Principal:** `E:\WoldVirtualP2P3D`
- **Área de Trabajo General:** `E:\areadetrabajo`
- **.NET SDK & Runtimes:** `E:\Program Files\dotnet\dotnet.exe`
  - Variable de entorno `DOTNET_ROOT`: `E:\Program Files\dotnet`
  - Siempre utilizar o priorizar el runtime instalado en el disco `E:` para compilaciones (`dotnet build`, `dotnet publish`, `dotnet run`).
- **Antigravity IDE:** `E:\areadetrabajo\antygrabity`
- **Python / Entornos Virtuales:** Ubicados prioritariamente en el disco `E:` (e.g. `E:\areadetrabajo\AreaDeTrabajo\...`).

---

## 2. Git y Flujo de Commits
- **Repositorio Local:** `E:\WoldVirtualP2P3D`
- **Rama de Desarrollo Activa:** `DevAntigravity`
- **Remoto Oficial:** `origin` (`https://github.com/Chicook/WoldVirtualP2P3D.git`)
- **Git Safe Directory:** `E:/WoldVirtualP2P3D` y `E:/*` configurados globalmente.
- **Autor de Commits:** `Juan Angel Lopez Diaz <102910494+Chicook@users.noreply.github.com>`
- **Credenciales:** Autenticado vía Windows Credential Manager (`credential.helper = manager`).
- **Políticas de Commits:**
  - Solo commitear archivos fuente de código (C#, Python, GDScript, HTML/JS, Markdown).
  - Nunca commitear ejecutables (`*.exe`), librerías (`*.dll`) ni paquetes comprimidos (`*.zip`).
  - Respetar siempre el archivo `.gitignore` raíz.

---

## 3. Motor 3D (Godot) y Visor C#
- **Proyecto Godot:** Ubicado en la versión activa: `VersionDe_sesion/Sistema_Principal/PRY/<version_actual>/src/MTBGT/WoldVirtualP2P3D`.
- **Proyecto Visor C#:** Ubicado en `VersionDe_sesion/Sistema_Principal/PRY/<version_actual>/src/VSC#`.
- **Empaquetado Standalone:**
  - El visor standalone incrusta `godot_exe.zip` (motor) y `wvp3d.pck` (mundo exportado), generados localmente.
  - La extracción del runtime en ejecución se realiza en `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<version_actual>\`.
  - La publicación se genera mediante `dotnet publish -c Release -r win-x64 --self-contained true`.

---

## 4. Actualizaciones: el flujo de Godot es obligatorio
- **Leer `REGLAS_DE_ACTUALIZACION.md` (raíz del repo) antes de cualquier cambio que acabe en un binario publicado** — mundo Godot, motor, PCK, C#, portal WebNodo o metadatos de release.
- Sus reglas mandan sobre las secciones anteriores cuando haya conflicto puntual, porque están citadas a fichero y línea.
- Ninguna actualización se considera terminada sin el checklist de §7 de ese documento.
