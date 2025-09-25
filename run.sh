#!/bin/bash
set -euo pipefail

# Check if interval argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <interval_seconds>"
    echo "Example: $0 300  # Run every 5 minutes"
    exit 1
fi

INTERVAL=$1

# Validate that interval is a positive integer
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -le 0 ]; then
    echo "Error: Interval must be a positive integer (seconds)"
    exit 1
fi

echo "=== iPhone Stock Bot - Running every $INTERVAL seconds ==="
echo "Press Ctrl+C to stop"

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n=== Stopping iPhone Stock Bot ==="
    docker-compose down
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Start DynamoDB once
echo "=== Starting DynamoDB ==="
docker-compose up -d dynamodb

# Main loop
while true; do
    echo -e "\n=== $(date) - Grabbing fresh cookies ==="
    bash get-cookie.sh

    echo -e "\n=== $(date) - Running iPhone Stock Bot ==="
    docker-compose run --rm iphone-stock-bot

    echo -e "\n=== $(date) - Waiting $INTERVAL seconds before next run ==="
    sleep "$INTERVAL"
done
