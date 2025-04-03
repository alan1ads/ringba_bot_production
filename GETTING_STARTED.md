# Getting Started with Ringba RPC Monitor Bot

This guide will walk you through the process of setting up and running the Ringba RPC Monitor Bot on your local machine before deployment.

## Step 1: Initial Setup

### Running the Setup Script

The `setup.bat` script will install all required dependencies and prepare your environment. Here's how to run it:

#### Method 1: Using File Explorer
1. Open File Explorer
2. Navigate to `C:\Users\Alan Leyva\Documents\Atlas\John\ringba-bot`
3. Double-click on `setup.bat`
4. If you get a security warning, click "Run" or "Yes"

#### Method 2: Using Command Prompt
1. Press `Win + R` to open the Run dialog
2. Type `cmd` and press Enter to open Command Prompt
3. Navigate to the project directory with:
   ```
   cd "C:\Users\Alan Leyva\Documents\Atlas\John\ringba-bot"
   ```
4. Run the setup script:
   ```
   setup.bat
   ```

#### Method 3: Using PowerShell
1. Right-click on the Start menu and select "Windows PowerShell"
2. Navigate to the project directory:
   ```
   cd "C:\Users\Alan Leyva\Documents\Atlas\John\ringba-bot"
   ```
3. Run the script:
   ```
   .\setup.bat
   ```

### What the Setup Script Does
- Installs all Python dependencies from `requirements.txt`
- Creates a `.env` file from the `.env.sample` template if it doesn't exist
- Provides instructions for next steps

## Step 2: Configure Your Credentials

After running the setup script, you need to edit the `.env` file with your actual credentials:

1. Open the `.env` file in any text editor (right-click and select "Edit" or open with Notepad)
2. Replace the placeholder values with your actual credentials:
   ```
   # Ringba credentials
   RINGBA_EMAIL=your_actual_email@example.com
   RINGBA_PASSWORD=your_actual_password

   # Slack webhook URL
   SLACK_WEBHOOK_URL=your_actual_slack_webhook_url
   ```
3. Save the file

### Getting a Slack Webhook URL

If you don't have a Slack webhook URL yet:

1. Go to [Slack API Apps page](https://api.slack.com/apps)
2. Click "Create New App"
   - Choose "From scratch"
   - Name your app (e.g., "Ringba RPC Monitor")
   - Select your workspace
3. In the left sidebar, click on "Incoming Webhooks"
4. Enable Incoming Webhooks by toggling the switch
5. Click "Add New Webhook to Workspace"
   - Select the channel where notifications should be sent
   - Click "Allow"
6. Copy the Webhook URL provided
7. Paste this URL as the value for `SLACK_WEBHOOK_URL` in your `.env` file

## Step 3: Test the Bot

Before deployment, you should test if the bot works correctly on your local machine:

1. Open Command Prompt or PowerShell
2. Navigate to the project directory:
   ```
   cd "C:\Users\Alan Leyva\Documents\Atlas\John\ringba-bot"
   ```
3. Run the test script:
   ```
   python test_bot.py
   ```
4. The script will:
   - Launch a Chrome browser
   - Log in to Ringba
   - Navigate to the Reporting tab
   - Extract the Target and RPC data
   - Display the extracted data in the console
   - Ask if you want to send a test notification to Slack

If everything works correctly, you're ready to proceed with deployment to Render.com for 24/7 operation.

## Troubleshooting Setup Issues

### Python Not Found
If you get an error that Python is not recognized:
1. Make sure Python is installed
2. Add Python to your PATH environment variable
3. Try using the full path to Python:
   ```
   C:\Path\To\Python\python.exe -m pip install -r requirements.txt
   ```

### Permission Issues
If you get "Access denied" errors:
1. Right-click on Command Prompt or PowerShell and select "Run as administrator"
2. Navigate to the project directory and run the commands again

### Chrome Driver Issues
If you get errors related to ChromeDriver:
1. Make sure Google Chrome is installed on your system
2. Try running the test script again - it should download the correct ChromeDriver version
3. If problems persist, download ChromeDriver manually from [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads)

### Dependency Installation Failures
If pip fails to install dependencies:
1. Ensure you have internet connectivity
2. Try updating pip:
   ```
   python -m pip install --upgrade pip
   ```
3. Install dependencies one by one to identify which one is causing issues

## Next Steps

After successful testing, follow the instructions in `DEPLOYMENT_GUIDE.md` to deploy the bot to Render.com for continuous operation.