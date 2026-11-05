@echo off
title Church of Jesus Christ EMCOMM — Drill Simulator
echo.
echo  Looking for Python...

where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    goto found
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python3
    goto found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py
    goto found
)

echo.
echo  ERROR: Python not found.
echo.
echo  Python 3.7 or newer is required (it is free and built into Windows 11).
echo  Download from: https://www.python.org/downloads/
echo  During install, check "Add Python to PATH".
echo.
pause
exit /b 1

:found
echo  Found Python at: %PYTHON%
echo.
echo  Starting the EMCOMM simulator (drill controller)... Keep the EOC Server window running too.
echo.
%PYTHON% "%~dp0sim_server.py"
echo.
pause
