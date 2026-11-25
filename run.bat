@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if not exist ".venv\Scripts\python.exe" (
  echo Первый запуск: устанавливаю зависимости...
  %PY% -m venv .venv || goto :err
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
)
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0
:err
echo Не получилось. Установлен ли Python 3.12 (с галочкой "Add python.exe to PATH")?
pause
