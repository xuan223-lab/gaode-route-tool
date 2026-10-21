@echo off
chcp 65001 >nul
REM ============================================
REM  打包为单文件 exe（PyInstaller）
REM  用法：双击本文件，或在本目录执行 build_exe.bat
REM  产物：dist\GaodeRouteTool.exe
REM ============================================

echo [1/3] 安装打包工具 PyInstaller ...
python -m pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo 安装 PyInstaller 失败，请检查网络或 Python 环境。
    pause
    exit /b 1
)

echo [2/3] 开始打包 ...
python -m PyInstaller --noconfirm --clean --onefile ^
  --name GaodeRouteTool ^
  --add-data "%~dp0static;static" ^
  --workpath "%~dp0_build" ^
  --specpath "%~dp0_build" ^
  --distpath "%~dp0dist" ^
  app.py
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)

echo [3/3] 打包完成！
echo 产物位置：%~dp0dist\GaodeRouteTool.exe
echo 提示：把 GaodeRouteTool.exe 单独复制到任意目录即可运行，数据会保存在 exe 旁边。
pause
