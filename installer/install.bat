@echo off
title Church of Jesus Christ EMCOMM — Installer
echo.
echo  Starting Church of Jesus Christ EMCOMM Installer...
echo.
set CHURCH_EMCOMM_BAT=1
powershell.exe -NoLogo -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
