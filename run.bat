@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==================================================
echo   SEO Cannibalization Explorer - launcher
echo ==================================================
echo.

echo [1/3] Installing dependencies...
pip install -q -r requirements.txt

echo.
echo [2/3] Claude subscription auth...
if exist ".env" (
  echo   .env found - using existing token. Delete .env to re-authenticate.
) else (
  echo   No .env found. A browser will open to sign in to your Claude Max/Pro subscription.
  echo   Running: claude setup-token
  echo.
  call claude setup-token
  echo.
  set /p TOKEN="Paste the token shown above (starts with sk-ant-oat): "
  >.env echo CLAUDE_CODE_OAUTH_TOKEN=!TOKEN!
  echo   Saved token to .env
)

echo.
echo [3/3] Starting Streamlit at http://localhost:8501 ...
echo   (Press Ctrl+C in this window to stop the app.)
streamlit run app.py
pause
