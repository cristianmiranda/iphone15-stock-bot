#!/usr/bin/python3

import boto3
import requests
import time
import os
import json
from urllib.parse import quote

from datetime import datetime

# Constants - can be moved to environment variables
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME')
TELEGRAM_API_BASE_URL = os.getenv('TELEGRAM_API_BASE_URL')
APPLE_BUY_BASE_URL = os.getenv('APPLE_BUY_BASE_URL')
GOOGLE_MAPS_BASE_URL = os.getenv('GOOGLE_MAPS_BASE_URL')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT')) if os.getenv('REQUEST_TIMEOUT') else None
MAX_RETRIES = int(os.getenv('MAX_RETRIES')) if os.getenv('MAX_RETRIES') else None
INITIAL_RETRY_DELAY = int(os.getenv('INITIAL_RETRY_DELAY')) if os.getenv('INITIAL_RETRY_DELAY') else None
IPHONE_MODELS_CSV = os.getenv('IPHONE_MODELS_CSV')
APPLE_FULFILLMENT_BASE_URL = os.getenv('APPLE_FULFILLMENT_BASE_URL')
LOCATION = os.getenv('LOCATION')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_IDS = os.getenv('TELEGRAM_CHAT_IDS')

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


def construct_apple_url(location=None, models_csv=None):
    """
    Construct Apple fulfillment messages URL from environment variables

    Args:
        location: Store location code (defaults to LOCATION)
        models_csv: Comma-separated list of iPhone model codes (defaults to IPHONE_MODELS_CSV)

    Returns:
        Complete Apple fulfillment URL
    """
    if location is None:
        location = LOCATION
    if models_csv is None:
        models_csv = IPHONE_MODELS_CSV

    # Split the CSV and create parts parameters with URL encoding
    models = models_csv.split(',')
    parts_params = '&'.join([f'parts.{i}={quote(model.strip())}' for i, model in enumerate(models)])

    # Construct the full URL
    url = f"{APPLE_FULFILLMENT_BASE_URL}?mts.0=regular&mts.1=compact&pl=true&location={location}&{parts_params}"

    return url


def escape_markdown(text):
    """Escape special characters for Telegram Markdown"""
    if not text:
        return text
    # Escape Markdown special characters, but preserve decimal numbers
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '=', '|', '{', '}', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def generate_availability_table(available_items):
    """Generate a compact table of available iPhones with buy links"""
    if not available_items:
        return "\n\n📋 **CURRENTLY AVAILABLE**\n\n😔 *No iPhones currently in stock*\n💤 *All stores are out of inventory*\n\n🔔 *You'll be notified when stock becomes available!*"

    table_text = "\n\n📋 **CURRENTLY AVAILABLE**\n\n"
    for item in available_items:
        table_text += f"✅ **{escape_markdown(item['model'])}**\n🏪 {escape_markdown(item['store'])} *({escape_markdown(item['zipCode'])})*\n📍 [{escape_markdown(item['distance'])}]({item['maps_link']})\n🛒 [Buy Now]({item['buy_url']})\n\n"

    return table_text


def run(apple_url, bot_token, recipients):
    # bot_token = sys.argv[1]
    # recipients = json.loads(sys.argv[2])

    # Make a GET request to the URL with proper headers and retry logic
    headers = DEFAULT_HEADERS

    max_retries = MAX_RETRIES or 3
    retry_delay = INITIAL_RETRY_DELAY or 1

    for attempt in range(max_retries):
        try:
            response = requests.get(apple_url, headers=headers, timeout=REQUEST_TIMEOUT or 30)
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

        # Collect availability changes and current available items
        availability_changes = []
        currently_available = []

        # Iterate over each store in the JSON data
        for store in data['body']['content']['pickupMessage']['stores']:
            store_name = store['storeName']
            store_latitude = store['storelatitude']
            store_longitude = store['storelongitude']
            zipCode = store['address']['postalCode']
            google_maps_link = f"{GOOGLE_MAPS_BASE_URL}{store_latitude},{store_longitude}"

            print(f"-------------------------------------")
            print(f"> {store_name} ({zipCode})")
            print(f"")

            for part, details in store['partsAvailability'].items():
                availability = details['pickupDisplay']
                model = details['messageTypes']['compact']['storePickupProductTitle']

                model_parts = model.split(' ')
                storage = model_parts[4].lower()  # Extracting "1TB"
                color = '-'.join(model_parts[5:]).lower()  # Converting "Natural Titanium" to "natural-titanium"
                buy_url = f"{APPLE_BUY_BASE_URL}6.9-inch-display-{storage}-{color}-unlocked"

                availability_icon = '🚫'
                if availability == 'available':
                    availability_icon = '✅'
                    currently_available.append({
                        'model': model,
                        'store': store_name,
                        'zipCode': zipCode,
                        'distance': store['storeDistanceWithUnit'],
                        'maps_link': google_maps_link,
                        'buy_url': buy_url
                    })

                print(f"{availability_icon} {model} @ {zipCode} is {availability}")

                model_store_key = f"{model}@{store_name}"

                response = table.get_item(Key={'ID': model_store_key})
                db_item = response.get('Item')
                if db_item:
                    db_availability = db_item.get('availability')
                else:
                    db_availability = None

                if db_availability != availability:
                    print(f"Availability changed for {model} @ {zipCode}! Recording change...")
                    table.put_item(
                        Item={
                            'ID': model_store_key,
                            'availability': availability
                        }
                    )

                    change_message = f"📱 **{escape_markdown(model)}**\n🏪 {escape_markdown(store_name)} *({escape_markdown(zipCode)})*\n📍 [{escape_markdown(store['storeDistanceWithUnit'])}]({google_maps_link})\n\n{availability_icon} **{availability.upper()}**\n\n🛒 [Buy Now]({buy_url})"
                    availability_changes.append(change_message)

        # Send consolidated message if there are any changes
        if availability_changes:
            header = "🚨 **STOCK ALERT** 🚨\n"
            consolidated_message = "\n\n---\n\n".join(availability_changes)
            availability_table = generate_availability_table(currently_available)
            final_message = header + consolidated_message + availability_table

            print("Sending consolidated message:")
            print(final_message)
            telegram_bot_sendtext(final_message, bot_token, recipients)
        else:
            print("No availability changes detected.")
    else:
        print(f"Failed to fetch the data. Status code: {response.status_code}")


def telegram_bot_sendtext(bot_message, bot_token, recipients):
    for bot_chatID in recipients:
        send_text = TELEGRAM_API_BASE_URL + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&disable_web_page_preview=true&text=' + bot_message
        response = requests.get(send_text)
        print(response.json())


def handler(event, context):
    # Get parameters from environment variables
    bot_token = TELEGRAM_BOT_TOKEN
    recipients = json.loads(TELEGRAM_CHAT_IDS) if TELEGRAM_CHAT_IDS else []

    # Construct Apple URL from environment variables
    apple_url = construct_apple_url()
    print(f"Constructed Apple URL from environment variables: {apple_url}")

    if bot_token:
        print(f"Bot token received!")

    if recipients:
        print(f"Recipients: {recipients}")

    print("Checking iPhone stock availability")
    run(apple_url=apple_url, bot_token=bot_token, recipients=recipients)

    return { 'status' : 200, 'body' : 'Lambda executed successfully!' }
