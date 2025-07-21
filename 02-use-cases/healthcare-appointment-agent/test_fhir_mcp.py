from dotenv import load_dotenv
import requests
import argparse
import utils

load_dotenv()

#setting parameters
parser = argparse.ArgumentParser(
                    prog='test_fhir_mcp',
                    description='Test MCP gateway for FHIR tools',
                    epilog='Input Parameters')

parser.add_argument('--gateway_id', help = "Gateway Id")

#create boto3 session and client
(boto_session, agentcore_client) = utils.create_agentcore_client()

def list_gateway_tools(gateway_endpoint, jwt_token):
    requestBody = {
        "jsonrpc": "2.0",
        "id": 24,
        "method": "tools/list",
        "params": {}
    }

    response = requests.post(
        gateway_endpoint,
        json=requestBody,
        headers={'Authorization': f'Bearer {jwt_token}', 'Content-Type': 'application/json'},
        #verify=False
    )

    # Print the status code for confirmation
    print(f"Status Code: {response.status_code}")

    # Access and print all response headers
    print("\nResponse Headers:")
    for header, value in response.headers.items():
        print(f"{header}: {value}")

    return response.json()

def invoke_gateway_tool(gateway_endpoint, jwt_token, tool_params):
    print(f"Invoking tool {tool_params['name']}")

    requestBody = {
        "jsonrpc": "2.0",
        "id": 24,
        "method": "tools/call",
        "params": tool_params
    }

    response = requests.post(
        gateway_endpoint,
        json=requestBody,
        headers={'Authorization': f'Bearer {jwt_token}', 'Content-Type': 'application/json'},
        #verify=False
    )

    # Print the status code for confirmation
    print(f"Status Code: {response.status_code}")

    # Access and print all response headers
    print("\nResponse Headers:")
    for header, value in response.headers.items():
        print(f"{header}: {value}")

    return response.json()

if __name__ == "__main__":
    args = parser.parse_args()

    #Validations
    if args.gateway_id is None:
        raise Exception("Gateway Id is required")

    gatewayEndpoint=utils.get_gateway_endpoint(agentcore_client=agentcore_client, gateway_id=args.gateway_id)
    print(f"Gateway Endpoint: {gatewayEndpoint}")

    jwtToken = utils.get_oath_token()
    print(f"Token refreshed")

    toolResp = list_gateway_tools(gateway_endpoint=gatewayEndpoint, jwt_token=jwtToken)
    print(toolResp)

    if 'result' in toolResp:
        if 'tools' in toolResp['result']:
            for tool in toolResp['result']['tools']:
                if 'searchPatients' in tool['name']:
                    ##Search patients
                    toolParams = {
                        "name": tool['name'],
                        "arguments": {
                            "address_state": "MA"
                        }
                    }
                    toolResp = invoke_gateway_tool(gateway_endpoint=gatewayEndpoint, jwt_token=jwtToken, tool_params=toolParams)
                    print(toolResp)
                elif  'getPatient' in tool['name']:
                    ##Get patients
                    toolParams = {
                        "name": tool['name'],
                        "arguments": {
                            "patient_id": "pediatric-patient-001"
                        }
                    }
                    toolResp = invoke_gateway_tool(gateway_endpoint=gatewayEndpoint, jwt_token=jwtToken, tool_params=toolParams)
                    print(toolResp)
                elif 'x-amz' in tool['name'] and '-search' in tool['name']:
                    ##Search tools
                    toolParams = {
                        "name": tool['name'],
                        "arguments": {
                            "query": "find tool for getting a patient record"
                        }
                    }
                    toolResp = invoke_gateway_tool(gateway_endpoint=gatewayEndpoint, jwt_token=jwtToken, tool_params=toolParams)
                    print(toolResp)
                else:
                    ##Other tools (if any)
                    toolParams = {
                        "name": tool['name']
                    }
                    toolResp = invoke_gateway_tool(gateway_endpoint=gatewayEndpoint, jwt_token=jwtToken, tool_params=toolParams)
                    print(toolResp)
