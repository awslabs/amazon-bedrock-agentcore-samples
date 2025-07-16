"""
DynamoDB models for Device Management Lambda
"""
import boto3
import os
import uuid
import datetime
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json

# Configure DynamoDB connection
# Always use AWS DynamoDB in us-west-2
aws_region = 'us-west-2'

# Initialize DynamoDB resource
def get_dynamodb_resource():
    """Get DynamoDB resource based on environment"""
    return boto3.resource('dynamodb', region_name=aws_region)

# Define table names
DEVICES_TABLE = 'Devices'
DEVICE_SETTINGS_TABLE = 'DeviceSettings'
WIFI_NETWORKS_TABLE = 'WifiNetworks'
USERS_TABLE = 'Users'
USER_ACTIVITIES_TABLE = 'UserActivities'

# Helper function to convert datetime to ISO format string
def datetime_to_iso(dt):
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt

# Helper function to handle decimal serialization for DynamoDB
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def json_dumps(obj):
    return json.dumps(obj, cls=DecimalEncoder)

# Table creation functions
def create_devices_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=DEVICES_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'}  # Partition key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_device_settings_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=DEVICE_SETTINGS_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'setting_key', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'},
            {'AttributeName': 'setting_key', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_wifi_networks_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=WIFI_NETWORKS_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'network_id', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'},
            {'AttributeName': 'network_id', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_users_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=USERS_TABLE,
        KeySchema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'}  # Partition key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'username', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'EmailIndex',
                'KeySchema': [
                    {'AttributeName': 'email', 'KeyType': 'HASH'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            },
            {
                'IndexName': 'UsernameIndex',
                'KeySchema': [
                    {'AttributeName': 'username', 'KeyType': 'HASH'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_user_activities_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=USER_ACTIVITIES_TABLE,
        KeySchema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
            {'AttributeName': 'activity_type', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'ActivityTypeIndex',
                'KeySchema': [
                    {'AttributeName': 'activity_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

# Initialize all tables
def init_db():
    """Initialize DynamoDB tables if they don't exist"""
    try:
        dynamodb = get_dynamodb_resource()
        # Check if tables exist
        existing_tables = [table.name for table in dynamodb.tables.all()]
        
        tables_to_create = [
            (DEVICES_TABLE, create_devices_table),
            (DEVICE_SETTINGS_TABLE, create_device_settings_table),
            (WIFI_NETWORKS_TABLE, create_wifi_networks_table),
            (USERS_TABLE, create_users_table),
            (USER_ACTIVITIES_TABLE, create_user_activities_table)
        ]
        
        created_tables = []
        for table_name, create_func in tables_to_create:
            if table_name not in existing_tables:
                table = create_func()
                print(f"Creating table {table_name}...")
                table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
                created_tables.append(table_name)
        
        if created_tables:
            print(f"Created tables: {', '.join(created_tables)}")
        else:
            print("All tables already exist")
            
        return True
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        return False

if __name__ == "__main__":
    init_db()
    print("DynamoDB tables initialized successfully.")
