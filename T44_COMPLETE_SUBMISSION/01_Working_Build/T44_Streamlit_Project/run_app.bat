@echo off
cd /d "%~dp0"
echo.
echo ==========================================
echo T44 Competitor Price Intelligence
ECHO ==========================================
echo Installing/checking required Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package installation failed. Check Python/pip and internet access.
  pause
  exit /b 1
)
echo.
echo Launching Streamlit...
python -m streamlit run app.py
pause
