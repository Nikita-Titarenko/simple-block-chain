@echo off
start "" pythonw main.py --port 5001 --peers http://127.0.0.1:5002,http://127.0.0.1:5003
start "" pythonw main.py --port 5002 --peers http://127.0.0.1:5001,http://127.0.0.1:5003
start "" pythonw main.py --port 5003 --peers http://127.0.0.1:5001,http://127.0.0.1:5002