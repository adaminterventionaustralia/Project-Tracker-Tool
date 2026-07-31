@echo off
cd /d %~dp0

echo Running scan...
python scan-all.py
if %errorlevel% neq 0 (
    echo scan-all.py failed. Exiting.
    exit /b %errorlevel%
)

echo Compiling report...
python compile-report.py --reports-dir reports
if %errorlevel% neq 0 (
    echo compile-report.py failed. Exiting.
    exit /b %errorlevel%
)

echo Generating Dashboard...
python dashboard.py daily-digest-latest.md
if %errorlevel% neq 0 (
    echo dashboard.py failed. Exiting.
    exit /b %errorlevel%
)

echo Cleaning to Archive...
python tidy.py --all
if %errorlevel% neq 0 (
    echo tidy.py failed. Exiting.
    exit /b %errorlevel%
)

echo Pushing results...
git add .
git commit -m "Update compiled report"
git push

echo Done.