param(
    [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Step($Message) {
    Write-Host "[dev] $Message"
}

foreach ($port in $Ports) {
    $connections = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    if ($connections.Count -eq 0) {
        Write-Step "Port $port is not listening."
        continue
    }

    foreach ($connection in $connections) {
        $pidValue = $connection.OwningProcess
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
        $commandLine = $processInfo.CommandLine
        $isProjectProcess = $false

        if ($commandLine) {
            $isProjectProcess = $commandLine -like "*$RepoRoot*" -or
                $commandLine -like "*uvicorn app.main:app*" -or
                $commandLine -like "*vite*"
        }

        if ($isProjectProcess) {
            Write-Step "Stopping PID $pidValue on port $port"
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        }
        else {
            Write-Warning "Port $port is used by PID $pidValue, but it does not look like this project. Skipped."
        }
    }
}
