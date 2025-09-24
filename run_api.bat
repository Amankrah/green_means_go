@echo off
echo Starting African LCA Assessment API...
echo.

echo Activating Python virtual environment...
call african_lca_api\Scripts\activate.bat

echo.
echo Starting FastAPI server...
echo API will be available at: http://localhost:8000
echo API documentation at: http://localhost:8000/docs
echo.

cd app
python main.py

pause