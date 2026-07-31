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

REM origin is a PUBLIC repo. `git add -u` stages only files that are ALREADY tracked,
REM so scan output and any other new file can never be published by this script --
REM adding a new file to the public repo has to be a deliberate `git add`.
echo Pushing source changes...
git add -u
git diff --cached --quiet
if %errorlevel% equ 0 goto :nochanges

git commit -m "Update project tracker source"
if %errorlevel% neq 0 (
    echo git commit failed. Exiting.
    exit /b %errorlevel%
)

git push
if %errorlevel% neq 0 (
    echo git push failed. Exiting.
    exit /b %errorlevel%
)
goto :done

:nochanges
echo No source changes to push.

:done
echo Done.