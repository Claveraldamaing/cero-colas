# Backend P1 — Cero Colas

La implementación activa utiliza FastAPI y PostgreSQL. La guía completa de funciones,
arranque, cuentas de demostración, contratos y límites está en [P1_IMPLEMENTACION.md](../P1_IMPLEMENTACION.md).

## Arranque local

Desde la raíz: `./scripts/start-local.ps1`. Inicia PostgreSQL (55432), Prism (4010),
FastAPI (8000) y Vite (5173). Usa los accesos privados de `.local/ACCESOS.md`.
Para detener: `./scripts/stop-local.ps1`.

El archivo `.env` se lee desde `backend/.env`, independientemente del directorio actual.
La base activa es `cerocolas_p1`; SQLite se utiliza únicamente en las pruebas aisladas.
El prototipo anterior y su archivo SQLite fueron retirados; SQLite solo se usa en las pruebas aisladas.

## Migración y pruebas

Desde backend:

```powershell
.\.venv\Scripts\python.exe -m app.migrate
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest tests --postgres -q
```

La segunda ejecución de pruebas usa esquemas PostgreSQL temporales; no modifica
los usuarios reales de `public`. El DDL de referencia es `database/schema_p1.sql`.

## Administración local

```powershell
.\.venv\Scripts\python.exe -m app.p1.auth create-admin --email tu-correo --name Administrador
.\.venv\Scripts\python.exe -m app.p1.auth local-mail
```

La primera orden pide una contraseña; la segunda muestra un enlace privado de recuperación
del buzón local de desarrollo. No publicar esa salida.

## Despliegue de demostración con Docker

El Compose de esta carpeta se ejecuta desde la raíz:

```powershell
docker compose -f backend/docker-compose.yml up --build
```

Definir previamente `POSTGRES_PASSWORD` en el entorno (secreto alfanumérico propio).
El contenedor sirve la interfaz compilada en `http://localhost:8000` y utiliza un volumen
nuevo `cerocolas_p1_pgdata`, no la base del prototipo anterior. No se probó Docker en esta
máquina porque no está instalado. La ejecución nativa sí se verificó con PostgreSQL.

## Restricciones explícitas

- Un worker: los tokens hospitalarios se mantienen solo en memoria del backend.
- Modo simulador, sin credenciales ni acceso real al hospital.
- Referencias bloqueadas para reserva hasta que Admisión defina su vigencia.
- La cuenta local es independiente de la identificación hospitalaria.
- Producción necesita política institucional, HTTPS/proxy, SMTP y CAPTCHA adecuados,
  configuración de IP de salida y auditoría del hospital. El desafío aritmético es de desarrollo.
- Las rutas del prototipo anterior fueron retiradas; la aplicación activa solo registra los routers P1.
