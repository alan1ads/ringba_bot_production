"""
Chrome Helper - Utility functions for setting up Chrome WebDriver
"""

import os
import sys
import logging
import zipfile
import shutil
import requests
import subprocess
import platform
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def get_chrome_version():
    """
    Get the installed Chrome version on Windows
    """
    try:
        # Method 1: Try using registry
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        return version
    except:
        # Method 2: Try using PowerShell
        try:
            result = subprocess.check_output(
                ['powershell', '-command', 
                 r'(Get-Item -Path "$env:PROGRAMFILES\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion;'],
                stderr=subprocess.STDOUT)
            return result.decode('utf-8').strip()
        except:
            # Method 3: Try using direct path for 32-bit Chrome
            try:
                result = subprocess.check_output(
                    ['powershell', '-command', 
                     r'(Get-Item -Path "$env:PROGRAMFILES(x86)\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion;'],
                    stderr=subprocess.STDOUT)
                return result.decode('utf-8').strip()
            except:
                # Cannot determine Chrome version
                return None

def download_chromedriver(chrome_version=None, force=False):
    """
    Download the appropriate ChromeDriver for the installed Chrome version
    
    Args:
        chrome_version (str): Optional Chrome version to match, if None will attempt to detect
        force (bool): Force download even if driver exists
        
    Returns:
        str: Path to the ChromeDriver executable
    """
    driver_dir = Path.home() / "ringba_chromedriver"
    os.makedirs(driver_dir, exist_ok=True)
    
    # Get major Chrome version (e.g., "94" from "94.0.4606.81")
    if not chrome_version:
        chrome_version = get_chrome_version()
    
    if not chrome_version:
        logger.warning("Could not determine Chrome version, using latest")
        chrome_major = "latest"
    else:
        chrome_major = chrome_version.split(".")[0]
    
    logger.info(f"Chrome version: {chrome_version}, Major version: {chrome_major}")
    
    # Check if we already have the correct driver
    driver_path = driver_dir / f"chromedriver_{chrome_major}.exe"
    
    if not force and driver_path.exists():
        logger.info(f"ChromeDriver for Chrome {chrome_major} already exists at {driver_path}")
        return str(driver_path)
    
    # Determine download URL based on version
    logger.info("Downloading ChromeDriver...")
    
    try:
        # For Chrome >= 115, use the new API
        if chrome_major != "latest" and int(chrome_major) >= 115:
            # Get available Chrome versions
            response = requests.get("https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json")
            data = response.json()
            
            # Find the closest matching version
            available_versions = []
            for version_data in data["versions"]:
                if version_data["version"].startswith(f"{chrome_major}."):
                    available_versions.append(version_data)
            
            if not available_versions:
                logger.warning(f"No matching version found for Chrome {chrome_major}, using latest")
                download_url = f"https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/115.0.5790.170/win32/chromedriver-win32.zip"
            else:
                # Use the latest patch version for this major version
                latest_version = available_versions[-1]
                download_url = None
                
                # Find the chromedriver download for win32
                for download in latest_version["downloads"].get("chromedriver", []):
                    if download["platform"] == "win32":
                        download_url = download["url"]
                
                if not download_url:
                    download_url = f"https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/{latest_version['version']}/win32/chromedriver-win32.zip"
                
                logger.info(f"Using ChromeDriver version: {latest_version['version']}")
        else:
            # For older Chrome versions or "latest"
            download_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{chrome_major}"
            if chrome_major == "latest":
                download_url = "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
            
            try:
                response = requests.get(download_url)
                driver_version = response.text.strip()
                download_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_win32.zip"
            except:
                # Fallback to a known working version
                download_url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_win32.zip"
                
        # Download the driver
        logger.info(f"Downloading from: {download_url}")
        response = requests.get(download_url)
        
        # Save the zip file
        zip_path = driver_dir / "chromedriver_temp.zip"
        with open(zip_path, "wb") as f:
            f.write(response.content)
        
        # Extract the zip
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Extract to a temp directory
            temp_dir = driver_dir / "temp_extract"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            zip_ref.extractall(temp_dir)
        
        # Find the chromedriver.exe in the extracted folder (handle different zip structures)
        chromedriver_exe = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower() == "chromedriver.exe":
                    chromedriver_exe = Path(root) / file
                    break
            if chromedriver_exe:
                break
        
        if not chromedriver_exe:
            raise Exception("Could not find chromedriver.exe in the downloaded zip")
        
        # Copy to the final location
        shutil.copy2(chromedriver_exe, driver_path)
        
        # Cleanup
        if zip_path.exists():
            os.remove(zip_path)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        logger.info(f"ChromeDriver downloaded and saved to {driver_path}")
        return str(driver_path)
        
    except Exception as e:
        logger.error(f"Error downloading ChromeDriver: {e}")
        raise

def get_selenium_webdriver(headless=True):
    """
    Set up and return a Chrome WebDriver for Selenium
    
    Args:
        headless (bool): Whether to run Chrome in headless mode
        
    Returns:
        webdriver.Chrome: A configured Chrome WebDriver
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        
        # Print system info for debugging
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Python version: {platform.python_version()}")
        
        # Download ChromeDriver if needed
        driver_path = download_chromedriver()
        logger.info(f"Using ChromeDriver from: {driver_path}")
        
        # Set up Chrome options with more robust settings
        chrome_options = Options()
        
        # Essential options
        if headless:
            chrome_options.add_argument("--headless=new")  # Use the newer headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Additional options to improve reliability
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--remote-debugging-port=9222")  # Enable debugging
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Hide automation
        
        # Add options to fix TensorFlow Lite dynamic tensor issues
        chrome_options.add_argument("--disable-features=BlinkGenPropertyTrees")
        chrome_options.add_argument("--disable-gpu-driver-bug-workarounds")
        chrome_options.add_argument("--disable-gpu-compositing")
        chrome_options.add_argument("--force-device-scale-factor=1")
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Try to create the WebDriver with multiple retries
        max_attempts = 3
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"WebDriver creation attempt {attempt + 1} of {max_attempts}")
                
                # Create Service and WebDriver
                service = Service(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.implicitly_wait(10)
                
                # Verify driver works by loading a simple page
                try:
                    driver.get("about:blank")
                    logger.info("Successfully loaded blank page - WebDriver is working")
                except Exception as inner_e:
                    logger.warning(f"WebDriver created but failed basic test: {inner_e}")
                    driver.quit()
                    raise
                
                return driver
                
            except Exception as e:
                last_exception = e
                logger.warning(f"WebDriver creation attempt {attempt + 1} failed: {e}")
                time.sleep(2)  # Wait a bit before retrying
                
                # Try different Chrome options on each retry
                if attempt == 1:
                    logger.info("Trying with fewer Chrome options")
                    chrome_options = Options()
                    if headless:
                        chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                
        # If all attempts failed, raise the last exception
        logger.error("All WebDriver creation attempts failed")
        raise last_exception or Exception("Failed to create WebDriver")
        
    except Exception as e:
        logger.error(f"Error setting up WebDriver: {e}")
        raise

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Download ChromeDriver when script is run directly
    chrome_version = get_chrome_version()
    if chrome_version:
        print(f"Detected Chrome version: {chrome_version}")
    else:
        print("Could not detect Chrome version, will use latest ChromeDriver")
    
    driver_path = download_chromedriver(chrome_version, force=True)
    print(f"ChromeDriver downloaded to: {driver_path}")
    
    print("\nYou can now use this ChromeDriver with Selenium")
    print("Test the setup with: python test_bot.py")
    
    # Optionally test the WebDriver creation directly
    try:
        print("\nTesting WebDriver creation...")
        driver = get_selenium_webdriver(headless=True)
        print("Successfully created WebDriver!")
        driver.quit()
        print("WebDriver test passed!")
    except Exception as e:
        print(f"WebDriver test failed: {e}")