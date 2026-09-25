@echo off
cd /d "%~dp0"
set "EXPLORER_DIR=%~dp0..\explorer"
start "" python -m http.server 8000 --directory "%EXPLORER_DIR%"
start "" http://127.0.0.1:8000/index.html
echo Explorer started at http://127.0.0.1:8000/index.html
