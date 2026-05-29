"""Embedded cfnresponse module.

CloudFormation only ships cfnresponse for inline Lambda code. CDK uses
Code.from_asset, so we embed our own copy and import it from each
custom-resource Lambda.
"""

import json
import urllib3

SUCCESS = "SUCCESS"
FAILED = "FAILED"


def send(event, context, response_status, response_data=None, physical_resource_id=None, reason=None):
    response_body = json.dumps(
        {
            "Status": response_status,
            "Reason": reason
            or f"See CloudWatch Log Stream: {context.log_stream_name}",
            "PhysicalResourceId": physical_resource_id or context.log_stream_name,
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
            "Data": response_data or {},
        }
    )

    headers = {"content-type": "", "content-length": str(len(response_body))}
    http = urllib3.PoolManager()
    http.request("PUT", event["ResponseURL"], headers=headers, body=response_body)
