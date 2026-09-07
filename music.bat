@echo off
chcp 65001 >nul

REM 切換到 BAT 所在資料夾
cd /d "%~dp0"

echo.
echo =====================
echo 開始打包旗艦完美版 (含自訂圖示)...
echo =====================

python -m PyInstaller ^
--clean ^
--onefile ^
--windowed ^
--collect-data ytmusicapi ^
--add-data "libvlc.dll;." ^
--add-data "libvlccore.dll;." ^
--add-data "plugins;plugins" ^
--add-data "icon.ico;." ^
--icon "icon.ico" ^
music.py

echo.
echo =====================
echo 打包完成！
echo 請到 dist 資料夾內找 music.exe
echo =====================

pause