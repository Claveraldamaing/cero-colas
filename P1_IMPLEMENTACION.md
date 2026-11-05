# Cero Colas — implementación del practicante 1

Actualizado el 5 de noviembre de 2026. Alcance: `doccumentacion/P1-Usuarios, identificación, dashboards y satisfacción.docx`, reparto entregado por el equipo y contrato `doccumentacion/apicitas/openapi.yaml`.

## Uso en esta computadora

Puedes hacer doble clic en `INICIAR_CERO_COLAS.cmd` para iniciar y en `DETENER_CERO_COLAS.cmd` para apagar frontend, backend, simulador y PostgreSQL local. Cerrar el navegador o la ventana del lanzador no detiene los servicios. El cierre conserva la base de datos y solo detiene los procesos registrados por el lanzador y la instancia local de PostgreSQL. Si otro programa ocupa esos puertos, se avisa sin cerrarlo. Puedes ejecutar el cierre aunque ya esté detenido.

Desde la raíz del proyecto, en PowerShell:

```powershell
.\scripts\start-local.ps1
```

Abre **http://127.0.0.1:5173**. La API está en **http://127.0.0.1:8000/docs**. PostgreSQL local escucha únicamente en `127.0.0.1:55432`; Prism, en `127.0.0.1:4010`.

Las dos cuentas de demostración (administrador y paciente) tienen contraseñas aleatorias, guardadas en **`.local/ACCESOS.md`**. No compartir ni subir ese archivo. También puedes crear una cuenta desde la pantalla de registro. No hay contraseña administrativa predeterminada en el código.

Datos hospitalarios de prueba del contrato: DNI `40123456`, nacimiento `1985-03-14`. Prism responde con ejemplos: **no verifica la identidad ni el SIS de una persona real**. Las fechas y pacientes que devuelve proceden del YAML entregado. El aviso de simulación permanece visible.

Para detener los procesos iniciados por el lanzador:

```powershell
.\scripts\stop-local.ps1
```

El prototipo anterior y su SQLite fueron retirados. La aplicación P1 no publica rutas sin autenticación ni operaciones que finjan éxito. No se importaron datos de pacientes a PostgreSQL.

## Funcionalidades implementadas

| Bloque | Comportamiento |
|---|---|
| Registro y acceso | Registro por nombre/correo/contraseña, login, logout y correo normalizado único. El registro público siempre crea rol Paciente. |
| Seguridad | Contraseñas scrypt, sesiones opacas en cookie HttpOnly, CSRF, expiración, intentos limitados, desafío aritmético de un solo uso, cierre de sesiones tras cambio de contraseña o estado/rol. |
| Cuenta | Perfil, preferencias de apariencia clara/oscura/sistema, idioma español y preferencia de correo. Cambiar una preferencia no envía notificaciones. |
| Recuperación | Enlaces de 30 minutos y un solo uso; respuesta genérica sin revelar la existencia de cuentas; SMTP configurable o buzón local en desarrollo. |
| Administración | Lista paginada y búsqueda, activar/desactivar cuentas, asignar roles; no permite desactivarse ni retirarse el propio rol administrativo. |
| Identificación | DNI y fecha de nacimiento, consentimiento y protección contra intentos; llamada servidor a servidor al endpoint entregado. |
| Elegibilidad | SIS, condición, referencias, especialidades, próxima fecha permitida, mensajes por motivo, expiración y cambio de paciente. |
| Inicio del paciente | Estado de identidad, resumen de elegibilidad y próxima cita consultada con `GET /citas`. El resumen de notificaciones indica que requiere integración P3. |
| Resumen administrativo | Cuentas reales de la base, salud del servicio/canal, promedios y distribución de encuestas guardadas. Los contadores que dependen de P2/P3/P4 muestran «Sin integrar». |
| Satisfacción | Facilidad y satisfacción de 1 a 5, comentario opcional, una respuesta por sesión local que haya completado una consulta de elegibilidad. La escala y la condición de habilitación son decisiones del prototipo, no reglas atribuidas al hospital. |

La verificación aritmética es una protección básica de desarrollo acompañada de límites de intentos; no se presenta como un CAPTCHA de producción.

## Arquitectura y persistencia

```text
React (cookie local, sin tokens del hospital)
    → FastAPI /api/v1 (autenticación, autorización, CSRF)
        → PostgreSQL (cuentas, sesiones locales, uso y encuestas)
        → Prism / API del hospital (OAuth + identificación + elegibilidad)
```

`backend/app/p1/auth.py` administra cuentas y permisos. `hospital.py` contiene el adaptador de `apicitas`; `portal.py`, elegibilidad, dashboards y encuestas. `frontend/src/p1` contiene las pantallas activas; el código del prototipo anterior fue retirado.

Tablas P1: `p1_users`, `p1_sessions`, `p1_challenges`, `p1_recovery_tokens`, `p1_auth_attempts`, `p1_usage_events`, `p1_surveys`, `p1_schema_migrations`. Sesiones y recuperación guardan hashes, nunca el token local en texto claro. El adaptador no persiste DNI, nacimiento, token de paciente ni token de cliente hospitalario; estos últimos permanecen en memoria del servidor. El comentario de la encuesta advierte que no debe contener información clínica.

La migración inicial es aditiva, versionada e idempotente. Se ejecuta al arrancar y también manualmente:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.migrate
```

El DDL de referencia está en `backend/database/schema_p1.sql`. Cambios futuros de esquema necesitan una nueva migración; `create_all` no modifica columnas ya existentes.

## Prueba de demostración

1. Crear una cuenta o entrar como paciente de prueba.
2. Abrir Identificación, usar los datos de prueba del contrato, aceptar el aviso y resolver la verificación.
3. Revisar SIS, condición, referencias, especialidades y advertencia sobre vigencia pendiente.
4. Abrir Mi inicio para consultar la próxima cita del simulador.
5. Responder Satisfacción y comprobar que no permite duplicar la respuesta en esa sesión.
6. Cambiar nombre, preferencias y contraseña. Cerrar sesión.
7. Entrar como administrador, revisar estadísticas de satisfacción y administrar una cuenta de paciente.

Recuperación local: solicitarla desde la pantalla y leer el enlace desde el equipo del desarrollador:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.p1.auth local-mail
```

El comando imprime un enlace privado de recuperación. No copiarlo a registros públicos. En desarrollo los mensajes se guardan en `backend/.local/mailbox/recovery.jsonl`; no existe una ruta HTTP para leer ese buzón. Con SMTP configurado el enlace se envía por ese servicio. El frontend retira el token de la URL después de abrirlo.

Para crear otro administrador (solicita la contraseña sin mostrarla):

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.p1.auth create-admin --email tu-correo --name "Administrador"
```

## Contrato para integrar a los otros practicantes

| Consumidor | Integración prevista |
|---|---|
| P2 · Reserva | Reutilizar `current_user`, `require_csrf` y el adaptador en backend. Obtener `reserve_ready`, `specialties_allowed` y referencias. No mandar tokens hospitalarios al navegador. La cuenta local no sustituye la identificación. |
| P3 · Citas/notificaciones | La próxima cita ya consulta `/citas`; detalle, anulaciones, QR y notificaciones corresponden a ese módulo. Agregar su fuente al resumen `notifications`, hoy `integrated:false`. |
| P4 · Soporte/analítica | Aportar agregados de tickets y chatbot; definir los contadores de actividad junto a P2/P3. Conectar esos valores al resumen administrativo, hoy `null`. |

Los endpoints locales se documentan en Swagger. Principales rutas: `/auth/challenge`, `/auth/register`, `/auth/login`, `/auth/me`, `/auth/profile`, `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/logout`; `/admin/users`; `/portal/policies`, `/portal/identify`, `/portal/identity`, `/portal/eligibility`, `/portal/dashboard`, `/portal/admin/dashboard`, `/portal/surveys/status` y `/portal/surveys`.

Las operaciones autenticadas de escritura requieren `X-CSRF-Token`, recibido al iniciar sesión o consultar `/auth/me`. Los errores usan `detail.code` y `detail.message`; si el hospital entrega `rastreo` o `Retry-After`, se informa al usuario. No hay sustitución silenciosa de fallos por pacientes o citas ficticios.

## Definiciones y servicios todavía externos

- **Vigencia de referencias:** falta la regla de Admisión. `REFERENCE_MAX_AGE_DAYS` queda sin definir; `reserve_ready` permanece falso. El parámetro permite probar una regla de días cuando el hospital la confirme. Si la regla real es más compleja, se debe adaptar el evaluador.
- **Privacidad institucional:** se muestra un aviso provisional de pruebas. El modo `hospital` bloquea la identificación hasta configurar texto y aprobación de la política. No marcarla aprobada sin el documento correspondiente.
- **Ambiente hospitalario real:** faltan URL, client_id, client_secret e IP de salida autorizada. El prototipo está conectado a Prism, no al hospital.
- **Producción:** requiere política aprobada, protección CAPTCHA adecuada, correo institucional, HTTPS, configuración del proxy/IP real y auditoría del hospital. SMTP se implementó pero no se probó un envío real por falta de credenciales.
- **Dependencias de equipo:** reservar, anular, tickets, chatbot y envío de notificaciones no se implementaron como operaciones ficticias dentro de P1.

Usar **un solo worker**: las sesiones hospitalarias y límites de identificación están en memoria. Reiniciar FastAPI exige identificar nuevamente al paciente. Escalar requiere un diseño compartido y efímero aprobado que siga respetando la guía de datos del hospital.

## Instalación en otra máquina

Requiere Python 3.12, Node.js compatible con Vite 8 y PowerShell. Desde la raíz:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm.cmd ci --prefix frontend
npm.cmd ci --prefix tools
.\scripts\setup-local.ps1
.\backend\.venv\Scripts\python.exe scripts/create-demo-accounts.py
.\scripts\start-local.ps1
```

El instalador local usa los [binarios PostgreSQL publicados por EDB](https://www.enterprisedb.com/download-postgresql-binaries), crea un clúster de desarrollo propio en `.local/pgdata`, exige contraseña SCRAM y genera credenciales aleatorias. No instala un servicio global ni usa datos de otra instalación. `.local/`, `backend/.env` y los buzones están excluidos de Git y del contexto Docker.

También hay un Compose con PostgreSQL, Prism y frontend compilado servido por FastAPI. Definir `POSTGRES_PASSWORD` con un secreto alfanumérico propio antes de `docker compose -f backend/docker-compose.yml up --build`. Esa configuración es para demostración local; no es una configuración final del servidor hospitalario. Docker no está instalado en esta computadora, por lo que el Compose se entrega sin prueba de ejecución.

## Verificación

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest tests --postgres -q
cd ../frontend
npm.cmd run build
npm.cmd run lint:p1
npm.cmd audit
```

La opción `--postgres` crea un esquema temporal aleatorio para cada prueba y elimina solo ese esquema al terminar; no toca las tablas públicas. Se verificaron 26 pruebas en SQLite y las mismas 26 en PostgreSQL: sesiones, CSRF, roles, intentos, recuperación, contrato hospitalario, errores, privacidad y encuestas. Hay una advertencia de deprecación de `httpx` en el cliente de pruebas de Starlette; no es un fallo de ejecución.

Se verificó el recorrido con Edge en escritorio y vista móvil de 390 px. La auditoría posterior a la actualización de dependencias no reportó vulnerabilidades conocidas en los requisitos del backend ni en el frontend en la fecha de revisión. Las pruebas hospitalarias son contra Prism o fixtures identificadas; no prueban disponibilidad ni reglas del servidor real.
