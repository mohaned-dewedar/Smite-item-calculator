@echo off
:: ============================================================
:: Smite 2 Patch Checker — weekly Task Scheduler entry point
::
:: To register this as a weekly Windows scheduled task, run
:: the command below ONCE from an elevated (Admin) prompt:
::
::   schtasks /create /tn "Smite2PatchCheck" /tr "\"C:\Users\mdewe\OneDrive\Desktop\Me\Smite\schedule_patch_check.bat\"" /sc weekly /d MON /st 09:00 /f
::
:: To run manually at any time, just double-click this file
:: or call it from a terminal.
:: ============================================================

set "SMITE_DIR=C:\Users\mdewe\OneDrive\Desktop\Me\Smite"
set "LOG=%SMITE_DIR%\patch_check.log"

echo [%date% %time%] Running patch check >> "%LOG%"
cd /d "%SMITE_DIR%\scraper"

python check_patch.py >> "%LOG%" 2>&1

echo [%date% %time%] Patch check finished >> "%LOG%"
