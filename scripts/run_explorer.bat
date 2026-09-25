@echo off
cd /d "%~dp0"
start "" python -m http.server 8000 --directory "%~dp0explorer"
start "" http://127.0.0.1:8000/index.html
echo Explorer started at http://127.0.0.1:8000/index.html
