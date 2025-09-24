@echo off
echo Running Test Results Demonstration...
echo.

REM Check if virtual environment exists
if not exist "african_lca_api\Scripts\activate.bat" (
    echo Error: Virtual environment not found. Please run install_deps.bat first.
    pause
    exit /b 1
)

echo Activating Python virtual environment...
call african_lca_api\Scripts\activate.bat

echo.
echo Running demonstration...
python show_test_results.py

echo.
pause

