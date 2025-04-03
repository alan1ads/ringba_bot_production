"""
Test script for the Ringba RPC Monitor Bot.
This script tests the core functionality of the bot without running on schedule.
Use this to verify your setup before deployment.
"""

import os
import logging
from dotenv import load_dotenv
import chrome_helper  # Import our custom chrome helper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_bot():
    """
    Test the main functionality of the bot
    """
    logger.info("Starting test run...")
    
    # Load environment variables
    load_dotenv()
    
    # Check if environment variables are set
    ringba_email = os.getenv("RINGBA_EMAIL")
    ringba_password = os.getenv("RINGBA_PASSWORD")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    if not ringba_email or not ringba_password or not slack_webhook_url:
        logger.error("Missing required environment variables. Please check .env file.")
        return False
    
    # Import these functions only after verifying environment variables
    from ringba_bot import login_to_ringba, navigate_to_reporting, extract_target_rpc_data, send_slack_notification, RPC_THRESHOLD
    
    driver = None
    try:
        # Set up WebDriver directly using our chrome_helper
        logger.info("Setting up WebDriver using chrome_helper...")
        driver = chrome_helper.get_selenium_webdriver(headless=True)
        logger.info("WebDriver setup successful")
        
        # Login to Ringba
        login_to_ringba(driver)
        
        # Navigate to Reporting tab
        navigate_to_reporting(driver)
        
        # Extract Target and RPC data
        target_rpc_data = extract_target_rpc_data(driver)
        
        # Display extracted data
        logger.info(f"Successfully extracted data for {len(target_rpc_data)} targets")
        for item in target_rpc_data:
            logger.info(f"Target: {item['Target']}, RPC: ${item['RPC']}")
        
        # Filter for low RPC values
        low_rpc_data = [item for item in target_rpc_data if item["RPC"] < RPC_THRESHOLD]
        
        # Show results
        if low_rpc_data:
            logger.info(f"Found {len(low_rpc_data)} targets with RPC below ${RPC_THRESHOLD}")
            
            # Ask user if they want to send a test notification
            send_test = input(f"Send test Slack notification for {len(low_rpc_data)} low RPC values? (yes/no): ")
            
            if send_test.lower() == "yes":
                send_slack_notification(low_rpc_data)
                logger.info("Test notification sent to Slack")
        else:
            logger.info(f"No targets with RPC below ${RPC_THRESHOLD}")
        
        logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        try:
            # Take a screenshot of the error state
            if driver:
                driver.save_screenshot("test_error.png")
                logger.info("Error screenshot saved as test_error.png")
        except:
            pass
        return False
    
    finally:
        # Close the WebDriver
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

if __name__ == "__main__":
    try:
        logger.info("=== RUNNING CHROME HELPER SETUP ===")
        # Run the chrome_helper module directly to download ChromeDriver if needed
        chrome_version = chrome_helper.get_chrome_version()
        if chrome_version:
            logger.info(f"Detected Chrome version: {chrome_version}")
        else:
            logger.warning("Could not detect Chrome version, will use latest ChromeDriver")
        
        chrome_helper.download_chromedriver(chrome_version)
        logger.info("Chrome helper setup completed")
        logger.info("=== STARTING BOT TEST ===")
        
        test_bot()
    except KeyboardInterrupt:
        logger.info("Test stopped manually")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")