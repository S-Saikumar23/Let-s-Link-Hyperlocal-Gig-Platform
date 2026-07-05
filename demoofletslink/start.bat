@echo off
title Let's Link - Dev Server
color 0A
echo.
echo ========================================
echo    Let's Link - Starting Dev Server
echo ========================================
echo.

REM ── Step 1: Check if PostgreSQL is running ──
echo [1/3] Checking PostgreSQL...
netstat -ano | findstr ":5432" | findstr LISTENING >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] PostgreSQL is NOT running. Attempting to start...
    net start postgresql-x64-16 >nul 2>&1
    timeout /t 3 /nobreak >nul
    netstat -ano | findstr ":5432" | findstr LISTENING >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Could not start PostgreSQL!
        echo.
        echo   Try manually:  net start postgresql-x64-16
        echo   Or open pgAdmin and start the server.
        echo.
        pause
        exit /b 1
    )
)
echo [OK] PostgreSQL is running on port 5432

REM ── Step 2: Activate virtual environment ──
echo [2/3] Activating virtual environment...
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at %~dp0venv
    echo   Run:  python -m venv venv
    pause
    exit /b 1
)
call "%~dp0venv\Scripts\activate.bat"
echo [OK] Virtual environment activated

REM ── Step 3: Start the backend server ──
echo [3/3] Starting FastAPI backend...
echo.
echo ========================================
echo   App running at: http://localhost:8000
echo   Press CTRL+C to stop
echo ========================================
echo.

cd /d "%~dp0backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
