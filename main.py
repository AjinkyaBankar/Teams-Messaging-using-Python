import utils
import requests

tenant_id = " "
client_id = " "
client_secret = " "
username = " " 
password = " "


user_app_token = utils.get_user_app_token(tenant_id, client_id, client_secret, username, password)
print(user_app_token)

client_app_token = utils.get_client_app_token(tenant_id, client_id, client_secret)
print(client_app_token)


# Get SignedIn user data
signedin_user_data = utils.get_signedin_user_data(user_app_token)
sender_ms_teams_id = signedin_user_data["id"]
print(sender_ms_teams_id)


# Find Teams-id using email addresses
group_email = ['aaa@organization.com', 'bbb@organization.com']
other_chat_members = []
for email in group_email:
    ms_teams_user = utils.get_ms_teams_users_using_emails(client_app_token, emails=[email])
    other_chat_members.append(ms_teams_user[0]["id"])
print(other_chat_members)


# Find existing chat-id if available
existing_chat_id = utils.get_existing_chat_id_new(user_app_token, sender_ms_teams_id, other_chat_members)
print('Existing chat-id: {}'.format(existing_chat_id))

mail_body = 'Hello World!'


# Send Teams message
if len(other_chat_members) == 1:
    # Send message
    print('One on one chat')
    is_message_sent = utils.send_message_to_ms_teams_user(user_app_token, sender_ms_teams_id, other_chat_members[0], mail_body)

elif len(other_chat_members) > 1 and existing_chat_id is not None:
    print('Group chat with existing chat_id')
    is_message_sent = utils.send_message_to_existing_teams_group(user_app_token, existing_chat_id, mail_body)

elif len(other_chat_members) > 1 and existing_chat_id is None:
    print('Group chat with new chat_id')
    is_message_sent = utils.send_message_to_new_teams_group(user_app_token, sender_ms_teams_id, other_chat_members, mail_body)

if is_message_sent:
    print("Message sent")
else:
    print("Message sending Failed")