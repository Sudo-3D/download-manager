@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run this script as Administrator!
    pause
    exit /b
)

set "CURRENT_DIR=%~dp0"
set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

set "HOST_NAME=com.python.download.manager"
set "JSON_PATH=%CURRENT_DIR%\com.python.download.manager.json"

echo Registering Python bridge for all browsers...

:: 1. Google Chrome
reg add "HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\%HOST_NAME%" /ve /d "%JSON_PATH%" /f >nul

:: 2. Microsoft Edge
reg add "HKEY_CURRENT_USER\Software\Microsoft\Edge\NativeMessagingHosts\%HOST_NAME%" /ve /d "%JSON_PATH%" /f >nul

:: 3. Brave Browser
reg add "HKEY_CURRENT_USER\Software\BraveSoftware\Brave\NativeMessagingHosts\%HOST_NAME%" /ve /d "%JSON_PATH%" /f >nul

:: 4. Opera
reg add "HKEY_CURRENT_USER\Software\Chromium\NativeMessagingHosts\%HOST_NAME%" /ve /d "%JSON_PATH%" /f >nul

:: 5. Mozilla Firefox (إذا قررت دعمه مستقبلاً)
reg add "HKEY_CURRENT_USER\Software\Mozilla\NativeMessagingHosts\%HOST_NAME%" /ve /d "%JSON_PATH%" /f >nul

echo --------------------------------------------------
echo [SUCCESS] Native Messaging host registered for:
echo - Google Chrome
echo - Microsoft Edge
echo - Brave Browser
echo - Opera
echo - Mozilla Firefox
echo --------------------------------------------------
echo Path set to: %JSON_PATH%
pause