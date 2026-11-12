@echo off
setlocal
title Church of Jesus Christ EMCOMM - Drill Simulator
echo.
echo  Looking for Python 3...
set "PYEXE="
set "PYARG="

rem 1. The Python launcher that the python.org installer puts in Windows.
call :try_launcher
if defined PYEXE goto found

rem 2. python.exe or python3.exe on the PATH. Each one is test-run: the Microsoft Store
rem    placeholder in WindowsApps does not run Python, so it is skipped.
for %%N in (python.exe python3.exe) do for /f "delims=" %%P in ('where %%N 2^>nul') do if not defined PYEXE call :try "%%P"
if defined PYEXE goto found

rem 3. The usual install folders, even when Python is not on the PATH.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%LOCALAPPDATA%\Python\pythoncore-*" "%ProgramFiles%\Python3*" "C:\Python3*") do if not defined PYEXE if exist "%%~D\python.exe" call :try "%%~D\python.exe"
if defined PYEXE goto found

echo.
echo  ERROR: Python 3 was not found on this computer.
echo.
echo  The simulator needs Python 3.7 or newer. It is free.
echo  Windows does not include it. Install it BEFORE an emergency:
echo  the internet may be down when you need it.
echo.
echo   1. Run the Python installer from the EMCOMM USB kit,
echo      or download it from https://www.python.org/downloads/
echo   2. In the installer, tick "Add python.exe to PATH".
echo   3. Start the simulator again.
echo.
echo  Keep a copy of the Python installer on the USB kit.
echo.
pause
exit /b 1

:found
echo  Found Python:
"%PYEXE%" %PYARG% --version
echo  (%PYEXE% %PYARG%)
echo.
echo  Starting the EMCOMM simulator (drill controller). Keep the EOC Server window running too.
echo.
"%PYEXE%" %PYARG% "%~dp0sim_server.py" %*
echo.
pause
exit /b 0

rem Test-run one python.exe; keep it when it is a real Python 3.7 or newer.
:try
"%~1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYEXE=%~1"
exit /b 0

:try_launcher
where py >nul 2>&1
if errorlevel 1 exit /b 1
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYEXE=py"
set "PYARG=-3"
exit /b 0
