@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================================
echo   啟動 Lynn-music 手機版測試伺服器...
echo ========================================================
echo.

python api_server.py

pause
