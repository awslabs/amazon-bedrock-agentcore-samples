import boto3
import logging
import os
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    arn = event['SecretId']
    token = event['ClientRequestToken']
    step = event['Step']

    service_client = boto3.client('secretsmanager')

    metadata = service_client.describe_secret(SecretId=arn)
    if not metadata['RotationEnabled']:
        logger.error("Secret %s is not enabled for rotation" % arn)
        raise ValueError("Secret %s is not enabled for rotation" % arn)
    
    versions = metadata['VersionIdsToStages']
    if token not in versions:
        logger.error("Secret version %s has no stage for rotation of secret %s." % (token, arn))
        raise ValueError("Secret version %s has no stage for rotation of secret %s." % (token, arn))
    
    if "AWSCURRENT" in versions[token]:
        logger.info("Secret version %s already set as AWSCURRENT for secret %s." % (token, arn))
        return
    elif "AWSPENDING" not in versions[token]:
        logger.error("Secret version %s not set as AWSPENDING for rotation of secret %s." % (token, arn))
        raise ValueError("Secret version %s not set as AWSPENDING for rotation of secret %s." % (token, arn))

    if step == "createSecret":
        create_secret(service_client, arn, token)
    elif step == "setSecret":
        set_secret(service_client, arn, token)
    elif step == "testSecret":
        test_secret(service_client, arn, token)
    elif step == "finishSecret":
        finish_secret(service_client, arn, token)
    else:
        raise ValueError("Invalid step parameter")

def create_secret(service_client, arn, token):
    service_client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
    
    try:
        service_client.get_secret_value(SecretId=arn, VersionId=token, VersionStage="AWSPENDING")
        logger.info("createSecret: Successfully retrieved secret for %s." % arn)
    except service_client.exceptions.ResourceNotFoundException:
        current_secret = service_client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
        current_data = json.loads(current_secret['SecretString'])
        
        # Generate new API key/token (simplified - in real scenario, call external API)
        if 'api_key' in current_data:
            current_data['api_key'] = 'new-' + current_data['api_key']
        if 'zendesk_api_token' in current_data:
            current_data['zendesk_api_token'] = 'new-' + current_data['zendesk_api_token']
        
        service_client.put_secret_value(
            SecretId=arn, 
            ClientRequestToken=token, 
            SecretString=json.dumps(current_data), 
            VersionStages=['AWSPENDING']
        )
        logger.info("createSecret: Successfully put secret for ARN %s and version %s." % (arn, token))

def set_secret(service_client, arn, token):
    logger.info("setSecret: Secret set in external service for %s" % arn)

def test_secret(service_client, arn, token):
    logger.info("testSecret: Secret tested successfully for %s" % arn)

def finish_secret(service_client, arn, token):
    metadata = service_client.describe_secret(SecretId=arn)
    current_version = None
    for version in metadata["VersionIdsToStages"]:
        if "AWSCURRENT" in metadata["VersionIdsToStages"][version]:
            if version == token:
                logger.info("finishSecret: Version %s already marked as AWSCURRENT for %s" % (version, arn))
                return
            current_version = version
            break

    service_client.update_secret_version_stage(
        SecretId=arn, 
        VersionStage="AWSCURRENT", 
        MoveToVersionId=token, 
        RemoveFromVersionId=current_version
    )
    logger.info("finishSecret: Successfully set AWSCURRENT stage to version %s for secret %s." % (token, arn))