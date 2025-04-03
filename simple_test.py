"""
Simple test script to verify basic Chrome WebDriver functionality.
This script attempts to just open a browser and navigate to Ringba's login page.
"""

import logging
import time
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_browser_only():
    """
    Basic test to see if Chrome can be launched and navigate to a page
    """
    logger.info("Starting simple browser test...")
    
    try:
        # Import chrome_helper
        import chrome_helper
        
        # Just try to create a browser and navigate to Ringba
        logger.info("Attempting to create WebDriver...")
        driver = chrome_helper.get_selenium_webdriver(headless=False)  # Try with visible browser
        logger.info("WebDriver created successfully!")
        
        # Try to navigate to a simple site first
        logger.info("Navigating to Google...")
        driver.get("https://www.google.com")
        time.sleep(3)
        logger.info("Successfully loaded Google")
        
        # Now try Ringba
        logger.info("Navigating to Ringba login page...")
        driver.get("https://app.ringba.com/#/login")
        time.sleep(5)
        logger.info("Successfully loaded Ringba login page")
        
        # Get page title
        title = driver.title
        logger.info(f"Ringba page title: {title}")
        
        # Take a screenshot
        driver.save_screenshot("ringba_login.png")
        logger.info("Screenshot saved as ringba_login.png")
        
        driver.quit()
        logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during simple browser test: {e}")
        try:
            # Try to take a screenshot if we can
            if 'driver' in locals() and driver:
                driver.save_screenshot("error_screenshot.png")
                logger.info("Error screenshot saved")
                driver.quit()
        except:
            pass
        return False

def test_with_undetected_chrome():
    """
    Try alternative approach using undetected-chromedriver
    """
    logger.info("Trying with undetected-chromedriver...")
    
    try:
        # Check if undetected-chromedriver is installed
        try:
            import undetected_chromedriver as uc
        except ImportError:
            logger.info("Installing undetected-chromedriver...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "undetected-chromedriver"])
            import undetected_chromedriver as uc
        
        logger.info("Creating undetected Chrome browser...")
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        # Add options to fix TensorFlow Lite issues
        options.add_argument("--disable-features=BlinkGenPropertyTrees")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        # Disable TensorFlow Lite
        options.add_argument("--disable-gpu-driver-bug-workarounds")
        options.add_argument("--disable-gpu-compositing")
        # Force static sizing when possible
        options.add_argument("--force-device-scale-factor=1")
        
        driver = uc.Chrome(options=options)
        logger.info("Undetected Chrome browser created successfully!")
        
        # Try to navigate to Ringba
        logger.info("Navigating to Ringba login page with undetected Chrome...")
        driver.get("https://app.ringba.com/#/login")
        time.sleep(5)
        logger.info("Successfully loaded Ringba login page")
        
        # Take a screenshot
        driver.save_screenshot("ringba_login_undetected.png")
        logger.info("Screenshot saved as ringba_login_undetected.png")
        
        driver.quit()
        logger.info("Undetected Chrome test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error with undetected Chrome: {e}")
        try:
            if 'driver' in locals() and driver:
                driver.quit()
        except:
            pass
        return False

if __name__ == "__main__":
    print("=== SIMPLE BROWSER TEST ===")
    print("This script tests if a Chrome browser can be launched and navigate to Ringba.")
    print("First we'll try with our chrome_helper module...")
    
    success = test_browser_only()
    
    if not success:
        print("\nStandard approach failed. Let's try with undetected-chromedriver...")
        success = test_with_undetected_chrome()
    
    if success:
        print("\n✅ TEST SUCCESSFUL: Browser was able to navigate to Ringba!")
        print("You can now try the full test_bot.py script.")
    else:
        print("\n❌ TEST FAILED: Browser could not be launched or navigate to Ringba.")
        print("Please check the logs and try the solutions in TROUBLESHOOTING.md.")