param([int]$Port = 55432)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localRoot = Join-Path $projectRoot '.local'
$pgBin = Join-Path $localRoot 'postgresql/pgsql/bin'
$pgData = Join-Path $localRoot 'pgdata'
$passwordFile = Join-Path $localRoot 'postgres-admin-password'
$envFile = Join-Path $projectRoot 'backend/.env'
New-Item -ItemType Directory -Force $localRoot | Out-Null
function New-LocalSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
function New-FernetKey {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}
if (!(Test-Path (Join-Path $pgBin 'pg_ctl.exe'))) {
    $archive = Join-Path $localRoot 'postgresql-16.15.zip'
    if (!(Test-Path $archive)) {
        Invoke-WebRequest 'https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip' -OutFile $archive
    }
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $localRoot 'postgresql') -Force
}
if (!(Test-Path (Join-Path $pgData 'PG_VERSION'))) {
    New-LocalSecret | Set-Content -LiteralPath $passwordFile -NoNewline
    & (Join-Path $pgBin 'initdb.exe') -D $pgData -U postgres --encoding=UTF8 --locale=C --auth=scram-sha-256 --pwfile=$passwordFile
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar PostgreSQL.' }
}
& (Join-Path $pgBin 'pg_ctl.exe') status -D $pgData *> $null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $pgBin 'pg_ctl.exe') start -D $pgData -l (Join-Path $localRoot 'postgres.log') -o "-p $Port -h 127.0.0.1 -c timezone=America/Lima" -w
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar PostgreSQL.' }
}
if (!(Test-Path $envFile)) {
    $appPassword = New-LocalSecret
    $env:PGPASSWORD = Get-Content -Raw $passwordFile
    try {
        & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE cerocolas LOGIN PASSWORD '$appPassword';"
        if ($LASTEXITCODE -ne 0) { throw 'El rol ya existe o no se pudo crear. Revisar antes de modificar credenciales.' }
        & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p $Port -U postgres -O cerocolas cerocolas_p1
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la base P1.' }
    } finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
    @"
DATABASE_URL=postgresql+psycopg2://cerocolas:${appPassword}@127.0.0.1:${Port}/cerocolas_p1
ENVIRONMENT=development
COOKIE_SECURE=false
FRONTEND_URL=http://127.0.0.1:5173
HOSPITAL_MODE=simulator
HOSPITAL_API_BASE_URL=http://127.0.0.1:4010
HOSPITAL_CLIENT_ID=simulator
HOSPITAL_CLIENT_SECRET=simulator-only-not-a-real-secret
CITA_ENCRYPTION_KEY=$(New-FernetKey)
"@ | Set-Content -LiteralPath $envFile -Encoding utf8
}
$encryptionSetting = Select-String -LiteralPath $envFile -Pattern '^\s*CITA_ENCRYPTION_KEY=(.*)$' | Select-Object -First 1
if (!$encryptionSetting) {
    Add-Content -LiteralPath $envFile -Value "CITA_ENCRYPTION_KEY=$(New-FernetKey)" -Encoding utf8
} elseif (!$encryptionSetting.Matches[0].Groups[1].Value.Trim()) {
    $lines = [System.IO.File]::ReadAllLines($envFile)
    for ($index = 0; $index -lt $lines.Length; $index++) {
        if ($lines[$index] -match '^\s*CITA_ENCRYPTION_KEY=\s*$') {
            $lines[$index] = "CITA_ENCRYPTION_KEY=$(New-FernetKey)"
            break
        }
    }
    [System.IO.File]::WriteAllLines($envFile, $lines)
}
Write-Host "PostgreSQL local disponible en 127.0.0.1:$Port. Las credenciales están en backend/.env (no compartir)."
