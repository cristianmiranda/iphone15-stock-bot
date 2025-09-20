#!/usr/bin/python3

import boto3
import requests
import time
import os

from datetime import datetime

# Constants - can be moved to environment variables
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'IPHONE_STOCK')
TELEGRAM_API_BASE_URL = os.getenv('TELEGRAM_API_BASE_URL', 'https://api.telegram.org/bot')
APPLE_BUY_URL_BASE = os.getenv('APPLE_BUY_URL_BASE', 'https://www.apple.com/shop/buy-iphone/iphone-17-pro/')
GOOGLE_MAPS_URL_BASE = os.getenv('GOOGLE_MAPS_URL_BASE', 'https://maps.google.com/?q=')
USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
INITIAL_RETRY_DELAY = int(os.getenv('INITIAL_RETRY_DELAY', '1'))

# HTTP Headers
DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Initializing a DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def run(apple_url, bot_token, recipients):
    # bot_token = sys.argv[1]
    # recipients = json.loads(sys.argv[2])

    # Make a GET request to the URL with proper headers and retry logic
    headers = DEFAULT_HEADERS

    max_retries = MAX_RETRIES
    retry_delay = INITIAL_RETRY_DELAY

    for attempt in range(max_retries):
        try:
            response = requests.get(apple_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code != 503:
                break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Failed to fetch data after {max_retries} attempts. Last error: {e}")
                return

        if attempt < max_retries - 1:
            print(f"Attempt {attempt + 1} failed with status {response.status_code if 'response' in locals() else 'unknown'}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Load the JSON data from the response
        data = response.json()

        # Iterate over each store in the JSON data
        for store in data['body']['content']['pickupMessage']['stores']:
            store_name = store['storeName']
            store_latitude = store['storelatitude']
            store_longitude = store['storelongitude']
            zipCode = store['address']['postalCode']
            google_maps_link = f"{GOOGLE_MAPS_URL_BASE}{store_latitude},{store_longitude}"

            print(f"-------------------------------------")
            print(f"> {store_name} ({zipCode})")
            print(f"")

            for part, details in store['partsAvailability'].items():
                availability = details['pickupDisplay']
                model = details['messageTypes']['compact']['storePickupProductTitle']

                model_parts = model.split(' ')
                storage = model_parts[4].lower()  # Extracting "1TB"
                color = '-'.join(model_parts[5:]).lower()  # Converting "Natural Titanium" to "natural-titanium"
                buy_url = f"{APPLE_BUY_URL_BASE}6.9-inch-display-{storage}-{color}-unlocked"

                availability_icon = '🚫'
                if availability == 'available':
                    availability_icon = '✅'

                print(f"{availability_icon} {model} @ {zipCode} is {availability}")

                model_store_key = f"{model}@{store_name}"

                response = table.get_item(Key={'ID': model_store_key})
                db_item = response.get('Item')
                if db_item:
                    db_availability = db_item.get('availability')
                else:
                    db_availability = None

                if db_availability != availability:
                    print(f"Availability changed for {model} @ {zipCode}! Sending notification...")
                    table.put_item(
                        Item={
                            'ID': model_store_key,
                            'availability': availability
                        }
                    )

                    message = f"📱 {model}\n🏰 {store_name} ({zipCode})\n📍 {store['storeDistanceWithUnit']}\n🗺️ {google_maps_link}\n\n{availability_icon} **{availability.upper()}**\n\n🛒 {buy_url}"

                    print(message)
                    telegram_bot_sendtext(message, bot_token, recipients)
    else:
        print(f"Failed to fetch the data. Status code: {response.status_code}")


def telegram_bot_sendtext(bot_message, bot_token, recipients):
    for bot_chatID in recipients:
        send_text = TELEGRAM_API_BASE_URL + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
        response = requests.get(send_text)
        print(response.json())


def handler(event, context):
    apple_url = event['apple_url']
    bot_token = event['bot_token']
    recipients = event['recipients']

    if apple_url:
        print(f"Using Apple URL: {apple_url}")

    if bot_token:
        print(f"Bot token received!")

    if recipients:
        print(f"Recipients: {recipients}")

    print("Checking iPhone stock availability")
    run(apple_url=apple_url, bot_token=bot_token, recipients=recipients)

    return { 'status' : 200, 'body' : 'Lambda executed successfully!' }
