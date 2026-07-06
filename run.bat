@echo off
REM One-click launcher for the SEO Cannibalization Explorer.
REM Double-click this file, or run it from a terminal.
cd /d "%~dp0"
echo Installing/updating dependencies...
pip install -q -r requirements.txt
echo Starting Streamlit... a browser tab will open at http://localhost:8501
streamlit run app.py
pause
