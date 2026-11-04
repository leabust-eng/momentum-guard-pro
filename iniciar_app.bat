@echo off
REM Arranca el backtester y deja la ventana abierta (cerrarla detiene el servidor).
cd /d "%~dp0"
if not exist ".cache" mkdir ".cache"
start "" http://localhost:8501
python -m streamlit run app.py --server.headless true --server.port 8501 --browser.gatherUsageStats false
pause
