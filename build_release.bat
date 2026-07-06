@echo off
cd /d "%~dp0"
echo ==========================================
echo   Building BotManager (clean rebuild)
echo ==========================================
if exist build rmdir /s /q build
echo.
echo [1/2] Building exe with PyInstaller...
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 goto build_failed
echo.
echo [2/2] Packaging installer zip...
python make_installer_zip.py
if errorlevel 1 goto package_failed
echo.
echo ==========================================
echo   DONE - dist\BotManager-Setup.zip is ready
echo   send this file to your customers
echo ==========================================
explorer dist
pause
goto :eof

:build_failed
echo.
echo *** BUILD FAILED - see errors above ***
pause
exit /b 1

:package_failed
echo.
echo *** PACKAGING FAILED - see errors above ***
pause
exit /b 1
