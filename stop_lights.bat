@echo off
rem Double-click to STOP the WLED holiday scheduler cleanly. It will NOT restart by itself.
rem It stays stopped until you run start_lights.bat or the PC reboots.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 wled_holiday_scheduler.py --stop) || (python wled_holiday_scheduler.py --stop)
echo.
pause
