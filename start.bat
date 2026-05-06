@echo off
title CC CONFIG UI
echo.
echo   Starting CC CONFIG UI...
echo   Opening browser...
echo.
start http://127.0.0.1:8787
python "%~dp0server.py"
pause
