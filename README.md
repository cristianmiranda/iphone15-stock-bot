# 📱 iPhone Stock Bot

<p align="center">
  <img src="https://imgur.com/eCTbTxu.png" alt="Architecture" width="50%">
</p>

A serverless bot that monitors iPhone availability at Apple stores and sends Telegram notifications when stock becomes available.

## 🏗️ Architecture

The bot runs on AWS Lambda and uses:
- **ECR** - Container registry for the Lambda function
- **Lambda** - Serverless function that checks iPhone availability
- **DynamoDB** - NoSQL database to track availability changes
- **CloudWatch** - Logging and monitoring
- **EventBridge Scheduler** - Triggers the Lambda function periodically
- **Telegram Bot API** - Sends notifications to users

## 🚀 Features

- Monitors multiple iPhone models and stores simultaneously
- Tracks availability changes using DynamoDB
- Sends rich Telegram notifications with store details and Google Maps links
- Configurable via environment variables
- Automatic retry logic for API requests
- Dockerized for consistent deployment

## 📋 Environment Variables

The Lambda function requires these environment variables:

- `DYNAMODB_TABLE_NAME` - DynamoDB table name for tracking availability
- `TELEGRAM_API_BASE_URL` - Telegram Bot API base URL
- `APPLE_BUY_BASE_URL` - Apple store buy URL base
- `GOOGLE_MAPS_BASE_URL` - Google Maps URL base for directions
- `APPLE_FULFILLMENT_BASE_URL` - Apple fulfillment API endpoint
- `LOCATION` - Apple store location code
- `IPHONE_MODELS_CSV` - Comma-separated list of iPhone model codes to monitor
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_IDS` - JSON array of chat IDs to send notifications to
- `REQUEST_TIMEOUT` - HTTP request timeout (optional, default: 60)
- `MAX_RETRIES` - Maximum retry attempts (optional, default: 3)
- `INITIAL_RETRY_DELAY` - Initial retry delay in seconds (optional, default: 5)
- `APPLE_COOKIES` - Apple website cookies (required for API access)

## 🍪 Getting Apple Cookies

Apple is now enforcing cookies and doesn't allow anonymous requests anymore. To obtain valid cookies for authentication:

1. **Navigate to an Apple iPhone purchase page** in your browser and perform human interactions:
   ```
   https://www.apple.com/shop/buy-iphone/iphone-17-pro/6.9-inch-display-512gb-deep-blue-unlocked
   ```

2. **Scroll down or interact with the page** - perform some human-like actions to avoid detection

3. **Run the cookie extraction script**:
   ```bash
   ./get-cookie.sh
   ```

   This script will automatically:
   - Find your Firefox profile
   - Extract cookies from the SQLite database
   - Display them in the required format

4. **Copy the Cookie header** from the script output and set it as the `APPLE_COOKIES` environment variable

**Alternative Manual Method:**

1. Open Developer Tools (F12) while on the Apple page
2. Go to the Network tab and refresh the page
3. Find any Apple API request in the network log
4. Right-click → Copy → Copy as cURL
5. Extract the Cookie header from the cURL command

**Note:** Cookies expire periodically (aboute every 2 hours), so you'll need to update them when the bot starts failing with authentication errors.

## 🔧 Development & Deployment

### Local Development with Docker Compose

To run the bot locally using Docker Compose:

1. **Create a `.env` file** with your environment variables (use `.env.sample` as template)

2. **Build and run with Docker Compose**:
   ```bash
   docker compose up --build
   ```

3. **Run in detached mode** (background):
   ```bash
   docker compose up -d --build
   ```

4. **For debugging, run interactively**:
   ```bash
   docker compose run --rm app /bin/bash
   ```

5. **View logs**:
   ```bash
   docker compose logs -f
   ```

6. **Stop the service**:
   ```bash
   docker compose down
   ```

### Automated Deployment (GitHub Actions)

The repository includes a GitHub Actions workflow that automatically builds and deploys the Lambda function when code is pushed to the master branch.

### Manual Deployment

```bash
# Build and push docker image
docker build -t iphonestockbot .
docker tag iphonestockbot:latest 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphonestockbot:latest
docker push 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphonestockbot:latest

# Update lambda function
aws lambda update-function-code --function-name iPhoneStockBot --image-uri 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphonestockbot:latest
```

## 📱 Usage

### Lambda Event Payload

The Lambda function no longer requires event payload parameters. All configuration is handled via environment variables.

You can trigger the function with an empty event:

```json
{}
```

### Notification Format

When availability changes, users receive notifications like:

```
🚨 STOCK ALERT 🚨

📱 iPhone 17 Pro Max 1TB Deep Blue
🏪 Apple Store Name (ZIP Code)
📍 2.5 mi (clickable Maps link)

✅ AVAILABLE

🛒 Buy Now

📋 CURRENTLY AVAILABLE

✅ iPhone 17 Pro Max 1TB Deep Blue
🏪 Apple Store Name (ZIP Code)
📍 2.5 mi (clickable Maps link)
🛒 Buy Now
```

## 🖼️ AWS Resources

![](https://imgur.com/M5qoOjU.png)

![](https://imgur.com/JNYikb8.png)

![](https://imgur.com/BexCByB.png)

![](https://imgur.com/jGHZxSm.png)

```
Made in 🇦🇷
```
