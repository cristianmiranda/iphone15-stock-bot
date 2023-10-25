# 📱 iPhone 15 Stock Bot

## Deployment

```bash
# Build and push docker image
docker build -t iphone15stockbot .
docker tag iphone15stockbot:latest 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphone15stockbot:latest
docker push 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphone15stockbot:latest

# Refresh lambda
aws lambda update-function-code --function-name iPhone15StockBot --image-uri 387720813372.dkr.ecr.us-east-1.amazonaws.com/iphone15stockbot:latest
```

## AWS Lambda payload

```json
{
  "bot_token": "367849242:ABEY8aTMHxFZQRFqf3kguuz8jSBOp3QnKKR",
  "recipients": [168964322, 167890751]
}
```

## AWS resources:

- Lambda
- ECR
- EventBridge Scheduler

![](https://i.imgur.com/nsdQf2r.png)

```
Hecho con ❤️ en 🇦🇷 ... papá! 🤙🏼
```
