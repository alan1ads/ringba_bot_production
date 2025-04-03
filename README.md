# Ringba RPC Monitor Bot

A bot that monitors Ringba's Reporting tab for low RPC (Revenue Per Call) values and sends alerts to Slack at scheduled times throughout the day.

![Ringba RPC Monitor](https://www.ringba.com/wp-content/uploads/2020/01/ringba-logo-1.svg)

## Overview

This bot performs the following tasks:

1. **Scheduled Checks**: Automatically checks Ringba at 11 AM ET, 2 PM ET, and 4 PM ET
2. **Web Automation**: Logs in to Ringba, navigates to the Reporting tab, and extracts RPC data
3. **Smart Monitoring**: Identifies targets with RPC values below $12
4. **Slack Alerts**: Sends notifications to Slack when low RPC values are detected

## Features

- **Reliable Automation**: Uses Playwright for robust web automation
- **Anti-Detection**: Uses stealth techniques to avoid bot detection
- **Flexible Table Parsing**: Works with different table layouts in Ringba's UI
- **Scheduled Operation**: Runs automatically at specified times
- **Cloud Deployment**: Designed to run continuously on Render.com
- **Detailed Logging**: Provides comprehensive logs for monitoring and troubleshooting

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Ringba account credentials
- Slack webhook URL (for notifications)

### Installation

1. **Clone this repository**:
   ```bash
   git clone <repository-url>
   cd ringba-bot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**:
   ```bash
   python -m playwright install chromium
   ```

4. **Configure environment variables**:
   Create a `.env` file with the following:
   ```
   RINGBA_EMAIL=your-ringba-email@example.com
   RINGBA_PASSWORD=your-ringba-password
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your-webhook-url
   ```

### Running the Bot

#### Local Testing

For development and testing:

```bash
python playwright_bot.py
```

This will run a one-time check and show the results.

#### Production Deployment

For continuous operation:

```bash
python ringba_bot_production.py
```

This will set up scheduled checks and run continuously.

## Deployment

This bot is designed to be deployed to Render.com for 24/7 operation. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

## Troubleshooting

If you encounter issues:

1. Check the logs in `ringba_bot.log`
2. Verify your credentials in the `.env` file
3. Ensure your Slack webhook URL is active and correct
4. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for additional help

## Project Structure

- `ringba_bot_production.py`: Main production bot with scheduling
- `playwright_bot.py`: Testing version using Playwright
- `chrome_helper.py`: Helper module for Chrome WebDriver setup
- `Dockerfile`: Container configuration for deployment
- `requirements.txt`: Python dependencies
- `.env`: Environment variables (credentials)
- Documentation:
  - `README.md`: Project overview (this file)
  - `DEPLOYMENT_GUIDE.md`: Deployment instructions
  - `TROUBLESHOOTING.md`: Problem-solving guide
  - `GETTING_STARTED.md`: Quick start guide

## License

This project is proprietary and confidential.

## Support

For assistance, please contact the project maintainer.
