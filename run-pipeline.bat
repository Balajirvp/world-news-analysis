@echo off
cd /d %~dp0
bash run-and-shutdown.sh > logs\pipeline-%date:~-4,4%%date:~-7,2%%date:~-10,2%.log 2>&1