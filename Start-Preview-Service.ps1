<#
.SYNOPSIS
    Keeps the local V-ICE preview backend alive on Windows.
.DESCRIPTION
    Intended for a per-user Scheduled Task.  It starts the preview server when
    the configured port is free and restarts it after an unexpected exit.  If
    another healthy preview instance already owns the port, the supervisor
    waits and takes over only after that instance disappears.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8877,

    [ValidateRange(1, 300)]
    [int]$RestartDelaySeconds = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$server = Join-Path $projectRoot 'web_preview\server.py'
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "Preview server not found: $server"
}

$python = 'C:\Python312\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw 'Python 3.10+ was not found.'
    }
    $python = $pythonCommand.Source
}

$stateRoot = Join-Path $env:LOCALAPPDATA 'V-ICE'
New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
$log = Join-Path $stateRoot 'preview-service.log'

function Write-PreviewLog([string]$Message) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $log -Value "[$timestamp] $Message" -Encoding UTF8
}

function Test-PreviewPort {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        if (-not $connect.Wait(500)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

Write-PreviewLog "Supervisor started for http://127.0.0.1:$Port"

while ($true) {
    if (Test-PreviewPort) {
        Start-Sleep -Seconds 5
        continue
    }

    Write-PreviewLog "Starting $server"
    try {
        & $python -u $server --port $Port *>> $log
        Write-PreviewLog "Server exited with code $LASTEXITCODE"
    }
    catch {
        Write-PreviewLog "Server launch failed: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $RestartDelaySeconds
}
