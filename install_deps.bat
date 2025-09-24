@echo off
echo Activating virtual environment...
call african_lca_api\Scripts\activate.bat

echo Installing Python dependencies...
pip install -r requirements.txt

echo Dependencies installed successfully!
pause