# WoldVirtual P2P 3D

README de plan de desarrollo y coordinacion de ramas.

Fecha de auditoria: 2026-05-23

## Estado auditado del repositorio

Situacion observada directamente en `d:\WCVcoinMTB`:

- Ramas locales activas: `main`, `DevAntigravityIA`, `DevCodexIA`, `DevTraeIA`.
- HEAD actual durante la auditoria: `DevTraeIA`.
- Arbol git limpio al iniciar la revision.
- Diferencias reales entre ramas activas: casi solo datos runtime (`peer_*.json`, `current_user.json`), no cambios estructurales fuertes.
- Base funcional existente:
  - Visor WPF en `Capa3_Visor/CapaVisor3D`
  - Motor Godot en `WoldVirtual`
  - Estado global en `WoldVirtual/Estado_Global`
  - Nodo P2P del visor en `Capa3_Visor/CapaVisor3D/p2pipfsCS`
- Tamano funcional del codebase auditado: 342 archivos entre C#, GDScript, XAML, escenas y JSON.

Conclusion operativa:

- El repositorio esta en fase de prototipo funcional integrado.
- La prioridad ya no es anadir mas features aisladas, sino ordenar contratos, separar runtime de fuente, reducir deuda tecnica y estabilizar el camino hacia una integracion multi-rama limpia.

## Deuda tecnica prioritaria

### DT-01. Artefactos generados versionados

Se observan `bin/`, `obj/`, ejecutables generados y librerias compiladas dentro del repo.

Impacto:

- ensucia diffs
- aumenta el peso del repositorio
- dificulta saber que es fuente y que es build
- favorece ejecuciones contra binarios viejos

### DT-02. Datos runtime versionados

Se observan archivos de estado vivos dentro del repo, por ejemplo:

- `WoldVirtual/Estado_Global/peers/peer_ChicookDirector.json`
- `WoldVirtual/woldvirtual/scene/MTC/users3D/current_user.json`

Impacto:

- genera divergencia artificial entre ramas
- mezcla sesion local con codigo fuente
- complica integraciones y validacion

### DT-03. Orquestacion demasiado concentrada en `MainWindow.xaml.cs`

El visor concentra UI, login, bridge HTTP, embebido Godot, listeners UDP, arranque P2P y parte del control de sesion.

Impacto:

- baja mantenibilidad
- alto riesgo de regresiones
- dificil de testear por modulo

### DT-04. Sync legacy y sync actual coexistiendo

Conviven piezas como `NetworkLayer.gd`, `IslandStateSync.gd` y logica C# de estado sin un contrato unico y estable.

Impacto:

- doble fuente de verdad
- mas complejidad de integracion
- deuda funcional en la sincronizacion multipeer

### DT-05. P2P del visor incompleto como red real

Existe distribucion por ZIP, HTTP local, tuneles e integracion con IPFS, pero no existe todavia una capa P2P completa del metaverso para estado, presencia y consistencia entre nodos.

Impacto:

- el reparto del visor existe
- el reparto del estado del mundo aun no esta cerrado

### DT-06. Ausencia de pipeline de calidad

No hay solucion `.sln`, no hay CI visible, no hay suite de tests automatizada y no hay control fuerte sobre formato/encoding.

Impacto:

- poca trazabilidad
- menor confianza en cambios cruzados entre ramas
- mas coste al integrar

## Objetivo del siguiente ciclo

Pasar de "prototipo local funcional" a "base integrable y mantenible" en cuatro frentes:

1. estabilizar el repositorio
2. aislar responsabilidades tecnicas
3. consolidar el transporte y la sincronizacion
4. preparar una integracion posterior sobre `main` sin deuda acumulada

## Politica de trabajo entre ramas

Este plan asume estas reglas:

- No hacer merge directo entre ramas de trabajo.
- Cada rama entrega piezas acotadas y verificables.
- `main` actua como rama de integracion, no como rama de experimentacion.
- Los archivos runtime no deben volver a ser el factor principal de divergencia entre ramas.
- La documentacion de plan debe mantenerse identica en todas las ramas activas.

## Plan de implementacion distribuido por ramas

### `main`

Rol:

- base de integracion
- referencia estable de build
- control de calidad del proyecto

Entregables:

1. definir la linea base de compilacion valida del visor
2. fijar la politica de que solo entra codigo integrable y sin basura de runtime
3. centralizar changelog tecnico del ciclo
4. validar que las ramas de trabajo entregan piezas compatibles

Pendientes:

- introducir `.gitignore` coherente para artefactos generados
- separar datos de sesion local del codigo fuente
- crear solucion `.sln` para el visor
- preparar estructura minima para CI y smoke build

Criterio de cierre:

- `main` debe poder compilar de forma repetible
- `main` no debe arrastrar `peer_*.json` o `current_user.json` como diferencia estructural

### `DevCodexIA`

Rol:

- saneamiento del repositorio
- consolidacion de estructura
- reduccion de deuda tecnica transversal

Entregables:

1. limpieza de artefactos versionados (`bin`, `obj`, ejecutables de salida, residuos de build)
2. normalizacion de estructura y nombres
3. separacion clara entre fuente, runtime, assets y resultados compilados
4. unificacion de encoding a UTF-8 sin corrupciones visibles
5. inventario de codigo legacy o duplicado

Pendientes concretos:

- mover datos runtime a rutas no versionadas o plantillas base
- revisar coexistencia de `IslandStateSync.gd` y `NetworkLayer.gd`
- revisar carpetas y binarios que no deben vivir en control de versiones
- documentar mapa real del repo despues de la limpieza

Dependencias:

- ninguna fuerte para empezar
- su salida desbloquea trabajo mas seguro para el resto

Criterio de cierre:

- repo mas pequeno y legible
- menos ruido en diffs
- estructura apta para automatizacion posterior

### `DevAntigravityIA`

Rol:

- arquitectura
- contratos tecnicos
- seguridad y modelo de evolucion del sistema

Entregables:

1. definir contrato unico de identidad del nodo
2. especificar handshake entre visor, nodo y capa de estado
3. definir modelo de confianza y validacion entre peers
4. bajar a diseno la evolucion desde JSON local a sincronizacion distribuida
5. fijar criterios de consistencia, bootstrap y recuperacion

Pendientes concretos:

- contrato de identidad de nodo y persistencia
- contrato de handshake P2P
- modelo de consistencia del estado global
- estrategia de aislamiento entre UI, transporte y sincronizacion
- criterios de seguridad para `P2PWebNode.cs` e IPFS auxiliar

Dependencias:

- necesita la limpieza basica de `DevCodexIA` para trabajar con menos ruido
- su salida define interfaces para `DevTraeIA`

Criterio de cierre:

- decisiones de arquitectura cerradas y accionables
- contratos suficientemente concretos para implementacion

### `DevTraeIA`

Rol:

- transporte
- servicios de red
- endurecimiento del nodo del visor
- preparacion del camino hacia sincronizacion real

Entregables:

1. extraer listeners y transporte de `MainWindow.xaml.cs` a servicios dedicados
2. formalizar heartbeat, reconexion y manejo de peers
3. endurecer `P2PWebNode.cs` para uso mas estable
4. preparar discovery local y pool de conexiones
5. reducir acoplamiento entre UI WPF y red del visor

Pendientes concretos:

- encapsular UDP actual en una capa reutilizable
- extraer logica de inicio/parada del nodo P2P a servicios
- instrumentar timeouts, reintentos y estados de conexion
- definir capa de eventos para que la UI consuma estado sin conocer la red en detalle
- preparar compatibilidad futura con cache, chunks o discovery real

Dependencias:

- consume contratos definidos por `DevAntigravityIA`
- se beneficia de la limpieza estructural de `DevCodexIA`

Criterio de cierre:

- transporte desacoplado del visor
- nodo P2P mas predecible
- menos logica de red dentro de la UI principal

## Secuencia recomendada

### Fase 1. Higiene y estabilizacion

Responsables:

- `DevCodexIA`
- `main`

Objetivo:

- limpiar repo
- separar runtime
- fijar baseline de compilacion

### Fase 2. Contratos y arquitectura

Responsable principal:

- `DevAntigravityIA`

Objetivo:

- cerrar definiciones de identidad, handshake, estado y seguridad

### Fase 3. Implementacion del transporte

Responsable principal:

- `DevTraeIA`

Objetivo:

- convertir la red actual en modulos mantenibles y reutilizables

### Fase 4. Integracion sobre `main`

Responsable:

- `main` como rama receptora

Objetivo:

- integrar por lotes pequenos, verificables y sin merge masivo entre ramas de trabajo

## Riesgos a vigilar

- seguir versionando datos de sesion y artefactos compilados
- continuar ampliando `MainWindow.xaml.cs` en vez de dividir responsabilidades
- introducir nueva funcionalidad de red sin contrato previo
- intentar integrar ramas por volumen en vez de por entregables pequenos
- seguir usando JSON locales como sustituto indefinido de una capa de sincronizacion real

## Definition of done del ciclo

El ciclo se considera bien encaminado cuando se cumpla todo esto:

- README alineado en todas las ramas activas
- repo saneado de artefactos generados y runtime innecesario
- contratos tecnicos base cerrados
- transporte desacoplado del visor principal
- `main` listo para recibir integraciones pequenas sin merge cruzado entre ramas de trabajo

## Estado de sincronizacion de este README

Este README debe mantenerse identico en:

- `main`
- `DevCodexIA`
- `DevAntigravityIA`
- `DevTraeIA`

La sincronizacion entre ramas debe hacerse sin merge, mediante aplicacion explicita del mismo cambio documental.
