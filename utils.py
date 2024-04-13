from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import re
import requests
import json

CONTENT_TYPE = "application/json"

# User sign in token
def get_user_app_token(tenant_id, client_id, client_secret, username, password):
    """
    This function would change depending on your login method
    """
    ser = Service(executable_path='/usr/local/bin/chromedriver')
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--incognito")
    options.binary_location = '/usr/bin/google-chrome' # path to Chrome binary
    driver = webdriver.Chrome(service=ser, options=options)

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&response_mode=query&scope=user.read%20chat.read&state=12345"
    driver.get(url)
    print(driver.current_url)
    #open_tab
    time.sleep(5)

    element_id = webdriver.common.by.By.ID
    email_locator = (element_id, "i0116")
    driver.find_element(*email_locator).send_keys(username+"@crowley.com")

    next_button_locator = (element_id, "idSIButton9")
    driver.find_element(*next_button_locator).click()

    time.sleep(25)
    print(driver.current_url)

    # Assuming you are now on the Okta login page. Find and fill in the username field
    okta_username_locator = (element_id, "okta-signin-username")
    driver.find_element(*okta_username_locator).send_keys(username)

    # Click the "Next" button on the Okta page
    okta_next_button_locator = (element_id, "okta-signin-submit")
    driver.find_element(*okta_next_button_locator).click()

    time.sleep(10)
    print(driver.current_url)

    # Assuming you are now on the Okta password entry page. Find and fill in the password field
    okta_password_locator = (webdriver.common.by.By.NAME, "password")
    password_input = driver.find_element(*okta_password_locator)
    password_input.send_keys(password)

    # Find the "Verify" button using a CSS selector
    okta_verify_button_locator = (webdriver.common.by.By.CSS_SELECTOR, '.button.button-primary[type="submit"][data-type="save"]')
    verify_button = driver.find_element(*okta_verify_button_locator)

    # Click the "Verify" button on the Okta page
    verify_button.click()
    time.sleep(5)
    print(driver.current_url)

    url_pattern = 'https://www.organization.com/\?code=(?P<code>[^&]*)&state=12345.*'
    re_match = re.match(url_pattern, driver.current_url)
    code = re_match.group('code')

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    body = {'grant_type': 'authorization_code',
             'code': code,
             'client_id': client_id,
             'client_secret': client_secret}

    response = requests.post(f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",headers=headers,data = body)

    bearer_token = json.loads(response.text)['access_token']
    return bearer_token


# Client App access token
def get_client_app_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(url, data=payload, headers=headers)
        resp.raise_for_status()  # Raise an HTTPError for bad responses
        print("Authentication successful")
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
        print(resp.text)  # Print the response text for debugging
    except Exception as err:
        print(f"An error occurred: {err}")

    app_token = resp.json()["access_token"]
    return app_token


def get_headers(bearer_token):
    """This is the headers for the Microsoft Graph API calls"""
    return {
        "Accept": CONTENT_TYPE,
        "Authorization": f"Bearer {bearer_token}",
        "ConsistencyLevel": "eventual",
    }


def get_signedin_user_data(bearer_token):
    """
    Get SignedIn user data
    """

    resp = requests.get(f"https://graph.microsoft.com/v1.0/me",
                        headers=get_headers(bearer_token))

    json_resp = resp.json()
    return json_resp


def get_ms_teams_users(bearer_token, filters=""):
    """
    Get/Search MS Teams users
    """

    if filters:
        filters = f"$filter={filters}"

    url = f"https://graph.microsoft.com/beta/users?{filters}"
    resp = requests.get(url, headers=get_headers(bearer_token))
    if resp.status_code != 200:
        print(resp.json())
        return None

    json_resp = resp.json()
    try:
        return json_resp["value"]
    except KeyError as err:
        return []


def get_ms_teams_users_using_emails(bearer_token, emails=[]):
    filters = [f"mail eq '{email}'" for email in emails]
    filters = " OR ".join(filters)
    users = get_ms_teams_users(bearer_token, filters=filters)

    return users


def get_chat_members(bearer_token, chat_id):
    """
    Get chat members using HTTP request.
    """
    get_members_url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/members"
    headers = {"Authorization": f"Bearer {bearer_token}"}

    try:
        resp = requests.get(get_members_url, headers=headers)
        resp.raise_for_status()  # Raise an error for unsuccessful responses

        json_resp = resp.json()
        members = json_resp.get('value', [])

        return members

    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Request Error: {err}")

    return None


# This method checks all the pages of the json_resp object. Since it searches entire history, there wont be problem of new chat-id creation for the same user group
def get_existing_chat_id_new(bearer_token, sender_ms_teams_id, other_members):
    """
    Get the chat ID of an existing group chat based on participants.
    """

    get_chats_url = "https://graph.microsoft.com/v1.0/me/chats"
    headers = get_headers(bearer_token)
    
    while get_chats_url:
        resp = requests.get(get_chats_url, headers=headers)
        json_resp = resp.json()

        if resp.status_code != 200:
            return None
        
        #------------------------------------------------------------#
        for chat in json_resp.get('value', []):
            # print(chat['id'])
        
            chat_id = chat['id']
            chat_members = get_chat_members(bearer_token, chat_id)
            member_ids = []
            for member_id in chat_members:
                member_ids.append(member_id['userId'])
            # print(member_ids)  
            # print('\n')

            # Check if all required members are present in the chat
            combined_ids = [sender_ms_teams_id] + other_members
            if set(member_ids) == set(combined_ids) and len(member_ids) == len(combined_ids):
                return chat_id
        #------------------------------------------------------------#
        
        # Check if there's another page of results
        next_link = json_resp.get('@odata.nextLink')
        get_chats_url = next_link  # Set the URL for the next page if available

    return None


def send_message_to_new_teams_group(bearer_token, sender_ms_teams_id, other_chat_members, message):
    """
    Send Message to MS Teams user is done in 2 steps:
        1: Create chat
        2: Use chat-id created in 1st step and send message to the user.
    """
    # 1st step: Create chat
    creat_chat_url = "https://graph.microsoft.com/v1.0/chats"
    
    team_ids = other_chat_members + [sender_ms_teams_id]
    members_data = []  
    for team_id in team_ids:
        member_data = {
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "roles": ["owner"],
            "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{team_id}')",
        }
        members_data.append(member_data)

    data = {
        "chatType": "group",
        "members": members_data,
       }

    resp = requests.post(creat_chat_url, headers=get_headers(bearer_token), json=data)
    json_resp = resp.json()
    if resp.status_code not in [200, 201]:
        return False

    # 2nd step: Use created chat-id and send message to it.
    chat_id = json_resp["id"] 
    
    send_message_url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
    messsage_data = {"body": {"contentType": "html", "content": message}}
    resp = requests.post(send_message_url, headers=get_headers(bearer_token), json=messsage_data)
    json_resp = resp.json()
    if resp.status_code not in [200, 201]:
        return False

    return True


def send_message_to_existing_teams_group(bearer_token, chat_id, message):
    """
    Send Message to existing MS Teams chat-id 
    """
    send_message_url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
    messsage_data = {"body": {"contentType": "html", "content": message}}
    resp = requests.post(send_message_url, headers=get_headers(bearer_token), json=messsage_data)
    json_resp = resp.json()
    if resp.status_code not in [200, 201]:
        return False

    return True


def send_message_to_ms_teams_user(bearer_token, sender_ms_team_id, user_ms_teams_id, message):
    """
    Send Message to MS Teams user is done in 2 steps:
        1: Create chat
        2: Use chat-id created in 1st step and send message to the user.
    """
    # 1st step: Create chat
    creat_chat_url = "https://graph.microsoft.com/v1.0/chats"
    data = {
        "chatType": "OneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_ms_teams_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{sender_ms_team_id}')",
            },
        ],
    }

    resp = requests.post(
        creat_chat_url, headers=get_headers(bearer_token), json=data)
    json_resp = resp.json()
    if resp.status_code not in [200, 201]:
        return False

    # 2nd step: Use created chat-id and send message to it.
    chat_id = json_resp["id"]
    send_message_url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"

    messsage_data = {"body": {"contentType": "html", "content": message}}
    resp = requests.post(send_message_url, headers=get_headers(
        bearer_token), json=messsage_data)
    json_resp = resp.json()
    if resp.status_code not in [200, 201]:
        return False

    return True