import requests
import time
import json
from datetime import datetime, timedelta
import apprise


# refresh token, obtain it using https://github.com/adriankumpf/tesla_auth
refresh_token = "<Refresh Token>"
# Reservation number, starts with RN
reservation_number = "<Reservation Number>"
# Check interval in seconds (10 minutes)
interval = 600
# Notification via apprise, Set to false if unsure
wantnotification = False
# Apprise string (see https://github.com/caronc/apprise)
apprisestr = "tgram://<BotToken>/<ChatId>/"


### Do not change anything below unless you know what you're doing
# Token expiry time (8 hours)
token_expiry = datetime.now() + timedelta(hours=8)

headers = {
    "accept": "*/*",
    "x-tesla-user-agent": "TeslaApp/4.28.2-2157",
    "charset": "utf-8",
    "cache-control": "no-cache",
    "accept-language": "en",
    "authorization": "Bearer",
    "Connection": "Keep-Alive",
    "User-Agent": "okhttp/4.10.0",
}

params = {
    "deviceLanguage": "en",
    "deviceCountry": "US",
    "referenceNumber": reservation_number,
    "appVersion": "4.28.2-2157",
}


def refresh_access_token():
    payload = json.dumps(
        {
            "grant_type": "refresh_token",
            "client_id": "ownerapi",
            "refresh_token": refresh_token,
            "scope": "openid email offline_access",
        }
    )
    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request(
        "POST", "https://auth.tesla.com/oauth2/v3/token", headers=headers, data=payload
    )
    if response.status_code != 200:
        print(
            f"[!] Something went wrong refreshing the access token, is the refresh token correct? {response.text}"
        )
    print(f"Succesfully refreshed token")
    return response.json()["access_token"], response.json()["refresh_token"]


def fetch_data(acces_token):
    headers["authorization"] = f"Bearer {access_token}"
    response = requests.get(
        "https://akamai-apigateway-vfx.tesla.com/tasks", params=params, headers=headers
    )
    if response.status_code != 200:
        print(f"[!] Something went wrong: {response.status_code}, {response.text}")
    else:
        return response.json()


# Notify using Apprise
def notify(message):
    apobj = apprise.Apprise()
    # Initialize apprise from config up in the file
    apobj.add(apprisestr)
    # Send notification
    apobj.notify(title="Something changed in your tesla status", body=message)


# Save data to file
def savedata(new_data):
    with open('lastdata.txt', 'w') as file:
                json.dump(new_data, file, indent=4)

# Function to compare JSON data
def compare_data(old_data, new_data, parent_key=""):
    
    for key, value in old_data.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if key in new_data:
            if isinstance(value, dict) and isinstance(new_data[key], dict):
                # Recursive call for nested dictionaries
                compare_data(
                    value, new_data[key], parent_key=full_key
                )
            elif new_data[key] != value:
                message = (
                    f"'{full_key}': old value: '{value}' new value: '{new_data[key]}'"
                )
                print(message)
                if wantnotification:
                    notify(message)


# Debug notification
# notify("test")

# Set access token for the first time
access_token, refresh_token = refresh_access_token()
# Try to load initial data from lastdata.txt
try:
    with open('lastdata.txt', 'r') as file:
        print("[i] Continuing from last session")
        previous_data = json.load(file)
except FileNotFoundError:
    print("[!] No previous data found, doing intial call and saving")
    previous_data = fetch_data(access_token)  # Fetch new data if file doesn't exist
    savedata(previous_data)
    print(json.dumps(previous_data, indent=4))

# uncomment if you want to print initial values
print(json.dumps(previous_data, indent=4))

while True:
    try:
        # Check if the token is about to expire
        if datetime.now() >= token_expiry - timedelta(minutes=20):
            access_token, refresh_token = refresh_access_token(refresh_token)
            token_expiry = datetime.now() + timedelta(hours=8)
            print("Token refreshed")

        # Make the API request
        new_data = fetch_data(access_token)
        print(f"{datetime.now()} - Checking for differences")
        compare_data(previous_data, new_data)
        previous_data = new_data

        # Overwrite lastdata.txt with new data
        with open('lastdata.txt', 'w') as file:
            json.dump(new_data, file, indent=4)

        # Sleep for a while before the next request
        time.sleep(interval)

    except Exception as e:
        print(f"An error occurred: {e}")
        # Optional: delay before continuing
        time.sleep(600)
