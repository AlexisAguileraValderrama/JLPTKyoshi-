@echo off
echo JLPT Kyoshi - Azure Static Web Apps local dev
echo.
echo Requirements:
echo   npm install -g @azure/static-web-apps-cli
echo   pip install -r api/requirements.txt
echo   Fill in api/local.settings.json with COSMOS_ENDPOINT, COSMOS_KEY, XAI_API_KEY
echo.
echo Starting SWA CLI (static files + Azure Functions emulator)...
swa start . --api-location api
