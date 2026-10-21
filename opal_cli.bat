@echo off
title Opal CLI - zero-click file studio from the command line
cd /d "%~dp0"
python "%~dp0opal_studio\cli.py" %*
