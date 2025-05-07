"""
Ringba RPC Monitor Bot - Production Version

This bot checks Ringba's reporting tab at scheduled times (11 AM, 2 PM, and 4 PM ET),
extracts Target and RPC data, and sends Slack notifications for all targets with their RPC values.

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
from supabase import create_client, Client

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
                
                # Add report type (comparative or standard)
                if last_run_result.get("is_comparative", False):
                    html += f"""
                    <p><strong>Report Type:</strong> <span class="success">Comparative Report</span></p>
                    """
                else:
                    html += f"""
                    <p><strong>Report Type:</strong> Standard Report</p>
                    """
                
                if last_run_result.get("success"):
                    target_rpc_data = last_run_result.get("target_rpc_data", [])
                    targets_displayed = last_run_result.get("targets_displayed", [])
                    threshold = last_run_result.get("threshold", 12.0)
                    is_comparative = last_run_result.get("is_comparative", False)
                    
                    # Different table structure for comparative reports
                    if is_comparative:
                        html += f"""
                        <div class="info-box">
                            <h3 class="success">📊 Ringba Comparative Report - {len(targets_displayed)} targets</h3>
                            <table>
                                <tr>
                                    <th>Target</th>
                                    <th>RPC</th>
                                    <th>Incoming</th>
                                    <th>Converted</th>
                                    <th>Status</th>
                                </tr>
                        """
                        
                        # Sort by RPC percentage change (largest negative first)
                        sorted_targets = sorted(
                            [t for t in targets_displayed if "RPC_pct" in t and t["RPC_pct"] is not None],
                            key=lambda x: x["RPC_pct"]
                        )
                        
                        for target in sorted_targets[:50]:  # Limit to first 50 targets
                            target_name = target.get("Target", "Unknown")
                            rpc_value = target.get("RPC", 0)
                            rpc_pct = target.get("RPC_pct", 0)
                            incoming_count = target.get("Incoming", 0)
                            incoming_pct = target.get("Incoming_pct", 0)
                            converted_count = target.get("Converted", 0)
                            converted_pct = target.get("Converted_pct", 0)
                            
                            # Determine status class based on RPC percentage change
                            if rpc_pct > 5:  # More than 5% increase
                                status_class = "success"
                                status_text = "↗️ Improved"
                            elif rpc_pct < -5:  # More than 5% decrease
                                status_class = "error"
                                status_text = "↘️ Decreased"
                            else:  # Between -5% and 5%
                                status_class = "warning"
                                status_text = "→ Stable"
                            
                            # Format percentage changes
                            rpc_pct_str = f"{'+' if rpc_pct > 0 else ''}{rpc_pct:.1f}%"
                            incoming_pct_str = f"{'+' if incoming_pct > 0 else ''}{incoming_pct:.1f}%"
                            converted_pct_str = f"{'+' if converted_pct > 0 else ''}{converted_pct:.1f}%"
                            
                            html += f"""
                            <tr>
                                <td>{target_name}</td>
                                <td>${rpc_value:.2f} ({rpc_pct_str})</td>
                                <td>{incoming_count} ({incoming_pct_str})</td>
                                <td>{converted_count} ({converted_pct_str})</td>
                                <td class="{status_class}">{status_text}</td>
                            </tr>
                            """
                    else:
                        # Standard report table
                        html += f"""
                        <div class="info-box">
                            <h3 class="success">📊 Ringba Report - {len(targets_displayed)} targets</h3>
                            <table>
                                <tr>
                                    <th>Target</th>
                                    <th>RPC Value</th>
                                    <th>Incoming</th>
                                    <th>Converted</th>
                                    <th>Status</th>
                                </tr>
                        """
                        
                        # Sort by RPC value (lowest first)
                        sorted_targets = sorted(target_rpc_data, key=lambda x: x['RPC'])
                        
                        for target in sorted_targets[:50]:  # Limit to first 50 targets
                            target_name = target.get("Target", "Unknown")
                            rpc_value = target.get("RPC", 0)
                            incoming_count = target.get("Incoming", 0)
                            converted_count = target.get("Converted", 0)  # Add converted count
                            is_below = rpc_value < threshold
                            status_class = "error" if is_below else "success"
                            status_text = "Below threshold" if is_below else "OK"
                            
                            html += f"""
                            <tr>
                                <td>{target_name}</td>
                                <td>${rpc_value:.2f}</td>
                                <td>{incoming_count}</td>
                                <td>{converted_count}</td>
                                <td class="{status_class}">{status_text}</td>
                            </tr>
                            """
                    
                    html += """
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
                "success": last_run_result.get("success", False),
                "isComparative": last_run_result.get("is_comparative", False)
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
RPC_THRESHOLD = 0.0  # No threshold filtering - show all targets
DATA_STORAGE_FILE = "ringba_report_data.json"  # File to store previous run data

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
    Navigate directly to the call logs report page - simplified approach for Render.com
    """
    logger.info("Navigating to call logs report page...")
    
    try:
        # First verify browser is usable
        try:
            await page.evaluate("1")
        except Exception as e:
            logger.error(f"Browser not usable before navigation: {e}")
            return False
            
        # Direct approach with retry mechanism
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"Navigation attempt {attempt+1}/{max_attempts}")
                
                # Use longer timeout with domcontentloaded to speed things up
                await page.goto("https://app.ringba.com/#/dashboard/call-logs/report/new", 
                               timeout=60000, 
                               wait_until="domcontentloaded")
                logger.info("Navigated to call logs report page via direct URL")
                
                # Take a screenshot for debugging
                try:
                    await page.screenshot(path=f"call_logs_navigation_{attempt+1}.png")
                except Exception:
                    pass
                    
                # Check if page is responsive
                try:
                    await page.evaluate("1")
                    logger.info("Page is responsive after navigation")
                    
                    # Wait a moment for the page to initialize
                    await asyncio.sleep(5)
                    
                    # Success - we've reached the page and it's responsive
                    return True
                except Exception as e:
                    logger.error(f"Page not responsive after navigation attempt {attempt+1}: {e}")
                    
                    if attempt < max_attempts - 1:
                        # Wait before retrying
                        wait_time = 3 * (attempt + 1)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        return False
                        
            except Exception as e:
                logger.error(f"Navigation attempt {attempt+1} failed: {e}")
                
                if attempt < max_attempts - 1:
                    # Wait before retrying
                    wait_time = 3 * (attempt + 1)
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    return False
        
        # If we get here, all attempts failed
        logger.error("All navigation attempts failed")
        return False
        
    except Exception as e:
        logger.error(f"Error in navigate_to_reporting: {e}")
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
        converted_column = None  # Add converted column tracking
        
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
        
        # Find Converted column - specifically look for exact match first
        for col in df.columns:
            if col.lower() == 'converted':
                converted_column = col
                logger.info(f"Found Converted column: {converted_column}")
                break
        
        if target_column is None or rpc_column is None:
            logger.warning(f"Could not identify Target or RPC columns in: {df.columns}")
            return []
            
        logger.info(f"Using columns: Target='{target_column}', RPC='{rpc_column}'")
        
        # Extract the data
        data = []
        for _, row in df.iterrows():
            target_name = row[target_column]
            rpc_value = row[rpc_column]
            
            # Skip empty values
            if pd.isna(target_name) or pd.isna(rpc_value):
                continue
                
            # Convert RPC to float if it's a string with a dollar sign
            if isinstance(rpc_value, str):
                rpc_value = rpc_value.replace('$', '').replace(',', '')
                try:
                    rpc_value = float(rpc_value)
                except ValueError:
                    logger.warning(f"Could not convert RPC value to float: {rpc_value}")
                    continue
            
            # Try to get incoming count if available
            incoming_count = 0
            for col in df.columns:
                if col.lower() in ['incoming', 'calls', 'call count', 'inbound', 'inbound calls']:
                    try:
                        incoming_count = int(row[col])
                        break
                    except (ValueError, TypeError):
                        # Try to convert string to number if needed
                        try:
                            val = str(row[col]).replace(',', '')
                            incoming_count = int(float(val))
                            break
                        except:
                            incoming_count = 0
            
            # Get converted value if the column was found
            converted_value = 0
            if converted_column and not pd.isna(row[converted_column]):
                try:
                    # Convert to integer, handling string with commas
                    if isinstance(row[converted_column], str):
                        converted_value = int(float(row[converted_column].replace(',', '')))
                    else:
                        converted_value = int(row[converted_column])
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert Converted value to integer: {row[converted_column]}")
                    converted_value = 0
            
            # Handle NaN or empty target names - these are typically total/average rows
            if pd.isna(target_name) or str(target_name).lower() == 'nan' or str(target_name).strip() == '':
                target_name = "Totals (all targets average)"
            
            data.append({
                'Target': str(target_name),
                'RPC': float(rpc_value),
                'Incoming': incoming_count,
                'Converted': converted_value
            })
        
        logger.info(f"Extracted {len(data)} rows of Target and RPC data from CSV")
        
        # Log the first few entries for debugging
        for i, item in enumerate(data[:5]):
            logger.info(f"CSV Row {i}: Target: {item['Target']}, RPC: ${item['RPC']}")
            
        return data
        
    except Exception as e:
        logger.error(f"Error reading CSV data: {e}")
        return []

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_time_slot(run_time):
    hour = run_time.hour
    minute = run_time.minute
    if hour == 10 and minute < 30:
        return "10AM"
    elif hour == 14 and minute < 30:
        return "2PM"
    elif hour == 16 and minute >= 30:
        return "4:30PM"
    return f"{hour}:{minute}"

def save_report_data(target_rpc_data, run_time):
    try:
        run_time_str = run_time.strftime("%Y-%m-%d %H:%M:%S")
        time_slot = get_time_slot(run_time)
        data = {
            "time_slot": time_slot,
            "timestamp": run_time_str,
            "targets": target_rpc_data
        }
        # Upsert (insert or update) the record for this time_slot
        supabase.table("ringba_reports").upsert(data, on_conflict=["time_slot"]).execute()
        logger.info(f"Saved report data to Supabase for time slot: {time_slot}")
        return True
    except Exception as e:
        logger.error(f"Error saving data to Supabase: {e}")
        return False

def get_previous_report_data(current_time):
    try:
        time_slot = get_time_slot(current_time)
        previous_slot = None
        if time_slot == "2PM":
            previous_slot = "10AM"
        elif time_slot == "4:30PM":
            previous_slot = "2PM"
        if previous_slot:
            result = supabase.table("ringba_reports").select("targets").eq("time_slot", previous_slot).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]["targets"]
        return None
    except Exception as e:
        logger.error(f"Error retrieving data from Supabase: {e}")
        return None

def calculate_percentage_difference(current_value, previous_value):
    """
    Calculate percentage difference between current and previous values
    
    Args:
        current_value: Current numeric value
        previous_value: Previous numeric value to compare against
    
    Returns:
        Float representing percentage change (positive for increase, negative for decrease)
    """
    if previous_value == 0:
        # Avoid division by zero
        if current_value == 0:
            return 0.0  # No change if both are zero
        else:
            return 100.0  # 100% increase if previous was zero
    
    return ((current_value - previous_value) / previous_value) * 100.0

def create_comparative_report(current_data, previous_data):
    """
    Create a comparative report showing percentage differences
    
    Args:
        current_data: List of dictionaries with current target data
        previous_data: List of dictionaries with previous target data
    
    Returns:
        List of dictionaries with the same structure as current_data but with percentage differences
    """
    logger.info("Creating comparative report")
    
    if not previous_data:
        logger.warning("No previous data available for comparison")
        return current_data
    
    # Create a lookup dictionary from previous data for faster access
    previous_lookup = {item["Target"]: item for item in previous_data}
    
    # Create comparative report
    comparative_data = []
    for current_item in current_data:
        target_name = current_item["Target"]
        
        # Create a new report item
        report_item = {
            "Target": target_name,
            "RPC": current_item["RPC"],
            "Incoming": current_item["Incoming"],
            "Converted": current_item["Converted"],
            "is_comparative": True  # Flag to indicate this is a comparative report
        }
        
        # Add percentage differences if target was in previous data
        if target_name in previous_lookup:
            previous_item = previous_lookup[target_name]
            
            # Calculate percentage differences
            report_item["RPC_pct"] = calculate_percentage_difference(
                current_item["RPC"], previous_item["RPC"])
            
            report_item["Incoming_pct"] = calculate_percentage_difference(
                current_item["Incoming"], previous_item["Incoming"])
            
            report_item["Converted_pct"] = calculate_percentage_difference(
                current_item["Converted"], previous_item["Converted"])
            
            # Also store previous values for reference
            report_item["Previous_RPC"] = previous_item["RPC"]
            report_item["Previous_Incoming"] = previous_item["Incoming"]
            report_item["Previous_Converted"] = previous_item["Converted"]
        else:
            # Target is new, so no percentage change available
            logger.info(f"Target '{target_name}' is new, no comparison available")
            report_item["RPC_pct"] = None
            report_item["Incoming_pct"] = None
            report_item["Converted_pct"] = None
        
        comparative_data.append(report_item)
    
    logger.info(f"Created comparative report with {len(comparative_data)} targets")
    return comparative_data

async def send_slack_notification(message):
    """
    Send Slack notification for low RPC values
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured")
        return False
        
    try:
        import requests
        
        # Check if message is too large (Slack has ~4000 char limit)
        if len(message) > 3000:
            logger.info(f"Message length ({len(message)} chars) exceeds recommended size, splitting into smaller messages")
            
            # Split the message - find the header part
            header_parts = message.split("\n\n", 1)
            header = header_parts[0] + "\n\n"
            
            # Rest of the message contains the targets
            targets_part = header_parts[1] if len(header_parts) > 1 else ""
            
            # Split targets into chunks of ~10 targets each
            target_lines = targets_part.split("\n")
            
            # Send header as first message
            first_payload = {
                "text": header + f"*Sending data in multiple messages due to size ({len(target_lines)} targets)*"
            }
            
            response = requests.post(
                SLACK_WEBHOOK_URL,
                data=json.dumps(first_payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send first Slack notification: {response.status_code} {response.text}")
                return False
                
            # Send targets in chunks of 10
            chunk_size = 10
            for i in range(0, len(target_lines), chunk_size):
                chunk = target_lines[i:i + chunk_size]
                chunk_message = "\n".join(chunk)
                
                if chunk_message.strip():  # Only send non-empty chunks
                    chunk_payload = {
                        "text": f"*Targets (continued, {i+1}-{min(i+chunk_size, len(target_lines))} of {len(target_lines)})*\n\n{chunk_message}"
                    }
                    
                    chunk_response = requests.post(
                        SLACK_WEBHOOK_URL,
                        data=json.dumps(chunk_payload),
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if chunk_response.status_code != 200:
                        logger.error(f"Failed to send chunk Slack notification: {chunk_response.status_code} {chunk_response.text}")
            
            logger.info("Split Slack notifications sent successfully")
            return True
            
        # For smaller messages, send normally
        # Create payload for Slack - using simple text instead of blocks for better compatibility
        payload = {
            "text": message
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
    Get CSV values from Ringba reporting page
    """
    MAX_RETRIES = 4
    
    # Create new browser instance if needed
    browser = None
    context = None
    playwright_instance = None
    
    try:
        if start_fresh or not page:
            logger.info("Starting get_csv_values...")
            logger.info("Creating new browser instance...")
            
            # Set up browser with retry mechanism
            playwright_instance, browser, context, page = await setup_browser(headless=True)
            
            # Login to Ringba
            logger.info("Logging in to Ringba...")
            login_success = await login_to_ringba(page)
            
            if not login_success:
                logger.error("Login failed")
                if retry_count < MAX_RETRIES:
                    logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                    if browser:
                        await browser.close()
                    return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
                else:
                    logger.error("Max retries reached for login, giving up")
                    return []
            
            # Take screenshot after successful login
            try:
                await page.screenshot(path="after_login.png")
                logger.info("Saved screenshot after login")
            except Exception as ss_error:
                logger.warning(f"Could not save screenshot: {ss_error}")
        
        # Navigate to Reporting tab
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
                return []
                
        # Export and download CSV
        csv_path = await export_and_download_csv(page)
        
        if not csv_path:
            logger.error("Failed to export and download CSV")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                logger.error("Max retries reached for CSV export, giving up")
                return []
        
        logger.info(f"CSV downloaded to: {csv_path}")
        
        # Process the CSV file to extract RPC values
        try:
            import pandas as pd
            
            # Read the CSV file
            df = pd.read_csv(csv_path)
            logger.info(f"CSV loaded with columns: {df.columns.tolist()}")
            
            # Look for target column and RPC column
            target_column = None
            rpc_column = None
            converted_column = None  # Add converted column tracking
            
            # Find target column
            for col in df.columns:
                if col.lower() in ['target', 'campaign', 'campaign name', 'name']:
                    target_column = col
                    break
            
            # Find RPC column
            for col in df.columns:
                if 'rpc' in col.lower():
                    rpc_column = col
                    logger.info(f"Found RPC column: {rpc_column}")
                    break
                    
            # Find Converted column - specifically look for exact match first
            for col in df.columns:
                if col.lower() == 'converted':
                    converted_column = col
                    logger.info(f"Found Converted column: {converted_column}")
                    break
            
            if not target_column:
                logger.warning("Could not find a target column, using first column")
                target_column = df.columns[0]
            
            if not rpc_column:
                logger.warning("Could not find an RPC column, trying alternative column names")
                # Try common alternative names
                for col in df.columns:
                    if any(keyword in col.lower() for keyword in ['revenue', 'profit', 'earning', 'value']):
                        rpc_column = col
                        logger.info(f"Using alternative column as RPC: {rpc_column}")
                        break
            
            if not rpc_column:
                logger.error("Could not find a usable RPC column in the CSV")
                if retry_count < MAX_RETRIES:
                    logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                    if browser:
                        await browser.close()
                    return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
                else:
                    logger.error("Max retries reached, giving up")
                    return []
            
            # Clean the RPC values (remove $ and commas)
            if df[rpc_column].dtype == object:  # if string type
                df[rpc_column] = df[rpc_column].astype(str).str.replace('$', '').str.replace(',', '')
            
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
                    return []
            
            # Create a list of target and RPC data
            target_rpc_data = []
            for _, row in df.iterrows():
                target_name = row[target_column]
                rpc_value = row[rpc_column]
                
                # Try to get incoming count if available
                incoming_count = 0
                for col in df.columns:
                    if col.lower() in ['incoming', 'calls', 'call count', 'inbound', 'inbound calls']:
                        try:
                            incoming_count = int(row[col])
                            break
                        except (ValueError, TypeError):
                            # Try to convert string to number if needed
                            try:
                                val = str(row[col]).replace(',', '')
                                incoming_count = int(float(val))
                                break
                            except:
                                incoming_count = 0
                
                # Get converted value if the column was found
                converted_value = 0
                if converted_column and not pd.isna(row[converted_column]):
                    try:
                        # Convert to integer, handling string with commas
                        if isinstance(row[converted_column], str):
                            converted_value = int(float(row[converted_column].replace(',', '')))
                        else:
                            converted_value = int(row[converted_column])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert Converted value to integer: {row[converted_column]}")
                        converted_value = 0
                
                # Handle NaN or empty target names - these are typically total/average rows
                if pd.isna(target_name) or str(target_name).lower() == 'nan' or str(target_name).strip() == '':
                    target_name = "Totals (all targets average)"
                
                target_rpc_data.append({
                    'Target': str(target_name),
                    'RPC': float(rpc_value),
                    'Incoming': incoming_count,
                    'Converted': converted_value
                })
            
            logger.info(f"Extracted {len(target_rpc_data)} target RPC values")
            
            # Clean up the CSV file
            try:
                os.remove(csv_path)
                logger.info(f"Removed CSV file: {csv_path}")
            except Exception as remove_error:
                logger.warning(f"Could not remove CSV file: {remove_error}")
            
            return target_rpc_data
            
        except Exception as csv_error:
            logger.error(f"Error processing CSV file: {csv_error}")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying get_csv_values (attempt {retry_count + 1}/{MAX_RETRIES})...")
                if browser:
                    await browser.close()
                return await get_csv_values(page=None, start_fresh=True, retry_count=retry_count + 1)
            else:
                return []
    
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
            return []
            
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
        target_rpc_data = await get_csv_values(start_fresh=True)
        
        if not target_rpc_data:
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
        
        # Get the RPC threshold (default to 12.0)
        threshold = float(os.environ.get("RPC_THRESHOLD", "12.0"))
        
        # Use all targets instead of filtering by RPC
        targets_to_display = target_rpc_data
        
        # Get current time in Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Get previous report data for comparison if needed
        is_comparative_report = False
        report_data = None
        
        # Determine if this is a comparison report time (2 PM or 4:30 PM)
        if now.hour == 14 and now.minute < 30:  # 2 PM ET
            logger.info("This is a 2 PM run - creating comparative report vs 10 AM")
            is_comparative_report = True
            previous_data = get_previous_report_data(now)
            if previous_data:
                report_data = create_comparative_report(target_rpc_data, previous_data)
            else:
                logger.warning("No 10 AM data available for comparison, using standard report")
                report_data = target_rpc_data
                is_comparative_report = False
        elif now.hour == 16 and now.minute >= 30:  # 4:30 PM ET
            logger.info("This is a 4:30 PM run - creating comparative report vs 2 PM")
            is_comparative_report = True
            previous_data = get_previous_report_data(now)
            if previous_data:
                report_data = create_comparative_report(target_rpc_data, previous_data)
            else:
                logger.warning("No 2 PM data available for comparison, using standard report")
                report_data = target_rpc_data
                is_comparative_report = False
        else:
            # Standard report for other times (e.g., 10 AM)
            logger.info("This is a standard report - no comparison needed")
            report_data = target_rpc_data
        
        # Format message for Slack differently based on report type
        if is_comparative_report:
            # Format as comparative report
            if now.hour == 14:
                message = f"📊 *Ringba Comparative Report - {now.strftime('%Y-%m-%d %H:%M:%S')} ET (vs 10 AM):*\n\n"
            else:  # 4:30 PM
                message = f"📊 *Ringba Comparative Report - {now.strftime('%Y-%m-%d %H:%M:%S')} ET (vs 2 PM):*\n\n"
            
            # Add each target to the message with comparative formatting
            for item in report_data:
                target_name = item["Target"]
                
                # Format percentage changes with arrows
                rpc_pct = item.get("RPC_pct")
                incoming_pct = item.get("Incoming_pct")
                converted_pct = item.get("Converted_pct")
                
                # Only include targets that have comparison data
                if rpc_pct is not None:
                    # Format RPC with arrow
                    if rpc_pct > 0:
                        rpc_str = f"↗️ +{rpc_pct:.1f}%"
                    elif rpc_pct < 0:
                        rpc_str = f"↘️ {rpc_pct:.1f}%"
                    else:
                        rpc_str = f"→ {rpc_pct:.1f}%"
                    
                    # Format Incoming with arrow
                    if incoming_pct > 0:
                        incoming_str = f"↗️ +{incoming_pct:.1f}%"
                    elif incoming_pct < 0:
                        incoming_str = f"↘️ {incoming_pct:.1f}%"
                    else:
                        incoming_str = f"→ {incoming_pct:.1f}%"
                    
                    # Format Converted with arrow
                    if converted_pct > 0:
                        converted_str = f"↗️ +{converted_pct:.1f}%"
                    elif converted_pct < 0:
                        converted_str = f"↘️ {converted_pct:.1f}%"
                    else:
                        converted_str = f"→ {converted_pct:.1f}%"
                    
                    # Add target to message with percentage changes
                    message += f"• {target_name} - RPC: {rpc_str}, Incoming: {incoming_str}, Converted: {converted_str}\n"
                else:
                    # New target with no comparison data
                    message += f"• {target_name} - RPC: ${item['RPC']:.2f}, Incoming: {item['Incoming']}, Converted: {item['Converted']} (new target, no comparison)\n"
        else:
            # Format as standard report
            message = f"📊 *Ringba Report - {now.strftime('%Y-%m-%d %H:%M:%S')} ET:*\n"
            message += f"Current target RPC values:\n\n"
            
            # Add each target to the message with standard formatting
            for item in report_data:
                message += f"• {item['Target']} - RPC: ${item['RPC']:.2f}, Incoming: {item['Incoming']}, Converted: {item['Converted']}\n"
        
        # Update last run result
        last_run_result = {
            "success": True,
            "target_rpc_data": target_rpc_data,
            "targets_displayed": report_data,
            "threshold": threshold,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "environment": env_info,
            "is_comparative": is_comparative_report
        }
        
        # Send notification to Slack
        logger.info(f"Sending Slack notification for {len(report_data)} targets")
        await send_slack_notification(message)
        
        # Save the data for future comparison
        save_report_data(target_rpc_data, now)
        
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
    # Schedule checks at 10 AM, 2 PM, and 4:30 PM Eastern Time
    eastern = pytz.timezone('US/Eastern')
    local_tz = pytz.timezone('US/Eastern')  # Adjust based on server location if needed
    
    # Get current time in both timezones
    now_eastern = datetime.now(eastern)
    now_local = datetime.now(local_tz)
    
    # Calculate offset to convert from Eastern to local time
    offset_hours = (now_local.hour - now_eastern.hour) % 24
    
    # Schedule checks in local time
    schedule.every().day.at(f"{(10 + offset_hours) % 24:02d}:00").do(run_check)
    logger.info(f"Scheduled check at 10:00 AM ET (local time: {(10 + offset_hours) % 24:02d}:00)")
    
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