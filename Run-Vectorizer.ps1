<#
.SYNOPSIS
    Launch the geometry-first vectorizer on your own files.

.DESCRIPTION
    Thin wrapper around run_vectorizer.py that selects an interpreter which has
    torch + OpenCV + Pillow installed. All arguments are passed straight through.

.EXAMPLE
    .\Run-Vectorizer.ps1 web_preview\uploads\117_icon_group_6_src.png

.EXAMPLE
    .\Run-Vectorizer.ps1 my_logo.png --smoothing perceptual,cad --open

.EXAMPLE
    .\Run-Vectorizer.ps1 .\web_preview\uploads --tag batch1
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

# C:\Python312 is the environment that carries torch (CUDA), cv2 and Pillow.
# Fall back to whatever "python" resolves to on PATH if that path is gone.
$python = 'C:\Python312\python.exe'
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    throw "No suitable Python found (need torch + cv2 + Pillow). Install or edit `$python in this script."
}

& $python (Join-Path $root 'run_vectorizer.py') @args
