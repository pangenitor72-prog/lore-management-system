@echo off
REM run_agent.bat: Dynamically pulls context from GitHub and injects it into Gemini CLI.

REM --- 1. CONFIGURATION (CRITICAL: EDIT THESE) ---

set "LOCAL_RULES=GEMINI.md"

REM **CRITICAL**: REPLACE THESE WITH YOUR ACTUAL RAW GITHUB DOC URLs
set "DOC_URL_1=https://github.com/pangenitor72-prog/lore-management-system/blob/main/README.md"
set "DOC_URL_2=https://github.com/pangenitor72-prog/lore-management-system/blob/main/phase-viii-complete-audit.py"
set "DOC_URL_3=https://github.com/pangenitor72-prog/lore-management-system/blob/main/roadmap.md
set "DOC_URL_4=https://github.com/pangenitor72-prog/lore-management-system/blob/main/make_db_audit.py
set "DOC_URL_5=https://github.com/pangenitor72-prog/lore-management-system/blob/main/run.py
set "DOC_URL_6=https://github.com/pangenitor72-prog/lore-management-system/blob/main/docs/deferred/API%20Endpoints%20Specification.txt
set "DOC_URL_7=
REM Verified Working Command
set "GEMINI_COMMAND=gemini" 

set "TEMP_CONTEXT_FILE=temp_combined_context.md"

REM --- 2. VALIDATION ---

if "%~1" equ "" (
    echo ERROR: Missing query. Usage: %~n0 "Your analysis prompt here"
    goto :eof
)
if not exist "%LOCAL_RULES%" (
    echo ERROR: Local rules file '%LOCAL_RULES%' not found.
    goto :eof
)

REM --- 3. CONTEXT INJECTION WORKFLOW (FIXED) ---

echo --- Starting dynamic context injection... ---

REM A. Start with your local rules
copy "%LOCAL_RULES%" "%TEMP_CONTEXT_FILE%" >nul
echo.>>"%TEMP_CONTEXT_FILE%"
echo --- Appending GitHub Documentation --->>"%TEMP_CONTEXT_FILE%"
echo.>>"%TEMP_CONTEXT_FILE%"

REM B. Download the latest GitHub docs and append them
echo Fetching: %DOC_URL_1%
curl -s "%DOC_URL_1%" >> "%TEMP_CONTEXT_FILE%"

echo Fetching: %DOC_URL_2%
curl -s "%DOC_URL_2%" >> "%TEMP_CONTEXT_FILE%"

echo --- Context successfully combined. ---

REM C. Run the Gemini CLI command by reading the entire combined file 
REM    and prepending it to the user's query (%~1).
REM The CLI will now see the entire context as the start of the prompt.
set /p CONTEXT=<"%TEMP_CONTEXT_FILE%"
"%GEMINI_COMMAND%" chat "%CONTEXT% %~1"

REM --- 4. CLEANUP ---
del "%TEMP_CONTEXT_FILE%"
echo --- Cleanup complete. Agent run finished. ---