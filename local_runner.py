#!/usr/bin/env python3

import os
import boto3
from lambda_function import handler

# Configure boto3 to use local DynamoDB
os.environ['AWS_ENDPOINT_URL'] = 'http://dynamodb:8000'

# Override boto3 to use local endpoint
def get_local_dynamodb():
    return boto3.resource('dynamodb',
                         endpoint_url='http://dynamodb:8000',
                         region_name='us-east-1',
                         aws_access_key_id='test',
                         aws_secret_access_key='test')

# Patch the lambda_function to use local DynamoDB
import lambda_function
lambda_function.dynamodb = get_local_dynamodb()
lambda_function.table = lambda_function.dynamodb.Table(os.getenv('DYNAMODB_TABLE_NAME'))

# Create the DynamoDB table if it doesn't exist
def create_table_if_not_exists():
    try:
        table = lambda_function.table
        table.load()
        print(f"Table {os.getenv('DYNAMODB_TABLE_NAME')} already exists")
    except table.meta.client.exceptions.ResourceNotFoundException:
        print(f"Creating table {os.getenv('DYNAMODB_TABLE_NAME')}")
        table = lambda_function.dynamodb.create_table(
            TableName=os.getenv('DYNAMODB_TABLE_NAME'),
            KeySchema=[
                {
                    'AttributeName': 'ID',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'ID',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        print(f"Table {os.getenv('DYNAMODB_TABLE_NAME')} created successfully")

if __name__ == "__main__":
    create_table_if_not_exists()

    # Run the Lambda handler
    result = handler({}, {})
    print(f"Handler result: {result}")

    # Explicit exit to ensure container terminates
    import sys
    sys.exit(0)