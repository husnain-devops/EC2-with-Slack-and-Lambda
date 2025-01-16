import json
import boto3
import base64
import urllib.parse
import os
from datetime import datetime
import http.client


region = 'eu-north-1' # Specify the region
ec2 = boto3.client('ec2', region_name=region)
VALID_SLACK_TOKEN = os.environ['SIGNING_KEY']  # Set this in the Lambda environment variables
S3_BUCKET = os.environ['S3_BUCKET_NAME']  # Set this in the Lambda environment variables
S3_KEY = 'retained_servers.json'  # File name for the retained list in the S3 bucket
s3 = boto3.client('s3', region_name=region)


aliases = {'name': 'instance-id'} # Replace with the actual instance ID for the devbox  # Add more aliases as needed 

def lambda_handler(event, context):

    if event.get("source") == "aws.events":
        return cron_shutdown_handler(event, context)
    print("Received event: " + json.dumps(event))
    body = event['body']
    decoded_body = base64.b64decode(body).decode('utf-8')
    parsed_body = urllib.parse.parse_qs(decoded_body)
    slack_token = parsed_body.get('token', [''])[0]
    if slack_token != VALID_SLACK_TOKEN:
        return {
            'statusCode': 403,
            'body': json.dumps('Error: Invalid Slack token.')
        }
    command = parsed_body.get('command', [''])[0]
    user_name = parsed_body.get('user_name', [''])[0]
    text = parsed_body.get('text', [''])[0] if 'text' in parsed_body else ''  # Check if 'text' exists
    action_parts = text.split()
    action = action_parts[0].lower()

    if action == 'list' and len(action_parts) == 1:
        server_statuses = ["\n"]
        for alias, instance_id in aliases.items():
            try:
                # Retrieve instance status
                response = ec2.describe_instances(InstanceIds=[instance_id])
                instance_status = response['Reservations'][0]['Instances'][0]['State']['Name']
                server_statuses.append(f"*{alias}* -status: *{instance_status}*\n")
            except Exception as e:
                error_code = e.response['Error']['Code']
                server_statuses.append(f"{alias} - Error retrieving status - {error_code}")
        response_message = "Available servers with their current status: " + "\n".join(server_statuses)
        return create_response(200, response_message)

    
    elif action == 'list' and len(action_parts) > 1 and action_parts[1].lower() == 'retain':
        retained = read_retained_list()
        if not retained:
            response_message = "No servers are currently retained."
        else:
            retained_servers = ["\n"]
            for alias, instance_id in retained.items():
                retained_servers.append(f"*{alias}*\n")
            response_message = "Currently retained servers:" + "\n".join(retained_servers)
        return create_response(200, response_message)

    elif action == 'drop' and len(action_parts) > 1:
        alias_to_drop = action_parts[1].strip()
        retained = read_retained_list()
        if alias_to_drop not in retained:
            response_message = f"Error: Server *{alias_to_drop}* is not in the retained list."
        else:
            del retained[alias_to_drop]
            write_retained_list(retained)
            response_message = f"Successfully dropped server *{alias_to_drop}* from the retained list."
        return create_response(200, response_message)


    # Set the instance ID
    instance_id_name = action_parts[1].strip() if len(action_parts) > 1 else user_name
    instance_id = aliases.get(instance_id_name)

    if instance_id is None:
        return create_response(400, f"Error: No instance ID found for user '{user_name}'.")

    try:
        # Retrieve instance status
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance_status = response['Reservations'][0]['Instances'][0]['State']['Name']
        
        # Process commands
        if action == 'status':
            response_message = f'Dev server {instance_id_name} is currently {instance_status}'

        elif action == 'start':
            response_message = start_instance(instance_id, instance_id_name, instance_status)

        elif action == 'stop':
            response_message = stop_instance(instance_id, instance_id_name, instance_status)

        elif action == 'retain':
            # Read the retained list from the S3 bucket
            retained = read_retained_list()
            # Check if the instance is already retained
            if instance_id_name in retained:
                response_message = f"Server *{instance_id_name}* is already retained."
            else:
                # Add the new instance to the retained list
                retained[instance_id_name] = instance_id
                write_retained_list(retained)
                response_message = f"Successfully retained server *{instance_id_name}*."

        else:
            response_message = 'Error: Invalid command. Use start, stop, status, list, retain, drop or list retain.'

    except Exception as e:
        response_message = f'Error: {str(e)}'
        
    return create_response(200, response_message)


def start_instance(instance_id, instance_id_name, instance_status):
    if instance_status == 'running':
        return f'Dev server {instance_id_name} is already running.'
    else:
        ec2.start_instances(InstanceIds=[instance_id])
        return f'Successfully started dev server {instance_id_name}'


def stop_instance(instance_id, instance_id_name, instance_status):
    if instance_status in ['stopped', 'stopping']:
        return f'Dev server {instance_id_name} is already {instance_status}.'
    else:
        ec2.stop_instances(InstanceIds=[instance_id])
        return f'Successfully stopped dev server {instance_id_name}'


def read_retained_list():
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        retained = json.loads(response['Body'].read().decode('utf-8'))
        print(f"Retained list loaded from S3: {retained}")
        return retained
    except s3.exceptions.NoSuchKey:
        print("No retained list found in S3. Initializing an empty list.")
        return {}  # Return empty dictionary if no file exists


def write_retained_list(retained):
    try:
        s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=json.dumps(retained))
        print(f"Retained list saved to S3: {retained}")
    except Exception as e:
        print(f"Error writing retained list to S3: {e}")


def delete_retained_list():
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=S3_KEY)
        print("Retained list cleared from S3.")
    except Exception as e:
        print(f"Error deleting retained list from S3: {e}")


def cron_shutdown_handler(event, context):
    try:
        retained = read_retained_list()  # Load retained instances
        shutdown_messages = []

        # Iterate over aliases and handle shutdown
        for alias, instance_id in aliases.items():
            if alias in retained:
                shutdown_messages.append(f"Server *{alias}* is retained and will not be shut down.")
                continue  # Skip retained servers

            # Describe the instance to get its current state
            try:
                response = ec2.describe_instances(InstanceIds=[instance_id])
                instance_status = response['Reservations'][0]['Instances'][0]['State']['Name']

                # Stop the instance if it is running
                if instance_status == 'running':
                    ec2.stop_instances(InstanceIds=[instance_id])
                    shutdown_messages.append(f"Successfully stopped server *{alias}*.")
                else:
                    shutdown_messages.append(f"Server *{alias}* is already {instance_status}.")
            except Exception as e:
                shutdown_messages.append(f"Error checking or stopping server *{alias}*: {str(e)}")

        # Clear the retained list after processing
        delete_retained_list()

        # Prepare the shutdown summary
        summary_message = "\n".join(shutdown_messages)
        print("Cron job completed: Shutdown process executed.")

        # Send notification to Slack
        send_slack_message("Shceduled Shutdown", summary_message)
        #return shutdown_messages  # Return the messages for logging or further processing
        return create_response(200, summary_message)
    except Exception as e:
        error_message = f"Error during cron job shutdown: {e}"
        print(error_message)

        # Send error notification to Slack

        send_slack_message("Cron Job Error", error_message)

        return create_response(500, error_message)
    
def send_slack_message(title, message):
    """Send a formatted message to Slack."""
    try:
        webhook_url = "hooks.slack.com"
        webhook_path = "/services/TMP8TGHPU/B08376V5NQK/lvOE6ZjF0ueZEFIGwOqboGqy" # Your Slack webhook URL
        # Construct the payload
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }

        # Create a connection
        connection = http.client.HTTPSConnection(webhook_url)

        # Send the POST request
        headers = {"Content-Type": "application/json"}
        connection.request("POST", webhook_path, body=json.dumps(payload), headers=headers)

        # Get the response
        response = connection.getresponse()
        if response.status == 200:
            print("Message sent successfully!")
        else:
            print(f"Failed to send message. Status: {response.status}, Reason: {response.reason}")
        connection.close()
    except Exception as e:
        print(f"Error occurred: {e}")

def retain_server(alias, instance_id):
    retained = read_retained_list()
    retained[alias] = instance_id
    write_retained_list(retained)
    return f"Successfully retained server *{alias}*."

def create_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            "response_type": "in_channel",
            "text": message,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        })
    }