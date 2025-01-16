# AWS Server Manager for Slack

## Overview
This AWS Lambda function manages EC2 instances using Slack commands. It integrates with AWS services like EC2 and S3 and supports Slack webhook notifications.
Features

## Slack Integration:

•	Interact with EC2 instances via Slack commands.

•	Authenticate Slack requests using a signing key.

•	Send formatted responses to Slack channels.
## AWS EC2 Management:

•	Start, stop, and fetch the status of EC2 instances.

•	Manage a retained list of servers stored in S3.

## Automated Shutdown:

•	Periodic shutdowns, skipping retained instances.

•	Notifications sent to Slack after processing.

### Installation

#AWS Setup:
  1.	Create an IAM role with permissions for EC2, S3, and Lambda.
  2.	Attach the role to your Lambda function.

## Environment Variables:

Set the following variables in your Lambda environment:

•	SIGNING_KEY: Slack signing key for authentication.

•	S3_BUCKET_NAME: S3 bucket to store retained server data.

## Slack Webhook:
1.	Create an incoming webhook in Slack.
2.	Update the webhook_path in send_slack_message with your webhook URL.

## Slack Commands
#se the following commands in Slack to manage your servers:
### Command	Description

/command status <alias>	Fetch the current status of a server.
/command start <alias>	Start a specific server.
/command stop <alias>	Stop a specific server.
/command list	List all servers and their statuses.
/command list retain	List all retained servers.
/command retain <alias>	Retain a server (prevent automated shutdown).
/command drop <alias>	Remove a server from the retained list.

### Functionality
#### Command Flow:
1.	Parse Slack command input.
2.	Authenticate Slack token.
3.	Execute actions like start/stop/status.
4.	Send responses back to Slack.

## Scheduled Shutdown:
•	Runs on a cron schedule to stop all instances except retained ones.

•	Sends a summary report to Slack.

## File Structure

##### File/Module	Purpose

##### lambda_handler	Entry point for handling events.

##### start_instance	Starts an EC2 instance.

##### stop_instance	Stops an EC2 instance.

##### read_retained_list	Reads the retained list from S3.

##### write_retained_list	Writes the retained list to S3.

##### cron_shutdown_handler	Handles scheduled shutdown tasks.

##### send_slack_message	Sends notifications to Slack using webhooks.


## Deployment
1.	Upload the code to your Lambda function, add the environment variables.
2.	Test the Lambda function with sample events.

## Usage Examples
## Slack Commands:
•	Start a server: /command start devbox

•	Stop a server: /command stop devbox

•	Check server status: /command status devbox

•	List all servers: /command list

•	Retain a server: /command retain devbox

## Cron-Based Shutdown: 
•	Scheduled a Event Brdige's cron-job to run periodically to stop non-retained servers.

•	Automatically sends a report to Slack.

## Contributions
Feel free to fork the repository and submit pull requests. Please ensure your code adheres to the guidelines provided in the CONTRIBUTING.md file.

##### License
This project is licensed under the MIT License.

# Additional Notes
•	Ensure all environment variables are securely stored and managed.

•	Test thoroughly in a staging environment before deploying to production.

