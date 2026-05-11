# HireFlow AI — Windows build helper
# Usage:  .\tools\build_exe.ps1
#
# Produces:  dist\HireFlow\HireFlow.exe  (one-folder distribution)

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Activating virtual environment…" -ForegroundColor Cyan
& "$PSScriptRoot\..\.venv\Scripts\Activate.ps1"

Write-Host "[2/4] Regenerating logo assets…" -ForegroundColor Cyan
python "$PSScriptRoot\generate_logo.py"

Write-Host "[3/4] Cleaning previous build artifacts…" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$PSScriptRoot\..\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$PSScriptRoot\..\dist"  -ErrorAction SilentlyContinue

Write-Host "[4/4] Running PyInstaller (this takes 3-6 minutes)…" -ForegroundColor Cyan
Push-Location "$PSScriptRoot\.."
try {
    pyinstaller HireFlow.spec --clean --noconfirm
}
finally {
    Pop-Location
}

$exe = "$PSScriptRoot\..\dist\HireFlow\HireFlow.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "OK  Built dist\HireFlow\HireFlow.exe ($size MB)" -ForegroundColor Green
    Write-Host "    Distribute the whole 'dist\HireFlow\' folder to your users."
    Write-Host "    On the target machine: double-click HireFlow.exe."
}
else {
    Write-Host "FAIL  Executable was not produced — check the PyInstaller output above." -ForegroundColor Red
    exit 1
}
