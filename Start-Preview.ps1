<#
.SYNOPSIS
    Launch the VAI web-preview UI (drop images, play with modes) in the browser.
.DESCRIPTION
    Runs preview.py, which starts the local server and opens the browser.
    preview.py itself finds an interpreter that has the pipeline dependencies,
    so this wrapper only needs any Python to bootstrap it.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

# Any Python can run preview.py (stdlib only); prefer the full one if present.
$python = 'C:\Python312\python.exe'
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    throw "No Python found on this machine. Install Python 3.10+ and try again."
}

& $python (Join-Path $root 'preview.py') @args
