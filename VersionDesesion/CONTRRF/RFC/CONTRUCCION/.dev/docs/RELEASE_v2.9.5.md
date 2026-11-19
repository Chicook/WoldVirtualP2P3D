# Wold Virtual P2P 3D v2.9.5 — DAOLCDMWoldVirtualP2P3Dv2.9.5.exe

Ejecutable oficial autocontenido del Visor 3D y DAO descentralizada para WoldVirtualP2P3D.

---

## 🚀 Novedades y Desarrollos en v2.9.5

### 1. Reconexión Automática DAO y Túnel Efímero
* **Sincronización de Túnel Bidireccional:** Resuelto el problema de desconexión del túnel efímero al retornar a la Isla DAO (`(0, 0, 0)`). La DAO ahora detecta la llegada del usuario y restablece el túnel de manera idéntica al resto de islas del metaverso.
* **Persistencia Atómica (`user://tunel_dao_url.json`):** Publicación inmediata del estado y enlace para consumo por la interfaz de recepción y el visor 3D.
* **Gestión de Ciclo de Vida Espacial:** Al desplazarse a otras islas, el túnel se libera ordenadamente; al regresar, la conexión se reactiva automáticamente y copia la URL efímera al portapapeles.
* **Terminal 3D Interactivo:** Acceso directo a la asamblea y registro ciudadano desde la plaza central de la Isla Única LucIA.

---

## 📉 Optimización y Ahorro Masivo de Tamaño

| Versión | Ejecutable Principal | Reducción de Tamaño |
|:---|:---:|:---:|
| **v2.8.3** | `LCDMWoldVirtualP2P3Dv2.8.3.exe` (1,41 GB) | — (Línea base) |
| **v2.9.5** | `DAOLCDMWoldVirtualP2P3Dv2.9.5.exe` (**481 MB**) | **≈ 930 MB ahorrados (-66%)** |

* **Eliminación de redundancias:** Se purgó el empaquetado doble de archivos comprimidos dentro del ejecutable.
* **Túneles SSH ligeros:** Sustitución de daemons de túnel pesados por clientes SSH nativos contra endpoints efímeros (`localhost.run` / `serveo.net`).
* **Optimización de runtime:** Mayor contención y reducción de assets de depuración.

---

## 🏛️ Gobernanza y DeFi 3D
Consulte en el repositorio `ARTICULO_DAO_DEFI_METAVERSO.md` para conocer los detalles de la Asamblea 3D, votación de propuestas, tesorería comunitaria y el rol de LucIA como oráculo autónomo.
