$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project virtual environment is missing. Follow the README setup instructions.'
}
& $pythonPath (Join-Path $projectRoot 'scripts\local_postgres.py') start
if ($LASTEXITCODE -ne 0) { throw 'The project database could not start.' }
try {
    $existing = Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2
} catch { $existing = $null }
if ($existing) {
    if ($existing.info.title -ne 'API Performance Profiler') {
        throw 'Port 8000 belongs to another application.'
    }
    Write-Output 'Dashboard is already running: http://127.0.0.1:8000/'
    return
}
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = 'postgresql://profiler:local-profiler-dev@127.0.0.1:5434/profiler'
    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'data\api.stdout.log') -RedirectStandardError (Join-Path $projectRoot 'data\api.stderr.log') -PassThru
} finally {
    $env:DATABASE_URL = $previousDatabaseUrl
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if ($apiProcess.HasExited) { throw 'API startup failed. See data\api.stderr.log.' }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2
        if ($health.status -eq 'ok') {
            Write-Output 'Dashboard is running: http://127.0.0.1:8000/'
            return
        }
    } catch { }
    Start-Sleep -Milliseconds 500
}
throw 'The API did not become ready. See data\api.stderr.log.'
