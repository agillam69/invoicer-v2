@echo off
REM Run Invoice Generator from a local non-OneDrive folder.
REM This avoids OneDrive sync/file-lock issues that can prevent the exe from starting.

setlocal
set "LOCAL_DIR=C:\InvoicerData"
set "LOCAL_EXE=%LOCAL_DIR%\InvoiceGenerator.exe"

if not exist "%LOCAL_EXE%" (
    echo Copying exe to local folder: %LOCAL_DIR%
    mkdir "%LOCAL_DIR%" 2>nul
    copy "%~dp0dist\Invoice Generator v1.49.exe" "%LOCAL_EXE%"
)

set "INVOICER_DATA_DIR=%LOCAL_DIR%"
start "" "%LOCAL_EXE%"
endlocal
