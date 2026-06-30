# WoldVirtual P2P 3D

Plan de desarrollo y estado de la rama `DevCodexIA`.

Fecha de revision: 2026-06-28

## Estado actual de la rama

Estado observado en el repositorio:

- Rama actual: `DevCodexIA`
- Rama remota de seguimiento: `origin/DevCodexIA`
- Arbol limpio al momento de la revision
- El proyecto combina:
  - visor WPF en `Capa3_Visor/CapaVisor3D`
  - motor Godot en `WoldVirtual`
  - estado global en `WoldVirtual/Estado_Global`
  - logica P2P y publicacion IPFS en `Capa3_Visor/CapaVisor3D/p2pipfsCS`
- Hay bastante artefacto generado versionado (`bin/`, `obj/`, ejecutables y salidas de publish)
- Tambien hay datos de sesion y estado runtime dentro del repositorio, lo que dificulta comparar ramas

Lectura rapida:

- La base funcional existe
- La estructura necesita higiene
- La red y la sincronizacion necesitan contratos mas claros
- La UI principal concentra demasiadas responsabilidades

## Objetivo de esta rama

Convertir la rama en una base mas limpia, mantenible y preparada para integracion, sin romper la funcion actual del visor ni del mundo Godot.

La meta no es agregar features aisladas, sino reducir deuda tecnica para que el siguiente desarrollo sea mas predecible.

## Principios de trabajo

1. Mantener separacion entre fuente, runtime y artefactos compilados.
2. Evitar que archivos generados se conviertan en diferencias permanentes entre ramas.
3. Reducir el acoplamiento entre UI, red, persistencia y logica de mundo.
4. Hacer cambios pequenos y verificables.
5. Documentar cada paso importante para facilitar la coordinacion entre ramas.

## Plan de desarrollo

### Fase 1. Higiene del repositorio

Objetivo:

- eliminar ruido de compilacion y salida generada del control de versiones
- identificar datos runtime que no deberian versionarse
- preparar una base estable para trabajar sobre codigo fuente real

Acciones:

- revisar y consolidar `.gitignore`
- separar `bin/`, `obj/`, `publish/` y otros artefactos generados
- mover o aislar archivos de estado local como `current_user.json` y `peer_*.json`
- verificar que los binarios del visor no se usan como fuente de verdad

Resultado esperado:

- diffs mas limpios
- menor peso del repositorio
- menos divergencias artificiales entre ramas

### Fase 2. Orden de arquitectura

Objetivo:

- aclarar responsabilidades entre UI, transporte, estado global y mundo 3D

Acciones:

- revisar `MainWindow.xaml.cs` y extraer logica que no sea estrictamente de interfaz
- separar arranque, conexiones, eventos y persistencia en servicios dedicados
- revisar coexistencia de `NetworkLayer.gd` e `IslandStateSync.gd`
- definir una unica fuente de verdad para estado compartido

Resultado esperado:

- codigo mas legible
- menos riesgo de regresiones
- mejor capacidad de test y mantenimiento

### Fase 3. Contratos tecnicos

Objetivo:

- definir interfaces claras entre visor, nodo y sincronizacion

Acciones:

- documentar identidad del nodo
- definir handshake minimo entre componentes
- acordar el formato de eventos de red
- fijar criterios de consistencia y recuperacion

Resultado esperado:

- integraciones mas seguras
- menos improvisacion al conectar nuevas piezas
- base tecnica util para futuras ramas

### Fase 4. Transporte y estabilidad

Objetivo:

- hacer que la capa de red sea mas robusta y reutilizable

Acciones:

- encapsular listeners y reintentos
- formalizar heartbeat, reconexion y estados de conexion
- reducir dependencia de la UI respecto a detalles del transporte
- preparar la capa P2P para crecer sin rehacerla

Resultado esperado:

- nodo mas predecible
- mejor manejo de desconexiones
- menos logica de red en la ventana principal

### Fase 5. Preparacion para integracion

Objetivo:

- dejar la rama lista para recibir cambios futuros sin acumular deuda nueva

Acciones:

- validar que los cambios importantes estan documentados
- revisar compatibilidad con `main`
- dejar trazabilidad de decisiones y pendientes

Resultado esperado:

- rama util como base de integracion
- menor costo de merge o rebase posterior

## Prioridades concretas

Orden recomendado de ejecucion:

1. limpieza de artefactos generados
2. separacion de runtime y fuente
3. extraccion de responsabilidades desde `MainWindow.xaml.cs`
4. unificacion de contratos de red y estado
5. endurecimiento del transporte P2P
6. documentacion de la nueva estructura

## Riesgos a vigilar

- seguir versionando salidas de compilacion
- mezclar datos de sesion con codigo fuente
- ampliar la UI principal en vez de dividirla
- mantener dos rutas de sincronizacion sin contrato comun
- introducir cambios de red sin criterios de recuperacion o reconexion

## Definition of Done

Esta rama se considera mejorada cuando:

- el repositorio tiene menos ruido de build
- los datos runtime estan fuera del flujo normal de versionado
- `MainWindow.xaml.cs` no concentra toda la orquestacion
- existe una base clara para la sincronizacion de estado
- la documentacion del proyecto explica el estado real de la rama

## Siguiente paso sugerido

La siguiente accion mas rentable es limpiar primero los artefactos generados y los datos runtime versionados, porque eso mejora inmediatamente la lectura de la rama y reduce el riesgo de arrastrar basura a futuras integraciones.

