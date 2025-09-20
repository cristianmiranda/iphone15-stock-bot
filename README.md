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
- `REQUEST_TIMEOUT` - HTTP request timeout (optional, default: 30)
- `MAX_RETRIES` - Maximum retry attempts (optional, default: 3)
- `INITIAL_RETRY_DELAY` - Initial retry delay in seconds (optional, default: 1)

## 🔧 Deployment

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

The Lambda function expects this JSON payload:

```json
{
  "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "recipients": [CHAT_ID_1, CHAT_ID_2]
}
```

### Notification Format

When availability changes, users receive notifications like:

```
📱 iPhone 15 Pro Max 1TB Natural Titanium
🏰 Apple Store Name (ZIP Code)
📍 2.5 miles away
🗺️ [Google Maps Link]

✅ **AVAILABLE**

🛒 [Apple Store Purchase Link]
```

## 🖼️ AWS Resources

![](https://imgur.com/M5qoOjU.png)

![](https://imgur.com/JNYikb8.png)

![](https://imgur.com/BexCByB.png)

![](https://imgur.com/jGHZxSm.png)

```
Made in 🇦🇷
```
