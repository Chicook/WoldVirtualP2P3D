# WCVcoin — Hoja de ruta

> **Estado:** planificado. Este documento no contiene código, contratos ni instrucciones de despliegue.
> **Ámbito:** `src/WCVcoin` (token) y billetera embebida del visor en `src/VSC#`.
> **Fecha:** 2026-10-26.
> **Regla de lectura:** las cifras de coste son órdenes de magnitud, no cotizaciones. Dependen de la cadena, del alcance, del país y del proveedor. No constituyen asesoría financiera ni legal.

---

## 1. Decisión de producto

WCVcoin será la unidad económica del metaverso Wold Virtual P2P 3D. La intención declarada es:

- **Suministro fijo:** 30.000.000 WCV.
- **Decimales:** 3.
- **Adquisición:** solo con criptomonedas envueltas (*wrapped*) dentro de DeFi.
- **Exclusiones:** nunca de forma directa con stablecoins ni con fiat.

### 1.1 Precisión técnica del suministro

Con 3 decimales, la unidad mínima representable es **0,001 WCV**, no 0,000. El suministro fijo expresado en unidades mínimas es **30.000.000.000**. Un saldo de 0,000 no existe salvo como redondeo de visualización.

> **Decisión pendiente:** confirmar si se quieren 3 decimales (mínimo 0,001) o 4 decimales (mínimo 0,0001). El resto del documento asume 3 decimales.

### 1.2 Estado actual del proyecto

- `src/WCVcoin` está vacío: no hay token, contratos, pruebas ni direcciones desplegadas.
- La billetera embebida existe solo de forma **parcial**: genera una frase BIP-39 de 12 palabras, permite verificarla y descargarla en un ZIP. **No** deriva claves, **no** firma transacciones, **no** consulta la cadena y **no** conoce WCVcoin.
- El archivo local `semilla_wallet.json` guarda las 12 palabras en texto plano. Es una deuda de seguridad crítica que debe resolverse antes de manejar fondos reales.

---

## 2. ¿Cuesta dinero crear la criptomoneda?

**Respuesta corta:** el contrato del token puede desplegarse por muy poco o por nada en una red de prueba; el coste real de lanzar una criptomoneda seria está en la auditoría, la seguridad legal, la liquidez y el mantenimiento, no en “crear” el token.

| Concepto | ¿Cuesta dinero? | Orden de magnitud | Nota |
|---|---|---|---|
| Despliegue en testnet | No | 0 | La red de prueba entrega fondos de prueba; no tienen valor real. |
| Despliegue en una L2 de Ethereum | Sí, gas | Céntimos a decenas de dólares | Depende de la congestión y del tamaño del contrato. |
| Despliegue en Ethereum L1 | Sí, gas | Decenas a miles de dólares | El gas varía mucho; un contrato con restricciones y venta cuesta más que un token simple. |
| Auditoría de seguridad | Muy recomendable | 5.000–100.000+ USD | El rango depende del alcance, del auditor y de si hay venta, bóveda o puente. |
| Asesoría legal y constitución | Sí | 3.000–50.000+ USD | Varía por país; puede ser mucho mayor si hay valores negociables o licencias. |
| Liquidez inicial | Sí, y es capital | 10.000–1.000.000+ USD | No es una comisión: es capital depositado en los pares y expuesto a pérdida. |
| Billetera e integración | Sí | Desarrollo interno o 10.000–100.000+ USD | Depende de si se usan librerías estándar o se construye desde cero. |
| Infraestructura | Sí, recurrente | 100–2.000 USD/mes | RPC, indexador, monitorización, copias y soporte. |
| Listado en un DEX | Gas de creación del par | Bajo en L2; variable en L1 | No hay una comisión obligatoria de listado; la liquidez sí es necesaria. |
| Listado en un CEX | Potencialmente alto | Variable | No es necesario para el objetivo DeFi y puede contradecir la política de acceso. |
| Marketing y comunidad | Opcional | Variable | No crea demanda por sí solo. |

### 2.1 Lectura correcta del coste

- **Crear el contrato** es la parte barata. Un token estándar con suministro fijo puede desplegarse en una L2 por menos que una cena.
- **Crear un mercado** es la parte cara. Sin liquidez en activos envueltos, el token no se puede comprar ni vender de forma mínimamente estable.
- **Crear confianza** es la parte más cara. Auditoría, transparencia, gestión de claves, soporte y cumplimiento legal cuestan más que el despliegue.
- **El suministro fijo no crea valor.** 30 millones de unidades no valen nada por sí mismas; el valor depende de la utilidad, la demanda, la liquidez y la confianza.

### 2.2 Escenarios orientativos

| Escenario | Qué incluye | Orden de magnitud |
|---|---|---|
| Prueba de concepto | Testnet, token simple, billetera de prueba, sin liquidez real | 0–5.000 USD (tiempo propio aparte) |
| Piloto controlado | L2, auditoría básica, legal inicial, liquidez pequeña, billetera funcional | 25.000–100.000 USD |
| Lanzamiento público | Auditoría completa, legal, liquidez profunda, soporte, monitorización | 100.000–500.000+ USD |

> Estas cifras no incluyen el coste de oportunidad del equipo ni posibles requisitos regulatorios extraordinarios. Tampoco garantizan que el proyecto capte demanda.

---

## 3. Decisiones fijadas y decisiones pendientes

### 3.1 Fijadas por el momento

| Decisión | Valor |
|---|---|
| Nombre | WCVcoin |
| Suministro total | 30.000.000 WCV |
| Decimales | 3 (unidad mínima 0,001 WCV) |
| Suministro en unidades mínimas | 30.000.000.000 |
| Política de adquisición | Solo activos envueltos permitidos en DeFi |
| Exclusiones | Stablecoins y fiat directo |

### 3.2 Pendientes antes de escribir contratos

1. **Cadena:** Ethereum L1, una L2 EVM, Solana u otra.
2. **Jurisdicción:** país de constitución, fiscalidad y marco regulatorio aplicable.
3. **Reparto:** tesorería, liquidez, equipo, comunidad y reserva. Sin porcentajes definitivos todavía.
4. **Gobernanza:** multisig, timelock, DAO o renuncia a la propiedad.
5. **Mecanismo de restricción:** solo en el mercado oficial o también a nivel de transferencias.
6. **Auditoría:** alcance, auditor y presupuesto.
7. **Billetera:** autocustodia, custodia híbrida o hardware wallet.
8. **Alcance de “sin fiat”:** solo en la interfaz oficial o también en contratos y socios.
9. **Decimales:** confirmar 3 frente a 4.
10. **Política de liquidez:** pares permitidos, bloqueo y gestión.

---

## 4. Principios de diseño

1. **Suministro fijo y verificable.** No hay emisión posterior al despliegue. Cualquier función de acuñación debe estar ausente o bloqueada de forma demostrable.
2. **Autocustodia por defecto.** Las claves privadas no salen del equipo del usuario y nunca llegan a Godot, a un servidor de juego ni a un repositorio.
3. **Restricción explícita y auditable.** La política de “solo activos envueltos” debe estar escrita, implementada donde sea posible y verificable por terceros.
4. **Seguridad antes que velocidad.** Sin auditoría y sin pruebas adversariales no hay fondos reales.
5. **Transparencia.** Direcciones, suministro, liquidez, tesorería y cambios de política deben publicarse y poder comprobarse en cadena.
6. **Cumplimiento legal.** La exclusión de fiat en la interfaz no exime de obligaciones regulatorias.
7. **Sin promesas de rentabilidad.** WCVcoin debe presentarse como utilidad del metaverso, no como inversión con rendimiento garantizado.
8. **Compatibilidad con el metaverso.** Si el token no se puede transferir entre usuarios, deja de servir como moneda. La restricción debe equilibrar control y utilidad.

---

## 5. Hoja de ruta por fases

Las duraciones son propuestas de planificación, no compromisos. Cada fase termina con una puerta de decisión; no se avanza si la puerta no se cumple.

### F0 — Definición y documento fundacional (2–3 semanas)

**Objetivo:** fijar qué es WCVcoin, para qué sirve y qué no promete.

Entregables:

- Documento de una página con propósito, suministro, decimales y política de adquisición.
- Glosario de términos: activo envuelto, stablecoin, DEX, liquidez, vesting, timelock, multisig.
- Modelo de amenazas inicial.
- Registro de decisiones abiertas.

Puerta de salida:

- Suministro y decimales confirmados por escrito.
- Definición de “compra” acordada: mercado oficial, transferencias o ambas.
- Lista inicial de activos envueltos permitidos y excluidos.

### F1 — Legal y regulatorio (4–8 semanas, en paralelo)

**Objetivo:** saber en qué país se puede lanzar y bajo qué condiciones.

Entregables:

- Opinión legal escrita sobre la naturaleza del token.
- Análisis de valores negociables, MiCA si aplica, prevención de blanqueo, sanciones, fiscalidad y protección al consumidor.
- Términos de uso, política de privacidad y avisos de riesgo.
- Decisión sobre KYC/KYB y sobre quién puede usar la interfaz oficial.

Puerta de salida:

- No se despliega en mainnet sin opinión legal favorable o, como mínimo, sin un análisis de riesgos firmado y aceptado.
- Se sabe si la política “solo DeFi” es viable en la jurisdicción elegida.

### F2 — Selección de cadena y arquitectura (2–3 semanas)

**Objetivo:** elegir dónde vive WCVcoin y con qué herramientas.

Criterios:

| Criterio | Pregunta |
|---|---|
| Coste | ¿Cuánto cuesta desplegar, transferir y operar? |
| Ecosistema | ¿Hay DEX, activos envueltos y liquidez reales? |
| Billetera | ¿El visor puede firmar y consultar la cadena con librerías mantenidas? |
| Finalidad | ¿Cuánto tarda una transacción en considerarse final? |
| Puentes | ¿Qué riesgo se asume al traer activos envueltos? |
| Auditoría | ¿Hay herramientas y auditores para esa cadena? |
| Regulación | ¿La jurisdicción elegida encaja con la cadena? |

Puerta de salida:

- Cadena elegida y justificada.
- Activos envueltos disponibles en esa cadena.
- Confirmación de que la billetera puede soportarla.

### F3 — Especificación del token (2–4 semanas)

**Objetivo:** describir el contrato antes de escribirlo.

Debe cubrir:

- Nombre, símbolo, decimales y suministro exacto.
- Ausencia de emisión posterior y de funciones ocultas.
-Política de transferencias y lista de contratos autorizados.
- Roles: tesorería, multisig, timelock, emergencia y renuncia.
- Upgradability: contrato inmutable o proxy con gobernanza. Cada opción tiene un coste de confianza.
- Eventos y datos que deben poder auditarse.
- Metadatos públicos y verificación en el explorador de la cadena.

Puerta de salida:

- Especificación revisada por seguridad y legal.
- Alcance de auditoría cerrado.
- No se escribe código hasta que esta puerta esté aprobada.

### F4 — Mercado oficial y liquidez (2–3 semanas)

**Objetivo:** definir cómo se compra y vende WCVcoin sin stablecoins ni fiat.

Reglas propuestas:

- Pares oficiales solo con activos envueltos permitidos: por ejemplo, WETH, WBTC y el activo nativo envuelto de la cadena elegida.
- Exclusión explícita de USDC, USDT, DAI, FRAX, PYUSD, EURC y cualquier token respaldado por fiat, incluida su versión puenteada.
- Ningún módulo de compra con tarjeta, transferencia bancaria o proveedor de fiat en la interfaz oficial.
- Liquidez inicial depositada por la tesorería y documentada públicamente.
- Bloqueo o vesting de la liquidez según la política aprobada.
- Política de retirada de liquidez: quién puede hacerlo, con qué aviso y con qué límites.

Puerta de salida:

- Plan de liquidez aprobado y financiado.
- Pares permitidos publicados.
- Confirmación legal de que la estructura no promete rendimiento.

### F5 — Billetera embebida (6–10 semanas)

**Objetivo:** pasar de una frase semilla a una billetera que pueda custodyar y mover WCVcoin con seguridad.

Estado de partida:

- Generación BIP-39 de 12 palabras en [`SemillaWalletWindow.xaml.cs`](../VSC%23/SemillaWalletWindow.xaml.cs).
- Verificación de 3 palabras en [`VerificarSemillaWindow.xaml.cs`](../VSC%23/VerificarSemillaWindow.xaml.cs).
- Lista de palabras en [`Seguridad/Bip39.cs`](../VSC%23/Seguridad/Bip39.cs).
- Copia local en texto plano y ZIP descargable.
- Sin derivación de claves, sin direcciones, sin firma, sin RPC y sin token.

Entregables:

1. Derivación de claves conforme a BIP-32/BIP-44 y a la cadena elegida.
2. Almacenamiento cifrado en reposo con DPAPI o Credential Manager; nunca texto plano.
3. Firma de transacciones fuera de Godot y fuera de los logs.
4. Cliente RPC con reconexión, timeouts y validación de cadena.
5. Consulta de saldo, historial y estado de transacciones.
6. Envío y recepción con confirmación, simulación y aviso de dirección.
7. Interfaz de intercambio limitada a los pares permitidos.
8. Recuperación desde la semilla y prueba de restauración.
9. Libreta de direcciones, límites de gasto y protección contra phishing.
10. Compatibilidad opcional con hardware wallet.

Puerta de salida:

- La semilla nunca se escribe en texto plano.
- Se firma y se confirma una transacción en testnet.
- Se recupera una billetera desde cero y se comprueba el mismo saldo.
- Auditoría de la billetera o, como mínimo, revisión de seguridad externa.

> **Deuda crítica actual:** el archivo `semilla_wallet.json` contiene las palabras en claro. No debe usarse con fondos reales hasta que se corrija.

### F6 — Integración con el metaverso (4–8 semanas)

**Objetivo:** que WCVcoin tenga uso real dentro del mundo, no solo en un exchange.

Casos de uso a validar (no son promesas de producto):

- Compra de terrenos o assets del metaverso.
- Pagos por creación o personalización.
- Mercado entre jugadores.
- Recompensas por actividad o contribución.
- Acceso a experiencias o servicios.

Arquitectura:

- La billetera C# custodia las claves y firma.
- Godot solicita un pago y recibe solo el comprobante; nunca la clave.
- El anfitrión o el servicio correspondiente valida la transacción contra la cadena.
- Se evitan dobles gastos, repetición de comprobantes y carreras entre clientes.
- Se define qué ocurre sin conexión y cómo se reintenta.
- No se confía en el cliente para acreditar pagos.

Puerta de salida:

- Flujo completo en testnet: comprar, recibir, gastar y verificar.
- Pruebas de abuso: comprobante falso, repetición, doble gasto y caída de RPC.

### F7 — Pruebas, auditoría y bug bounty (4–8 semanas)

**Objetivo:** encontrar fallos antes de que haya dinero real.

Matriz mínima:

| Prueba | Qué debe demostrar |
|---|---|
| Unitaria | Suministro, decimales, transferencias y permisos. |
| Integración | DEX, billetera, RPC y eventos. |
| Fork de mainnet | Comportamiento con liquidez y contratos reales simulados. |
| Testnet pública | Flujo completo con usuarios externos. |
| Adversarial | Intento de comprar con stablecoin, fiat o par no autorizado. |
| Recuperación | Pérdida de dispositivo, semilla y Copia de seguridad. |
| Carga | Muchas billeteras y transacciones simultáneas. |
| Seguridad | Revisión de claves, dependencias, permisos y upgradeabilidad. |

Puerta de salida:

- Sin hallazgos críticos o altos abiertos.
- Informe de auditoría publicado.
- Bug bounty o programa de divulgación responsable activo.

### F8 — Piloto en testnet (4–6 semanas)

**Objetivo:** validar el sistema con usuarios reales sin fondos reales.

Entregables:

- Testnet pública con faucet y límites.
- Guía de uso y preguntas frecuentes.
- Métricas de errores, abandono y soporte.
- Revisión de la política de activos permitidos.

Puerta de salida:

- El flujo se completa sin intervención manual.
- Los incidentes se registran y se resuelven.
- Se decide si se pasa a mainnet o se repite el piloto.

### F9 — Lanzamiento en mainnet (2–3 semanas)

**Objetivo:** poner WCVcoin en producción con el menor riesgo posible.

Entregables:

- Despliegue y verificación del contrato.
- Publicación de direcciones, suministro y política de activos.
- Liquidez inicial en los pares aprobados.
- Monitorización, alertas y panel público.
- Plan de respuesta a incidentes.
- Soporte y documentación para usuarios.

Puerta de salida:

- Checklist de lanzamiento completo.
- Auditoría publicada.
- Liquidez bloqueada o gestionada según la política.
- Ningún módulo de fiat en la interfaz oficial.

### F10 — Operación y gobernanza (continuo)

**Objetivo:** mantener el sistema seguro, transparente y actualizado.

- Informes periódicos de tesorería y suministro.
- Gestión de la lista de activos permitidos con timelock y multisig.
- Revisiones de seguridad y dependencias.
- Atención de incidentes y comunicación.
- Evaluación de nuevas cadenas o puentes.
- Revisión legal periódica.

---

## 6. Tokenómica

### 6.1 Suministro

| Dato | Valor |
|---|---|
| Suministro total | 30.000.000 WCV |
| Decimales | 3 |
| Unidad mínima | 0,001 WCV |
| Unidades mínimas totales | 30.000.000.000 |
| Emisión posterior | Ninguna |
| Rebase | No previsto |
| Quema | A decidir; no se promete |

### 6.2 Reparto

El reparto no está decidido. Antes de fijarlo hay que responder:

- ¿Qué porcentaje va a liquidez inicial?
- ¿Qué porcentaje queda en tesorería del metaverso?
- ¿Qué porcentaje se reserva para equipo y asesores?
- ¿Qué porcentaje se destina a comunidad y recompensas?
- ¿Qué porcentaje queda como reserva de largo plazo?

Principios propuestos:

- Vesting y cliff para equipo y asesores.
- Bloqueo de liquidez con calendario público.
- Tesorería con multisig y timelock.
- Sin asignaciones ocultas ni direcciones no identificadas.
- Sin promesas de precio ni de rendimiento.

### 6.3 Liquidez

- Solo pares con activos envueltos permitidos.
- Sin pares con stablecoins.
- Sin compra directa con fiat.
- Liquidez inicial financiada y documentada.
- Política de retirada publicada antes del lanzamiento.
- Prohibición de usar liquidez de usuarios para fines discrecionales.

### 6.4 Tesorería

- Multisig con varias personas.
- Timelock para operaciones grandes.
- Informes periódicos.
- Direcciones públicas.
- Separación entre tesorería, liquidez y operación.
- Plan de contingencia si un firmante pierde acceso.

---

## 7. El mecanismo “solo activos envueltos”

### 7.1 Definición operativa

No basta con decir “wrapped”. Hay que definir una **lista de contratos permitidos por dirección**, no por nombre comercial.

Ejemplos iniciales a evaluar:

- WETH (ETH envuelto).
- WBTC (BTC envuelto).
- El activo nativo envuelto de la cadena elegida.
- Otros activos envueltos que la gobernanza apruebe expresamente.

Excluidos de forma explícita:

- USDC, USDT, DAI, FRAX, PYUSD, EURC.
- Cualquier stablecoin o token respaldado por fiat.
- Versiones puenteadas de stablecoins.
- Activos nativos sin envolver, salvo que se envuelvan antes de la compra.
- Cualquier par que implique fiat directo.

### 7.2 Dos modelos posibles

**Modelo A — Política de mercado oficial (recomendado para utilidad):**

- La compra y venta oficial solo ocurre en pares permitidos.
- La interfaz oficial no integra fiat ni stablecoins.
- Las transferencias entre usuarios son libres.
- No se puede impedir que alguien venda WCV fuera del mercado oficial por acuerdo privado, incluso habiendo recibido fiat.

**Modelo B — Restricción a nivel de contrato (semipermissionado):**

- El contrato solo permite transferencias desde y hacia contratos autorizados, o entre billeteras verificadas.
- Se bloquean los pares no autorizados, incluidas stablecoins.
- Se limita o impide el uso de WCV como moneda entre usuarios.
- Exige gobernanza, listas y posibles procesos de exclusión.
- Deja de ser un token totalmente permissionless.

### 7.3 Qué se puede y qué no se puede garantizar

Se puede:

- Rechazar transferencias desde contratos no autorizados.
- Impedir que la interfaz oficial opere con stablecoins o fiat.
- Publicar y auditar la lista de pares permitidos.
- Bloquear la creación de pools no autorizados en el contrato, si se implementa el Modelo B.

No se puede garantizar:

- Que nadie compre WCV con fiat fuera de la cadena y reciba tokens por acuerdo privado.
- Que el vendedor use ese fiat para comprar el activo envuelto que luego entrega.
- Que un usuario no compre activos envueltos con stablecoins en otro sitio y luego compre WCV.
- Que un custodio externo no acepte fiat y entregue WCV.

**Conclusión:** la regla elimina la compra directa con stablecoin o fiat en el sistema oficial, pero no es un cortafuegos universal. Si se exige una restricción absoluta, hay que aceptar un diseño semipermissionado y sus consecuencias legales, de gobernanza y de usabilidad.

### 7.4 Gobernanza de la lista

- Multisig y timelock para añadir o quitar activos.
- Publicación previa de cada cambio.
- Prohibición de retirar liquidez o congelar saldos sin proceso.
- Registro público de decisiones.
- Revisión legal de cada activo añadido.
- Plan de emergencia para activos comprometidos.

---

## 8. Billetera embebida

### 8.1 Lo que existe hoy

| Capacidad | Estado |
|---|---|
| Generar frase BIP-39 de 12 palabras | Implementado |
| Verificar 3 palabras elegidas al azar | Implementado |
| Descargar ZIP con la semilla | Implementado |
| Guardar copia local | Implementado, pero en texto plano |
| Derivar claves y direcciones | No implementado |
| Firmar transacciones | No implementado |
| Consultar saldo o historial | No implementado |
| Enviar o recibir WCVcoin | No implementado |
| Intercambiar por activos envueltos | No implementado |
| Recuperar desde la semilla | Parcial: solo se verifica la frase, no se restaura una billetera |

### 8.2 Arquitectura objetivo

- **Claves:** derivación jerárquica y determinista, con rutas documentadas por cadena.
- **Custodia:** cifrado en reposo con DPAPI o Credential Manager; opción de hardware wallet.
- **Firma:** local, con confirmación explícita y sin exponer la clave a Godot.
- **Red:** RPC con validación de cadena, reintentos y mensajes claros.
- **Saldos:** consulta de token y de activos permitidos.
- **Operaciones:** enviar, recibir, intercambiar solo pares permitidos.
- **Recuperación:** restauración completa desde la semilla en un equipo limpio.
- **Seguridad:** simulación previa, advertencia de dirección, límites de gasto, libreta y bloqueo por inactividad.
- **Privacidad:** no publicar direcciones ni saldos en el chat sin consentimiento.

### 8.3 Requisitos de seguridad

1. La semilla nunca se guarda en texto plano ni se envía por red.
2. La semilla nunca aparece en logs, capturas ni mensajes de error.
3. Las claves se borran de memoria cuando ya no se usan.
4. Las transacciones se muestran antes de firmar: destino, cantidad, comisión y red.
5. Se valida que la cadena y el contrato sean los correctos.
6. Se advierte de direcciones nuevas o sospechosas.
7. Se prueba la recuperación antes de manejar fondos reales.
8. Se revisa la seguridad de dependencias y del instalador.
9. Se separan claves de desarrollo, testnet y mainnet.
10. Se documenta el procedimiento si el usuario pierde el dispositivo.

### 8.4 Fases de la billetera

| Fase | Entrega | Criterio de aceptación |
|---|---|---|
| B1 | Derivación y direcciones | Se obtiene la misma dirección desde la misma semilla. |
| B2 | Almacenamiento cifrado | No queda ninguna semilla en texto plano. |
| B3 | Firma en testnet | Una transacción se firma y se confirma. |
| B4 | Saldos e historial | El saldo coincide con el explorador. |
| B5 | Envío y recepción | Se completa un ciclo con dos billeteras. |
| B6 | Intercambio permitido | Solo aparecen pares autorizados. |
| B7 | Recuperación | Se restaura una billetera desde cero. |
| B8 | Revisión de seguridad | Sin hallazgos críticos abiertos. |

---

## 9. Integración con el metaverso

### 9.1 Casos de uso

Los casos deben validarse con producto y legal antes de implementarse:

- Compra de terrenos o parcelas.
- Compra de assets y personalizaciones.
- Mercado entre jugadores.
- Pagos por creación o edición.
- Recompensas por actividades.
- Acceso a experiencias o servicios.

### 9.2 Flujo técnico

1. El usuario inicia una compra en Godot o en la interfaz WPF.
2. La billetera C# construye la transacción y la muestra.
3. El usuario confirma y firma.
4. La transacción se envía a la cadena.
5. El servicio correspondiente verifica el comprobante.
6. El mundo acredita el bien o el servicio.
7. Se registra el resultado y se evita repetir la operación.

Reglas:

- Godot nunca recibe claves privadas.
- El cliente nunca es la única fuente de verdad de un pago.
- El anfitrión o el servicio valida contra la cadena.
- Se evita el doble gasto y la repetición de comprobantes.
- Se define el comportamiento sin conexión y con transacciones pendientes.

### 9.3 Límites

- El metaverso es P2P y el anfitrión puede cambiar; la validación de pagos no puede depender de un único cliente.
- Las transacciones tienen coste y latencia; la experiencia debe mostrar el estado.
- No se deben prometer pagos instantáneos si la cadena no los garantiza.
- La integración no convierte automáticamente WCVcoin en un valor negociable ni en una inversión.

---

## 10. Seguridad

### 10.1 Modelo de amenazas

| Amenaza | Impacto | Mitigación |
|---|---|---|
| Robo de semilla o clave | Pérdida total de fondos | Cifrado, hardware wallet, educación, límites. |
| Phishing o dirección falsa | Pérdida de fondos | Simulación, libreta, advertencias. |
| Contrato mal diseñado | Pérdida o bloqueo | Auditoría, pruebas adversariales, timelock. |
| Gobernanza capturada | Cambios hostiles | Multisig, timelock, transparencia. |
| Puente comprometido | Pérdida de activos envueltos | Límites, diversificación, monitorización. |
| Liquidez retirada | Caída de mercado | Bloqueo y política pública. |
| Dependencia de RPC | Falta de servicio | Varios proveedores y reintentos. |
| Ingeniería social | Robo de credenciales | Formación y doble confirmación. |
| Cadena de suministro | Código malicioso | Dependencias fijadas y builds reproducibles. |

### 10.2 Controles

- Auditoría independiente antes de mainnet.
- Programa de divulgación responsable o bug bounty.
- Verificación del contrato en el explorador.
- Multisig y timelock para funciones sensibles.
- Bloqueo o vesting de liquidez.
- Monitorización de suministro, liquidez y transacciones anómalas.
- Plan de respuesta a incidentes con responsables y canales.
- Copias de seguridad y recuperación de claves de operación.
- Revisión periódica de dependencias y permisos.

### 10.3 Decisión sobre pausas y congelaciones

Un contrato inmutable no puede pausarse; uno actualizable o con roles puede congelar fondos. Ambas opciones tienen costes:

- Inmutable: más confianza descentralizada, menos capacidad de reacción.
- Actualizable: más capacidad de corregir, más poder para la gobernanza.

La decisión debe tomarse antes de la auditoría y publicarse.

---

## 11. Legal y cumplimiento

Temas que deben tratarse con abogados de la jurisdicción elegida:

- Calificación del token: utilidad, valor negociable u otra categoría.
- MiCA si se opera en la Unión Europea.
- Prevención de blanqueo de capitales y financiación del terrorismo.
- Sanciones y listas de exclusión.
- Fiscalidad de compras, ventas, recompensas y tesorería.
- Protección al consumidor y publicidad.
- Privacidad y tratamiento de datos.
- Términos de uso y resolución de conflictos.
- Responsabilidad de la DAO o de la fundación.
- Reglas sobre promociones y promesas de rentabilidad.

Advertencias:

- **“Solo DeFi” no elimina las obligaciones regulatorias.**
- **Excluir el fiat de la interfaz no impide el fiat fuera de ella.**
- **La ausencia de KYC en el contrato no significa ausencia de KYC en el negocio.**
- **Nada de este documento es asesoría legal.**

---

## 12. Pruebas y aceptación

### 12.1 Matriz de pruebas

| Área | Caso | Resultado esperado |
|---|---|---|
| Suministro | Consultar total | 30.000.000 WCV; 30.000.000.000 unidades mínimas. |
| Decimales | Transferir 0,001 | Aceptado. |
| Decimales | Transferir 0,0001 | Rechazado por precisión. |
| Emisión | Intentar acuñar | Imposible. |
| Compra permitida | Par con WETH/WBTC | Permitido. |
| Compra prohibida | Par con stablecoin | Rechazado o no disponible. |
| Fiat | Compra con tarjeta | No existe en la interfaz oficial. |
| Transferencia | Usuario a usuario | Según el modelo elegido. |
| Recuperación | Restaurar desde semilla | Misma dirección y saldo. |
| Seguridad | Semilla en disco | Cifrada, nunca en claro. |
| Red | Caída de RPC | Mensaje claro y reintento. |
| Abuso | Comprobante repetido | Rechazado. |

### 12.2 Checklist de lanzamiento

- [ ] Suministro y decimales confirmados.
- [ ] Cadena y jurisdicción decididas.
- [ ] Contrato auditado y verificado.
- [ ] Lista de activos permitidos publicada.
- [ ] Pares con stablecoins bloqueados o inexistentes.
- [ ] Ningún módulo de fiat en la interfaz oficial.
- [ ] Liquidez inicial depositada y documentada.
- [ ] Billetera probada en testnet y revisada.
- [ ] Recuperación desde semilla probada.
- [ ] Monitorización y respuesta a incidentes activas.
- [ ] Términos, privacidad y avisos de riesgo publicados.
- [ ] Tesorería con multisig y timelock.
- [ ] Informe de auditoría público.
- [ ] Plan de comunicación y soporte.

---

## 13. Presupuesto y financiación

### 13.1 Partidas

| Partida | Tipo | Comentario |
|---|---|---|
| Desarrollo del contrato | Interno o externo | Especificación, implementación y pruebas. |
| Auditoría | Externo | La partida más importante antes de mainnet. |
| Legal | Externo | Constitución, opinión, términos y cumplimiento. |
| Liquidez | Capital | No es un gasto corriente; queda expuesto en los pares. |
| Billetera | Interno o externo | Derivación, firma, RPC, UX y seguridad. |
| Infraestructura | Recurrente | RPC, indexador, monitorización y copias. |
| Soporte | Recurrente | Atención de usuarios e incidentes. |
| Comunidad | Variable | Educación y comunicación, sin promesas de rentabilidad. |

### 13.2 Fuentes de financiación posibles

- Tesorería del proyecto.
- Preventa privada solo si es legal y compatible con la política de activos envueltos.
- Subvenciones del ecosistema de la cadena elegida.
- Ingresos del metaverso.
- Capital propio del equipo.

> Cualquier preventa debe analizarse con legal antes de existir. Una preventa con fiat o stablecoins contradiría la política declarada.

---

## 14. Riesgos principales

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El token se considera valor negociable | Media | Alto | Opinión legal y diseño de utilidad. |
| Auditoría insuficiente | Media | Alto | Alcance claro, auditor reconocido y bug bounty. |
| Liquidez insuficiente | Alta | Alto | Capital inicial y política de mercado. |
| Restricción de stablecoins eludible | Alta | Medio | Modelo B o aceptar el límite del Modelo A. |
| Pérdida de claves de usuarios | Media | Alto | Cifrado, recuperación y educación. |
| Gobernanza centralizada | Media | Medio | Multisig, timelock y transparencia. |
| Puente de activos envueltos comprometido | Baja/Media | Alto | Límites y diversificación. |
| Falta de demanda real | Alta | Alto | Utilidad en el metaverso y producto antes que token. |
| Regulación cambia | Media | Alto | Revisión legal periódica y diseño adaptable. |
| Reputación por promesas exageradas | Media | Alto | Comunicación prudente y sin rendimientos. |

---

## 15. Decisiones abiertas

| # | Decisión | Estado | Responsable | Fecha |
|---|---|---|---|---|
| 1 | Confirmar 3 o 4 decimales | Abierta | Producto | — |
| 2 | Cadena principal | Abierta | Técnico + legal | — |
| 3 | Jurisdicción | Abierta | Legal | — |
| 4 | Reparto del suministro | Abierta | Producto + tesorería | — |
| 5 | Modelo A o B de restricción | Abierta | Producto + legal | — |
| 6 | Gobernanza y upgradeabilidad | Abierta | Técnico + legal | — |
| 7 | Auditor | Abierta | Técnico | — |
| 8 | Custodia de la billetera | Abierta | Producto + seguridad | — |
| 9 | Alcance de la prohibición de fiat | Abierta | Legal | — |
| 10 | Calendario de lanzamiento | Abierta | Producto | — |

---

## 16. Próximos pasos inmediatos (sin código)

1. Confirmar por escrito los decimales y el suministro.
2. Elegir una lista corta de cadenas candidatas y comparar costes reales.
3. Contratar o consultar asesoría legal antes de diseñar la venta.
4. Definir la lista inicial de activos envueltos permitidos y excluidos.
5. Decidir si la restricción es de mercado oficial (Modelo A) o de contrato (Modelo B).
6. Fijar las categorías del reparto y las reglas de vesting.
7. Revisar la seguridad de la billetera actual y eliminar la semilla en texto plano.
8. Escribir la especificación técnica del token y de la billetera como documentos separados.
9. Solo después de las puertas F0–F3, escribir código y preparar la auditoría.

---

## 17. Referencias internas

- Billetera actual: [`SemillaWalletWindow.xaml.cs`](../VSC%23/SemillaWalletWindow.xaml.cs).
- Verificación de semilla: [`VerificarSemillaWindow.xaml.cs`](../VSC%23/VerificarSemillaWindow.xaml.cs).
- Generación BIP-39: [`Seguridad/Bip39.cs`](../VSC%23/Seguridad/Bip39.cs).
- Documentación de la sesión: [`README_desarrollo_20261026_chat_construccion.md`](../README_desarrollo_20261026_chat_construccion.md).
- Hoja de ruta general del proyecto: [`HOJA_DE_RUTA.md`](../HOJA_DE_RUTA.md).

Estándares y marcos que habrá que citar en la especificación técnica: BIP-39, BIP-32, BIP-44, ERC-20 (o el estándar equivalente de la cadena elegida), MiCA (si aplica) y las normas locales de prevención de blanqueo.

---

*Documento de planificación. No contiene código, no despliega contratos y no constituye asesoría financiera ni legal. Las cifras son estimaciones y deben validarse con presupuestos reales.*
