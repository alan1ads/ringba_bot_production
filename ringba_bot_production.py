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
import pandas as pd
import platform
import psutil
from playwright.async_api import async_playwright

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
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # Create HTML status page with last run result
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ringba Bot Status</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                    .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                    h1 { color: #333; }
                    .success { color: green; }
                    .error { color: red; }
                    .warning { color: orange; }
                    .info-box { background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 15px 0; }
                    .button { display: inline-block; background-color: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; margin-top: 20px; }
                    table { width: 100%; border-collapse: collapse; }
                    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background-color: #f2f2f2; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Ringba Bot Status</h1>
            """
            
            if last_run_result:
                if last_run_result.get("success"):
                    status_class = "success"
                    status_text = "Success"
                else:
                    status_class = "error"
                    status_text = "Error"
                    
                html += f"""
                    <h2>Last Run Status: <span class="{status_class}">{status_text}</span></h2>
                    <p>Last run: {last_run_result.get("timestamp", "Unknown")}</p>
                """
                
                if last_run_result.get("success"):
                    threshold = last_run_result.get("threshold", 20)
                    overall_rpc = last_run_result.get("overall_rpc", 0)
                    is_below_threshold = last_run_result.get("is_below_threshold", False)
                    
                    if is_below_threshold:
                        alert_class = "error"
                        alert_text = f"⚠️ RPC is below threshold (${threshold:.2f})"
                    else:
                        alert_class = "success"
                        alert_text = f"✅ RPC is above threshold (${threshold:.2f})"
                    
                    html += f"""
                    <div class="info-box">
                        <h3 class="{alert_class}">{alert_text}</h3>
                        <table>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                            <tr>
                                <td>Current RPC</td>
                                <td>${last_run_result.get("overall_rpc", 0):.2f}</td>
                            </tr>
                            <tr>
                                <td>Min RPC</td>
                                <td>${last_run_result.get("min_rpc", 0):.2f}</td>
                            </tr>
                            <tr>
                                <td>Max RPC</td>
                                <td>${last_run_result.get("max_rpc", 0):.2f}</td>
                            </tr>
                            <tr>
                                <td>Threshold</td>
                                <td>${threshold:.2f}</td>
                            </tr>
                        </table>
                    </div>
                    """
                else:
                    html += f"""
                    <div class="info-box error">
                        <h3>Error Details</h3>
                        <p>{last_run_result.get("error", "Unknown error")}</p>
                    </div>
                    """
                
                # Display environment information
                env_info = last_run_result.get("environment", {})
                if env_info:
                    html += """
                    <h3>Environment Information</h3>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                    """
                    
                    for key, value in env_info.items():
                        html += f"""
                        <tr>
                            <td>{key}</td>
                            <td>{value}</td>
                        </tr>
                        """
                    
                    html += """
                    </table>
                    """
            else:
                html += """
                <h2 class="warning">No Data Available</h2>
                <p>The bot has not completed any runs yet.</p>
                """
            
            html += """
                    <a href="/run" class="button">Run Check Now</a>
                </div>
            </body>
            </html>
            """
            
            self.wfile.write(html.encode())
        
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            health_status = {
                "status": "healthy",
                "lastRun": last_run_result.get("timestamp", "Never"),
                "success": last_run_result.get("success", False)
            }
            
            self.wfile.write(json.dumps(health_status).encode())
        
        elif self.path == "/run":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # Start the RPC check in a separate thread
            threading.Thread(target=run_check).start()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Run Triggered</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; text-align: center; background-color: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                    h1 { color: #333; }
                    p { margin: 20px 0; }
                    .button { display: inline-block; background-color: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; }
                </style>
                <meta http-equiv="refresh" content="5;url=/" />
            </head>
            <body>
                <div class="container">
                    <h1>Check Started</h1>
                    <p>The RPC check has been triggered and is running in the background.</p>
                    <p>You will be redirected to the status page in 5 seconds...</p>
                    <a href="/" class="button">Return to Status Page</a>
                </div>
            </body>
            </html>
            """
            
            self.wfile.write(html.encode())
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def start_health_check_server():
    """Start a simple HTTP server for health checks"""
    port = int(os.environ.get('PORT', 10000))  # Render.com sets the PORT environment variable
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    logger.info(f"Starting health check server on port {port}")
    server.serve_forever()

# Constants
RINGBA_URL = "https://app.ringba.com/#/login"
RINGBA_EMAIL = os.getenv("RINGBA_EMAIL")
RINGBA_PASSWORD = os.getenv("RINGBA_PASSWORD")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
RPC_THRESHOLD = 12.0  # $12 threshold for notifications

# Global variable to store the last run result
last_run_result = None

# Initialize playwright
playwright = None

# Random delay function for human-like behavior
def random_sleep_async(min_seconds=0.5, max_seconds=2.0):
    """Generate a random sleep duration for human-like behavior"""
    return random.uniform(min_seconds, max_seconds)

async def setup_browser(headless=True, retry_count=3):
    """
    Set up and configure Playwright browser with retry mechanism
    """
    for attempt in range(retry_count):
        try:
            logger.info(f"Starting Playwright (attempt {attempt+1}/{retry_count})...")
            playwright = await async_playwright().start()
            
            # Use chromium for best compatibility
            browser = await playwright.chromium.launch(
                headless=headless,  # Use headless=True for production
                args=[
                    "--disable-features=BlinkGenPropertyTrees",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",  # Helps with memory issues in containerized environments
                    "--no-sandbox",  # Required for running in containers
                    "--disable-setuid-sandbox",
                    "--single-process",  # Use single process to reduce memory usage
                ]
            )
            
            # Create a context with specific viewport and user agent
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},  # Reduced size for less memory usage
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
            
            # Add event listeners for potential errors
            page.on("crash", lambda: logger.error("Page crashed"))
            page.on("close", lambda: logger.warning("Page was closed"))
            
            logger.info("Playwright browser setup complete")
            return playwright, browser, context, page
        
        except Exception as e:
            logger.error(f"Error setting up Playwright (attempt {attempt+1}/{retry_count}): {e}")
            
            # Last attempt, raise the error
            if attempt == retry_count - 1:
                raise
            
            # Wait before retrying
            await asyncio.sleep(3)

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
    Navigate to the Reporting tab and export CSV data with better error handling
    """
    logger.info("Navigating to Reporting tab...")
    
    try:
        # Navigate directly to the call logs report page with increased timeout
        await page.goto("https://app.ringba.com/#/dashboard/call-logs/report/new", timeout=90000)
        logger.info("Navigating directly to call-logs/report/new page")
        
        # Check if page is still usable after navigation
        try:
            await page.evaluate("1")
        except Exception as e:
            logger.error(f"Page is no longer usable after initial navigation: {e}")
            return False
        
        # Wait longer for the page to load in cloud environments
        # Use shorter sleep intervals with checks to avoid browser termination
        for i in range(5):
            await asyncio.sleep(3)
            try:
                # Check if page is still alive
                await page.evaluate("1")
            except Exception:
                logger.error("Browser context was closed during page load wait")
                return False
        
        # Save a screenshot for debugging
        try:
            await page.screenshot(path="reporting_navigation.png")
            logger.info("Saved screenshot after navigating to Reporting")
        except Exception as ss_error:
            logger.warning(f"Could not save screenshot: {ss_error}")
        
        # Check if page is still usable before interacting
        try:
            await page.evaluate("1")
        except Exception:
            logger.error("Browser context was closed before UI interaction")
            return False
        
        # Try several approaches to find the right UI to interact with
        apply_clicked = False
        table_clicked = False
        run_clicked = False
        
        # Approach 1: Look for and click the "Apply" button to load the report
        try:
            apply_button = await page.wait_for_selector("button:has-text('Apply')", timeout=10000)
            if apply_button:
                logger.info("Found Apply button, clicking it to load report data")
                await apply_button.click()
                apply_clicked = True
                
                # Wait in smaller intervals with browser checks
                for i in range(5):
                    await asyncio.sleep(3)
                    try:
                        await page.evaluate("1")
                    except Exception:
                        logger.error("Browser context was closed during Apply wait")
                        return False
        except Exception as e:
            logger.warning(f"Could not find or click Apply button: {e}")
            # Continue execution even if this fails
        
        # Check if browser is still alive
        try:
            await page.evaluate("1")
        except Exception:
            logger.error("Browser context was closed after Apply button")
            return False
        
        # Approach 2: Try to click on the Table view option
        if not apply_clicked:
            try:
                table_options = [
                    "text=Table",
                    "button:has-text('Table')",
                    "div[role='tab']:has-text('Table')",
                    ".tab:has-text('Table')"
                ]
                
                for selector in table_options:
                    try:
                        table_tab = await page.wait_for_selector(selector, timeout=5000)
                        if table_tab:
                            logger.info(f"Found Table tab with selector: {selector}, clicking it")
                            await table_tab.click()
                            table_clicked = True
                            
                            # Wait in smaller intervals with browser checks
                            for i in range(3):
                                await asyncio.sleep(3)
                                try:
                                    await page.evaluate("1")
                                except Exception:
                                    logger.error("Browser context was closed during table tab wait")
                                    return False
                            break
                    except Exception:
                        pass
            except Exception as tab_error:
                logger.warning(f"Could not find or click Table tab: {tab_error}")
                # Continue execution even if this fails
        
        # Check if browser is still alive
        try:
            await page.evaluate("1")
        except Exception:
            logger.error("Browser context was closed after Table tab")
            return False
        
        # Approach 3: Look for any "Run Report" or similar button
        if not apply_clicked and not table_clicked:
            try:
                run_buttons = [
                    "button:has-text('Run')",
                    "button:has-text('Run Report')",
                    "button:has-text('Generate')",
                    "button:has-text('Submit')"
                ]
                
                for btn_selector in run_buttons:
                    try:
                        run_btn = await page.wait_for_selector(btn_selector, timeout=5000)
                        if run_btn:
                            logger.info(f"Found button with selector: {btn_selector}, clicking it")
                            await run_btn.click()
                            run_clicked = True
                            
                            # Wait in smaller intervals with browser checks
                            for i in range(5):
                                await asyncio.sleep(3)
                                try:
                                    await page.evaluate("1")
                                except Exception:
                                    logger.error("Browser context was closed during run button wait")
                                    return False
                            break
                    except Exception:
                        pass
            except Exception as btn_error:
                logger.warning(f"Could not find or click run button: {btn_error}")
                # Continue execution even if this fails
        
        # Take another screenshot after interactions
        try:
            await page.screenshot(path="after_report_interactions.png")
            logger.info("Saved screenshot after report page interactions")
        except Exception as ss_error:
            logger.warning(f"Could not save final screenshot: {ss_error}")
        
        # Check if browser is still alive before returning
        try:
            await page.evaluate("1")
            # Even if some steps fail, return success so we can try to export CSV
            return True
        except Exception:
            logger.error("Browser context was closed at the end of navigation")
            return False
        
    except Exception as e:
        logger.error(f"Error navigating to Reporting tab: {e}")
        return False

async def export_and_download_csv(page):
    """
    Find and click the EXPORT CSV button, then download the CSV file with better resilience
    """
    logger.info("Looking for EXPORT CSV button...")
    
    try:
        # First verify browser is usable
        try:
            await page.evaluate("1")
        except Exception as e:
            logger.error(f"Browser not usable before export attempt: {e}")
            return False
            
        # First take a screenshot to debug
        try:
            await page.screenshot(path="before_export.png")
        except Exception as ss_error:
            logger.warning(f"Could not save export screenshot: {ss_error}")
        
        # Try multiple selectors for the EXPORT CSV button
        export_selectors = [
            "button:has-text('EXPORT CSV')",
            "button:has-text('Export CSV')",
            "button:has-text('Export')",
            "button.export-csv",
            ".export-csv",
            "button:has-text('CSV')",
            "text=EXPORT CSV",
            "text=Export CSV",
            "a:has-text('Export')",
            "a:has-text('CSV')",
            "[aria-label*='export' i]",
            "[aria-label*='csv' i]",
            "[title*='export' i]", 
            "[title*='csv' i]"
        ]
        
        export_button = None
        for selector in export_selectors:
            try:
                # Verify browser is still usable before each selector attempt
                try:
                    await page.evaluate("1")
                except Exception:
                    logger.error("Browser context closed during export button search")
                    return False
                    
                logger.info(f"Trying to find export button with selector: {selector}")
                export_button = await page.wait_for_selector(selector, timeout=5000)
                if export_button:
                    logger.info(f"Found export button with selector: {selector}")
                    break
            except Exception:
                pass
                
        if not export_button:
            logger.warning("Could not find EXPORT CSV button with selectors")
            # Try more generic selectors
            try:
                logger.info("Trying to find any export-related element")
                await page.screenshot(path="export_search.png")
                
                # Verify browser is still usable
                try:
                    await page.evaluate("1")
                except Exception:
                    logger.error("Browser context closed during generic button search")
                    return False
                
                # Get all buttons on the page
                buttons = await page.query_selector_all("button, a.btn, .btn, a[role='button']")
                logger.info(f"Found {len(buttons)} potential buttons")
                
                # Check each button's text for export-related keywords
                for button in buttons:
                    try:
                        # Check if browser is still alive
                        try:
                            await page.evaluate("1")
                        except Exception:
                            logger.error("Browser context closed during button text check")
                            return False
                            
                        button_text = await button.inner_text()
                        logger.info(f"Button text: {button_text}")
                        if "export" in button_text.lower() or "csv" in button_text.lower() or "download" in button_text.lower():
                            export_button = button
                            logger.info(f"Found potential export button with text: {button_text}")
                            break
                    except Exception:
                        pass
            except Exception as search_error:
                logger.warning(f"Error searching for buttons: {search_error}")
            
        if not export_button:
            # Last attempt - try to find by looking at all elements with click handlers
            try:
                logger.info("Last attempt - trying to find exportable elements")
                
                # Verify browser is still usable
                try:
                    await page.evaluate("1")
                except Exception:
                    logger.error("Browser context closed during last export button search")
                    return False
                
                # Use JavaScript to find clickable elements that might be export buttons
                clickable_elements = await page.evaluate("""() => {
                    const possibleExportElements = [];
                    // Find elements with onclick attributes or event listeners
                    document.querySelectorAll('*').forEach(element => {
                        // Check text content for export/csv related terms
                        const text = element.textContent || '';
                        if ((text.toLowerCase().includes('export') || text.toLowerCase().includes('csv') || 
                             text.toLowerCase().includes('download')) && 
                            (element.tagName === 'BUTTON' || element.tagName === 'A' || 
                             element.role === 'button' || window.getComputedStyle(element).cursor === 'pointer')) {
                            possibleExportElements.push({
                                tagName: element.tagName,
                                id: element.id,
                                className: element.className,
                                text: text.trim().substring(0, 50),
                                xpath: getXPath(element)
                            });
                        }
                    });
                    
                    // XPath helper function
                    function getXPath(element) {
                        if (element.id) return `//*[@id="${element.id}"]`;
                        if (element === document.body) return '/html/body';
                        
                        let ix = 0;
                        const siblings = element.parentNode.childNodes;
                        for (let i = 0; i < siblings.length; i++) {
                            const sibling = siblings[i];
                            if (sibling === element) return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) ix++;
                        }
                    }
                    
                    return possibleExportElements;
                }""")
                
                logger.info(f"Found {len(clickable_elements)} potential export elements via JavaScript")
                
                # Try clicking each potential export element
                for element_info in clickable_elements:
                    logger.info(f"Trying potential export element: {element_info}")
                    
                    # Verify browser is still usable
                    try:
                        await page.evaluate("1")
                    except Exception:
                        logger.error("Browser context closed during element click attempt")
                        return False
                    
                    try:
                        if element_info.get("xpath"):
                            element = await page.wait_for_selector(f"xpath={element_info['xpath']}", timeout=2000)
                            if element:
                                export_button = element
                                logger.info(f"Found potential export button with XPath: {element_info['xpath']}")
                                break
                    except Exception:
                        pass
            except Exception as js_error:
                logger.warning(f"Error in JavaScript search for export elements: {js_error}")
        
        if not export_button:
            logger.error("Could not find any export button after exhaustive search")
            return False
            
        # Set up a download handler before clicking the button
        download_path = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_path, exist_ok=True)
        
        # Verify browser is still usable before download attempt
        try:
            await page.evaluate("1")
        except Exception:
            logger.error("Browser context closed before download attempt")
            return False
        
        # Handle the download event
        logger.info("Setting up download handler")
        
        try:
            # Try the async with approach first
            async with page.expect_download(timeout=30000) as download_info:
                # Check if browser is still usable
                try:
                    await page.evaluate("1")
                except Exception:
                    logger.error("Browser context closed right before button click")
                    return False
                
                await export_button.click()
                logger.info("Clicked EXPORT CSV button, waiting for download...")
                
                # Wait for the download to complete
                download = await download_info.value
                logger.info(f"Download started: {download.suggested_filename}")
                
                # Save the downloaded file
                csv_path = os.path.join(download_path, download.suggested_filename)
                await download.save_as(csv_path)
                logger.info(f"Downloaded CSV to: {csv_path}")
                
                return csv_path
        except Exception as download_error:
            logger.warning(f"First download approach failed: {download_error}")
            
            # If the first approach fails, try a simpler approach
            try:
                logger.info("Trying alternative download approach")
                
                # Check if browser is still usable
                try:
                    await page.evaluate("1")
                except Exception:
                    logger.error("Browser context closed before alternative download attempt")
                    return False
                
                await export_button.click()
                logger.info("Clicked export button, waiting for download...")
                
                # Wait in small increments for the download
                for _ in range(10):
                    await asyncio.sleep(1)
                    
                    # Check if browser is still alive
                    try:
                        await page.evaluate("1")
                    except Exception:
                        logger.warning("Browser closed during download wait, but download may have started")
                        break
                
                # Wait a bit longer for download to complete
                await asyncio.sleep(5)
                
                # Check if any files were downloaded
                import glob
                downloaded_files = glob.glob(os.path.join(download_path, "*.csv"))
                
                if downloaded_files:
                    latest_file = max(downloaded_files, key=os.path.getctime)
                    logger.info(f"Found downloaded file: {latest_file}")
                    return latest_file
                else:
                    logger.error("No CSV files found in downloads directory")
                    return False
            except Exception as alt_error:
                logger.error(f"Alternative download approach failed: {alt_error}")
                return False
    
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

async def send_slack_notification(message):
    """
    Send Slack notification for low RPC values
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured")
        return False
        
    try:
        import requests
        
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
        logger.info("Sending Slack notification")
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

async def get_csv_values(page=None, start_fresh=False, retry_count=0):
    """
    Navigate to the reporting page and extract the RPC value from the CSV
    """
    logger.info("Starting get_csv_values...")
    MAX_RETRIES = 3
    browser = None
    
    try:
        # If starting fresh or no page provided, create a new browser session
        if start_fresh or not page:
            logger.info("Creating new browser instance...")
            playwright, browser, context, page = await setup_browser(headless=True)
            
            # Login first
            login_success = await login_to_ringba(page)
            if not login_success:
                logger.error("Login failed")
                if retry_count < MAX_RETRIES:
                    if browser:
                        await browser.close()
                    if 'playwright' in globals():
                        await playwright.stop()
                    return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
                else:
                    logger.error("Max retries reached for login, giving up")
                    return None, None, None
        
        # Check if browser/page is usable
        try:
            await page.evaluate("1")
        except Exception as e:
            logger.error(f"Page is not usable after login: {e}")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                logger.error("Max retries reached, giving up")
                return None, None, None
                
        # Take screenshot for debugging
        try:
            await page.screenshot(path="after_login.png")
            logger.info("Saved screenshot after login")
        except Exception as ss_error:
            logger.warning(f"Could not save screenshot: {ss_error}")
        
        # Navigate to reporting page
        logger.info("Navigating to reporting page...")
        navigation_success = await navigate_to_reporting(page)
        
        if not navigation_success:
            logger.error("Failed to navigate to reporting page")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                logger.error("Max retries reached for navigation, giving up")
                return None, None, None
        
        # Download the CSV file
        csv_path = await export_and_download_csv(page)
        if not csv_path:
            logger.error("Failed to download CSV file")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                logger.error("Max retries reached, giving up")
                return None, None, None
        
        logger.info(f"CSV downloaded to: {csv_path}")
        
        # Process the CSV file to extract RPC values
        try:
            import pandas as pd
            
            # Read the CSV file
            df = pd.read_csv(csv_path)
            logger.info(f"CSV loaded with columns: {df.columns.tolist()}")
            
            # Look for RPC column
            rpc_column = None
            for col in df.columns:
                if 'RPC' in col or 'rpc' in col.lower():
                    rpc_column = col
                    logger.info(f"Found RPC column: {rpc_column}")
                    break
            
            if not rpc_column:
                logger.warning("Could not find an RPC column, trying alternative column names")
                # Try common alternative names
                for col in df.columns:
                    if any(keyword in col.lower() for keyword in ['revenue', 'profit', 'earning', 'value']):
                        rpc_column = col
                        logger.info(f"Using alternative column as RPC: {rpc_column}")
                        break
            
            if not rpc_column and not df.empty and len(df.columns) > 0:
                # If still not found, use the last numeric column as a desperate measure
                for col in df.columns:
                    try:
                        # Check if column can be converted to numeric
                        pd.to_numeric(df[col], errors='raise')
                        rpc_column = col
                        logger.info(f"Using numeric column as fallback for RPC: {rpc_column}")
                        break
                    except:
                        continue
            
            if not rpc_column:
                logger.error("Could not find a usable RPC column in the CSV")
                if retry_count < MAX_RETRIES:
                    logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                    if browser:
                        await browser.close()
                    return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
                else:
                    logger.error("Max retries reached, giving up")
                    return None, None, None
            
            # Clean the RPC values (remove $ and commas)
            if isinstance(df[rpc_column].iloc[0], str):
                df[rpc_column] = df[rpc_column].str.replace('$', '').str.replace(',', '')
            
            # Convert to numeric
            df[rpc_column] = pd.to_numeric(df[rpc_column], errors='coerce')
            
            # Drop NaN values
            df = df.dropna(subset=[rpc_column])
            
            if df.empty:
                logger.error("No valid RPC values found after conversion")
                if retry_count < MAX_RETRIES:
                    logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                    if browser:
                        await browser.close()
                    return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
                else:
                    logger.error("Max retries reached, giving up")
                    return None, None, None
            
            # Calculate min, max, and average RPC
            min_rpc = df[rpc_column].min()
            max_rpc = df[rpc_column].max()
            overall_rpc = df[rpc_column].mean()
            
            logger.info(f"Extracted RPC values - Min: {min_rpc}, Avg: {overall_rpc}, Max: {max_rpc}")
            
            # Clean up the CSV file
            try:
                os.remove(csv_path)
                logger.info(f"Removed CSV file: {csv_path}")
            except Exception as remove_error:
                logger.warning(f"Could not remove CSV file: {remove_error}")
            
            return min_rpc, overall_rpc, max_rpc
            
        except Exception as csv_error:
            logger.error(f"Error processing CSV file: {csv_error}")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                return None, None, None
    
    except Exception as e:
        logger.error(f"Error in get_csv_values: {e}")
        logger.exception(e)
        if retry_count < MAX_RETRIES:
            logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
            if browser:
                await browser.close()
            return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
        else:
            logger.error("Max retries reached, giving up")
            return None, None, None
            
    finally:
        # Close browser if we created it and it's still open
        if start_fresh and browser:
            try:
                await browser.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

async def main():
    """
    Main function to get RPC values and send Slack notification
    """
    global last_run_result
    
    # Configure environment information for debugging
    env_info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "processor": platform.processor(),
        "memory": f"{psutil.virtual_memory().total / (1024 * 1024 * 1024):.2f} GB",
        "free_memory": f"{psutil.virtual_memory().available / (1024 * 1024 * 1024):.2f} GB",
        "free_disk": f"{psutil.disk_usage('/').free / (1024 * 1024 * 1024):.2f} GB"
    }
    
    logger.info(f"Starting Ringba bot with environment: {env_info}")
    
    try:
        # Initialize playwright
        global playwright
        playwright = await async_playwright().start()
        logger.info("Playwright initialized")
        
        # Get RPC values with retries
        logger.info("Getting CSV values...")
        min_rpc, overall_rpc, max_rpc = await get_csv_values(start_fresh=True)
        
        if min_rpc is None or overall_rpc is None or max_rpc is None:
            error_message = "Failed to get RPC values after multiple attempts"
            logger.error(error_message)
            
            # Update last run result
            last_run_result = {
                "success": False,
                "error": error_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "environment": env_info
            }
            
            # Send error notification to Slack
            await send_slack_notification(
                f"❌ *Ringba Bot Error*: Failed to retrieve RPC values\n"
                f"*Error*: Failed to get valid RPC values\n"
                f"*Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"*Environment*: Running on {env_info['platform']} with {env_info['free_memory']} free memory"
            )
            return
        
        # Format values as currency
        min_rpc_formatted = f"${min_rpc:.2f}"
        overall_rpc_formatted = f"${overall_rpc:.2f}"
        max_rpc_formatted = f"${max_rpc:.2f}"
        
        # Get the threshold from environment variable, default to 20
        threshold = float(os.environ.get("RPC_THRESHOLD", "20"))
        
        # Determine if RPC is below threshold
        is_below_threshold = overall_rpc < threshold
        
        # Create message for Slack
        if is_below_threshold:
            message = (
                f"🚨 *RPC Alert*: Current RPC is below threshold of ${threshold:.2f}\n"
                f"*Current RPC*: {overall_rpc_formatted}\n"
                f"*Min RPC*: {min_rpc_formatted}\n"
                f"*Max RPC*: {max_rpc_formatted}\n"
                f"*Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            message = (
                f"✅ *RPC Status*: Current RPC is above threshold of ${threshold:.2f}\n"
                f"*Current RPC*: {overall_rpc_formatted}\n"
                f"*Min RPC*: {min_rpc_formatted}\n"
                f"*Max RPC*: {max_rpc_formatted}\n"
                f"*Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Update last run result
        last_run_result = {
            "success": True,
            "min_rpc": min_rpc,
            "overall_rpc": overall_rpc,
            "max_rpc": max_rpc,
            "is_below_threshold": is_below_threshold,
            "threshold": threshold,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "environment": env_info
        }
        
        # Send notification to Slack
        logger.info(f"Sending Slack notification: {message}")
        await send_slack_notification(message)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        logger.exception(e)
        
        # Update last run result
        last_run_result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "environment": env_info
        }
        
        # Send error notification to Slack
        await send_slack_notification(
            f"❌ *Ringba Bot Error*: An error occurred\n"
            f"*Error*: {str(e)}\n"
            f"*Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"*Environment*: Running on {env_info['platform']} with {env_info['free_memory']} free memory"
        )
    
    finally:
        # Clean up playwright
        if 'playwright' in globals():
            try:
                await playwright.stop()
                logger.info("Playwright stopped")
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {e}")

def run_check():
    """
    Wrapper to run the async check function
    """
    logger.info("Scheduled check triggered")
    asyncio.run(main())

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

# Add this after the main function
async def check_rpc_values():
    """
    Alias for the main function to maintain backwards compatibility
    """
    logger.info("check_rpc_values called (alias for main function)")
    return await main()

# Run the first check and then schedule periodic checks
if __name__ == "__main__":
    try:
        # Start health check server in a separate thread
        logger.info("Starting health check server thread...")
        health_thread = threading.Thread(target=start_health_check_server, daemon=True)
        health_thread.start()
        
        # Run the first check
        logger.info("Running initial RPC check...")
        asyncio.run(main())
        
        # Set up schedule for periodic checks
        setup_schedule()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
        logger.exception(e) 