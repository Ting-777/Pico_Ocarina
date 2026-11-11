@echo off
setlocal DisableDelayedExpansion
where pyw.exe >nul 2>&1
if not errorlevel 1 (
    start "" pyw.exe -3 "%~dp0tools\midi_gui_launcher.pyw"
    exit /b 0
)
where pythonw.exe >nul 2>&1
if not errorlevel 1 (
    start "" pythonw.exe "%~dp0tools\midi_gui_launcher.pyw"
    exit /b 0
)
echo Python was not found.
echo Install Python 3.9 or newer with Tcl/Tk and Add Python to PATH enabled.
echo Then double-click this file again.
pause
exit /b 1
