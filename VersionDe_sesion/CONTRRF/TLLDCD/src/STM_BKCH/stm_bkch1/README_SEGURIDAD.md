# Servidor Blockchain BKSVCB - Medidas de Seguridad Anti-Múltiples Cuentas

## Resumen

El servidor blockchain BKSVCB ha sido mejorado con medidas de seguridad para prevenir la creación de múltiples cuentas por usuario. Estas medidas aseguran que cada usuario solo pueda tener una cuenta activa en el sistema.

## Medidas de Seguridad Implementadas

### 1. **Una Cuenta por Huella de Máquina (UUID)**
- **Máximo permitido**: 1 cuenta por UUID de máquina
- **Validación**: Se verifica que no exista una cuenta con la misma huella antes de crear una nueva
- **Implementación**: `_cuentas_por_huella` dictionary mantiene el contador de cuentas por huella
- **Endpoint afectado**: `/alta-cuenta`, `/migrar-cuenta`

### 2. **Una Cuenta por Ubicación Física**
- **Máximo permitido**: 1 cuenta por ubicación física (ubicacion_hash)
- **Validación**: Si se proporciona ubicación_hash, se verifica que no exista una cuenta con la misma ubicación
- **Implementación**: `_cuentas_por_ubicacion` dictionary mantiene el contador de cuentas por ubicación
- **Endpoint afectado**: `/alta-cuenta`, `/migrar-cuenta`
- **Nota**: Si no se proporciona ubicación_hash, esta validación se omite

### 3. **Rate Limiting por IP**
- **Límite**: 10 requests por IP por minuto
- **Ventana**: 60 segundos
- **Implementación**: `_rate_limit_store` dictionary mantiene el timestamp de cada request
- **Response**: HTTP 429 (Too Many Requests) si se excede el límite
- **Endpoints afectados**: Todos los endpoints HTTP

### 4. **Registro de Intentos de Creación**
- **Propósito**: Auditoría de intentos de creación de cuenta
- **Información registrada**:
  - Timestamp
  - Tipo de operación (alta/migración)
  - IP del cliente
  - Huella (primeros 16 caracteres)
  - Éxito/Fallo
  - Motivo del fallo
- **Almacenamiento**: Últimos 1000 intentos en memoria
- **Endpoint de auditoría**: `GET /intentos`

### 5. **Validación de Formato de Datos**
- **Nick**: Mínimo 3 caracteres
- **Huella**: Debe ser un UUID de 32 caracteres hexadecimales
- **Cuenta Hash**: Debe ser SHA-256 de 64 caracteres hexadecimales
- **Ubicación Hash**: Debe ser SHA-256 de 64 caracteres hexadecimales (si se proporciona)

## Endpoints HTTP

### POST /alta-cuenta
Crea una cuenta nueva con validaciones de seguridad.

**Request Body**:
```json
{
  "nick": "usuario123",
  "huella": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d",
  "ubicacion_hash": "opcional_hash_ubicacion_fisica"
}
```

**Response**:
- `201 Created`: Cuenta creada exitosamente
- `400 Bad Request`: Datos inválidos
- `409 Conflict`: Cuenta duplicada (misma huella o ubicación)
- `429 Too Many Requests`: Rate limit excedido

### POST /migrar-cuenta
Migra una cuenta antigua al hash único de cuenta.

**Request Body**:
```json
{
  "nick": "usuario123",
  "huella": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d",
  "ubicacion_hash": "opcional_hash_ubicacion_fisica"
}
```

**Response**:
- `200 OK`: Cuenta migrada exitosamente
- `400 Bad Request`: Datos inválidos
- `409 Conflict`: Cuenta duplicada
- `429 Too Many Requests`: Rate limit excedido

### GET /descargar-cuenta-zip?cuenta_hash=<hash>
Descarga el .zip con el hash único de cuenta.

**Query Parameters**:
- `cuenta_hash`: Hash SHA-256 de 64 caracteres

**Response**:
- `200 OK`: Archivo .zip descargado
- `400 Bad Request`: Hash inválido

### GET /intentos
Obtiene el registro de intentos de creación de cuenta (últimos 100).

**Response**:
```json
{
  "intentos": [
    {
      "timestamp": 1699999999.999,
      "tipo": "alta",
      "ip": "127.0.0.1",
      "huella": "a1b2c3d4e5f6a1b2...",
      "exito": true,
      "motivo": ""
    }
  ]
}
```

### GET /status
Obtiene el estado del servidor blockchain con información de seguridad.

**Response**:
```json
{
  "servidor": "CelebroBlockchainServer-BKSVCB-Seguro",
  "total_bloques": 10,
  "cadena_valida": true,
  "error_validacion": null,
  "ultimo_bloque": {...},
  "cuentas_por_huella": {"a1b2c3d4...": 1},
  "cuentas_por_ubicacion": {"ubicacion...": 1}
}
```

## Configuración

Las constantes de seguridad se pueden modificar en `bksvcb_net.py`:

```python
MAX_CUENTAS_POR_HUELLA = 1  # Máximo 1 cuenta por UUID de máquina
MAX_CUENTAS_POR_UBICACION = 1  # Máximo 1 cuenta por ubicación física
RATE_LIMIT_REQUESTS = 10  # Máximo 10 requests por IP por minuto
RATE_LIMIT_WINDOW = 60  # Ventana de 60 segundos
```

## Uso

### Iniciar el servidor:

```python
from STM_BKCH.bksvcb_net import iniciar_servidor_blockchain

daemon = iniciar_servidor_blockchain(puerto=8545)
# El servidor corre en http://127.0.0.1:8545
```

### Ejecutar como script:

```bash
python -m STM_BKCH.bksvcb_net
```

## Integración con LucIA

El script `LuciaRecepcion.gd` en Godot se comunica con estos endpoints:

1. **Crear cuenta nueva**: `POST /alta-cuenta`
2. **Migrar cuenta antigua**: `POST /migrar-cuenta`
3. **Descargar .zip**: `GET /descargar-cuenta-zip`

## Consideraciones de Seguridad

- **Persistencia**: Los contadores de cuentas se reinician al reiniciar el servidor. Para persistencia a largo plazo, se recomienda almacenar en la blockchain o en una base de datos externa.
- **Distribución**: En un entorno distribuido, los contadores deben ser compartidos entre todas las instancias del servidor (ej: usando Redis o una base de datos compartida).
- **IP Spoofing**: El rate limiting por IP puede ser evadido usando proxies. Para entornos de producción, se recomienda usar CAPTCHA o autenticación adicional.
- **Ubicación Física**: La validación por ubicación física requiere que el visor C# genere el hash de ubicación correcto (ARP del gateway + Wi-Fi ambiental).

## Auditoría

Para revisar los intentos de creación de cuenta:

```bash
curl http://127.0.0.1:8545/intentos
```

## Futuras Mejoras

- [ ] Persistencia de contadores en blockchain
- [ ] CAPTCHA para validación de nuevos usuarios
- [ ] Autenticación de usuarios existentes
- [ ] Bloqueo temporal de IPs abusivas
- [ ] Integración con sistema de reputación
