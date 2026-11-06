# Tablas actuales de Cero Colas

Este documento describe las tablas de aplicación que la migración P1 crea y usa
actualmente. La fuente del esquema es [`schema_p1.sql`](./schema_p1.sql), y los
modelos SQLAlchemy están en `app/modules/auth/models.py`,
`app/modules/surveys/models.py`, `app/modules/reservations/models.py` y
`app/db/migrate.py`.

La aplicación activa usa PostgreSQL y el esquema público de la base configurada
en `backend/.env`. Las migraciones `001_p1` y `002_reservations` crean ocho
tablas P1 y tres tablas de reservas; `003_reservation_idempotency` agrega la
huella de contenido para que las claves idempotentes no se reutilicen con otra
reserva.
Esta lista cubre las tablas administradas por la aplicación; no incluye las
tablas internas de PostgreSQL ni tablas que alguien haya agregado manualmente.

## Resumen

| Tabla | Módulo | Propósito |
|---|---|---|
| `p1_users` | Auth / Admin | Cuentas locales, rol, estado y preferencias. |
| `p1_sessions` | Auth | Sesiones locales y revocación. |
| `p1_challenges` | Auth | Desafíos aritméticos de un solo uso para desarrollo. |
| `p1_recovery_tokens` | Auth | Recuperación de contraseña. |
| `p1_auth_attempts` | Auth | Registro temporal de intentos para limitar solicitudes. |
| `p1_usage_events` | Surveys / Portal | Registra una consulta de elegibilidad por sesión. |
| `p1_surveys` | Surveys / Admin | Respuestas de facilidad y satisfacción. |
| `p1_schema_migrations` | Infraestructura | Versiones de migraciones aplicadas. |
| `cita_local` | Reservations | Copia local de la cita hospitalaria, ligada a la cuenta P1. |
| `cita_indicacion` | Reservations | Indicaciones de una cita. |
| `auditoria_api` | Integrations | Solicitudes salientes, resultado HTTP, duración y reintentos. |

## Detalle de tablas

### `p1_users`

Una fila por cuenta local.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `name` | `VARCHAR(120)` | No | Nombre mostrado. |
| `email` | `VARCHAR(254)` | No | Correo normalizado; índice único. |
| `password_hash` | `VARCHAR(256)` | No | Hash de contraseña; nunca almacena la contraseña en texto claro. |
| `role` | `VARCHAR(16)` | No | Rol de la cuenta, por ejemplo `PACIENTE` o `ADMIN`. |
| `active` | `BOOLEAN` | No | Indica si la cuenta puede iniciar sesión. |
| `preferences` | `JSON` | No | Preferencias; actualmente idioma, tema y avisos por correo. |
| `created_at` | `TIMESTAMP` | No | Fecha de creación. |
| `updated_at` | `TIMESTAMP` | No | Última actualización. |

### `p1_sessions`

Una sesión autenticada del portal. `user_id` referencia `p1_users.id`
(borrado en cascada). Se guardan hashes de los tokens, no el token de sesión
ni el token CSRF en texto claro.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `user_id` | `VARCHAR(36)` | No | Cuenta propietaria; clave foránea. |
| `token_hash` | `VARCHAR(64)` | No | Hash único del token de sesión. |
| `csrf_hash` | `VARCHAR(64)` | No | Hash del token CSRF asociado. |
| `created_at` | `TIMESTAMP` | No | Fecha de creación. |
| `expires_at` | `TIMESTAMP` | No | Caducidad; indexada. |
| `revoked_at` | `TIMESTAMP` | Sí | Fecha de revocación; nulo mientras no se revoque. |

### `p1_challenges`

Desafíos aritméticos temporales usados por el flujo de autenticación de
desarrollo. No son CAPTCHA de producción.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(64)` | No | Identificador del desafío; clave primaria. |
| `answer_hash` | `VARCHAR(64)` | No | Hash de la respuesta. |
| `client_hash` | `VARCHAR(64)` | No | Huella hasheada para ligar el desafío al cliente. |
| `expires_at` | `TIMESTAMP` | No | Caducidad; indexada. |
| `consumed_at` | `TIMESTAMP` | Sí | Fecha de uso; nulo si no se ha consumido. |

### `p1_recovery_tokens`

Tokens de recuperación de cuentas. `user_id` referencia `p1_users.id`
(borrado en cascada); el token se almacena como hash.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `user_id` | `VARCHAR(36)` | No | Cuenta propietaria; clave foránea e indexada. |
| `token_hash` | `VARCHAR(64)` | No | Hash único del token de recuperación. |
| `created_at` | `TIMESTAMP` | No | Fecha de creación. |
| `expires_at` | `TIMESTAMP` | No | Caducidad. |
| `used_at` | `TIMESTAMP` | Sí | Fecha de uso o invalidación; nulo si sigue vigente. |

### `p1_auth_attempts`

Intentos asociados a una acción y a un sujeto anonimizado. La aplicación los
usa para limitar solicitudes y elimina registros antiguos.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `scope` | `VARCHAR(32)` | No | Acción limitada, por ejemplo inicio de sesión o registro. |
| `subject_hash` | `VARCHAR(64)` | No | Hash del sujeto de control; no es el correo o IP en texto claro. |
| `created_at` | `TIMESTAMP` | No | Fecha del intento. |

Índice compuesto: `(scope, subject_hash, created_at)`.

### `p1_usage_events`

Marca el uso local de la consulta de elegibilidad para habilitar la encuesta.
`user_id` referencia `p1_users.id` y `session_id` referencia
`p1_sessions.id`; ambos borrados en cascada. No contiene DNI ni datos clínicos.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `user_id` | `VARCHAR(36)` | No | Cuenta propietaria; clave foránea e indexada. |
| `session_id` | `VARCHAR(36)` | No | Sesión local asociada; clave foránea. |
| `event_type` | `VARCHAR(40)` | No | Tipo de evento; actualmente `eligibility_consulted`. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No | Fecha del evento. |

Restricción única: `(session_id, event_type)`, para evitar duplicar el mismo
tipo de evento en una sesión.

### `p1_surveys`

Respuesta de satisfacción asociada a un uso. `user_id` referencia
`p1_users.id` y `usage_event_id` referencia `p1_usage_events.id`; ambas
relaciones se borran en cascada. Solo se permite una respuesta por evento de uso.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | No | Identificador UUID; clave primaria. |
| `user_id` | `VARCHAR(36)` | No | Cuenta que responde; clave foránea e indexada. |
| `usage_event_id` | `VARCHAR(36)` | No | Evento habilitante; clave foránea única. |
| `ease_score` | `INTEGER` | No | Puntaje de facilidad. |
| `satisfaction_score` | `INTEGER` | No | Puntaje de satisfacción. |
| `comment` | `TEXT` | Sí | Comentario opcional. No ingresar información clínica o sensible. |
| `scale_min` | `INTEGER` | No | Mínimo de la escala guardada con la respuesta. |
| `scale_max` | `INTEGER` | No | Máximo de la escala guardada con la respuesta. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No | Fecha de respuesta. |

Restricciones: `scale_min < scale_max`; ambos puntajes deben estar dentro de
la escala guardada en la fila.

### `p1_schema_migrations`

Tabla técnica para que la aplicación conozca las migraciones aplicadas.

| Columna | Tipo SQL | Nulo | Descripción |
|---|---|---:|---|
| `version` | `VARCHAR(40)` | No | Identificador de migración; clave primaria. |
| `applied_at` | `TIMESTAMP WITH TIME ZONE` | No | Fecha de aplicación; por defecto `now()`. |

Se registran `001_p1`, `002_reservations` y `003_reservation_idempotency`.

### Tablas de reservas (migraciones `002_reservations` y `003_reservation_idempotency`)

El diseño P2 compartido también incluía `usuario` y `rol`, pero no se crean:
P1 ya administra las cuentas en `p1_users`. Para evitar duplicar usuarios,
`cita_local.id_usuario` es `VARCHAR(36)` y referencia `p1_users.id`, en vez de
ser el `BIGINT` del DDL original.

| Tabla | Columnas relevantes | Propósito |
|---|---|---|
| `cita_local` | `id_cita_local`, `id_usuario`, `codigo_cita`, `clave_anulacion_cifrada`, `idempotency_key`, `idempotency_fingerprint`, `estado`, `canal`, `fecha`, `hora_inicio`, `hora_fin`, `especialidad`, `consultorio`, `medico`, `financiamiento`, `anulable_hasta`, `fecha_registro`, `fecha_sincronizacion` | Copia de la confirmación de cita del hospital. La clave de idempotencia es única por cuenta y no puede reutilizarse con otro contenido; `codigo_cita` es único. La huella puede ser nula solo en citas registradas antes de la migración 003. |
| `cita_indicacion` | `id_indicacion`, `id_cita_local`, `descripcion`, `orden` | Indicaciones asociadas a la cita; borrado en cascada. |
| `auditoria_api` | `id_auditoria`, `request_id`, `metodo_http`, `endpoint`, `estado_http`, `codigo_error`, `rastreo`, `tiempo_respuesta_ms`, `numero_reintento`, `fecha_hora` | Auditoría técnica. No registra cuerpos, DNI ni tokens. |

`clave_anulacion_cifrada` usa Fernet. `CITA_ENCRYPTION_KEY` se configura en
`backend/.env`; no se debe cambiar después de guardar citas sin migrar las
claves cifradas.

## Relaciones principales

```text
p1_users 1 ─── N p1_sessions
p1_users 1 ─── N p1_recovery_tokens
p1_users 1 ─── N p1_usage_events
p1_sessions 1 ─── N p1_usage_events
p1_usage_events 1 ─── 0..1 p1_surveys
p1_users 1 ─── N cita_local
cita_local 1 ─── N cita_indicacion
```

`p1_challenges`, `p1_auth_attempts` y `p1_schema_migrations` son registros
independientes, sin claves foráneas a las otras tablas.

## Límites actuales para integrar otros módulos

- Las tablas P1 cubren cuentas, seguridad de sesión y encuestas; las tablas P2
  recién integradas guardan citas, indicaciones y auditoría de API.
- Aún no hay tablas de anulaciones, notificaciones, tickets ni chatbot; esos
  agregados siguen pendientes de integración con P3/P4.
- La identidad hospitalaria se mantiene en el adaptador en memoria; DNI, fecha
  de nacimiento y tokens hospitalarios no se persisten en estas tablas.
- Para integrar otro módulo, coordinar primero sus entidades y propietario de
  datos con el equipo. Agregar una migración versionada; no modificar
  migraciones ya aplicadas.
- No ejecutar un DDL antiguo ni copiar datos a producción sin una migración
  revisada y un plan de respaldo.

## Comprobación en PostgreSQL

Desde PowerShell, en la carpeta `backend`:

```powershell
.\.venv\Scripts\python.exe -c "from app.core.config import settings; print(settings.DATABASE_URL.split('@')[-1])"
```

Para listar las tablas `p1_*` de la base configurada, si `psql` está disponible:

```powershell
psql "<cadena-de-conexion>" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'p1_%' ORDER BY table_name;"
```

No pegues la cadena de conexión en chats ni la publiques: contiene credenciales.
