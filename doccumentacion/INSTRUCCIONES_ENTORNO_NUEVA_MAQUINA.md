# Preparar y ejecutar Cero Colas en una nueva máquina

Guía para **Windows x64 con PowerShell**. Actualizada el 5 de noviembre de 2026.

La implementación activa es **P1**: React/Vite, FastAPI, PostgreSQL local y Prism. La referencia funcional completa está en [`P1_IMPLEMENTACION.md`](../P1_IMPLEMENTACION.md).

## 1. Alcance

| Servicio | URL / puerto |
|---|---|
| Portal React/Vite | http://127.0.0.1:5173 |
| API FastAPI + Swagger | http://127.0.0.1:8000/docs |
| Prism (simulador hospitalario) | http://127.0.0.1:4010 |
| PostgreSQL local | 127.0.0.1:55432 |

- La aplicación **no usa SQLite en ejecución**. SQLite solo se usa en las pruebas aisladas por defecto; la opción `--postgres` usa esquemas temporales.
- El frontend **no necesita `frontend/.env`**: llama a `/api/v1` con rutas relativas y Vite hace proxy a FastAPI (`vite.config.js`).
- No se usan credenciales reales del hospital. `HOSPITAL_MODE=simulator` y Prism devuelven ejemplos del contrato `doccumentacion/apicitas/openapi.yaml`.
- Docker es opcional para una demostración; el arranque local no lo requiere.

## 2. Requisitos

- Windows x64 y PowerShell.
- Python **3.12** (probado con 3.12.15).
- Node.js LTS compatible con Vite 8 (probado con Node 24.19.0).
- No hace falta Git: el proyecto no tiene repositorio `.git`.
- No copiar `.venv`, `node_modules`, `__pycache__` ni `dist` de otra máquina.

## 3. Ubicar el proyecto

Abrir PowerShell, sustituir **una sola vez** la ruta y comprobar los archivos necesarios:

```powershell
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath 'C:\RUTA\CeroColas').Path
Set-Location -LiteralPath $projectRoot

foreach ($relative in @(
    'backend/requirements-dev.txt',
    'frontend/package-lock.json',
    'tools/package.json',
    'scripts/start-local.ps1',
    'scripts/stop-local.ps1',
    'doccumentacion/apicitas/openapi.yaml'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative))) {
        throw "Falta un archivo requerido: $relative"
    }
}
Get-ChildItem -Force
```

## 4. Instalar las herramientas base

Primero comprobar qué existe:

```powershell
Get-Command node, npm.cmd, uv -ErrorAction SilentlyContinue |
    Select-Object Name, Source
```

Si falta Node LTS o uv, instalar solo lo que falte:

```powershell
winget install --id OpenJS.NodeJS.LTS --exact --source winget --accept-package-agreements --accept-source-agreements
winget install --id astral-sh.uv --exact --source winget --accept-package-agreements --accept-source-agreements
```

Si WinGet falla, usar el instalador Windows LTS de [Node.js](https://nodejs.org/en/download) y el instalador oficial de [uv](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
```

Cerrar y abrir PowerShell para actualizar el PATH. Después comprobar:

```powershell
node --version
npm.cmd --version
uv --version
```

Usar `npm.cmd` evita que una política de PowerShell bloquee `npm.ps1`.

## 5. Crear el entorno de Python e instalar dependencias

```powershell
Set-Location -LiteralPath $projectRoot

uv python install 3.12.15
uv venv --python 3.12.15 backend/.venv
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt

npm.cmd ci --prefix frontend
npm.cmd ci --prefix tools
```

`requirements-dev.txt` incluye `requirements.txt` y las herramientas de prueba. `npm.cmd ci --prefix tools` instala Prism, necesario para el simulador hospitalario.

Si no se usa `uv`, la alternativa es:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Comprobar el entorno:

```powershell
.\backend\.venv\Scripts\python.exe --version
.\backend\.venv\Scripts\python.exe -m pip check
.\backend\.venv\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy, pydantic, pydantic_settings, psycopg2, httpx; print('Importaciones OK')"
```

## 6. Preparar PostgreSQL local y `backend/.env`

Desde la raíz:

```powershell
.\scripts\setup-local.ps1
```

El script realiza estas tareas:

1. Descarga los binarios de PostgreSQL 16.15 en `.local/postgresql` si no existen.
2. Inicializa el clúster de desarrollo en `.local/pgdata` con autenticación SCRAM.
3. Arranca PostgreSQL únicamente en `127.0.0.1:55432`.
4. Crea el rol `cerocolas` y la base `cerocolas_p1`.
5. Genera `backend/.env` con credenciales aleatorias si el archivo no existe.

Variables activas de `backend/.env`:

```text
DATABASE_URL=postgresql+psycopg2://cerocolas:...@127.0.0.1:55432/cerocolas_p1
ENVIRONMENT=development
COOKIE_SECURE=false
FRONTEND_URL=http://127.0.0.1:5173
HOSPITAL_MODE=simulator
HOSPITAL_API_BASE_URL=http://127.0.0.1:4010
HOSPITAL_CLIENT_ID=simulator
HOSPITAL_CLIENT_SECRET=simulator-only-not-a-real-secret
```

Notas:

- Si `backend/.env` ya existe, `setup-local.ps1` no lo sobrescribe. Revisar que `DATABASE_URL` apunte a `cerocolas_p1`.
- No compartir `backend/.env`, `.local/postgres-admin-password` ni `.local/ACCESOS.md`.
- Para usar el hospital real habría que cambiar `HOSPITAL_MODE`, las credenciales y la política de privacidad. Eso no forma parte de esta instalación local.

## 7. Cuentas de demostración (opcional)

```powershell
.\backend\.venv\Scripts\python.exe scripts/create-demo-accounts.py
```

Crea las cuentas `admin@cerocolas.test` y `paciente@cerocolas.test` con contraseñas aleatorias y guarda los accesos en `.local/ACCESOS.md`. Si las cuentas ya existen, no las sobrescribe. También se puede crear una cuenta desde la pantalla de registro.

Crear otro administrador:

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
.\.venv\Scripts\python.exe -m app.p1.auth create-admin --email tu-correo --name "Administrador"
```

Ver el último enlace de recuperación local:

```powershell
.\.venv\Scripts\python.exe -m app.p1.auth local-mail
```

En desarrollo, los mensajes se guardan en `backend/.local/mailbox/recovery.jsonl`. El buzón se crea cuando se necesita; no hay una ruta HTTP para leerlo.

## 8. Arrancar el proyecto

Desde la raíz:

```powershell
.\scripts\start-local.ps1
```

También se puede hacer doble clic en `INICIAR_CERO_COLAS.cmd`.

El script inicia PostgreSQL, Prism, FastAPI y Vite. Los registros quedan en `.local/*.log`. Abrir:

- Portal: http://127.0.0.1:5173
- Swagger: http://127.0.0.1:8000/docs

Para detener todo:

```powershell
.\scripts\stop-local.ps1
```

También se puede usar `DETENER_CERO_COLAS.cmd`. El cierre conserva la base de datos en `.local/pgdata`.

## 9. Verificar antes de dar por terminada la instalación

```powershell
$front = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 15
$health = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 10
$docs = Invoke-WebRequest 'http://127.0.0.1:8000/docs' -UseBasicParsing -TimeoutSec 10

[pscustomobject]@{
    FrontendHTTP = $front.StatusCode
    EstadoAPI = $health.status
    BaseDatos = $health.database
    Modulo = $health.module
    ModoHospital = $health.hospital_mode
    SwaggerHTTP = $docs.StatusCode
}
```

Esperado: HTTP 200 en frontend y Swagger; API `healthy`, base `postgresql`, módulo `P1` y modo `simulator`.

Comprobar las tablas activas:

```powershell
$env:PGPASSWORD = Get-Content -Raw (Join-Path $projectRoot '.local/postgres-admin-password')
& (Join-Path $projectRoot '.local/postgresql/pgsql/bin/psql.exe') -h 127.0.0.1 -p 55432 -U postgres -d cerocolas_p1 -c "\dt p1_*"
Remove-Item Env:PGPASSWORD
```

Deben aparecer las 8 tablas `p1_*`: `p1_auth_attempts`, `p1_challenges`, `p1_recovery_tokens`, `p1_schema_migrations`, `p1_sessions`, `p1_surveys`, `p1_usage_events` y `p1_users`.

Ejecutar las pruebas:

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest tests --postgres -q

Set-Location -LiteralPath (Join-Path $projectRoot 'frontend')
npm.cmd run build
npm.cmd run lint:p1
```

Las pruebas por defecto usan SQLite en memoria. `--postgres` crea un esquema temporal aleatorio y lo elimina al terminar; no toca las tablas públicas.

## 10. Detener todos los servicios

```powershell
.\scripts\stop-local.ps1
```

El script detiene únicamente los procesos registrados por el lanzador y la instancia local de PostgreSQL. Al finalizar deben quedar libres los puertos `4010`, `5173`, `8000` y `55432`.

Si otro programa ocupa uno de esos puertos, el script avisa y no lo cierra. No detener todos los procesos `python.exe` o `node.exe` del equipo.

## 11. Problemas conocidos

| Síntoma | Qué comprobar |
|---|---|
| `backend/.env` no existe | Ejecutar `.\scripts\setup-local.ps1`. |
| Faltan dependencias de Python | Recrear `backend/.venv` con el paso 5. |
| Falta Prism | Ejecutar `npm.cmd ci --prefix tools`. |
| Frontend no conecta con la API | Verificar que Vite esté en `5173` y FastAPI en `8000`. No crear `VITE_API_BASE_URL`; la ruta `/api/v1` es relativa y usa el proxy de Vite. |
| PostgreSQL no arranca | Revisar `.local/postgres.log` y que el puerto `55432` esté libre. |
| Un puerto está ocupado | Identificar el proceso propietario. `start-local.ps1` omite el servicio si el puerto ya está en uso; `stop-local.ps1` solo cierra procesos registrados por el proyecto. |
| Las pruebas fallan con PostgreSQL | Confirmar que `DATABASE_URL` apunta a `cerocolas_p1` y que PostgreSQL está activo. |

## 12. Docker (opcional)

El Compose de demostración se ejecuta desde la raíz:

```powershell
$env:POSTGRES_PASSWORD = 'un-secreto-alfanumerico-propio'
docker compose -f backend/docker-compose.yml up --build
```

Sirve la interfaz compilada en http://localhost:8000 y usa un volumen nuevo, no la base local. No se probó Docker en esta máquina porque no está instalado.

## 13. Datos y limpieza

- `.local/` y `backend/.env` son locales y están excluidos de Git y Docker.
- `.local/pgdata` contiene la base PostgreSQL. No borrarlo si se quieren conservar los datos.
- `frontend/dist` es generado por `npm.cmd run build` y puede regenerarse.
- El prototipo anterior, su SQLite y los artefactos de agentes IA fueron retirados; no se necesitan para ejecutar P1.
