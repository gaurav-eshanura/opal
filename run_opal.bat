@echo off
title Opal
cd /d "%~dp0"
echo Starting Opal...
start "" pythonw "%~dp0opal_studio\main.py"
echo Opal is running in the background. Look for the citrus icon in your system tray!
exit
