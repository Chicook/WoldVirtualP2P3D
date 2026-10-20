/**
 * Wold Virtual P2P 3D — WebNodo
 * ================================
 * Servidor Express que:
 *  1. Sirve una pagina de descarga publica del .exe mas actualizado.
 *  2. Provee endpoint /descargar para que el usuario descargue el .exe directamente.
 *  3. Muestra estado de la red P2P (si hay sesion activa).
 *  4. Endpoint /health para diagnostico de conectividad.
 *
 * Uso:
 *   npm install
 *   npm start
 *   Accede a: http://localhost:3030
 *
 * SOLUCION DE PROBLEMAS:
 *   Si el servidor no arranca, ejecuta primero: npm install
 *   Si el puerto 3030 esta ocupado, cambia la variable PORT abajo.
 */

// ── Comprobacion de dependencias ───────────────────────────────────────────────
let express;
try {
    express = require('express');
} catch (e) {
    console.error('');
    console.error('╔══════════════════════════════════════════════════════╗');
    console.error('║  ERROR: Dependencias no instaladas.                  ║');
    console.error('║  Ejecuta el siguiente comando en esta carpeta:       ║');
    console.error('║                                                      ║');
    console.error('║     npm install                                      ║');
    console.error('║                                                      ║');
    console.error('║  Luego vuelve a ejecutar: npm start                  ║');
    console.error('╚══════════════════════════════════════════════════════╝');
    console.error('');
    process.exit(1);
}

const path = require('path');
const fs   = require('fs');
const http = require('http');

const app  = express();
const PORT = process.env.PORT || 3030;

// WebNodo apunta al release publicado en GitHub (no guarda exes en descargas/).
const GITHUB_EXE_URL = 'https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v0.0.111_actualizacion_2069d33a/DMWoldVirtualp2pCNX_v0.0.011actualizacion_2069d33a.exe';

// Carpeta donde esta el .exe publicado (ruta relativa al server.js)
const DESCARGAS_DIR = path.join(__dirname, 'descargas');

// Auto-crear la carpeta descargas/ si no existe
if (!fs.existsSync(DESCARGAS_DIR)) {
    fs.mkdirSync(DESCARGAS_DIR, { recursive: true });
    console.log('[WebNodo] Carpeta "descargas/" creada automaticamente.');
}

// ─── Middleware ────────────────────────────────────────────────────────────────
// CORS: permite que cualquier origen acceda al nodo (necesario para P2P)
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') return res.sendStatus(200);
    next();
});

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// ─── Health check (para diagnostico de conectividad) ─────────────────────────
app.get('/health', (req, res) => {
    res.json({
        ok:        true,
        servicio:  'WoldVirtualP2P3D-WebNodo',
        version:   '0.0.011',
        timestamp: new Date().toISOString(),
        puerto:    PORT
    });
});

// ─── API: info del exe disponible ─────────────────────────────────────────────
app.get('/api/info', (req, res) => {
    res.json({
        disponible:   true,
        nombre:       'DMWoldVirtualp2pCNX_v0.0.011actualizacion_2069d33a.exe',
        tamano_mb:    '675.5',
        url_descarga: GITHUB_EXE_URL
    });
});

// ─── Descarga directa del .exe ─────────────────────────────────────────────────
app.get('/descargar', (req, res) => {
    res.redirect(GITHUB_EXE_URL);
});

app.get('/descargar/:nombre', (req, res) => {
    res.redirect(GITHUB_EXE_URL);
});

// ─── API: estado P2P (lee p2p_session.json si existe) ─────────────────────────
app.get('/api/p2p-status', (req, res) => {
    const sessionFile = path.join(
        process.env.APPDATA || '',
        'WoldVirtualP2P3D', 'usuario', 'p2p_session.json'
    );

    // Tambien buscar en la ruta alternativa que escribe el visor C#
    const sessionFileAlt = path.join(
        process.env.LOCALAPPDATA || '',
        'WoldVirtualP2P3D', 'runtime'
    );

    if (!fs.existsSync(sessionFile)) {
        return res.json({ online: false, mensaje: 'Sin sesion P2P activa' });
    }
    try {
        const data = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
        res.json({
            online:      true,
            tunnel_url:  data.myTunnelUrl || data.peerUrl || '',
            timestamp:   data.timestamp
        });
    } catch {
        res.json({ online: false, error: 'No se pudo leer p2p_session.json' });
    }
});

// ─── Ruta raiz: redirigir al index.html ───────────────────────────────────────
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ─── Helper: encontrar el .exe mas reciente en descargas/ ─────────────────────
function obtenerExeMasReciente() {
    if (!fs.existsSync(DESCARGAS_DIR)) return null;
    const archivos = fs.readdirSync(DESCARGAS_DIR)
        .filter(f => f.toLowerCase().endsWith('.exe'))
        .map(f => ({ nombre: f, mtime: fs.statSync(path.join(DESCARGAS_DIR, f)).mtime }))
        .sort((a, b) => b.mtime - a.mtime);
    return archivos.length > 0 ? archivos[0].nombre : null;
}

// ─── Manejo de errores globales ────────────────────────────────────────────────
app.use((err, req, res, next) => {
    console.error('[WebNodo] Error:', err.message);
    res.status(500).json({ error: 'Error interno del servidor' });
});

// ─── Iniciar servidor ─────────────────────────────────────────────────────────
const server = http.createServer(app);

server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
        console.error(`[WebNodo] ERROR: El puerto ${PORT} ya esta en uso.`);
        console.error(`[WebNodo] Cierra otro proceso que use ese puerto, o cambia PORT en server.js`);
    } else {
        console.error('[WebNodo] Error de red:', err.message);
    }
    process.exit(1);
});

server.listen(PORT, '0.0.0.0', () => {
    const exeInfo = obtenerExeMasReciente();
    console.log('');
    console.log('╔══════════════════════════════════════════════════════════╗');
    console.log('║         Wold Virtual P2P 3D — WebNodo Online             ║');
    console.log('╠══════════════════════════════════════════════════════════╣');
    console.log(`║  URL local:    http://localhost:${PORT}                    ║`);
    console.log(`║  Diagnostico:  http://localhost:${PORT}/health             ║`);
    console.log(`║  .exe activo:  ${exeInfo ? exeInfo : '(ninguno — coloca .exe en descargas/)'}  ║`);
    console.log('╚══════════════════════════════════════════════════════════╝');
    console.log('');
});

