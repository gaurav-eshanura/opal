@echo off
title Build Tangerine for Windows
cd /d "%~dp0"
echo Compiling standalone Tangerine release...
python build_release.py
pause
