# WebNodo — Wold Virtual P2P 3D

Servidor web Express que publica el `.exe` del visor para que cualquier usuario
pueda descargarlo **mientras el anfitrion esta en linea**, sin necesitar GitHub.

## Inicio rapido

```bash
cd webnodo
npm install
npm start
```

Abre el navegador en: http://localhost:3030

## Estructura

```
webnodo/
  server.js          Servidor Express
  package.json       Dependencias
  public/
    index.html       Pagina de descarga publica (UI premium)
  descargas/         <-- Coloca aqui el .exe que quieres publicar
```

## Publicar el .exe

1. Compila el visor: `dotnet publish -c Release`
2. Copia el `Visor3D.exe` generado a la carpeta `descargas/`
3. Arranca el servidor: `npm start`
4. Comparte el enlace de tu IP local: `http://TU_IP:3030`

## Endpoints API

| Endpoint           | Descripcion                                    |
|--------------------|------------------------------------------------|
| `GET /`            | Pagina de descarga HTML                        |
| `GET /api/info`    | Info del .exe disponible (JSON)                |
| `GET /descargar/:nombre` | Descarga directa del .exe             |
| `GET /api/p2p-status`    | Estado de la sesion P2P del anfitrion   |

## Seguridad

- Los nombres de archivo se sanean con `path.basename()` para prevenir path traversal.
- Solo sirve archivos `.exe` de la carpeta `descargas/`.
- Pensado para uso en red local / LAN mientras el anfitrion tiene sesion activa.
