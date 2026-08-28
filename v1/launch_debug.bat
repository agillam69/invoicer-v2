@echo off
REM Debug launcher for Invoice Generator v1.49
REM Redirects startup errors to a local log so we can see why the exe won't launch.

setlocal

REM Use a local data directory outside OneDrive to avoid sync/file-lock issues.
set "INVOICER_DATA_DIR=C:\InvoicerData"
if not exist "%INVOICER_DATA_DIR%" mkdir "%INVOICER_DATA_DIR%"

REM Local log file outside OneDrive so it is always writable.
set "LAUNCH_LOG=C:\InvoicerData\launch_debug.log"

echo --- Launch attempt --- >> "%LAUNCH_LOG%" 2>&1
echo Data dir: %INVOICER_DATA_DIR% >> "%LAUNCH_LOG%" 2>&1
echo Time: %date% %time% >> "%LAUNCH_LOG%" 2>&1

"%~dp0dist\Invoice Generator v1.49.exe" >> "%LAUNCH_LOG%" 2>&1
echo Exit code: %errorlevel% >> "%LAUNCH_LOG%" 2>&1

endlocal
