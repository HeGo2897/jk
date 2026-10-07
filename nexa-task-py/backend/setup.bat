@echo off
REM One-time setup: creates .\venv and installs Flask. Use "setup.bat mysql" to also install the MySQL driver.
cd /d "%~dp0"
python -m venv venv
if errorlevel 1 (
  echo Could not create the virtual environment. Is Python installed and on PATH?
  exit /b 1
)
set FILE=requirements.txt
if /i "%1"=="mysql" set FILE=requirements-mysql.txt
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r %FILE%
if errorlevel 1 exit /b 1
echo Setup OK. Start the server with run.bat
