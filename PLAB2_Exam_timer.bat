@echo off
setlocal

:: Set the path to your Python virtual environment
set VENV_PATH=c:\Users\deletable\OneDrive\Windows_software\openai whisper\openai

:: Change to the script directory
cd /d "%~dp0"

:: Activate the virtual environment
call "%VENV_PATH%\Scripts\activate.bat" >nul 2>&1

:: Run the Python script
start "" /b python "PLAB2_Exam_timer.py"