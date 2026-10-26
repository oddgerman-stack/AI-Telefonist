@echo off
title AI-Telefonist • Autonome Virtuele Receptioniste
echo ============================================================
echo   AI-Telefonist • 100%% Offline Front-Desk Receptionist
echo ============================================================
echo.

python -m web.app
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)
