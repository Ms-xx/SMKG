@echo off
chcp 65001 >nul
title LX 全平台一键启动
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
pause