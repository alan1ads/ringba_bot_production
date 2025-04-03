# Troubleshooting Guide for Ringba RPC Monitor Bot

This guide addresses common issues you might encounter when setting up and running the Ringba RPC Monitor Bot.

## Quick Fixes for Common Errors

### Error: "cannot access local variable 'ChromeDriverManager'"

This is a Python scope issue with the ChromeDriverManager import.

**Solution:**
1. The latest update to both `ringba_bot.py` and `test_bot.py` should have fixed this issue
2. If you still encounter it, ensure you're running the latest version of the scripts
3. Try running with the simplified approach:

```python
# Simple direct approach
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

chrome_options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
```

### Error: "ChromeDriverManager.__init__() got an unexpected keyword argument"

This error occurs when your webdriver-manager version doesn't support certain parameters.

**Solution:**
1. The updated code removes these problematic parameters
2. Update webdriver-manager: `pip install --upgrade webdriver-manager`
3. Try with the basic approach shown above

## ChromeDriver Issues

### Error: "%1 is not a valid Win32 application"

This error occurs due to a mismatch between your Chrome browser's architecture (32-bit vs 64-bit) and the downloaded ChromeDriver.

**Solution 1: Use the updated code**
The updated version of `ringba_bot.py` and `test_bot.py` should automatically handle this issue by trying multiple approaches.

**Solution 2: Manual fix**
If you still encounter issues:

1. Check your Chrome version:
   - Open Chrome
   - Navigate to chrome://settings/help
   - Note your Chrome version (e.g., 134.0.6998.165)

2. Download the correct ChromeDriver:
   - Go to [ChromeDriver downloads](https://googlechromelabs.github.io/chrome-for-testing/)
   - Download the version that matches your Chrome (both 32-bit/win32 and 64-bit/win64)

3. Extract the downloaded ZIP file

4. Update your code to use the specific ChromeDriver path:
   ```python
   driver_path = "C:/path/to/your/chromedriver.exe"
   service = Service(executable_path=driver_path)
   driver = webdriver.Chrome(service=service, options=chrome_options)
   ```

### Error: "ChromeDriver executable needs to be in PATH"

**Solution:**
1. Add ChromeDriver to your system PATH, or
2. Specify the executable path directly as shown above

## Selenium Issues

### Elements Not Found

If the bot fails to find elements on the Ringba page:

**Solution:**
1. Websites change their structure over time. You may need to update the selectors in the code.
2. Increase wait times by modifying lines like:
   ```python
   WebDriverWait(driver, 30).until(...)  # Increase from 20 to 30 seconds
   ```
3. Add more explicit waits before interactions

### TimeoutException

**Solution:**
1. Check your internet connection
2. Increase timeout values in WebDriverWait calls
3. Verify Ringba website is accessible manually

## Login Issues

### Cannot Log In to Ringba

**Solution:**
1. Double-check your credentials in the `.env` file
2. Ensure Ringba hasn't changed their login page
3. Check if Ringba has implemented CAPTCHA or other security measures
4. Try logging in manually to verify account status

## Slack Notification Issues

### No Notifications Being Sent

**Solution:**
1. Verify your Slack webhook URL is correct
2. Check if the webhook is still active in your Slack workspace
3. Ensure your network allows outbound connections to Slack APIs
4. Test the webhook with curl:
   ```
   curl -X POST -H 'Content-type: application/json' --data '{"text":"Hello, World!"}' YOUR_WEBHOOK_URL
   ```

## Scheduling Issues

### Bot Not Running at Scheduled Times

**Solution:**
1. Ensure the server time matches your expected timezone
2. Check if the process is still running (might have crashed)
3. Verify logs for any errors that occurred during scheduled runs
4. If using Render.com, verify the service isn't sleeping (use a paid plan)

## Render.com Deployment Issues

### Deployment Fails

**Solution:**
1. Check Render.com build logs for specific errors
2. Verify your Dockerfile is correctly formatted
3. Ensure all required environment variables are set in the Render dashboard
4. Check if your service has enough resources (memory/CPU)

### Service Crashes After Deployment

**Solution:**
1. Check logs in the Render dashboard
2. Increase resource allocation if the service is running out of memory
3. Implement better error handling in the code
4. Add health check endpoints to monitor service status

## Data Extraction Issues

### No Data Extracted from Table

**Solution:**
1. The table structure in Ringba may have changed
2. Update the selectors in the `extract_target_rpc_data()` function
3. Add debug logging to identify which part of the extraction is failing
4. Take a screenshot during the process to verify what the bot is seeing:
   ```python
   # Add in extract_target_rpc_data function
   driver.save_screenshot("debug_screenshot.png")
   ```

## Installation Issues

### Cannot Install Dependencies

**Solution:**
1. Update pip: `python -m pip install --upgrade pip`
2. Install dependencies one by one to identify problematic packages
3. Check for Python version compatibility issues
4. Use a virtual environment: `python -m venv venv` and activate it

### Python Version Errors

**Solution:**
1. Check which Python version you're running: `python --version`
2. The bot is designed for Python 3.8+ - upgrade if needed
3. Use a specific Python version with: `py -3.8` or `python3.8` instead of `python`

## Getting Additional Help

If you're still experiencing issues after trying these solutions:

1. Check the log file (`ringba_bot.log`) for more detailed error information
2. Search for specific error messages online
3. Check GitHub issues for the libraries used (Selenium, webdriver-manager, etc.)
4. Reach out for professional support if the bot is critical to your operations