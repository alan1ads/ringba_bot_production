"""
Stealth Selenium approach for Ringba RPC Monitor Bot
This uses standard Selenium with enhanced anti-detection techniques
"""

import os
import time
import logging
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv
import chrome_helper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add human-like behavior with random delays
def random_sleep(min_seconds=0.5, max_seconds=2.0):
    """Sleep for a random amount of time to simulate human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_like_typing(element, text):
    """Type text with random delays between keystrokes"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.2))  # Random delay between keystrokes

def setup_stealth_driver():
    """
    Setup a Chrome WebDriver with stealth mode and anti-detection features
    """
    logger.info("Setting up stealth Chrome WebDriver...")
    
    # Get Chrome version for appropriate driver
    chrome_version = chrome_helper.get_chrome_version()
    logger.info(f"Detected Chrome version: {chrome_version}")
    
    # Get the path to the appropriate ChromeDriver
    driver_path = chrome_helper.download_chromedriver(chrome_version)
    logger.info(f"Using ChromeDriver from: {driver_path}")
    
    # Set up Chrome options with stealth mode
    chrome_options = Options()
    
    # Don't use headless mode as it's more easily detected
    # Instead, we'll position the window offscreen
    chrome_options.add_argument("--window-position=-2000,0")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Add stealth mode settings
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Additional options to help avoid detection
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-gpu")
    
    # Add a user agent to appear like a regular browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    
    # Setup custom preferences to avoid detection
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "download_restrictions": 3,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Setup and start the WebDriver
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)
    
    # Execute CDP commands to make the driver stealthier
    # This updates navigator.webdriver value to undefined
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Overwrite the 'plugins' property to use a custom getter
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                // Create an object with fake plugins
                const plugins = {
                    length: 5,
                    refresh: function(){},
                    item: function(index) { return this[index]; },
                    namedItem: function(name) { return this[name]; },
                    0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Portable Document Format' },
                    2: { name: 'Native Client', filename: 'internal-nacl-plugin', description: 'Native Client Executable' },
                    3: { name: 'Microsoft Edge PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    4: { name: 'Microsoft Edge PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Portable Document Format' }
                };
                return plugins;
            }
        });
        
        // Overwrite the languages property
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'es', 'fr']
        });
        
        // Modify the permission values
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.__proto__.query = parameters =>
            parameters.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : originalQuery(parameters);
        """
    })
    
    logger.info("Stealth WebDriver setup complete")
    return driver

def login_to_ringba_stealthily(driver, email, password):
    """
    Login to Ringba with human-like behavior to avoid detection
    """
    logger.info("Starting stealth login to Ringba...")
    
    try:
        # Open a normal site first (misdirection)
        logger.info("Navigating to Google first...")
        driver.get("https://www.google.com")
        random_sleep(1, 3)
        
        # Now navigate to Ringba in a human-like way
        logger.info("Navigating to Ringba login page...")
        driver.get("https://app.ringba.com/")
        random_sleep(2, 4)
        
        # Take a screenshot
        driver.save_screenshot("stealth_ringba_login.png")
        logger.info("Login page screenshot saved")
        
        # Wait for login form
        logger.info("Waiting for login form...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        
        # Enter email with human-like typing
        logger.info("Entering email address...")
        email_field = driver.find_element(By.ID, "email")
        email_field.click()
        random_sleep()
        human_like_typing(email_field, email)
        random_sleep()
        
        # Tab to password field like a human would
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB)
        actions.perform()
        random_sleep()
        
        # Enter password with human-like typing
        logger.info("Entering password...")
        password_field = driver.find_element(By.ID, "password")
        human_like_typing(password_field, password)
        random_sleep(1, 2)
        
        # Take a screenshot before clicking login
        driver.save_screenshot("stealth_before_login_click.png")
        
        # Click login button
        logger.info("Clicking login button...")
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        
        # Move mouse to button before clicking (more human-like)
        actions = ActionChains(driver)
        actions.move_to_element(login_button)
        actions.perform()
        random_sleep(0.5, 1)
        
        login_button.click()
        logger.info("Login button clicked")
        
        # Wait for dashboard with long timeout
        logger.info("Waiting for dashboard to load...")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Dashboard')]"))
        )
        
        # Take a screenshot of the dashboard
        driver.save_screenshot("stealth_dashboard.png")
        logger.info("Successfully logged in to Ringba")
        
        return True
    except Exception as e:
        logger.error(f"Error during stealth login: {e}")
        driver.save_screenshot("stealth_login_error.png")
        return False

def test_stealth_login():
    """
    Test the stealth login approach
    """
    # Load environment variables
    load_dotenv()
    
    # Check if environment variables are set
    ringba_email = os.getenv("RINGBA_EMAIL")
    ringba_password = os.getenv("RINGBA_PASSWORD")
    
    if not ringba_email or not ringba_password:
        logger.error("Missing required environment variables. Please check .env file.")
        return False
    
    logger.info("Starting stealth login test...")
    driver = None
    
    try:
        # Set up the stealth driver
        driver = setup_stealth_driver()
        
        # Try to login
        success = login_to_ringba_stealthily(driver, ringba_email, ringba_password)
        
        if success:
            logger.info("Successfully logged in with stealth approach")
            
            # Try to navigate to Reporting
            logger.info("Attempting to navigate to Reporting...")
            try:
                # Move mouse to the Reporting link
                reporting_link = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Reporting']/../.."))
                )
                
                actions = ActionChains(driver)
                actions.move_to_element(reporting_link)
                actions.perform()
                random_sleep(0.5, 1)
                
                reporting_link.click()
                logger.info("Clicked Reporting link")
                
                # Wait for a bit for page to load
                random_sleep(5, 10)
                
                # Take screenshot of reporting page
                driver.save_screenshot("stealth_reporting.png")
                logger.info("Reporting page screenshot saved")
            except Exception as nav_error:
                logger.error(f"Error navigating to Reporting: {nav_error}")
                driver.save_screenshot("stealth_reporting_error.png")
            
            return True
        else:
            logger.error("Failed to login with stealth approach")
            return False
            
    except Exception as e:
        logger.error(f"Error in stealth test: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

if __name__ == "__main__":
    print("=== STEALTH SELENIUM TEST ===")
    print("This script tests a stealth approach to login to Ringba")
    print("Starting test...")
    
    success = test_stealth_login()
    
    if success:
        print("\n✅ TEST SUCCESSFUL: Successfully logged in with stealth approach!")
        print("This approach can be integrated into the main bot.")
    else:
        print("\n❌ TEST FAILED: Could not login with stealth approach.")
        print("Please check the screenshots and logs for more details.") 