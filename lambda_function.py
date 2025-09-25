#!/usr/bin/python3

import boto3
import requests
import time
import os
import json
from urllib.parse import quote
from decimal import Decimal
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
IPHONE_MODELS = os.getenv('IPHONE_MODELS')
APPLE_FULFILLMENT_BASE_URL = os.getenv('APPLE_FULFILLMENT_BASE_URL')
ZIP_CODES = os.getenv('ZIP_CODES')
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
        location: Store location code (defaults to first ZIP_CODES entry)
        models_csv: Comma-separated list of iPhone model codes (defaults to IPHONE_MODELS)

    Returns:
        Complete Apple fulfillment URL
    """
    if location is None:
        # Use the first ZIP code as default location
        location = ZIP_CODES.split(',')[0] if ZIP_CODES else None
    if models_csv is None:
        models_csv = IPHONE_MODELS

    # Split the CSV and create parts parameters with URL encoding
    models = models_csv.split(',')
    parts_params = '&'.join([f'parts.{i}={quote(model.strip())}' for i, model in enumerate(models)])

    # Construct the full URL using the working curl format (with location=ZIP)
    url = f"{APPLE_FULFILLMENT_BASE_URL}?fae=true&pl=true&mts.0=regular&cppart=UNLOCKED/US&{parts_params}&location={location}"

    return url


def escape_markdown(text):
    """Escape special characters for Telegram Markdown"""
    if not text:
        return text
    # Convert to string if not already
    text = str(text)
    # Escape Markdown special characters, but preserve decimal numbers
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '=', '|', '{', '}', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def sort_available_items(available_items):
    """
    Sort available items by:
    1. Distance (closer to furthest)
    2. Phone size (smaller to larger screen)
    3. Color (alphabetically)
    """
    def sort_key(item):
        distance = float(item['distance'])
        screen_size = float(item['screen_size'])
        color = item['color']
        return (distance, screen_size, color)

    return sorted(available_items, key=sort_key)


def generate_availability_table(available_items):
    """Generate a compact table of available iPhones with buy links"""
    if not available_items:
        return "\n**📋 CURRENTLY AVAILABLE**\n\n😔 *No iPhones currently in stock*"

    # Sort the items before displaying
    sorted_items = sort_available_items(available_items)

    # Limit the number of items to prevent extremely long messages
    MAX_ITEMS_TO_SHOW = 50
    items_to_show = sorted_items[:MAX_ITEMS_TO_SHOW]
    remaining_count = len(sorted_items) - MAX_ITEMS_TO_SHOW

    table_text = "\n**📋 CURRENTLY AVAILABLE**\n\n"
    for item in items_to_show:
        table_text += f"✅ **{escape_markdown(item['model'])}** @ {escape_markdown(item['store'])} - {escape_markdown(item['city'])} *({escape_markdown(item['zipCode'])})* - *{escape_markdown(item['distance'])} mi* - [Buy Now]({item['buy_url']})\n"

    # Add note if there are more items
    if remaining_count > 0:
        table_text += f"\n*\\+{remaining_count} more locations available\\.\\.\\.*"

    return table_text


def parse_cookies_to_session(cookie_string, session):
    """Parse cookie string and add cookies to session"""
    for cookie_pair in cookie_string.split('; '):
        if '=' in cookie_pair:
            name, value = cookie_pair.split('=', 1)
            session.cookies.set(name, value, domain='.apple.com')


def get_apple_cookies():
    """Get cookies from environment variable or .cookies file"""
    session = requests.Session()

    # Priority 1: Get cookies from environment variable
    manual_cookies = os.getenv('APPLE_COOKIES')
    if manual_cookies:
        print("Using manually configured cookies from environment")
        parse_cookies_to_session(manual_cookies, session)
        return session

    # Priority 2: Try to read from .cookies file
    try:
        with open('.cookies', 'r') as f:
            file_cookies = f.read().strip()
            if file_cookies:
                print("Using cookies from .cookies file")
                parse_cookies_to_session(file_cookies, session)
                return session
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error reading .cookies file: {e}")

    # Priority 3: No cookies found
    print("❌ No APPLE_COOKIES environment variable found!")
    return None


def run(apple_url, bot_token, recipients, zip_code):
    # bot_token = sys.argv[1]
    # recipients = json.loads(sys.argv[2])

    # Get cookies first by visiting the Apple store page
    session = get_apple_cookies()
    if not session:
        print("Failed to get Apple cookies, aborting")

        # Send Telegram notification about missing cookies
        error_message = f"🚨 **iPhone Stock Bot Error**\n\n❌ No Apple cookies configured for ZIP code {zip_code}\n\n💡 Please set the APPLE\\_COOKIES environment variable\n\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        telegram_bot_sendtext(error_message, bot_token, recipients)
        return [], [], False, "Unknown City"

    # Add a small delay to let cookies settle
    time.sleep(2)

    api_headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': 'https://www.apple.com/shop/buy-iphone/iphone-17-pro/6.9-inch-display-512gb-deep-blue-unlocked',
        'x-skip-redirect': 'true',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0'
    }

    session.headers.update(api_headers)

    max_retries = MAX_RETRIES or 3
    retry_delay = INITIAL_RETRY_DELAY or 1

    for attempt in range(max_retries):
        try:
            response = session.get(apple_url, timeout=REQUEST_TIMEOUT or 60, allow_redirects=True)
            if response.status_code not in [503, 541]:
                break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Failed to fetch data after {max_retries} attempts. Last error: {e}")
                return [], [], False, "Unknown City"

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
        area_city = None

        # Iterate over each store in the JSON data
        for store in data['body']['content']['pickupMessage']['stores']:
            store_name = store['storeName']
            store_latitude = store['storelatitude']
            store_longitude = store['storelongitude']
            zipCode = store['address']['postalCode']
            city = store.get('city', 'Unknown City')
            storeDistanceWithUnit = store['storeDistanceWithUnit']
            distance_miles = store['storedistance']
            google_maps_link = f"{GOOGLE_MAPS_BASE_URL}{store_latitude},{store_longitude}"

            # Store the area city (assuming all stores in same ZIP have same city)
            if area_city is None:
                area_city = city

            print(f"-------------------------------------")
            print(f"> {store_name} ({zipCode})")
            print(f"")

            for part, details in store['partsAvailability'].items():
                availability = details['pickupDisplay']

                # Try to get model name from different possible locations
                model = None
                if 'messageTypes' in details:
                    if 'compact' in details['messageTypes']:
                        model = details['messageTypes']['compact']['storePickupProductTitle']
                    elif 'regular' in details['messageTypes']:
                        model = details['messageTypes']['regular']['storePickupProductTitle']

                if not model:
                    model = f"iPhone Model {part}"  # Fallback name

                model_parts = model.split(' ')
                storage = model_parts[4].lower()  # Extracting "1TB"
                color = '-'.join(model_parts[5:]).lower()  # Converting "Natural Titanium" to "natural-titanium"

                # Extract screen size from model name (e.g., "iPhone 17 Pro Max" -> "6.9" for Pro Max)
                screen_size = "6.3"  # Default for regular Pro
                if "Pro Max" in model:
                    screen_size = "6.9"
                elif "Pro" in model:
                    screen_size = "6.3"

                buy_url = f"{APPLE_BUY_BASE_URL}6.9-inch-display-{storage}-{color}-unlocked"

                availability_icon = '🚫'
                if availability == 'available':
                    availability_icon = '✅'
                    currently_available.append({
                        'model': model,
                        'store': store_name,
                        'zipCode': zipCode,
                        'city': city,
                        'distance': distance_miles,
                        'screen_size': float(screen_size),
                        'color': color,
                        'storage': storage,
                        'maps_link': google_maps_link,
                        'buy_url': buy_url
                    })

                print(f"{availability_icon} {model} @ {city} ({zipCode}) is {availability}")

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
                            'availability': availability,
                            'city': city,
                            'distance': Decimal(str(distance_miles)),
                            'screen_size': Decimal(str(screen_size)),
                            'color': color,
                            'storage': storage
                        }
                    )

                    change_message = f"📱 **{escape_markdown(model)}**\n🏪 {escape_markdown(store_name)} - {escape_markdown(city)} *({escape_markdown(zipCode)})*\n📍 [{escape_markdown(storeDistanceWithUnit)}]({google_maps_link})\n\n{availability_icon} **{availability.upper()}**\n\n🛒 [Buy Now]({buy_url})"
                    availability_changes.append(change_message)

        # Don't send individual messages - collect changes for consolidation
        had_changes = bool(availability_changes)
        if availability_changes:
            print(f"Availability changes detected for ZIP {zip_code}")
        else:
            print("No availability changes detected.")

        # Return currently available items, changes, change status, and area city for consolidation
        return currently_available, availability_changes, had_changes, area_city
    else:
        print(f"Failed to fetch the data. Status code: {response.status_code}")

        # Send Telegram notification about the HTTP error
        error_message = f"🚨 **iPhone Stock Bot Error**\n\n❌ Apple API returned error for ZIP code {zip_code}\n\n🔢 Status Code: {response.status_code}\n🌐 URL: {apple_url}\n\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n💡 This might be due to:\n• Rate limiting\n• Expired cookies\n• API changes"
        telegram_bot_sendtext(error_message, bot_token, recipients)
        return [], [], False, "Unknown City"


def telegram_bot_sendtext(bot_message, bot_token, recipients):
    MAX_MESSAGE_LENGTH = 4000  # Leave some buffer below the 4096 limit

    # If message is short enough, send as normal
    if len(bot_message) <= MAX_MESSAGE_LENGTH:
        for bot_chatID in recipients:
            send_text = TELEGRAM_API_BASE_URL + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&disable_web_page_preview=true&text=' + bot_message
            response = requests.get(send_text)
            print(response.json())
        return

    # Split long message into chunks
    chunks = []
    current_chunk = ""
    lines = bot_message.split('\n')

    for line in lines:
        # If adding this line would exceed the limit, start a new chunk
        if len(current_chunk) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                # Single line too long, truncate it
                chunks.append(line[:MAX_MESSAGE_LENGTH])
        else:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    # Send each chunk
    for i, chunk in enumerate(chunks):
        # Add chunk indicator for multi-part messages
        if len(chunks) > 1:
            chunk_header = f"**📱 iPhone Stock Alert ({i+1}/{len(chunks)})**\n\n"
            chunk = chunk_header + chunk

        for bot_chatID in recipients:
            send_text = TELEGRAM_API_BASE_URL + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&disable_web_page_preview=true&text=' + chunk
            response = requests.get(send_text)
            print(response.json())

            # Small delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(0.5)


def handler(event, context):
    import datetime
    print(f"\n=== Lambda handler started at {datetime.datetime.now()} ===")

    # Get parameters from environment variables
    bot_token = TELEGRAM_BOT_TOKEN
    recipients = TELEGRAM_CHAT_IDS.split(',') if TELEGRAM_CHAT_IDS else []

    # Process multiple ZIP codes
    zip_codes = ZIP_CODES.split(',') if ZIP_CODES else []

    if bot_token:
        print(f"Bot token received!")

    if recipients:
        print(f"Recipients: {recipients}")

    if zip_codes:
        print(f"ZIP codes to check: {zip_codes}")

        # Collect all changes and currently available items across all ZIP codes
        all_currently_available = []
        all_changes = []
        any_changes_detected = False

        # Check availability for each ZIP code
        for zip_code in zip_codes:
            zip_code = zip_code.strip()
            print(f"\n--- Checking availability for ZIP code: {zip_code} ---")

            # Construct Apple URL for this specific ZIP code
            apple_url = construct_apple_url(location=zip_code)
            print(f"Constructed Apple URL: {apple_url}")

            if apple_url:
                print("Checking iPhone stock availability")
                currently_available, availability_changes, had_changes, area_city = run(apple_url=apple_url, bot_token=bot_token, recipients=recipients, zip_code=zip_code)

                if had_changes:
                    any_changes_detected = True
                    # Add ZIP code header with city and changes
                    zip_header = f"**🚨 STOCK ALERT - {area_city} ({zip_code}) 🚨**"
                    all_changes.append(zip_header)
                    all_changes.extend(availability_changes)

                if currently_available:
                    all_currently_available.extend(currently_available)

        # Send consolidated message only if there were changes
        if bot_token and recipients and any_changes_detected:
            # Remove duplicates from available items
            unique_available = []
            seen_items = set()

            for item in all_currently_available:
                item_key = f"{item['model']}@{item['store']}@{item['city']}@{item['zipCode']}"
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    unique_available.append(item)

            # Build consolidated message
            changes_section = "\n\n---\n\n".join(all_changes)
            availability_table = generate_availability_table(unique_available)

            final_message = changes_section
            if availability_table:
                final_message += "\n\n---\n" + availability_table

            print(f"\nSending consolidated message with {len(unique_available)} unique available items:")
            print(final_message)
            telegram_bot_sendtext(final_message, bot_token, recipients)
        else:
            print("No message sent (no changes detected)")
    else:
        print("No ZIP codes configured")

    return { 'status' : 200, 'body' : 'Lambda executed successfully!' }
