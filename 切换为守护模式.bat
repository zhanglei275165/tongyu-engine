@echo off
echo ============================================
echo   Switch Tongyu Engine to GUARDED mode
echo   (auto-restart on crash, no more segfault downtime)
echo ============================================
echo.
echo  WARNING: this restarts the engine (few seconds offline).
echo  DO NOT run during 00:00-06:00 novel night-batch!
echo  Run in daytime / after reboot instead.
echo.
pause
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :11434 ^| findstr LISTEN') do taskkill /f /pid %%a
timeout /t 3 >nul
start "" "F:\opensource\tongyu-engine\守护启动器.vbs"
echo.
echo  Done. Engine is now guarded - it auto-restarts if it crashes.
echo  You can close this window.
pause
