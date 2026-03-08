@echo off
REM ============================================
REM  Astra Agent — Auto-Start (Backend + Frontend)
REM  Launches both servers concurrently.
REM ============================================

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   🚀  Astra Agent — Starting Servers     ║
echo  ║   Backend:  http://localhost:8000         ║
echo  ║   Frontend: http://localhost:3000         ║
echo  ╚══════════════════════════════════════════╝
echo.

REM Start backend (Python FastAPI on port 8000)
echo [1/2] Starting Backend (FastAPI)...
cd /d "%~dp0backend"
start "Astra-Backend" cmd /k "python main.py"

REM Small delay to let backend initialize
timeout /t 3 /nobreak >nul

REM Start frontend (Vite dev server on port 3000)
echo [2/2] Starting Frontend (Vite)...
cd /d "%~dp0frontend"
start "Astra-Frontend" cmd /k "npm run dev"

echo.
echo  ✅ Both servers launching...
echo     Backend:  http://localhost:8000
echo     Frontend: http://localhost:3000
echo.
echo  Press any key to close this launcher (servers continue running).
pause >nul
