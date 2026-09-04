@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Keep a visible command window when launched by double-click.
if /I not "%~1"=="--inner" (
  start "RideScope Launcher" cmd.exe /k ""%~f0" --inner"
  exit /b 0
)

cd /d "%~dp0"
title RideScope Launcher
set "LOG_FILE=%CD%\RideScope-startup.log"
set "READY_FILE=%CD%\.venv\.deps_ready_v3"
set "PYTHON_EXE="
set "PYTHON_ARG="
set "VERSION_CHECK=import sys; assert sys.version_info.major == 3 and sys.version_info.minor in range(10,14)"

> "%LOG_FILE%" echo RideScope startup log
>>"%LOG_FILE%" echo Time: %time%
>>"%LOG_FILE%" echo Directory: %CD%
echo.
echo =============================================
echo   RideScope Cycling Track Analyzer
echo =============================================
echo.
echo [1/4] Checking Python 3.10 - 3.13...

rem Advanced override: RIDESCOPE_PYTHON may point to a compatible python.exe.
if defined RIDESCOPE_PYTHON (
  if exist "%RIDESCOPE_PYTHON%" (
    "%RIDESCOPE_PYTHON%" -c "!VERSION_CHECK!" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%RIDESCOPE_PYTHON%"
  )
)

where py.exe >nul 2>&1
if not errorlevel 1 (
  for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYTHON_EXE (
      py -%%V -c "import sys" >nul 2>&1
      if not errorlevel 1 (
        set "PYTHON_EXE=py.exe"
        set "PYTHON_ARG=-%%V"
      )
    )
  )
)

if not defined PYTHON_EXE (
  where python.exe >nul 2>&1
  if not errorlevel 1 (
    python.exe -c "!VERSION_CHECK!" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python.exe"
  )
)

if not defined PYTHON_EXE goto :python_error

echo   Command: %PYTHON_EXE% %PYTHON_ARG%
"%PYTHON_EXE%" %PYTHON_ARG% --version
>>"%LOG_FILE%" echo Python command: %PYTHON_EXE% %PYTHON_ARG%
"%PYTHON_EXE%" %PYTHON_ARG% --version >>"%LOG_FILE%" 2>&1

if /I "%~2"=="--check" goto :check_ok

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "!VERSION_CHECK!" >nul 2>&1
  if errorlevel 1 goto :venv_error
) else (
  echo [2/4] Creating an isolated environment...
  >>"%LOG_FILE%" echo Creating .venv
  "%PYTHON_EXE%" %PYTHON_ARG% -m venv ".venv" >>"%LOG_FILE%" 2>&1
  if errorlevel 1 goto :venv_create_error
)

if not exist "%READY_FILE%" (
  echo [3/4] Installing dependencies. The first run may take several minutes...
  echo       Details: RideScope-startup.log
  >>"%LOG_FILE%" echo Installing dependencies
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-cache-dir --upgrade pip setuptools wheel >>"%LOG_FILE%" 2>&1
  if errorlevel 1 goto :install_error
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-cache-dir -r "requirements.txt" >>"%LOG_FILE%" 2>&1
  if errorlevel 1 goto :install_error
  ".venv\Scripts\python.exe" -m pip check >>"%LOG_FILE%" 2>&1
  if errorlevel 1 goto :install_error
  ".venv\Scripts\python.exe" -c "import streamlit,pandas,numpy,plotly,fitparse" >>"%LOG_FILE%" 2>&1
  if errorlevel 1 goto :install_error
  type nul > "%READY_FILE%"
) else (
  echo [3/4] Dependencies are ready.
)

echo [4/4] Starting RideScope. Your browser will open automatically...
echo.
echo If it does not open, visit: http://localhost:8501
echo Close this window to stop the program.
echo Streamlit output is also written to RideScope-startup.log.
>>"%LOG_FILE%" echo Starting Streamlit

".venv\Scripts\python.exe" -m streamlit run "app.py" --server.address=127.0.0.1 --server.port=8501 --server.headless=false --server.showEmailPrompt=false --browser.gatherUsageStats=false >>"%LOG_FILE%" 2>&1
set "APP_EXIT=%errorlevel%"
>>"%LOG_FILE%" echo Streamlit exit code: %APP_EXIT%
echo.
echo RideScope stopped with exit code %APP_EXIT%.
echo ---------- Last log lines ----------
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 25" 2>nul
echo ------------------------------------
goto :hold

:check_ok
echo Python check passed.
>>"%LOG_FILE%" echo Python check passed
exit /b 0

:python_error
>>"%LOG_FILE%" echo ERROR: Python 3.10 - 3.13 was not found
echo.
echo [ERROR] A compatible Python installation was not found.
echo Install Python 3.12 and select "Add Python to PATH" during setup.
echo Download: https://www.python.org/downloads/
echo Python 3.14 is not supported by this package yet.
set "APP_EXIT=10"
goto :show_log

:venv_error
>>"%LOG_FILE%" echo ERROR: Existing .venv uses an incompatible Python
echo.
echo [ERROR] The existing .venv uses an incompatible Python version.
echo Delete the .venv folder inside this project, then run this file again.
set "APP_EXIT=11"
goto :show_log

:venv_create_error
>>"%LOG_FILE%" echo ERROR: Failed to create .venv
echo.
echo [ERROR] The isolated environment could not be created.
set "APP_EXIT=12"
goto :show_log

:install_error
>>"%LOG_FILE%" echo ERROR: Dependency installation failed
echo.
echo [ERROR] Dependency installation failed.
echo Check your network or proxy, then read RideScope-startup.log.
set "APP_EXIT=13"
goto :show_log

:show_log
echo.
echo ---------- Last log lines ----------
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 25" 2>nul
echo ------------------------------------

:hold
if not defined RIDESCOPE_NO_PAUSE pause
exit /b %APP_EXIT%

