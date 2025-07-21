"""
Test script for the Device Management Lambda function
"""
import json
from lambda_function import lambda_handler

def test_list_devices():
    """Test the list_devices tool"""
    event = {
        "action_name": "list_devices",
        "limit": 10
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_get_device_settings():
    """Test the get_device_settings tool"""
    event = {
        "action_name": "get_device_settings",
        "device_id": "DG-100001"
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_list_wifi_networks():
    """Test the list_wifi_networks tool"""
    event = {
        "action_name": "list_wifi_networks",
        "device_id": "DG-100001"
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_list_users():
    """Test the list_users tool"""
    event = {
        "action_name": "list_users",
        "limit": 5
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_query_user_activity():
    """Test the query_user_activity tool"""
    event = {
        "action_name": "query_user_activity",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-12-31T23:59:59",
        "limit": 5
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_update_wifi_ssid():
    """Test the update_wifi_ssid tool"""
    event = {
        "action_name": "update_wifi_ssid",
        "device_id": "DG-100001",
        "network_id": "wifi_1",
        "ssid": "New-Office-Network"
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_update_wifi_security():
    """Test the update_wifi_security tool"""
    event = {
        "action_name": "update_wifi_security",
        "device_id": "DG-100001",
        "network_id": "wifi_1",
        "security_type": "wpa3-psk"
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

def test_invalid_tool():
    """Test an invalid tool name"""
    event = {
        "action_name": "invalid_tool"
    }
    
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response Body: {json.dumps(json.loads(response['body']), indent=2)}")

if __name__ == "__main__":
    print("Testing Device Management Lambda Function")
    print("\n1. Testing list_devices:")
    test_list_devices()
    
    print("\n2. Testing get_device_settings:")
    test_get_device_settings()
    
    print("\n3. Testing list_wifi_networks:")
    test_list_wifi_networks()
    
    print("\n4. Testing list_users:")
    test_list_users()
    
    print("\n5. Testing query_user_activity:")
    test_query_user_activity()
    
    print("\n6. Testing update_wifi_ssid:")
    test_update_wifi_ssid()
    
    print("\n7. Testing update_wifi_security:")
    test_update_wifi_security()
    
    print("\n8. Testing invalid tool:")
    test_invalid_tool()
