# Genera installer\Output\TurnosDesktopSetup.exe. Ejecutar en Windows, desde la raíz del repo:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-SkipInstaller] [-SkipTests]
param([switch]$SkipInstaller, [switch]$SkipTests)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run($cmd) {
    Write-Host ">> $cmd"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Falló: $cmd" }
}

Run "python -m pip install -r requirements-build.txt"
if (-not $SkipTests) {
    Run "python -m pip install -r requirements-dev.txt"
    Run "python -m ruff check ."
    Run "python -m pytest -q"
}

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Run "python -m PyInstaller --noconfirm --distpath dist --workpath build packaging\turnos_desktop.spec"

# Prueba de humo del ejecutable empaquetado, con datos en una carpeta temporal.
$tmp = Join-Path $env:TEMP "turnos-selfcheck-$(Get-Random)"
$env:TURNOS_HOME = $tmp
$proc = Start-Process "dist\TurnosDesktop\TurnosDesktop.exe" "--self-check" -Wait -PassThru
Remove-Item Env:\TURNOS_HOME
if ($proc.ExitCode -ne 0) {
    Get-Content "$tmp\logs\app.log" -Tail 20 -ErrorAction SilentlyContinue
    throw "El ejecutable falló la autoverificación (código $($proc.ExitCode))"
}
Remove-Item -Recurse -Force $tmp
Write-Host "Autoverificación OK"

if (-not $SkipInstaller) {
    $version = python -c "from app.utils.constants import APP_VERSION; print(APP_VERSION)"
    $iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
    if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
    if (-not (Test-Path $iscc)) { throw "No se encontró Inno Setup 6 (ISCC.exe)" }
    Run "& `"$iscc`" /DAppVersion=$version installer\TurnosDesktop.iss"
    Write-Host "Instalador: installer\Output\TurnosDesktopSetup.exe"
}
