@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1

if not "%~2"=="" goto usage
if not "%~1"=="" if not "%~1"=="--optional" goto usage

if not defined PIP_INDEX_URL set "PIP_INDEX_URL=https://pypi-mirror.gitverse.ru/simple/"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if exist ".venv" goto use_venv

rem Prefer the Windows Python launcher, then try Python from PATH.
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
    if errorlevel 1 goto fail
    goto use_venv
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo Install Python 3.10 or newer, then rerun this script. >&2
    goto fail
)
python -m venv .venv
if errorlevel 1 goto fail

:use_venv
if not exist "%VENV_PYTHON%" (
    echo The existing .venv is not a working Windows environment. Move it aside and rerun this script. >&2
    goto fail
)

"%VENV_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 'Python 3.10 or newer is required.')"
if errorlevel 1 goto fail

"%VENV_PYTHON%" -m pip config --site set global.index-url "%PIP_INDEX_URL%"
if errorlevel 1 goto fail
"%VENV_PYTHON%" -m pip install --index-url "%PIP_INDEX_URL%" -r requirements.txt
if errorlevel 1 goto fail

if "%~1"=="--optional" (
    "%VENV_PYTHON%" -m pip install --index-url "%PIP_INDEX_URL%" -r requirements-optional.txt
    if errorlevel 1 goto fail
)

echo Setup complete. Select .venv\Scripts\python.exe as the notebook kernel in VS Code.
popd
exit /b 0

:usage
echo Usage: setup.bat [--optional] >&2
popd
exit /b 2

:fail
echo Setup failed. See the error above. >&2
popd
exit /b 1
