/**
 * Wold Virtual P2P 3D — WebNodo
 * ================================
 * Servidor Express que:
 *  1. Sirve una pagina de descarga publica del .exe mas actualizado.
 *  2. Provee endpoint /descargar para que el usuario descargue el .exe directamente.
 *  3. Muestra estado de la red P2P (si hay sesion activa).
 *
 * Uso:
 *   npm install
 *   npm start
 *   Accede a: http://localhost:3030
 */

const express = require('express');
const path    = require('path');
const fs      = require('fs');

const app  = express();
const PORT = process.env.PORT || 3030;

// Carpeta donde esta el .exe publicado (ruta relativa al server.js)
const DESCARGAS_DIR = path.join(__dirname, 'descargas');

// ─── Middleware ────────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// ─── API: info del exe disponible ─────────────────────────────────────────────
app.get('/api/info', (req, res) => {
    const exeName = obtenerExeMasReciente();
    if (!exeName) {
        return res.json({ disponible: false, mensaje: 'No hay .exe disponible todavia' });
    }

    const exePath = path.join(DESCARGAS_DIR, exeName);
    const stat    = fs.statSync(exePath);
    const sizeMB  = (stat.size / (1024 * 1024)).toFixed(1);

    res.json({
        disponible:   true,
        nombre:       exeName,
        tamano_mb:    sizeMB,
        modificado:   stat.mtime.toISOString(),
        url_descarga: `/descargar/${encodeURIComponent(exeName)}`
    });
});

// ─── Descarga directa del .exe ─────────────────────────────────────────────────
app.get('/descargar', (req, res) => {
    const exeName = obtenerExeMasReciente();
    if (!exeName) return res.status(404).json({ error: 'No hay .exe disponible todavía' });
    res.download(path.join(DESCARGAS_DIR, exeName), exeName);
});

app.get('/descargar/:nombre', (req, res) => {
    const nombre   = decodeURIComponent(req.params.nombre);
    // Sanitizar: solo permite nombre de archivo, sin rutas
    const limpio   = path.basename(nombre);
    const exePath  = path.join(DESCARGAS_DIR, limpio);

    if (!fs.existsSync(exePath)) {
        return res.status(404).json({ error: 'Archivo no encontrado' });
    }

    res.download(exePath, limpio, (err) => {
        if (err && !res.headersSent) {
            res.status(500).json({ error: 'Error al enviar el archivo' });
        }
    });
});

// ─── API: estado P2P (lee p2p_session.json si existe) ─────────────────────────
app.get('/api/p2p-status', (req, res) => {
    const sessionFile = path.join(
        process.env.APPDATA || '',
        'WoldVirtualP2P3D', 'usuario', 'p2p_session.json'
    );
    if (!fs.existsSync(sessionFile)) {
        return res.json({ online: false });
    }
    try {
        const data = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
        res.json({ online: true, tunnel_url: data.myTunnelUrl || '', timestamp: data.timestamp });
    } catch {
        res.json({ online: false });
    }
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

// ─── Iniciar servidor ─────────────────────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`[WebNodo] Wold Virtual P2P 3D`);
    console.log(`[WebNodo] Escuchando en http://localhost:${PORT}`);
    console.log(`[WebNodo] Carpeta de descargas: ${DESCARGAS_DIR}`);
    console.log(`[WebNodo] Coloca el .exe en la carpeta 'descargas/' para que los usuarios puedan descargarlo.`);
});
