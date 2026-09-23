@echo off
for /f "tokens=2" %%i in ('tasklist ^| findstr /i "python"') do (
    taskkill /PID %%i /F >nul 2>&1
)