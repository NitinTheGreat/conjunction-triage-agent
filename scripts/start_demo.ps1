<#
.SYNOPSIS
Start the local research dashboard and API, reusing matching services already running.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1
.EXAMPLE
.\scripts\start_demo.ps1 -NoBrowser
#>
[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExecutable = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$frontendDirectory = Join-Path $repositoryRoot 'frontend'
$logDirectory = Join-Path $repositoryRoot 'processed\demo'
$dashboardUrl = 'http://127.0.0.1:8001'

function Test-ListeningPort {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.ConnectAsync('127.0.0.1', $Port)
        return ($connection.Wait(500) -and $client.Connected)
    }
    catch { return $false }
    finally { $client.Dispose() }
}

function Test-DemoService {
    param($Service, [int]$TimeoutSeconds = 2)
    try {
        if ($Service.Name -eq 'API') {
            $schema = Invoke-RestMethod -Uri ($Service.Url + '/openapi.json') `
                -TimeoutSec $TimeoutSeconds -ErrorAction Stop
            return ($schema.info.title -eq 'ConjunctionTriage API' -and
                $null -ne $schema.paths.'/pc' -and $null -ne $schema.paths.'/triage')
        }
        $page = Invoke-WebRequest -Uri ($Service.Url + '/index.html') `
            -UseBasicParsing -TimeoutSec $TimeoutSeconds -ErrorAction Stop
        # Match this dashboard, including the recorded-demo control, rather than a
        # generic HTTP server or the separate frozen Phase 3 visualisation.
        return ($page.StatusCode -eq 200 -and
            $page.Content -match '<title>ConjunctionTriage' -and
            $page.Content -match 'id="tab-pc"' -and
            $page.Content -match 'id="triage-example"')
    }
    catch { return $false }
}

try {
    if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
        throw 'The project virtual environment is missing. Create .venv and install requirements.txt before starting the demo.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory 'index.html') -PathType Leaf)) {
        throw 'frontend/index.html is missing from this checkout.'
    }

    $services = @(
        [pscustomobject]@{
            Name = 'API'; Port = 8000; Url = 'http://127.0.0.1:8000'
            Arguments = @('-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000')
            Ready = $false; Process = $null; ErrorLog = $null
        },
        [pscustomobject]@{
            Name = 'Frontend'; Port = 8001; Url = $dashboardUrl
            Arguments = @('-m', 'http.server', '8001', '--bind', '127.0.0.1', '--directory', ('"{0}"' -f $frontendDirectory))
            Ready = $false; Process = $null; ErrorLog = $null
        }
    )

    # Check both ports before starting either service. Never stop a process to claim a port.
    foreach ($service in $services) {
        if (Test-ListeningPort -Port $service.Port) {
            if (-not (Test-DemoService -Service $service)) {
                throw ('Port {0} is occupied, but its service did not identify as the ConjunctionTriage {1}. Nothing was stopped. Resolve the port conflict and run this script again.' -f $service.Port, $service.Name)
            }
            $service.Ready = $true
            Write-Host ('Reusing {0} at {1}' -f $service.Name, $service.Url)
        }
    }

    $runStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    foreach ($service in $services) {
        if ($service.Ready) { continue }
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
        $logStem = Join-Path $logDirectory ($service.Name.ToLowerInvariant() + '-' + $runStamp)
        $service.ErrorLog = $logStem + '.stderr.log'
        $service.Process = Start-Process -FilePath $pythonExecutable `
            -ArgumentList $service.Arguments -WorkingDirectory $repositoryRoot `
            -WindowStyle Hidden -PassThru -RedirectStandardOutput ($logStem + '.stdout.log') `
            -RedirectStandardError $service.ErrorLog
        Set-Content -LiteralPath ($logStem + '.pid.txt') -Value $service.Process.Id -Encoding Ascii
        Write-Host ('Starting {0} on port {1}...' -f $service.Name, $service.Port)
    }

    $startupClock = [System.Diagnostics.Stopwatch]::StartNew()
    while (@($services | Where-Object { -not $_.Ready }).Count -gt 0) {
        foreach ($service in $services) {
            if ($service.Ready) { continue }
            $remainingSeconds = 30 - $startupClock.Elapsed.TotalSeconds
            if ($remainingSeconds -lt 1) {
                throw ('Startup did not finish within 30 seconds. Inspect logs in {0}, then run this script again. Started services were left running.' -f $logDirectory)
            }
            if ($null -ne $service.Process) {
                $service.Process.Refresh()
                if ($service.Process.HasExited) {
                    throw ('{0} exited before becoming ready. Inspect {1}.' -f $service.Name, $service.ErrorLog)
                }
            }
            $probeTimeout = [int][Math]::Min(2, [Math]::Floor($remainingSeconds))
            $service.Ready = Test-DemoService -Service $service -TimeoutSeconds $probeTimeout
        }
        if (@($services | Where-Object { -not $_.Ready }).Count -gt 0) {
            Start-Sleep -Milliseconds 250
        }
    }

    Write-Host ''
    Write-Host ('Demo ready: {0}' -f $dashboardUrl)
    Write-Host 'API reference: http://127.0.0.1:8000/docs'
    Write-Host 'Presenter guide: docs/DEMO_GUIDE.md'
    Write-Host 'Use the recorded triage example for a demonstration without an LLM request.'
    if (-not $NoBrowser) { Start-Process -FilePath $dashboardUrl | Out-Null }
}
catch {
    [Console]::Error.WriteLine('Demo startup failed: ' + $_.Exception.Message)
    exit 1
}
