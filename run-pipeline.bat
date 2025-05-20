@echo off
cd /d %~dp0

REM Use Git Bash explicitly - adjust path if your Git installation is different
"C:\Program Files\Git\bin\bash.exe" -c "./run-and-shutdown.sh" > logs\pipeline-%date:~-4,4%%date:~-7,2%%date:~-10,2%.log 2>&1

REM Return code from bash
set BASH_RESULT=%ERRORLEVEL%

REM Ensure any lingering bash processes are terminated
taskkill /F /IM bash.exe /FI "WINDOWTITLE eq run-and-shutdown*" >NUL 2>&1

REM Exit with the same code as the bash process
exit /b %BASH_RESULT%