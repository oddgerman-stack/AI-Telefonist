# AI-Telefonist PowerShell Launcher
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AI-Telefonist • 100% Offline Front-Desk Receptionist" -ForegroundColor Cyan
Write-Host "  Dual-Language: Nederlands (Standaard) & English" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[Error] Python 3 is niet geïnstalleerd of niet toegevoegd aan PATH." -ForegroundColor Red
    Exit 1
}

# Auto-start web server
python -m web.app
