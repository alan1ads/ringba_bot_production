import os
import time
import logging
import schedule
import json
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import chrome_helper
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ringba_bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
RINGBA_URL = "https://app.ringba.com/#/login"  # Specific login page URL
RINGBA_MAIN_URL = "https://www.ringba.com/"    # Main Ringba website
RINGBA_EMAIL = os.getenv("RINGBA_EMAIL")
RINGBA_PASSWORD = os.getenv("RINGBA_PASSWORD")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
RPC_THRESHOLD = 12.0  # $12 threshold for notifications

def setup_driver():
    """
    Set up and configure Chrome WebDriver for Selenium using our custom chrome_helper
    """
    logger.info("Setting up Chrome WebDriver using chrome_helper...")
    
    try:
        # Use our custom ChromeDriver helper that handles all the compatibility issues
        driver = chrome_helper.get_selenium_webdriver(headless=True)
        logger.info("Successfully set up WebDriver using chrome_helper")
        return driver
    except Exception as e:
        logger.error(f"Error setting up WebDriver: {e}")
        raise

def login_to_ringba(driver):
    """
    Log in to Ringba website
    """
    logger.info("Logging in to Ringba...")
    
    try:
        # Navigate to the login page
        driver.get(RINGBA_URL)
        
        # Take a screenshot for debugging
        try:
            driver.save_screenshot("ringba_login_before.png")
            logger.info("Login page screenshot saved")
        except Exception as ss_err:
            logger.warning(f"Could not save screenshot: {ss_err}")
        
        # Wait for login form to load with improved handling
        logger.info("Waiting for login form...")
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Add longer wait time
                WebDriverWait(driver, 45).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                logger.info("Login form found")
                break
            except Exception as wait_error:
                logger.warning(f"Attempt {attempt+1}/{max_attempts} - Login form wait error: {wait_error}")
                if attempt + 1 == max_attempts:
                    driver.save_screenshot("login_form_error.png")
                    logger.error("Could not find login form after multiple attempts")
                    raise
                driver.refresh()
                time.sleep(5)  # Wait before retrying
        
        # Enter credentials with explicit waits
        logger.info("Entering credentials...")
        email_field = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "email"))
        )
        email_field.clear()
        email_field.send_keys(RINGBA_EMAIL)
        
        password_field = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "password"))
        )
        password_field.clear()
        password_field.send_keys(RINGBA_PASSWORD)
        
        # Take screenshot before clicking login
        driver.save_screenshot("before_login_click.png")
        
        # Click login button with retry
        logger.info("Clicking login button...")
        for attempt in range(3):
            try:
                login_button = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
                )
                login_button.click()
                logger.info("Login button clicked")
                break
            except Exception as click_error:
                logger.warning(f"Attempt {attempt+1}/3 - Login button click error: {click_error}")
                if attempt == 2:  # Last attempt, try JavaScript click
                    try:
                        logger.info("Trying JavaScript click as last resort")
                        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
                        driver.execute_script("arguments[0].click();", login_button)
                    except Exception as js_error:
                        logger.error(f"JavaScript click also failed: {js_error}")
                        raise
        
        # Wait for dashboard to load - extend timeout for slower connections
        logger.info("Waiting for dashboard to load...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Dashboard')]"))
            )
            logger.info("Successfully logged in to Ringba")
        except Exception as dashboard_error:
            logger.error(f"Dashboard wait error: {dashboard_error}")
            # Take a screenshot of the current state to help debug
            driver.save_screenshot("dashboard_wait_error.png")
            
            # Check if we're already logged in but on a different page
            if "ringba.com" in driver.current_url and "login" not in driver.current_url:
                logger.info("We appear to be logged in, but on a different page")
                return  # Continue execution
            raise
    except Exception as e:
        logger.error(f"Error logging in to Ringba: {e}")
        # Take a screenshot of the error state
        driver.save_screenshot("login_error.png")
        raise

def navigate_to_reporting(driver):
    """
    Navigate to the Reporting tab and prepare for data extraction
    """
    logger.info("Navigating to Reporting tab...")
    
    try:
        # Find and click on Reporting in the side navigation
        logger.info("Looking for Reporting link in navigation...")
        reporting_link = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Reporting']/../.."))
        )
        reporting_link.click()
        logger.info("Clicked Reporting link")
        
        # Wait for the reporting page to load
        logger.info("Waiting for reporting page to load...")
        
        # First wait for the page structure to be visible
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'table')]"))
        )
        
        # Additional wait to ensure all data is loaded
        time.sleep(10)  # Allow time for table data to fully load
        
        logger.info("Successfully navigated to Reporting tab")
        
        # Take a screenshot for debugging if needed
        try:
            driver.save_screenshot("reporting_page.png")
            logger.info("Screenshot saved as reporting_page.png")
        except Exception as ss_error:
            logger.warning(f"Could not save screenshot: {ss_error}")
        
    except Exception as e:
        logger.error(f"Error navigating to Reporting tab: {e}")
        raise

def extract_target_rpc_data(driver):
    """
    Extract Target and RPC data from the table
    """
    logger.info("Extracting Target and RPC data...")
    table_data = []
    
    try:
        # Take screenshot for debugging
        driver.save_screenshot("before_extraction.png")
        logger.info("Saved screenshot before extraction")
        
        # Wait for the table to load
        logger.info("Waiting for table to be present...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'table') or contains(@class, 'grid')]"))
        )
        
        # Wait for actual data to load
        logger.info("Waiting for table data...")
        time.sleep(5)  # Additional wait for dynamic content

        # Get the page source for BeautifulSoup parsing
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Log the HTML structure for debugging (only in logs, not in production)
        with open("table_html.txt", "w", encoding="utf-8") as f:
            # Only save a portion of the HTML focused on the table
            table_element = soup.select_one("div[class*='table'], div[class*='grid']")
            if table_element:
                f.write(str(table_element))
                logger.info("Saved table HTML structure for debugging")
            else:
                f.write("Table element not found")
                logger.warning("Could not find table element for HTML debugging")
        
        # Try multiple selectors to find the table rows
        logger.info("Trying to locate table rows...")
        
        # Method 1: Using table-specific classes
        table_rows = soup.select("div.table-body-row, tr.table-row, div[class*='row']:not([class*='header'])")
        
        # Method 2: If Method 1 fails, look for the Summary section which contains the table
        if not table_rows:
            logger.info("Method 1 failed, trying alternate selector...")
            summary_section = soup.select_one("div#Summary, div.Summary, section#summary, [data-testid='summary-section']")
            if summary_section:
                table_rows = summary_section.select("div[class*='row']:not([class*='header']), tr")
        
        # Method 3: Last resort - look for any table-like structure with Target and RPC columns
        if not table_rows:
            logger.info("Method 2 failed, trying last resort selector...")
            # Find headers first to identify the table
            headers = soup.select("th, div[class*='header'] div[class*='cell']")
            header_texts = [h.get_text(strip=True) for h in headers]
            
            target_index = -1
            rpc_index = -1
            
            for i, text in enumerate(header_texts):
                if 'target' in text.lower():
                    target_index = i
                if 'rpc' in text.lower():
                    rpc_index = i
            
            if target_index >= 0 and rpc_index >= 0:
                logger.info(f"Found Target column at index {target_index} and RPC column at index {rpc_index}")
                # Now find rows that correspond to these columns
                all_rows = soup.select("tr, div[class*='row']")
                for row in all_rows:
                    cells = row.select("td, div[class*='cell']")
                    if len(cells) > max(target_index, rpc_index):
                        target_name = cells[target_index].get_text(strip=True)
                        rpc_text = cells[rpc_index].get_text(strip=True)
                        
                        try:
                            # Remove $ and convert to float
                            rpc_value = float(rpc_text.replace('$', '').replace(',', '').strip())
                            
                            table_data.append({
                                "Target": target_name,
                                "RPC": rpc_value
                            })
                        except ValueError:
                            logger.warning(f"Could not convert RPC value '{rpc_text}' to float for target '{target_name}'")
                
                # Skip the rest of processing if we found data this way
                if table_data:
                    logger.info(f"Method 3 succeeded. Extracted data for {len(table_data)} targets")
                    return table_data
        
        logger.info(f"Found {len(table_rows)} potential table rows")
        
        # Process the found rows
        for row in table_rows:
            # Try different selectors for cells
            target_cell = row.select_one("div[class*='target'], td.target, div[data-col='target'], td[data-col='target'], div:nth-child(1), td:nth-child(1)")
            rpc_cell = row.select_one("div[class*='rpc'], td.rpc, div[data-col='rpc'], td[data-col='rpc']")
            
            # Skip if either cell is missing
            if not target_cell or not rpc_cell:
                continue
                
            target_name = target_cell.get_text(strip=True)
            rpc_text = rpc_cell.get_text(strip=True)
            
            # Convert RPC to float
            try:
                # Remove $ and commas, then convert to float
                rpc_value = float(rpc_text.replace('$', '').replace(',', '').strip())
                
                table_data.append({
                    "Target": target_name,
                    "RPC": rpc_value
                })
            except ValueError:
                logger.warning(f"Could not convert RPC value '{rpc_text}' to float for target '{target_name}'")
        
        if not table_data:
            # One more attempt - use Execute Script to extract directly
            logger.info("Trying JavaScript extraction as fallback...")
            try:
                js_result = driver.execute_script("""
                    const result = [];
                    // Try to find table rows that might contain our data
                    const rows = document.querySelectorAll('tr, div[class*="row"]:not([class*="header"])');
                    
                    for (const row of rows) {
                        // Try to identify target and RPC cells
                        let targetText = '';
                        let rpcText = '';
                        
                        // Look for cells with specific text or class hints
                        const cells = row.querySelectorAll('td, div[class*="cell"]');
                        for (const cell of cells) {
                            const text = cell.textContent.trim();
                            
                            // Check cell classes and content
                            if (cell.className.includes('target') || 
                                cell.getAttribute('data-col') === 'target') {
                                targetText = text;
                            }
                            else if (cell.className.includes('rpc') || 
                                     cell.getAttribute('data-col') === 'rpc' ||
                                     (text.startsWith('$') && text.match(/^\$\d+\.\d+$/))) {
                                rpcText = text;
                            }
                        }
                        
                        if (targetText && rpcText) {
                            // Try to parse RPC value
                            const rpcValue = parseFloat(rpcText.replace('$', '').replace(',', ''));
                            if (!isNaN(rpcValue)) {
                                result.push({
                                    Target: targetText,
                                    RPC: rpcValue
                                });
                            }
                        }
                    }
                    
                    return result;
                """)
                
                if js_result and len(js_result) > 0:
                    table_data = js_result
                    logger.info(f"JavaScript extraction succeeded with {len(table_data)} rows")
            except Exception as js_error:
                logger.warning(f"JavaScript extraction failed: {js_error}")
        
        logger.info(f"Extracted data for {len(table_data)} targets")
        
        # Log the extracted data for debugging
        if table_data:
            for item in table_data:
                logger.info(f"Target: {item['Target']}, RPC: ${item['RPC']}")
        else:
            logger.warning("No data was extracted")
        
        return table_data
    except Exception as e:
        logger.error(f"Error extracting Target and RPC data: {e}")
        # Take screenshot of the error state
        try:
            driver.save_screenshot("extraction_error.png")
            logger.info("Saved screenshot of error state")
        except Exception:
            pass
        return []

def send_slack_notification(low_rpc_data):
    """
    Send notification to Slack when RPC is below threshold
    """
    if not low_rpc_data:
        logger.info("No low RPC values to report")
        return
    
    logger.info(f"Sending Slack notification for {len(low_rpc_data)} low RPC values...")
    
    try:
        # Format the message
        current_time = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d %I:%M %p ET")
        
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"⚠️ Low RPC Alert - {current_time}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The following targets have RPC values below ${RPC_THRESHOLD}:"
                    }
                }
            ]
        }
        
        # Add each low RPC item to the message
        for item in low_rpc_data:
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Target:* {item['Target']}\n*RPC:* ${item['RPC']:.2f}"
                }
            })
        
        # Send the message to Slack
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info("Successfully sent Slack notification")
        else:
            logger.error(f"Failed to send Slack notification. Status code: {response.status_code}, Response: {response.text}")
    
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")

def check_ringba_data():
    """
    Main function to check Ringba data and send notifications if needed
    """
    logger.info("Starting Ringba data check...")
    
    driver = None
    try:
        # Set up WebDriver
        driver = setup_driver()
        
        # Login to Ringba
        login_to_ringba(driver)
        
        # Navigate to Reporting tab
        navigate_to_reporting(driver)
        
        # Extract Target and RPC data
        target_rpc_data = extract_target_rpc_data(driver)
        
        # Filter for low RPC values
        low_rpc_data = [item for item in target_rpc_data if item["RPC"] < RPC_THRESHOLD]
        
        if low_rpc_data:
            logger.info(f"Found {len(low_rpc_data)} targets with RPC below ${RPC_THRESHOLD}")
            # Send notification to Slack
            send_slack_notification(low_rpc_data)
        else:
            logger.info(f"No targets with RPC below ${RPC_THRESHOLD}")
        
    except Exception as e:
        logger.error(f"Error in check_ringba_data: {e}")
        # Send error notification to Slack
        error_message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Ringba Bot Error",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"An error occurred during the Ringba data check:\n```{str(e)}```"
                    }
                }
            ]
        }
        
        try:
            requests.post(
                SLACK_WEBHOOK_URL,
                data=json.dumps(error_message),
                headers={"Content-Type": "application/json"}
            )
        except Exception as slack_error:
            logger.error(f"Failed to send error notification to Slack: {slack_error}")
    
    finally:
        # Close the WebDriver
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

def schedule_checks():
    """
    Schedule checks at specific times
    """
    logger.info("Scheduling checks...")
    
    # Schedule checks at 11 AM, 2 PM, and 4 PM ET
    # Convert to server's local time if needed
    
    # 11 AM ET check
    schedule.every().day.at("11:00").do(check_ringba_data)
    logger.info("Scheduled check for 11:00 AM ET")
    
    # 2 PM ET check
    schedule.every().day.at("14:00").do(check_ringba_data)
    logger.info("Scheduled check for 2:00 PM ET")
    
    # 4 PM ET check
    schedule.every().day.at("16:00").do(check_ringba_data)
    logger.info("Scheduled check for 4:00 PM ET")
    
    # Run the scheduler
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute for pending tasks

if __name__ == "__main__":
    logger.info("Starting Ringba Bot...")
    
    # Check if environment variables are set
    if not RINGBA_EMAIL or not RINGBA_PASSWORD or not SLACK_WEBHOOK_URL:
        logger.error("Missing required environment variables. Please check .env file.")
        exit(1)
    
    try:
        # Schedule regular checks
        schedule_checks()
    except KeyboardInterrupt:
        logger.info("Bot stopped manually")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")