"""
Ringba RPC Monitor Bot - Production Version

This bot checks Ringba's reporting tab at scheduled times (11 AM, 2 PM, and 4 PM ET),
extracts Target and RPC data, and sends Slack notifications for any targets with
RPC values below the threshold.

Usage:
1. Set up environment variables in .env file
2. Run this script on a server that will remain active (or use a service like Render.com)
3. The bot will automatically check at the scheduled times

Environment variables:
- RINGBA_EMAIL: Your Ringba account email
- RINGBA_PASSWORD: Your Ringba account password
- SLACK_WEBHOOK_URL: Your Slack webhook URL for notifications
"""

import os
import time
import logging
import asyncio
import random
import schedule
from datetime import datetime
import pytz
import json
import sys
from dotenv import load_dotenv
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ringba_bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Ensure required packages are installed
def ensure_packages_installed():
    """Ensure all required packages are installed"""
    try:
        import pandas
    except ImportError:
        logger.info("Installing pandas...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
        import pandas
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("Installing playwright...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.async_api import async_playwright

# Run package check at startup
ensure_packages_installed()

# Health check endpoint for Render.com
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Ringba RPC Monitor Bot is running')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        # Suppress HTTP logs to avoid cluttering the console
        return

def start_health_check_server():
    """Start a simple HTTP server for health checks"""
    port = int(os.environ.get('PORT', 10000))  # Render.com sets the PORT environment variable
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Starting health check server on port {port}")
    server.serve_forever()

# Constants
RINGBA_URL = "https://app.ringba.com/#/login"
RINGBA_EMAIL = os.getenv("RINGBA_EMAIL")
RINGBA_PASSWORD = os.getenv("RINGBA_PASSWORD")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
RPC_THRESHOLD = 12.0  # $12 threshold for notifications

# Random delay function for human-like behavior
def random_sleep_async(min_seconds=0.5, max_seconds=2.0):
    """Generate a random sleep duration for human-like behavior"""
    return random.uniform(min_seconds, max_seconds)

async def setup_browser(headless=True):
    """
    Set up and configure Playwright browser
    """
    try:
        from playwright.async_api import async_playwright
        
        logger.info("Starting Playwright...")
        playwright = await async_playwright().start()
        
        # Use chromium for best compatibility
        browser = await playwright.chromium.launch(
            headless=headless,  # Use headless=True for production
            args=[
                "--disable-features=BlinkGenPropertyTrees",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        # Create a context with specific viewport and user agent
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        
        # Add script to hide automation
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Overwrite plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return {
                        length: 5,
                        item: () => null,
                        refresh: () => {},
                        namedItem: () => null,
                        0: {name: 'Chrome PDF Plugin'},
                        1: {name: 'Chrome PDF Viewer'},
                        2: {name: 'Native Client'},
                        3: {name: 'Microsoft Edge PDF Plugin'},
                        4: {name: 'Microsoft Edge PDF Viewer'}
                    };
                }
            });
            
            // Add languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'es']
            });
        """)
        
        # Create a new page
        page = await context.new_page()
        
        logger.info("Playwright browser setup complete")
        return playwright, browser, context, page
    except Exception as e:
        logger.error(f"Error setting up Playwright: {e}")
        raise

async def login_to_ringba(page):
    """
    Log in to Ringba website using Playwright
    """
    logger.info("Logging in to Ringba...")
    
    try:
        # First navigate to main Ringba page
        logger.info("Navigating to Ringba main page...")
        await page.goto("https://www.ringba.com/")
        await asyncio.sleep(random_sleep_async(2, 3))
        
        # Look for and click the login button on the main page
        login_btn_selectors = [
            "a:has-text('Login')",
            "a[href*='login']", 
            "button:has-text('Login')",
            ".menu a[href*='login']"
        ]
        
        for selector in login_btn_selectors:
            try:
                login_btn = await page.wait_for_selector(selector, state="visible", timeout=3000)
                if login_btn:
                    logger.info(f"Found login button with selector: {selector}")
                    await login_btn.click()
                    logger.info("Clicked login button on main page")
                    await asyncio.sleep(random_sleep_async(2, 3))
                    break
            except Exception:
                pass
        
        # Now we should be on the login page - make sure we have the right URL
        current_url = page.url
        if "login" not in current_url:
            logger.info("Directly navigating to login page...")
            await page.goto("https://app.ringba.com/#/login")
            await asyncio.sleep(random_sleep_async(2, 3))
        
        # Try different selectors for the login form
        selectors_to_try = [
            "input[type='email']",
            "#email", 
            "input[name='email']", 
            "input[placeholder*='email' i]",
            "form input[type='text']:first-child"
        ]
        
        # Try to find the email field
        logger.info("Looking for email field...")
        email_field = None
        for selector in selectors_to_try:
            try:
                # Use a shorter timeout for each attempt
                email_field = await page.wait_for_selector(selector, state="visible", timeout=5000)
                if email_field:
                    logger.info(f"Found email field with selector: {selector}")
                    break
            except Exception:
                pass
        
        if not email_field:
            logger.error("Could not find login form")
            return False
        
        # We found the email field, continue with login
        await email_field.click()
        await email_field.fill(RINGBA_EMAIL)
        
        # Try to find password field
        logger.info("Looking for password field...")
        password_field = await page.wait_for_selector("input[type='password']", state="visible", timeout=5000)
        await password_field.click()
        await password_field.fill(RINGBA_PASSWORD)
        
        # Look for login button
        logger.info("Looking for login button...")
        login_button = await page.wait_for_selector(
            "button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign in')", 
            state="visible", 
            timeout=5000
        )
        
        await login_button.click()
        logger.info("Clicked login button")
        
        # Wait for navigation after login
        logger.info("Waiting for dashboard to load...")
        try:
            # Wait for login to complete - looking for common dashboard elements
            await page.wait_for_selector(
                "//span[contains(text(), 'Dashboard')] | //a[contains(text(), 'Dashboard')] | //div[contains(@class, 'dashboard')]", 
                state="visible", 
                timeout=60000
            )
            logger.info("Successfully logged in to Ringba")
            return True
        except Exception as dash_error:
            logger.error(f"Error waiting for dashboard: {dash_error}")
            
            # Check if we're on another page but logged in
            current_url = page.url
            if "ringba.com" in current_url and "login" not in current_url:
                logger.info(f"Appears to be logged in, but on page: {current_url}")
                return True
                
            return False
        
    except Exception as e:
        logger.error(f"Error logging in to Ringba: {e}")
        return False

async def navigate_to_reporting(page):
    """
    Navigate to the Reporting tab and export CSV data
    """
    logger.info("Navigating to Reporting tab...")
    
    try:
        # Navigate directly to the call logs report page
        await page.goto("https://app.ringba.com/#/dashboard/call-logs/report/new")
        logger.info("Navigating directly to call-logs/report/new page")
        
        # Wait for the page to load
        await asyncio.sleep(10)
        
        # Save a screenshot for debugging
        await page.screenshot(path="reporting_navigation.png")
        logger.info("Saved screenshot after navigating to Reporting")
        
        # Try several approaches to find the right UI to interact with
        
        # Approach 1: Look for and click the "Apply" button to load the report
        try:
            apply_button = await page.wait_for_selector("button:has-text('Apply')", timeout=5000)
            if apply_button:
                logger.info("Found Apply button, clicking it to load report data")
                await apply_button.click()
                await asyncio.sleep(10)  # Wait for data to load
        except Exception as e:
            logger.warning(f"Could not find or click Apply button: {e}")
        
        # Approach 2: Try to click on the Table view option
        try:
            table_options = [
                "text=Table",
                "button:has-text('Table')",
                "div[role='tab']:has-text('Table')",
                ".tab:has-text('Table')"
            ]
            
            for selector in table_options:
                try:
                    table_tab = await page.wait_for_selector(selector, timeout=2000)
                    if table_tab:
                        logger.info(f"Found Table tab with selector: {selector}, clicking it")
                        await table_tab.click()
                        await asyncio.sleep(5)
                        break
                except Exception:
                    pass
        except Exception as tab_error:
            logger.warning(f"Could not find or click Table tab: {tab_error}")
        
        # Approach 3: Look for any "Run Report" or similar button
        try:
            run_buttons = [
                "button:has-text('Run')",
                "button:has-text('Run Report')",
                "button:has-text('Generate')",
                "button:has-text('Submit')"
            ]
            
            for btn_selector in run_buttons:
                try:
                    run_btn = await page.wait_for_selector(btn_selector, timeout=2000)
                    if run_btn:
                        logger.info(f"Found button with selector: {btn_selector}, clicking it")
                        await run_btn.click()
                        await asyncio.sleep(10)
                        break
                except Exception:
                    pass
        except Exception as btn_error:
            logger.warning(f"Could not find or click run button: {btn_error}")
        
        # Take another screenshot after interactions
        await page.screenshot(path="after_report_interactions.png")
        logger.info("Saved screenshot after report page interactions")
        
        return True
        
    except Exception as e:
        logger.error(f"Error navigating to Reporting tab: {e}")
        return False

async def export_and_download_csv(page):
    """
    Find and click the EXPORT CSV button, then download the CSV file
    """
    logger.info("Looking for EXPORT CSV button...")
    
    try:
        # First take a screenshot to debug
        await page.screenshot(path="before_export.png")
        
        # Try multiple selectors for the EXPORT CSV button
        export_selectors = [
            "button:has-text('EXPORT CSV')",
            "button.export-csv",
            ".export-csv",
            "button:has-text('Export')",
            "button:has-text('CSV')",
            "text=EXPORT CSV"
        ]
        
        export_button = None
        for selector in export_selectors:
            try:
                logger.info(f"Trying to find export button with selector: {selector}")
                export_button = await page.wait_for_selector(selector, timeout=3000)
                if export_button:
                    logger.info(f"Found export button with selector: {selector}")
                    break
            except Exception:
                pass
                
        if not export_button:
            logger.error("Could not find EXPORT CSV button")
            return False
            
        # Set up a download handler before clicking the button
        download_path = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_path, exist_ok=True)
        
        # Handle the download event
        logger.info("Setting up download handler")
        async with page.expect_download() as download_info:
            await export_button.click()
            logger.info("Clicked EXPORT CSV button")
        
        # Wait for the download to complete
        download = await download_info.value
        logger.info(f"Download started: {download.suggested_filename}")
        
        # Save the downloaded file
        csv_path = os.path.join(download_path, download.suggested_filename)
        await download.save_as(csv_path)
        logger.info(f"Downloaded CSV to: {csv_path}")
        
        return csv_path
    
    except Exception as e:
        logger.error(f"Error downloading CSV: {e}")
        return False

async def read_csv_data(csv_path):
    """
    Read the downloaded CSV file and extract Target and RPC data
    """
    logger.info(f"Reading CSV data from: {csv_path}")
    
    try:
        import pandas as pd
        
        # Read the CSV file
        df = pd.read_csv(csv_path)
        logger.info(f"CSV loaded with {len(df)} rows and columns: {', '.join(df.columns)}")
        
        # Look for Target and RPC columns
        target_column = None
        rpc_column = None
        
        # Check for exact column matches
        for column in df.columns:
            col_lower = column.lower()
            if col_lower == 'target':
                target_column = column
            elif col_lower == 'rpc':
                rpc_column = column
        
        # If not found, try partial matches
        if target_column is None:
            for column in df.columns:
                if 'target' in column.lower():
                    target_column = column
                    break
                    
        if rpc_column is None:
            for column in df.columns:
                if 'rpc' in column.lower():
                    rpc_column = column
                    break
        
        if target_column is None or rpc_column is None:
            logger.warning(f"Could not identify Target or RPC columns in: {df.columns}")
            return []
            
        logger.info(f"Using columns: Target='{target_column}', RPC='{rpc_column}'")
        
        # Extract the data
        data = []
        for _, row in df.iterrows():
            target_value = row[target_column]
            rpc_value = row[rpc_column]
            
            # Skip empty values
            if pd.isna(target_value) or pd.isna(rpc_value):
                continue
                
            # Convert RPC to float if it's a string with a dollar sign
            if isinstance(rpc_value, str):
                rpc_value = rpc_value.replace('$', '').replace(',', '')
                try:
                    rpc_value = float(rpc_value)
                except ValueError:
                    logger.warning(f"Could not convert RPC value to float: {rpc_value}")
                    continue
            
            data.append({
                'Target': str(target_value),
                'RPC': float(rpc_value)
            })
        
        logger.info(f"Extracted {len(data)} rows of Target and RPC data from CSV")
        
        # Log the first few entries for debugging
        for i, item in enumerate(data[:5]):
            logger.info(f"CSV Row {i}: Target: {item['Target']}, RPC: ${item['RPC']}")
            
        return data
        
    except Exception as e:
        logger.error(f"Error reading CSV data: {e}")
        return []

async def send_slack_notification(data):
    """
    Send Slack notification for low RPC values
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured")
        return False
        
    try:
        import requests
        
        # Filter for low RPC values
        low_rpc_data = [item for item in data if item["RPC"] < RPC_THRESHOLD]
        
        if not low_rpc_data:
            logger.info(f"No targets with RPC below ${RPC_THRESHOLD}")
            return True
            
        # Create message text
        now = datetime.now(pytz.timezone('US/Eastern'))
        message = f"*RPC ALERT* - {now.strftime('%Y-%m-%d %I:%M %p ET')}:\n"
        message += f"The following targets have RPC values below ${RPC_THRESHOLD}:\n\n"
        
        for item in low_rpc_data:
            message += f"• *{item['Target']}*: ${item['RPC']:.2f}\n"
            
        # Create payload for Slack
        payload = {
            "text": message,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }
        
        # Send to Slack
        logger.info(f"Sending Slack notification for {len(low_rpc_data)} low RPC values")
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.error(f"Failed to send Slack notification: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False

async def check_rpc_values():
    """
    Main function to check RPC values
    """
    logger.info("Starting RPC check...")
    
    # Verify environment variables
    if not RINGBA_EMAIL or not RINGBA_PASSWORD:
        logger.error("Missing Ringba credentials. Please check .env file.")
        return
        
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured. No notifications will be sent.")
    
    playwright = None
    browser = None
    
    try:
        # Setup browser (use headless=True for production)
        playwright, browser, context, page = await setup_browser(headless=True)
        
        # Login to Ringba
        login_success = await login_to_ringba(page)
        
        if not login_success:
            logger.error("Login failed. Aborting check.")
            return
            
        # Navigate to Reporting
        reporting_success = await navigate_to_reporting(page)
        
        if not reporting_success:
            logger.error("Failed to navigate to Reporting tab. Aborting check.")
            return
        
        # Export and download CSV
        csv_path = await export_and_download_csv(page)
        
        if not csv_path:
            logger.error("Failed to download CSV. Aborting check.")
            return
            
        # Read data from CSV
        data = await read_csv_data(csv_path)
        
        if not data:
            logger.error("No data extracted from CSV. Aborting check.")
            return
            
        # Send notification if needed
        await send_slack_notification(data)
        
        logger.info("RPC check completed successfully")
        
    except Exception as e:
        logger.error(f"Error in RPC check: {e}")
        
    finally:
        # Clean up
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

def run_check():
    """
    Wrapper to run the async check function
    """
    logger.info("Scheduled check triggered")
    asyncio.run(check_rpc_values())

def setup_schedule():
    """
    Set up the schedule for automatic checks
    """
    # Schedule checks at 11 AM, 2 PM, and 4 PM Eastern Time
    eastern = pytz.timezone('US/Eastern')
    local_tz = pytz.timezone('US/Eastern')  # Adjust based on server location if needed
    
    # Get current time in both timezones
    now_eastern = datetime.now(eastern)
    now_local = datetime.now(local_tz)
    
    # Calculate offset to convert from Eastern to local time
    offset_hours = (now_local.hour - now_eastern.hour) % 24
    
    # Schedule checks in local time
    schedule.every().day.at(f"{(11 + offset_hours) % 24:02d}:00").do(run_check)
    logger.info(f"Scheduled check at 11:00 AM ET (local time: {(11 + offset_hours) % 24:02d}:00)")
    
    schedule.every().day.at(f"{(14 + offset_hours) % 24:02d}:00").do(run_check)
    logger.info(f"Scheduled check at 2:00 PM ET (local time: {(14 + offset_hours) % 24:02d}:00)")
    
    schedule.every().day.at(f"{(16 + offset_hours) % 24:02d}:30").do(run_check)
    logger.info(f"Scheduled check at 4:30 PM ET (local time: {(16 + offset_hours) % 24:02d}:30)")

def main():
    """
    Main function to start the bot
    """
    print("==== Ringba RPC Monitor Bot ====")
    print("This bot will check Ringba RPC values at scheduled times and send Slack notifications.")
    
    # Verify environment variables
    if not RINGBA_EMAIL or not RINGBA_PASSWORD:
        print("ERROR: Missing Ringba credentials. Please check .env file.")
        sys.exit(1)
        
    if not SLACK_WEBHOOK_URL:
        print("WARNING: Slack webhook URL not configured. No notifications will be sent.")
    
    # Start health check server in a separate thread
    health_check_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_check_thread.start()
    print(f"Health check server started on port {int(os.environ.get('PORT', 10000))}")
    
    # Set up schedule
    setup_schedule()
    
    # Run an initial check
    print("\nRunning initial check...")
    run_check()
    
    # Enter the schedule loop
    print("\nEntering schedule loop. Bot is now running.")
    print("Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check schedule every minute

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nERROR: {e}")
        sys.exit(1) 