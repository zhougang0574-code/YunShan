@echo off
REM 一键启动 YunShan（双击即可）。首次会自动构建前端，然后打开 http://127.0.0.1:8000
py -3 "%~dp0run.py" %*
pause
