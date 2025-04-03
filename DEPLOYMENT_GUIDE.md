# Deployment Guide for Ringba RPC Monitor Bot

This guide will help you deploy the Ringba RPC Monitor Bot to Render.com so it can run continuously in the cloud.

## Prerequisites

Before deploying, make sure you have:

1. A [Render.com](https://render.com/) account
2. Your Ringba login credentials (email and password)
3. A Slack webhook URL for notifications

## Deployment Steps

### 1. Prepare Your Configuration

First, you need to set up your environment variables. These contain sensitive information that should not be committed to your code repository.

#### Required Environment Variables

- `RINGBA_EMAIL`: Your Ringba account email
- `RINGBA_PASSWORD`: Your Ringba account password
- `SLACK_WEBHOOK_URL`: Your Slack webhook URL for notifications

### 2. Deploy to Render.com

Follow these steps to deploy your bot to Render.com:

1. **Log in to Render.com** and navigate to your dashboard

2. **Create a new Web Service**
   - Click the "New +" button and select "Web Service"

3. **Connect your repository**
   - You can connect to GitHub, GitLab, or BitBucket
   - Select the repository containing your bot code
   
4. **Configure your service**
   - **Name**: Choose a name for your service (e.g., "ringba-rpc-monitor")
   - **Environment**: Select "Docker"
   - **Branch**: Select the branch to deploy (usually "main" or "master")
   - **Region**: Choose the region closest to you

5. **Set environment variables**
   - Scroll down to the "Environment Variables" section
   - Add the following variables:
     - Key: `RINGBA_EMAIL`, Value: [Your Ringba Email]
     - Key: `RINGBA_PASSWORD`, Value: [Your Ringba Password]
     - Key: `SLACK_WEBHOOK_URL`, Value: [Your Slack Webhook URL]

6. **Set resource settings**
   - For a minimal deployment, the "Free" plan should work
   - For better reliability, consider using at least the "Starter" plan
   - **IMPORTANT**: Make sure to select a plan that remains active (free plans may spin down when inactive)

7. **Create Web Service**
   - Click the "Create Web Service" button
   - Render will now build and deploy your bot

### 3. Verify Deployment

After deployment completes:

1. **Check logs** to make sure the bot started correctly
   - Navigate to your service dashboard
   - Click the "Logs" tab to view application logs
   - Look for messages indicating successful login and scheduling

2. **Monitor the first scheduled check**
   - Wait for the first scheduled check to run (11 AM, 2 PM, or 4 PM ET)
   - Verify that you receive Slack notifications if any RPC values are below threshold

### 4. Troubleshooting

If you encounter issues:

1. **Check the logs** in Render.com for error messages

2. **Common issues**:
   - **Bot can't login**: Verify your Ringba credentials are correct
   - **No Slack notifications**: Verify your webhook URL is correct
   - **Bot stops running**: Ensure you're on a paid plan that doesn't spin down with inactivity

3. **Restart the service** if necessary
   - Navigate to your service dashboard
   - Click the "Manual Deploy" button and select "Clear build cache & deploy"

## Maintaining Your Deployment

### Updating Your Bot

When you make changes to your code:

1. Commit and push your changes to your repository
2. Render.com will automatically detect the changes and redeploy

### Monitoring

1. **Check logs regularly** to ensure the bot is running properly
2. **Set up Render.com alerts** for service failures
   - Navigate to your service settings
   - Click on "Alerts" to configure notifications for service issues

## Additional Tips

1. **Schedule downtime during non-business hours** if you need to make significant changes
2. **Consider setting up multiple instances** in different regions for redundancy
3. **Regularly check Slack notifications** to ensure they're working correctly

## Need Help?

If you encounter issues:

- Check the logs for specific error messages
- Review this deployment guide to ensure all steps were followed
- Contact support for assistance