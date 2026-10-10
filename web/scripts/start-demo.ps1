<#
.SYNOPSIS
Starts the local ConjunctionTriage Next.js demonstration without stopping existing services.
.EXAMPLE
.\scripts\start-demo.ps1 -NoBrowser
.EXAMPLE
.\scripts\start-demo.ps1 -Production -StaticOnly
#>
[CmdletBinding()]
param(
    [switch]$Production,
    [switch]$NoBrowser,
    [switch]$StaticOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$webRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $webRoot '..'))
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$nextPath = Join-Path $webRoot 'node_modules\next\dist\bin\next'
$logRoot = Join-Path $repoRoot 'processed\next-demo'
$webUrl = 'http://127.0.0.1:3000'
$apiUrl = 'http://127.0.0.1:8000'
$startupDeadline = [DateTime]::UtcNow.AddSeconds(45)

function Test-PortOccupied {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-ProjectApi {
    try {
        $reply = Invoke-RestMethod -Uri "$apiUrl/health" -TimeoutSec 2 -ErrorAction Stop
        $checkNames = @($reply.checks.PSObject.Properties.Name)
        return ($checkNames -contains 'sgp4') -and ($checkNames -contains 'tracss_store') -and
            (@('ok', 'degraded') -contains $reply.status)
    }
    catch {
        return $false
    }
}

function Test-ProjectWeb {
    try {
        $reply = Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        return $reply.StatusCode -eq 200 -and
            $reply.Content -match '(?is)<title>[^<]*ConjunctionTriage[^<]*orbital observatory[^<]*</title>'
    }
    catch {
        return $false
    }
}

function Wait-ProjectService {
    param(
        [scriptblock]$Check,
        [System.Diagnostics.Process]$Process,
        [string]$Name,
        [string]$ErrorLog
    )
    while ([DateTime]::UtcNow -lt $startupDeadline) {
        if (& $Check) { return }
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "$Name exited before becoming ready. Inspect $ErrorLog. No processes were stopped."
        }
        Start-Sleep -Milliseconds 400
    }
    throw "$Name did not become ready within the startup window. It may still be starting; inspect $ErrorLog and retry. No processes were stopped."
}

function New-LogPaths {
    param([string]$Name)
    if (-not (Test-Path -LiteralPath $logRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $suffix = [Guid]::NewGuid().ToString('N').Substring(0, 6)
    return @{
        Output = Join-Path $logRoot "$Name-$stamp-$suffix.stdout.log"
        Error = Join-Path $logRoot "$Name-$stamp-$suffix.stderr.log"
    }
}

try {
    $nodeCommand = Get-Command node.exe -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $nextPath -PathType Leaf)) {
        throw "Next.js dependencies are missing. Run npm ci from $webRoot first."
    }
    if ($Production -and -not (Test-Path -LiteralPath (Join-Path $webRoot '.next\BUILD_ID') -PathType Leaf)) {
        throw "A production build is required. Run npm run build from $webRoot first."
    }
    foreach ($dataFile in @('events.json', 'summary.json', 'phase7_results.json', 'triage_example.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $webRoot "public\data\$dataFile") -PathType Leaf)) {
            throw "The static export $dataFile is missing. Run npm run sync-data from $webRoot first."
        }
    }

    # Verify occupied ports before starting anything. A successful response alone is not
    # sufficient: another project may also expose a health endpoint or a web page.
    $apiOccupied = Test-PortOccupied -Port 8000
    $webOccupied = Test-PortOccupied -Port 3000
    $apiReady = $apiOccupied -and (Test-ProjectApi)
    $webReady = $webOccupied -and (Test-ProjectWeb)
    if (-not $StaticOnly -and $apiOccupied -and -not $apiReady) {
        throw 'Port 8000 is occupied by a service that could not be verified as the ConjunctionTriage API. Resolve the conflict manually; nothing was stopped.'
    }
    if ($webOccupied -and -not $webReady) {
        throw 'Port 3000 is occupied by a service that could not be verified as ConjunctionTriage: An orbital observatory. Resolve the conflict manually; nothing was stopped.'
    }

    if ($StaticOnly) {
        Write-Host 'Static-only mode: the launcher will not start the Python API.'
    }
    elseif ($apiReady) {
        Write-Host "Reusing the verified ConjunctionTriage API at $apiUrl."
    }
    else {
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "The Python environment is missing at $pythonPath. Configure the root project environment, or use -StaticOnly for the recorded demonstration."
        }
        $apiLogs = New-LogPaths -Name 'api'
        Write-Host 'Starting the Python API on 127.0.0.1:8000...'
        $apiProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $repoRoot `
            -ArgumentList @('-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000') `
            -WindowStyle Hidden -RedirectStandardOutput $apiLogs.Output -RedirectStandardError $apiLogs.Error -PassThru
        Wait-ProjectService -Check { Test-ProjectApi } -Process $apiProcess -Name 'Python API' -ErrorLog $apiLogs.Error
        Write-Host "API ready (PID $($apiProcess.Id))."
    }

    if ($webReady) {
        Write-Host "Reusing the verified Next.js app at $webUrl (existing mode unchanged)."
    }
    else {
        $nextMode = if ($Production) { 'start' } else { 'dev' }
        $webLogs = New-LogPaths -Name 'next'
        # Start-Process joins ArgumentList on Windows, so quote the script path itself.
        # A Windows file path cannot contain a double quote; the value is never shell code.
        $quotedNextPath = '"' + $nextPath + '"'
        Write-Host "Starting Next.js ($nextMode) on 127.0.0.1:3000..."
        $webProcess = Start-Process -FilePath $nodeCommand.Source -WorkingDirectory $webRoot `
            -ArgumentList @($quotedNextPath, $nextMode, '--hostname', '127.0.0.1', '--port', '3000') `
            -WindowStyle Hidden -RedirectStandardOutput $webLogs.Output -RedirectStandardError $webLogs.Error -PassThru
        Wait-ProjectService -Check { Test-ProjectWeb } -Process $webProcess -Name 'Next.js' -ErrorLog $webLogs.Error
        Write-Host "Next.js ready (PID $($webProcess.Id))."
    }

    Write-Host ''
    Write-Host "Demo ready: $webUrl"
    Write-Host 'Recorded examples make no provider calls. Live agent analysis runs only when requested in the laboratory.'
    Write-Host "New-service logs: $logRoot"
    if (-not $NoBrowser) {
        # The browser is intentionally visible: opening the presentation is this script's
        # requested user-facing action. Background helper processes above remain hidden.
        Start-Process -FilePath $webUrl | Out-Null
    }
}
catch {
    Write-Error $_
    exit 1
}
