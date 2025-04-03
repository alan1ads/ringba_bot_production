"""
Alternative test script using undetected-chromedriver to bypass potential Ringba anti-bot measures.
"""

import os
import time
import logging
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_with_undetected():
    """
    Test logging into Ringba using undetected-chromedriver
    """
    logger.info("Starting undetected ChromeDriver test...")
    
    # Load environment variables
    load_dotenv()
    
    # Check if environment variables are set
    ringba_email = os.getenv("RINGBA_EMAIL")
    ringba_password = os.getenv("RINGBA_PASSWORD")
    
    if not ringba_email or not ringba_password:
        logger.error("Missing required environment variables. Please check .env file.")
        return False
    
    try:
        # Try to import undetected-chromedriver
        try:
            import undetected_chromedriver as uc
        except ImportError:
            logger.info("Installing undetected-chromedriver...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "undetected-chromedriver"])
            import undetected_chromedriver as uc
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Set up Chrome options
        logger.info("Setting up undetected ChromeDriver...")
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        # Disable features that might cause issues
        options.add_argument("--disable-features=BlinkGenPropertyTrees")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu-driver-bug-workarounds")
        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--force-device-scale-factor=1")
        
        # Get Chrome version
        def get_chrome_version():
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                return version
            except:
                import subprocess
                try:
                    result = subprocess.check_output(
                        ['powershell', '-command', 
                         r'(Get-Item -Path "$env:PROGRAMFILES\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion;'],
                        stderr=subprocess.STDOUT)
                    return result.decode('utf-8').strip()
                except:
                    return None
        
        chrome_version = get_chrome_version()
        logger.info(f"Detected Chrome version: {chrome_version}")
        
        # Create the driver with version
        if chrome_version:
            major_version = chrome_version.split('.')[0]
            logger.info(f"Using Chrome version {major_version}")
            driver = uc.Chrome(options=options, version_main=int(major_version))
        else:
            logger.info("Could not detect Chrome version, using default")
            driver = uc.Chrome(options=options)
        
        driver.implicitly_wait(10)
        
        # Navigate to Ringba
        logger.info("Navigating to Ringba login page...")
        driver.get("https://app.ringba.com/#/login")
        
        # Take a screenshot
        driver.save_screenshot("undetected_login_page.png")
        logger.info("Login page screenshot saved")
        
        # Wait for login form
        logger.info("Waiting for login form...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        
        # Enter credentials
        logger.info("Entering credentials...")
        email_field = driver.find_element(By.ID, "email")
        email_field.clear()
        email_field.send_keys(ringba_email)
        
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(ringba_password)
        
        # Take a screenshot before clicking login
        driver.save_screenshot("undetected_before_login.png")
        
        # Click login button
        logger.info("Clicking login button...")
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # Wait for dashboard (extended timeout)
        logger.info("Waiting for dashboard to load...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Dashboard')]"))
            )
            logger.info("Successfully logged in to Ringba")
            
            # Take screenshot of the dashboard
            driver.save_screenshot("undetected_dashboard.png")
            logger.info("Dashboard screenshot saved")
            
            # Try to navigate to Reporting
            logger.info("Attempting to navigate to Reporting...")
            reporting_link = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Reporting']/../.."))
            )
            reporting_link.click()
            
            # Wait for reporting page to load
            time.sleep(10)
            
            # Take screenshot of reporting page
            driver.save_screenshot("undetected_reporting.png")
            logger.info("Reporting page screenshot saved")
            
            logger.info("Test completed successfully!")
            return True
            
        except Exception as wait_error:
            logger.error(f"Error waiting for dashboard: {wait_error}")
            driver.save_screenshot("undetected_error.png")
            
            # Check if we're logged in but on a different page
            if "ringba.com" in driver.current_url and "login" not in driver.current_url:
                logger.info("Appears to be logged in, but on a different page")
                driver.save_screenshot("undetected_different_page.png")
                return True
            
            return False
            
    except Exception as e:
        logger.error(f"Error in undetected test: {e}")
        try:
            if 'driver' in locals() and driver:
                driver.save_screenshot("undetected_error.png")
                driver.quit()
        except:
            pass
        return False
        
    finally:
        # Clean up
        try:
            if 'driver' in locals() and driver:
                driver.quit()
                logger.info("WebDriver closed")
        except:
            pass

if __name__ == "__main__":
    print("=== UNDETECTED CHROME TEST ===")
    print("This script tests if Ringba login works with undetected-chromedriver")
    print("Starting test...")
    
    success = test_with_undetected()
    
    if success:
        print("\n✅ TEST SUCCESSFUL: Successfully logged in with undetected-chromedriver!")
        print("This approach can be integrated into the main bot.")
    else:
        print("\n❌ TEST FAILED: Could not log in with undetected-chromedriver.")
        print("Please check the screenshots and logs for more details.") 