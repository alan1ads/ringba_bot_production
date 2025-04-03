@echo off
echo Setting up Ringba RPC Monitor Bot...

echo.
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Creating .env file from sample if it doesn't exist...
if not exist .env (
    copy .env.sample .env
    echo Created .env file. Please edit it with your credentials.
) else (
    echo .env file already exists.
)

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Edit the .env file with your Ringba credentials and Slack webhook URL
echo 2. Run test_bot.py to verify functionality: python test_bot.py
echo 3. If everything works, follow the DEPLOYMENT_GUIDE.md to deploy to Render.com
echo.
echo Thank you for using Ringba RPC Monitor Bot!