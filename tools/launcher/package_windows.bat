@echo off
rem Packs launcher.py into dist\MOHRS-Launcher.exe (one file, no Python needed to run it).
rem The exe must stay in the repo folder or its dist\ (it finds tools\launcher\build.sh from there).
rem Needs a Windows Python 3 with tkinter (python.org installer); PyInstaller goes into build\launcher-venv-win.
cd /d %~dp0..\..
if not exist build\launcher-venv-win\Scripts\python.exe python -m venv build\launcher-venv-win || exit /b 1
build\launcher-venv-win\Scripts\python -m pip install -q pyinstaller pillow || exit /b 1
build\launcher-venv-win\Scripts\python -m PyInstaller --noconfirm --onefile --windowed --name MOHRS-Launcher ^
  --icon "%CD%\tools\linux\mohrs.png" --distpath dist --workpath build\launcher-pyi-win --specpath build\launcher-pyi-win ^
  launcher.py || exit /b 1
echo built dist\MOHRS-Launcher.exe
