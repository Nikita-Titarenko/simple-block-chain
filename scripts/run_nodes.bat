@echo off
cd /d "%~dp0.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

PowerShell -NoProfile -ExecutionPolicy Bypass -Command ^
	"Start-Process -FilePath '%PYTHON%' -WorkingDirectory '%CD%' -WindowStyle Hidden -ArgumentList '.\main.py --port 5001 --peers http://127.0.0.1:5002,http://127.0.0.1:5003';" ^
	"Start-Process -FilePath '%PYTHON%' -WorkingDirectory '%CD%' -WindowStyle Hidden -ArgumentList '.\main.py --port 5002 --peers http://127.0.0.1:5001,http://127.0.0.1:5003';" ^
	"Start-Process -FilePath '%PYTHON%' -WorkingDirectory '%CD%' -WindowStyle Hidden -ArgumentList '.\main.py --port 5003 --peers http://127.0.0.1:5001,http://127.0.0.1:5002'"