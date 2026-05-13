# HireFlow AI — Windows build helper
# Usage:  .\tools\build_exe.ps1
#
# Produces:  dist\HireFlow\HireFlow.exe  (one-folder distribution)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot\.."

Write-Host "[1/5] Activating virtual environment…" -ForegroundColor Cyan
& "$Root\.venv\Scripts\Activate.ps1"

Write-Host "[2/5] Regenerating logo assets…" -ForegroundColor Cyan
python "$PSScriptRoot\generate_logo.py"

Write-Host "[3/5] Cleaning previous build artifacts…" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$Root\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$Root\dist"  -ErrorAction SilentlyContinue

Write-Host "[4/5] Downloading Playwright Chromium into build\ms-playwright…" -ForegroundColor Cyan
# Pin the download location so HireFlow.spec can pick it up and bundle it.
# Using a project-local dir (instead of the default ~/.cache or the
# site-packages .local-browsers) means a clean checkout produces a clean,
# self-contained installer every time.
$BrowsersDir = Join-Path $Root "build\ms-playwright"
New-Item -ItemType Directory -Force -Path $BrowsersDir | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL  playwright install chromium exited with code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host "[5/5] Running PyInstaller (this takes 3-6 minutes)…" -ForegroundColor Cyan
Push-Location $Root
try {
    pyinstaller HireFlow.spec --clean --noconfirm
}
finally {
    Pop-Location
}

$exe = "$Root\dist\HireFlow\HireFlow.exe"
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
