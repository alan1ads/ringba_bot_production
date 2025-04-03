# Deploying the Ringba RPC Monitor Bot to Render.com

This guide will walk you through deploying the Ringba RPC Monitor Bot to Render.com so it runs automatically at 11:00 AM ET, 2:00 PM ET, and 4:30 PM ET.

## Prerequisites

1. A GitHub account to host your code repository
2. A Render.com account (you can sign up for free at [render.com](https://render.com))
3. Your Ringba account credentials
4. Your Slack webhook URL for notifications

## Step 1: Prepare your GitHub repository

1. Create a new GitHub repository (if you don't have one already)
2. Make sure your repository contains all the necessary files:
   - `ringba_bot_production.py` (the main bot script)
   - `Dockerfile` (for container deployment)
   - `requirements.txt` (dependencies)
   - `render.yaml` (Render configuration)
   - `.env.sample` (template for environment variables)

3. Create a `.env` file locally (don't commit this to GitHub) with your actual credentials:
   ```
   RINGBA_EMAIL=your_actual_email@example.com
   RINGBA_PASSWORD=your_actual_password
   SLACK_WEBHOOK_URL=your_actual_slack_webhook_url
   ```

4. Commit and push all files except the `.env` file to your GitHub repository

## Step 2: Set up your Render.com service

1. Log in to your Render.com account
2. Click the "New" button and select "Blueprint" from the dropdown menu
3. Connect your GitHub account if you haven't already
4. Select the repository containing your Ringba bot code
5. Render will detect the `render.yaml` file and suggest the service to deploy
6. Click "Apply" to create the service

## Step 3: Configure environment variables

1. On the service creation page, you'll be prompted to enter the environment variables
2. Enter your actual values for:
   - `RINGBA_EMAIL`: Your Ringba account email
   - `RINGBA_PASSWORD`: Your Ringba account password
   - `SLACK_WEBHOOK_URL`: Your Slack webhook URL for notifications
3. Click "Create Blueprint" to continue

## Step 4: Monitor the deployment

1. Render will now build and deploy your service
2. This process may take several minutes to complete
3. You can monitor the build logs by clicking on your service name

## Step 5: Verify the bot is running

1. Once the service is deployed, check the logs to verify the bot is running correctly
2. You should see messages indicating:
   - "Scheduled check at 11:00 AM ET"
   - "Scheduled check at 2:00 PM ET"
   - "Scheduled check at 4:30 PM ET"
   - "Bot is now running"

## Additional information

### How the scheduling works

The bot is configured to check Ringba RPC values at 11:00 AM, 2:00 PM, and 4:30 PM Eastern Time (ET) every day. It will:

1. Log in to Ringba
2. Navigate to the Reporting tab
3. Export CSV data
4. Check for low RPC values
5. Send Slack notifications if any targets have RPC values below the threshold ($12)

### Monitoring and troubleshooting

- You can view your bot's logs anytime by going to your service on Render.com and clicking the "Logs" tab
- If you need to update the code, simply push changes to your GitHub repository and Render will automatically redeploy the service
- If you need to change any environment variables, go to your service on Render.com, click "Environment," update the variables, and then click "Save Changes"

### Managing costs

- The starter plan on Render.com should be sufficient for this bot
- The bot runs continuously but consumes minimal resources when idle between scheduled checks
- You can always scale down or pause the service if needed 