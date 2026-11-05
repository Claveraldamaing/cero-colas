$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'setup-local.ps1')
$logRoot = Join-Path $projectRoot '.local'
$node = (Get-Command node.exe).Source
$python = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
$prism = Join-Path $projectRoot 'tools/node_modules/@stoplight/prism-cli/dist/index.js'
if (!(Test-Path $prism)) { throw 'Ejecuta npm.cmd ci --prefix tools primero.' }
if (!(Test-Path $python)) { throw 'Crea backend/.venv e instala backend/requirements.txt.' }
$jobs = @(
    @{Name='prism'; Port=4010; File=$node; Args=@('"' + $prism + '"','mock','"' + (Join-Path $projectRoot 'doccumentacion/apicitas/openapi.yaml') + '"','--host','127.0.0.1','--port','4010'); Cwd=$projectRoot},
    @{Name='backend'; Port=8000; File=$python; Args=@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-proxy-headers','--no-access-log'); Cwd=(Join-Path $projectRoot 'backend')},
    @{Name='frontend'; Port=5173; File=$node; Args=@('"' + (Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js') + '"','--host','127.0.0.1','--port','5173','--strictPort'); Cwd=(Join-Path $projectRoot 'frontend')}
)
$saved = @()
$recordPath = Join-Path $logRoot 'processes.json'
if (Test-Path $recordPath) {
    $processRecords = Get-Content -Raw $recordPath | ConvertFrom-Json
    foreach ($record in $processRecords) {
        $existing = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.Path -eq $record.executable -and $existing.StartTime.ToUniversalTime() -eq ([datetime]$record.started).ToUniversalTime()) { $saved += $record }
    }
}
foreach ($job in $jobs) {
    if (Get-NetTCPConnection -State Listen -LocalPort $job.Port -ErrorAction SilentlyContinue) {
        Write-Host "$($job.Name): puerto $($job.Port) ocupado; no se modifica el proceso existente."
        continue
    }
    $proc = Start-Process -FilePath $job.File -ArgumentList $job.Args -WorkingDirectory $job.Cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "$($job.Name).log") -RedirectStandardError (Join-Path $logRoot "$($job.Name).err.log")
    $saved += @{name=$job.Name; pid=$proc.Id; executable=$job.File; started=$proc.StartTime.ToString('o')}
}
if ($saved.Count) { $saved | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $logRoot 'processes.json') }
Write-Host 'Portal: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs'
Write-Host 'Los servicios pueden tardar unos segundos. Registros en .local/.'
