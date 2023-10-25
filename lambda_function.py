#!/usr/bin/python3

import requests
import time

from datetime import datetime

def run(bot_token, recipients):
    # bot_token = sys.argv[1]
    # recipients = json.loads(sys.argv[2])

    # Define the URL
    url = "https://www.apple.com/us/shop/fulfillment-messages?mts.0=regular&location=34744&parts.0=MU673LL/A&parts.2=MU6C3LL/A&parts.1=MU6D3LL/A&parts.3=MU683LL/A&parts.4=MU6G3LL/A&parts.5=MU6H3LL/A&pl=true&mts.1=compact"

    # Make a GET request to the URL
    response = requests.get(url)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Load the JSON data from the response
        data = response.json()

        # Iterate over each store in the JSON data
        for store in data['body']['content']['pickupMessage']['stores']:
            zipCode = store['address']['postalCode']

            for part, details in store['partsAvailability'].items():
                availability = details['pickupDisplay']
                model = details['messageTypes']['compact']['storePickupProductTitle']

                print(f"{model} @ {zipCode} is {availability}")

                if availability == 'available':
                    message = f"📱 {model}\n🏰 {store['storeName']} ({zipCode})\n📍 {store['storeDistanceWithUnit']}"

                    print(message)
                    telegram_bot_sendtext(message, bot_token, recipients)
    else:
        print(f"Failed to fetch the data. Status code: {response.status_code}")


def telegram_bot_sendtext(bot_message, bot_token, recipients):
    for bot_chatID in recipients:
        send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
        response = requests.get(send_text)
        print(response.json())


def handler(event, context):
    bot_token = event['bot_token']
    recipients = event['recipients']

    if bot_token:
        print(f"Bot token received!")

    if recipients:
        print(f"Recipients: {recipients}")

    print("#1 - Checking iPhone 15 availability")
    run(bot_token=bot_token,recipients=recipients)

    time.sleep(30)

    print("#2 - Checking iPhone 15 availability")
    run(bot_token=bot_token,recipients=recipients)

    return { 'status' : 200, 'body' : 'Lambda executed successfully!' }
