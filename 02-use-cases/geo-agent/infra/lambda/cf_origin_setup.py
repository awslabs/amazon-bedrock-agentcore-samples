"""CloudFormation Custom Resource: configures an existing Amazon CloudFront distribution for GEO.

On Create/Update:
  - Adds a geo-lambda-origin pointing to the AWS Lambda Function URL
  - Attaches OAC for SigV4 signing
  - Associates the CloudFront Function with the specified cache behavior
  - Adds x-origin-verify custom header for defense-in-depth

On Delete:
  - Removes the GEO origin and CloudFront Function association

Properties (from CloudFormation):
  DistributionId: Amazon CloudFront distribution ID
  FunctionUrlDomain: AWS Lambda Function URL domain (without https://)
  OacId: Origin Access Control ID
  OriginVerifySecret: Shared secret for x-origin-verify header
  CffArn: ARN of the CloudFront Function to associate
  BehaviorPath: Cache behavior path pattern ("*" = default behavior)
"""

import json
import boto3
from urllib.parse import urlparse
from urllib.request import urlopen, Request as UrlRequest

cf = boto3.client("cloudfront")

_ALLOWED_RESPONSE_URL_SUFFIXES = [
    ".s3.amazonaws.com",
    ".s3-external-1.amazonaws.com",
    ".s3.us-east-1.amazonaws.com",
]


def _send_cfn_response(event, context, status, data=None):
    """Send a response to CloudFormation for the Custom Resource lifecycle.

    Validates that ResponseURL points to an Amazon S3 pre-signed URL
    (the only legitimate destination for CloudFormation Custom Resource responses)
    to prevent server-side request forgery.
    """
    response_url = event["ResponseURL"]
    parsed = urlparse(response_url)
    if parsed.scheme != "https" or not any(
        parsed.hostname.endswith(suffix) for suffix in _ALLOWED_RESPONSE_URL_SUFFIXES
    ):
        raise ValueError(f"Untrusted ResponseURL hostname: {parsed.hostname}")

    body = json.dumps({
        "Status": status,
        "Reason": f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    })
    req = UrlRequest(response_url, data=body.encode("utf-8"), method="PUT")
    req.add_header("Content-Type", "")
    req.add_header("Content-Length", str(len(body)))
    urlopen(req, timeout=10)


def handler(event, context):
    """Handle CloudFormation Custom Resource Create/Update/Delete events."""
    try:
        props = event["ResourceProperties"]
        dist_id = props["DistributionId"]
        request_type = event["RequestType"]

        if request_type == "Delete":
            _remove_origin(dist_id)
            _send_cfn_response(event, context, "SUCCESS", {})
            return

        # Create or Update
        func_url_domain = props["FunctionUrlDomain"]
        oac_id = props["OacId"]
        verify_secret = props.get("OriginVerifySecret", "")
        cff_arn = props.get("CffArn", "")
        behavior_path = props.get("BehaviorPath", "*")

        _add_origin(dist_id, func_url_domain, oac_id, verify_secret, cff_arn, behavior_path)
        _send_cfn_response(event, context, "SUCCESS", {
            "DistributionId": dist_id,
            "OriginId": "geo-lambda-origin",
        })
    except Exception as e:
        print(f"Error: {e}")
        _send_cfn_response(event, context, "FAILED", {"Error": str(e)})


ORIGIN_ID = "geo-lambda-origin"


def _get_dist_config(dist_id):
    """Fetch the current distribution config and ETag."""
    resp = cf.get_distribution_config(Id=dist_id)
    return resp["ETag"], resp["DistributionConfig"]


def _add_origin(dist_id, func_url_domain, oac_id, verify_secret, cff_arn, behavior_path):
    """Add the GEO Lambda origin with OAC to the distribution."""
    etag, config = _get_dist_config(dist_id)

    config["Origins"]["Items"] = [
        o for o in config["Origins"]["Items"] if o["Id"] != ORIGIN_ID
    ]

    new_origin = {
        "Id": ORIGIN_ID,
        "DomainName": func_url_domain,
        "OriginPath": "",
        "CustomHeaders": {"Quantity": 0, "Items": []},
        "CustomOriginConfig": {
            "HTTPPort": 80,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "https-only",
            "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
            "OriginReadTimeout": 60,
            "OriginKeepaliveTimeout": 5,
        },
        "ConnectionAttempts": 3,
        "ConnectionTimeout": 10,
        "OriginAccessControlId": oac_id,
        "OriginShield": {"Enabled": False},
    }

    if verify_secret:
        new_origin["CustomHeaders"] = {
            "Quantity": 1,
            "Items": [{"HeaderName": "x-origin-verify", "HeaderValue": verify_secret}],
        }

    config["Origins"]["Items"].append(new_origin)
    config["Origins"]["Quantity"] = len(config["Origins"]["Items"])

    if cff_arn:
        _attach_cff(config, cff_arn, behavior_path)

    cf.update_distribution(Id=dist_id, IfMatch=etag, DistributionConfig=config)
    print(f"Added origin {ORIGIN_ID} to distribution {dist_id}")


def _remove_origin(dist_id):
    """Remove the GEO Lambda origin and CloudFront Function association from the distribution."""
    etag, config = _get_dist_config(dist_id)

    original_count = len(config["Origins"]["Items"])
    config["Origins"]["Items"] = [
        o for o in config["Origins"]["Items"] if o["Id"] != ORIGIN_ID
    ]
    config["Origins"]["Quantity"] = len(config["Origins"]["Items"])

    if len(config["Origins"]["Items"]) == original_count:
        print(f"Origin {ORIGIN_ID} not found in distribution {dist_id}, skipping")
        return

    # Remove CFF association
    _detach_cff(config)

    cf.update_distribution(Id=dist_id, IfMatch=etag, DistributionConfig=config)
    print(f"Removed origin {ORIGIN_ID} from distribution {dist_id}")


def _attach_cff(config, cff_arn, behavior_path):
    """Attach a CloudFront Function to the specified cache behavior."""
    if behavior_path == "*":
        behavior = config["DefaultCacheBehavior"]
    else:
        # Find matching cache behavior
        behaviors = config.get("CacheBehaviors", {}).get("Items", [])
        behavior = next((b for b in behaviors if b["PathPattern"] == behavior_path), None)
        if not behavior:
            print(f"Behavior '{behavior_path}' not found, attaching to default")
            behavior = config["DefaultCacheBehavior"]

    fa = behavior.get("FunctionAssociations", {"Quantity": 0, "Items": []})
    items = fa.get("Items", [])
    items = [i for i in items if i["EventType"] != "viewer-request"]

    items.append({"FunctionARN": cff_arn, "EventType": "viewer-request"})
    behavior["FunctionAssociations"] = {"Quantity": len(items), "Items": items}


def _detach_cff(config):
    """Remove the viewer-request CloudFront Function from the default behavior."""
    behavior = config["DefaultCacheBehavior"]
    fa = behavior.get("FunctionAssociations", {"Quantity": 0, "Items": []})
    items = fa.get("Items", [])
    items = [i for i in items if i["EventType"] != "viewer-request"]
    behavior["FunctionAssociations"] = {"Quantity": len(items), "Items": items}
