param(
    [switch]$OpenBrowser,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$LogsDir = Join-Path $RepoRoot ".runtime-logs"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$NpmCmd = "npm.cmd"
$BackendBase = "http://127.0.0.1:$BackendPort"
$FrontendBase = "http://localhost:$FrontendPort"
$FrontendApiBase = "/api/v1"

function Write-Step($Message) {
    Write-Host "[dev] $Message"
}

function Test-Http($Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-ListeningProcessIds($Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Wait-Http($Url, $Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Http $Url) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

if (!(Test-Path $PythonExe)) {
    throw "Backend venv not found: $PythonExe"
}
if (!(Test-Path (Join-Path $FrontendDir "node_modules"))) {
    throw "Frontend dependencies not found. Run 'npm install' in frontend first."
}

New-Item -ItemType Directory -Force $LogsDir | Out-Null

$backendPids = Get-ListeningProcessIds $BackendPort
if ($backendPids.Count -eq 0) {
    Write-Step "Starting backend on $BackendBase ..."
    Start-Process `
        -FilePath $PythonExe `
        -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort" `
        -WorkingDirectory $BackendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogsDir "backend-$BackendPort.out.log") `
        -RedirectStandardError (Join-Path $LogsDir "backend-$BackendPort.err.log") | Out-Null
}
else {
    Write-Step "Backend port $BackendPort is already in use by PID(s): $($backendPids -join ', ')"
}

if (Wait-Http "$BackendBase/health" 30) {
    Write-Step "Backend is ready: $BackendBase"
}
else {
    Write-Warning "Backend did not become ready. Check .runtime-logs/backend-$BackendPort.err.log"
}

$frontendPids = Get-ListeningProcessIds $FrontendPort
if ($frontendPids.Count -eq 0) {
    Write-Step "Starting frontend on $FrontendBase ..."
    $frontendCommand = "set `"VITE_BACKEND_BASE=$FrontendApiBase`" && npm.cmd run dev -- --host localhost --port $FrontendPort"
    Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList "/c $frontendCommand" `
        -WorkingDirectory $FrontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogsDir "frontend-$FrontendPort.out.log") `
        -RedirectStandardError (Join-Path $LogsDir "frontend-$FrontendPort.err.log") | Out-Null
}
else {
    Write-Step "Frontend port $FrontendPort is already in use by PID(s): $($frontendPids -join ', ')"
}

if (Wait-Http $FrontendBase 30) {
    Write-Step "Frontend is ready: $FrontendBase"
}
else {
    Write-Warning "Frontend did not become ready. Check .runtime-logs/frontend-$FrontendPort.err.log"
}

Write-Host ""
Write-Host "Frontend: $FrontendBase"
Write-Host "Backend docs: $BackendBase/docs"
Write-Host "Backend health: $BackendBase/health"
Write-Host "Logs: $LogsDir"

if ($OpenBrowser) {
    Start-Process $FrontendBase
}
