# STM_RFC · README del sistema RFPRMN

Fecha: 2026-11-08 · **v2.10.0**. Todo lo descrito está implementado y verificado
por ejecución en `STM_RFPRMN/` (fachada `RFPRMN.py` + paquete
`STM_RFPRMN_stmDL/`) y en el subsistema `LC_STM/seq2seq`.

Cierra los issues **#80** y **#81**, corrige el fallo de descarga de modelos,
resuelve las fases R1–R6 de la discusión #84, añade el **puente LucIA ↔ red
neuronal** (embeddings reales y semilla con código real), deja la deuda
P1/P2/P4 resuelta, suma el **subsistema seq2seq** y los comandos
**`crear codigo`**, **`crear logica`** y **`test`**.

## 1. Lo implementado

### 1.1 Refactorización modular (tope 450 líneas por archivo)

**19 submódulos, ninguno por encima de 450 líneas**. El registro de símbolos
(§1.9) se genera por AST, así que las cifras no se quedan obsoletas:

| Archivo | Líneas | Contenido |
|---|---:|---|
| `RFPRMN.py` | 450 | Fachada + CLI (`--ayuda/--version/--estado/--presupuesto/--rutas/--configurar-rutas/--lucia/--seq2seq/--sembrar-lucia/--comando/--consumir-modelos/--openrouter`) |
| `STM_RFPRMN_stmDL/__init__.py` | 310 | Registro por AST (**253 símbolos**) + presupuesto + salud |
| `stm_base.py` | 212 | Estilo/UI, constantes, errores, re-export de rutas, `atexit` |
| `stm_rutas.py` | 345 | Única fuente de rutas, cadena de configuración, guardián RFC/PRY |
| `stm_fs.py` | 428 | Copia verificada, swap transaccional, borrado reportado, JSON atómico |
| `stm_fragmentos.py` | 132 | Troceado por AST, solape y constantes de refactor |
| `stm_gestion.py` | 385 | `refactorizar/enviar/actualizar` transaccionales |
| `stm_analisis.py` | 280 | `AnalisisArchivo` + plan + LucIA local |
| `stm_lucia.py` | 367 | Expediente, red neuronal, veredicto y escritura |
| `stm_calidad.py` | 119 | Vector del candidato y puntuación de calidad |
| `stm_corpus.py` | 103 | Semilla de entrenamiento con archivos reales |
| `stm_seq2seq.py` | 142 | Puente al subsistema `LC_STM/seq2seq` (memoria de refactors) |
| `stm_embeddings.py` | 203 | Embeddings de Ollama, detección y contracción |
| `stm_modelos.py` | 428 | Política de modelos (ligero primero) y ciclo de vida |
| `stm_descarga.py` | 165 | Descarga GGUF atómica, reanudable y verificada |
| `stm_openrouter.py` | 193 | Respaldo OpenRouter (desactivado por defecto) |
| `stm_refactor.py` | 350 | Fragmentos + validación + `comando_ds_ialocal` |
| `stm_creacion.py` | 216 | Comando `crear codigo` (diagnóstico → archivo nuevo) |
| `stm_logica.py` | 245 | **Nuevo**: comando `crear logica` (petición → función) |
| `test.py` | 206 | **Nuevo**: pruebas estáticas y diagnóstico de deuda |
| `stm_flujo.py` | 444 | `FlujoRefactorLucIA` (una sola definición de `ejecutar`) |
| `stm_registro.py` | 194 | Publicación del registro y limpieza |
| `stm_pesos.py` | 137 | Vectorización, cuantización y verificación |
| `stm_ipfs.py` | 167 | Subida a IPFS en cuatro niveles |

`from RFPRMN import X` y `RFPRMN().metodo()` siguen funcionando igual.

### 1.2 Rutas: una sola fuente de verdad (R1/R2/R5)

`stm_rutas.py` centraliza todas las rutas y aplica dos invariantes:

- **La herramienta no escribe bajo `CONTRRF/RFC` ni bajo `Sistema_Principal/PRY`.**
  `comprobar_ruta_segura()` lo impide.
- **Cada dato tiene un sitio estable:** pesos en `STM_RFPRMN/.modelos/`, registro
  en `STM_RFPRMN/registro_refactor.md`, configuración en `STM_RFPRMN/.config/`.

`RFC_DIR` y `PRY_DIR` se resuelven por: variables `RFPRMN_RFC_DIR`/`RFPRMN_PRY_DIR`
→ `.config/rutas.json` → rutas oficiales → layout.

```bash
python RFPRMN.py --rutas              # rutas activas y su origen
python RFPRMN.py --configurar-rutas   # elegirlas (valida y guarda)
```

La configuración de IA local se busca en `RFPRMN_IALOCAL_JSON` →
`PRY/actualizacion_*/src/STM_JSON` → `RFC/src` heredado → `.config`.

### 1.3 Issue #80 — flujo de refactor

Un solo `ejecutar()`, cortes por AST, solape real sin duplicar, rechazo de
resultados que exceden el tope (sin truncar), rotación que excluye modelos
fallidos y limpieza garantizada. El prompt prohíbe renombrar funciones y clases
públicas, en línea con la validación.

**Si el modelo devuelve el mismo código** no se considera un fallo del modelo:
el fragmento se reintenta una vez con la instrucción «aplica al menos una
mejora» y, si sigue igual, se pregunta si se da el archivo por terminado. Antes
se rotaba de modelo y se agotaban las tres IAs en un archivo que no necesitaba
cambios.

**Y documentar no es refactorizar**: si el cambio es solo de comentarios o
docstrings, se detecta comparando el código sin ruido (`ast` en Python,
comentarios fuera y espacios normalizados en el resto) y se reintenta con
«aplica una transformación real». En el último intento se acepta para no perder
la documentación, y el fragmento queda marcado.

### 1.4 Issue #81 — gestión de ficheros

Copia a `.tmp` + verificación por SHA-256 + intercambio con rollback, borrado
que reporta restos, JSON atómico con bloqueo, symlinks explícitos y rutas
críticas protegidas. `actualizar` verifica antes de purgar.

### 1.5 Descarga de modelos

`.part` + `Range` + reintentos + validación de cabecera GGUF + `os.replace`.
Un archivo truncado ya no se acepta como completo.

### 1.6 Modelos: el más ligero, y sin borrar lo tuyo (R3/R6)

Orden de decisión: reutiliza el más ligero instalado → si no hay, descarga el
más ligero que quepa en RAM → si `pull` falla, GGUF verificado + `ollama create`.
Los modelos **no se borran** salvo `--consumir-modelos` (o
`RFPRMN_CONSUMIR_MODELOS=1`). El respaldo OpenRouter está **desactivado** por
defecto (`--openrouter` para activarlo).

### 1.7 LucIA: expediente, embeddings, aprendizaje y semilla

Ciclo de `ds ialocal`:

1. **Expediente**: código + descripción funcional de LucIA + README con la
   deuda técnica concreta del archivo.
2. **Envío**: el contexto del expediente viaja con cada fragmento al modelo.
3. **Vectores**: entrada de **31** dimensiones = expediente (11 métricas + 8
   semánticas) + candidato (4 estructurales + 8 semánticas). La red **ve el
   candidato**, así distingue dos versiones del mismo archivo.
4. **Aprendizaje**: `NeuralNetworkOptimizer` de
   `LC_STM/red_neuronal/RF_SL/RFSL1/RF_SL1_4.py` entrena con
   `(expediente+candidato) → calidad`; pesos en `.modelos/lucia_rn_31x1.pkl`.
5. **Escritura**: LucIA puntúa **antes** de entrenar; si no convence, pregunta.
   El README del expediente se archiva en `.modelos/expedientes/`.

Calidad = 50 % fidelidad de definiciones + 30 % limpieza (líneas largas y
documentación) + 20 % seguridad (sintaxis, tope, no vacío).

**Embeddings** (`stm_embeddings.py`): modelo configurable por
`RFPRMN_EMBEDDING_MODEL` u opciones; si no, el más ligero instalado
(`all-minilm` 46 MB). Degrada a huella de hash si no hay modelo o Ollama no
responde.

**Semilla con código real** (no hay corpus de refactors humanos):

```bash
python RFPRMN.py --sembrar-lucia 12   # lee archivos reales del proyecto
python RFPRMN.py --lucia              # estado y muestras aprendidas
```

Genera dos muestras por archivo (documentado vs sin docstrings) con etiquetas
objetivas, y deja la red fuera del estado «aprendiendo» (`MIN_PASOS` = 8).

**Alcance honesto:** la red no genera texto; evalúa. La generación la hace el
modelo local y la decisión/escritura, LucIA.

### 1.8 Seq2Seq: generar, no solo evaluar (`LC_STM/seq2seq`)

La red de `red_neuronal` **evalúa**; el subsistema `seq2seq` **genera**. Está en
`LC_STM/seq2seq/` y es modular, sólo numpy:

| Módulo | Papel |
|---|---|
| `tokenizador.py` | tokens de código y lenguaje natural (regex, determinista) |
| `vectorizador.py` | *feature hashing* de tokens + coseno |
| `codificador.py` | encoder: petición → vector normalizado |
| `decodificador.py` | decoder: vecino más cercano sobre la memoria |
| `memoria.py` | pares petición→respuesta, con persistencia JSON y tope |
| `generador.py` | fachada: `aprender`, `generar`, `guardar`, `estado` |
| `puente_rn.py` | `NeuronaSeq2Seq`: mismo protocolo que `NeuronaMemoriaBase` |

**Cómo genera, sin adornos:** no entrena un transformer (imposible con numpy y
sin corpus masivo). Es un **seq2seq de memoria**: codifica la petición, busca el
par más parecido por coseno y devuelve *su* respuesta si supera el umbral; si no,
**se niega** en vez de inventar código que acabaría escrito en un archivo.

Integración con el flujo:

- al aceptar un refactor con calidad suficiente, el par
  `(código original → refactorizado)` se memoriza;
- si las IAs locales fallan y OpenRouter está apagado, se intenta recuperar de
  la memoria antes de darse por vencido.

```bash
python RFPRMN.py --seq2seq     # pares memorizados, umbral y ruta
```

La memoria vive en `STM_RFPRMN/.modelos/seq2seq.json` y el umbral se ajusta con
`RFPRMN_SEQ2SEQ_UMBRAL`.

### 1.9 Crear código desde un diagnóstico (`crear codigo`)

El otro sentido del ciclo: en vez de refactorizar lo que existe, se crea un
archivo nuevo a partir de una **descripción en lenguaje natural**.

```bash
python RFPRMN.py            # y dentro:  crear codigo
```

Pide ruta, qué debe hacer y lenguaje; después:

1. **Diagnóstico de creación**: LucIA (modelo local) propone responsabilidades,
   API pública, entradas/salidas, errores y criterios de aceptación. Si el
   modelo no responde, hay un plan de respaldo determinista.
2. Se muestra el plan y se pide confirmación.
3. **Generación** del archivo completo con el plan como contexto (mismo
   vigilante de CPU y política de modelo ligero que el refactor).
4. **Validación**: no vacío, tope de líneas y sintaxis (AST en Python). Si no
   pasa, **no se escribe nada**.
5. **Escritura atómica** y aprendizaje del par (descripción → código) para el
   `seq2seq`.

También sin interacción:

```bash
python RFPRMN.py --comando "crear codigo"
```

### 1.10 Test: probar y diagnosticar la deuda (`test.py`)

Cierra el ciclo: después de refactorizar o crear un archivo, se comprueba y se
mide su deuda técnica.

```bash
python RFPRMN.py            # y dentro:  test
```

Qué hace, y qué no: **no ejecuta el código** (ejecutar código ajeno desde una
herramienta de gestión no es seguro). Aplica una batería estática:

1. lectura y tamaño,
2. sintaxis: AST en Python; llaves y paréntesis en el resto,
3. lint con `ruff` si está instalado (solo `.py`),
4. métricas y deuda con `stm_lucia.deuda_tecnica`,
5. **puntuación 0-100** con descuentos explícitos y nivel
   (sano ≥ 85, aceptable ≥ 70, revisar ≥ 50, crítico).

Se ejecuta automáticamente al terminar `ds ialocal` y `crear codigo`, así que el
resultado del cambio se ve en el momento. También se puede comparar:

```python
from STM_RFPRMN_stmDL.test import mensaje_comparacion
mensaje_comparacion(60, "ruta/al/archivo.py")
# "Deuda técnica: 60 -> 97/100 (mejora 37)."
```

### 1.11 Crear lógica desde una petición (`crear logica`)

Primo de `crear codigo`, pero centrado en **la lógica**: lo único obligatorio es
decir qué quieres, en lenguaje natural.

```bash
python RFPRMN.py            # y dentro:  crear logica
¿Qué lógica quieres? Una función que calcule el IVA y lo redondee a 2 decimales
Archivo donde añadirla (vacío = archivo nuevo):
Lenguaje (vacío = deducir):
```

1. **Diseño de LucIA**: firma, parámetros y tipos, qué devuelve, casos límite y
   errores, algoritmo paso a paso. Con respaldo determinista si no hay modelo.
2. Confirmación del diseño.
3. **Generación** de la función (sin ejemplo de uso, para poder integrarla).
4. **Validación** antes de escribir (AST en Python, tope de líneas).
5. **Integración**: si indicas un archivo existente, la lógica se **añade** al
   final y se valida el conjunto; si no, se crea `logica_<petición>.py`.
6. Diagnóstico de deuda con el módulo `test`.

### 1.12 Registro e IPFS

`envios.json` → `registro.md` → pesos (`stm_pesos`) → IPFS en cuatro niveles
(`stm_ipfs`) → limpieza. **P1 resuelta**: un CID sintético del shim
(`QmLocal…` con `ok=False`) ya **no** cuenta como subida; el flujo baja a la
API, al binario y, si no hay nada, a un CID local honesto.

### 1.13 Registro de símbolos por AST (D4) y consola

`__init__.py` descubre los símbolos leyendo el árbol sintáctico de cada
submódulo: no hay listas a mano que se desincronicen. Se registran funciones y
clases (también privadas) y constantes públicas; si un nombre se repite, gana
el primer módulo del orden.

`sys.pycache_prefix` apunta a `.pycache_rfprmn` y el `atexit` limpia al salir.
Todas las salidas toleran consolas cp1252.

## 2. Pruebas y CI

**221 pruebas** propias (sin red, sin Ollama y sin tocar RFC/PRY):

```bash
cd VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN
python -m pytest tests -q -p no:cacheprovider
# sandbox de integridad baja (Windows): -p no:tmpdir y RFPRMN_TEST_TMP=<carpeta>
```

| Archivo | Cobertura |
|---|---|
| `test_rutas.py` | Nada bajo RFC/PRY, cadena de configuración, R5 |
| `test_fs.py` | Huella, swap con rollback, borrado, JSON atómico, bloqueo |
| `test_gestion.py` | Rutas críticas, registro atómico, P4 sin rama heredada |
| `test_fragmentos.py` | Cortes válidos, cobertura, `try/except`, solape |
| `test_flujo.py` | Un solo `ejecutar`, sin F821, sin truncar, rotación, limpieza |
| `test_modelos.py` | Registro de usados, R3, «el más ligero», R6 |
| `test_descarga.py` | `Range`, truncados, no repetir descargas |
| `test_openrouter.py` | Desactivado por defecto y activación explícita |
| `test_lucia.py` | Expediente, README, vector, calidad y veredicto |
| `test_embeddings.py` | Detección, endpoints, caché, contracción |
| `test_corpus.py` | Semilla con código real y muestra negativa |
| `test_seq2seq.py` | Tokenizador, vectorizador, memoria, generador, neurona y puente |
| `test_creacion.py` | `crear codigo`: extensión, plan, validación y escritura |
| `test_modulo_test.py` | Puntuación, niveles, sintaxis sin AST, comparación y comandos |
| `test_logica.py` | Nombre derivado, diseño, validación, añadir sin pisar y comando |
| `test_ipfs.py` | P1: el shim no cuenta como subida |

**CI**: `.github/workflows/rfprmn-tests.yml` ejecuta lint crítico, presupuesto,
estado y pruebas en Ubuntu y Windows × Python 3.11/3.12.

## 3. Deuda técnica

- **D1 (mitigada)**. `stm_flujo` (444), `stm_fs` y `stm_modelos` (428) están
  cerca del tope: el próximo cambio grande exige dividirlos.
- **D2 (cerrada por R5)**. Las rutas oficiales ya no son obligatorias.
- **D3 (mitigada)**. La parte semántica usa embeddings reales de Ollama.
- **D4 (cerrada)**. Registro de símbolos por AST.
- **D5**. Las rutas de limpieza usan `except OSError` amplio a propósito.
- **D6 (cerrada por R1/R2)**. Configuración y pesos fuera de `RFC/src`.

## 4. Deuda preexistente resuelta

- **P1**. El shim de IPFS ya no se da por bueno como subida (§1.8).
- **P2**. `SBSTM/IALOCAL.py` usaba `subir_pesos_neuronales()`/`add()`, que no
  existen; ahora llama a `almacenar_pesos()` y comprueba `ok`.
- **P4**. Eliminada la rama heredada `Construccion/...` de `refactorizar` y
  `actualizar`: sin layout se indica cómo configurarlo.

## 5. Tareas pendientes

1. Dividir `stm_flujo`/`stm_fs`/`stm_modelos` antes de crecer (D1).
2. Sustituir la huella de hash del respaldo por un codificador propio (D3).
3. Acumular refactors reales para que la red aprenda de resultados humanos,
   no solo de la semilla.
4. Resolver la deuda del proyecto ajeno a este módulo (visores, OTA, LucIA).
