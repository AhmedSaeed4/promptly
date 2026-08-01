@echo off
cd /d %~dp0
uv run pyinstaller --noconfirm --onefile --windowed --name "Promptly" --icon "app-icon.ico" --add-data "app-icon.svg;." --distpath "dist-onefile" --workpath "build-onefile" main.py
