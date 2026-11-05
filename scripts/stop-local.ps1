$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localRoot = Join-Path $projectRoot '.local'
$records = Join-Path $localRoot 'processes.json'
if (Test-Path $records) {
    $processRecords = Get-Content -Raw $records | ConvertFrom-Json
    foreach ($record in $processRecords) {
        $proc = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
        if ($proc -and $proc.Path -eq $record.executable -and $proc.StartTime.ToUniversalTime() -eq ([datetime]$record.started).ToUniversalTime()) {
            # Windows venv launchers may own a Python child. Stop only descendants of
            # the verified process created by start-local, before stopping its launcher.
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($proc.Id)"
            foreach ($child in $children) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
            if (Get-Process -Id $record.pid -ErrorAction SilentlyContinue) {
                Stop-Process -Id $record.pid
            }
            Write-Host "$($record.name): detenido."
        }
    }
}
$pgCtl = Join-Path $localRoot 'postgresql/pgsql/bin/pg_ctl.exe'
$pgData = Join-Path $localRoot 'pgdata'
if ((Test-Path $pgCtl) -and (Test-Path $pgData)) {
    & $pgCtl status -D $pgData *> $null
    $status = $LASTEXITCODE
    if ($status -eq 0) {
        & $pgCtl stop -D $pgData -m fast -w
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener PostgreSQL.' }
    } elseif ($status -ne 3) {
        throw "No se pudo comprobar PostgreSQL (codigo $status)."
    } else {
        Write-Host 'PostgreSQL: ya estaba detenido.'
    }
}
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 4010, 5173, 8000, 55432 -ErrorAction SilentlyContinue)
if ($listeners.Count) {
    Write-Warning ('Siguen ocupados estos puertos: ' + (($listeners.LocalPort | Sort-Object -Unique) -join ', ') + '. No se cerraron procesos ajenos al registro del proyecto.')
} else {
    Write-Host 'Puertos 4010, 5173, 8000 y 55432 libres.'
}
exit 0
