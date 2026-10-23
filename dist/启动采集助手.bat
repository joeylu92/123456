@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo 未检测到 Python。请先安装 Python 3.12，并勾选 Add python.exe to PATH。
  pause
  exit /b 1
)
py -3.12 -m pip install -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败，请检查网络后重试。
  pause
  exit /b 1
)
py -3.12 collector.py
pause
