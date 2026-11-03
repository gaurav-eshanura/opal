@echo off
title Build Opal for Windows
cd /d "%~dp0"
echo Compiling standalone Opal release...
python build_release.py
pause
