@echo off
rem Double-click to START the WLED holiday scheduler in the background (no window).
rem Safe to run if it is already running: the extra copy exits on its own.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" /B pyw -3 wled_holiday_scheduler.py) || (start "" /B pythonw wled_holiday_scheduler.py)
echo The scheduler is starting in the background. Details are in wled_scheduler.log.
timeout /t 5 >nul
