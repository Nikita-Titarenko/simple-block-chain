@echo off
PowerShell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$processes = Get-CimInstance Win32_Process;" ^
    "foreach ($process in $processes) {" ^
    "  if ($process.Name -match '^pythonw?(.exe)?$' -and $process.CommandLine -match 'main\.py --port (5001|5002|5003)') {" ^
    "    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue" ^
    "  }" ^
    "}"