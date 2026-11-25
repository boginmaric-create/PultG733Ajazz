@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Сборка «Пульт G733 + AJAZZ»

set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python не найден.
  echo Установите Python 3.12 с https://www.python.org/downloads/ и отметьте галочку "Add python.exe to PATH".
  pause
  exit /b 1
)

echo [1/4] Виртуальное окружение...
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto :err
set "VPY=.venv\Scripts\python.exe"

echo [2/4] Установка зависимостей (первый раз — пара минут)...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt pyinstaller || goto :err

echo [3/4] Иконка...
"%VPY%" make_icon.py || goto :err

echo [4/4] Сборка exe...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name PultG733Ajazz --icon assets\app.ico --version-file version_info.txt main.py || goto :err

echo.
echo Готово! Программа: %cd%\dist\PultG733Ajazz.exe
echo Можно перенести этот exe в любую папку, например C:\Program Files\PultG733Ajazz
explorer dist
pause
exit /b 0

:err
echo.
echo Ошибка сборки — скопируйте текст выше и пришлите его.
pause
exit /b 1
