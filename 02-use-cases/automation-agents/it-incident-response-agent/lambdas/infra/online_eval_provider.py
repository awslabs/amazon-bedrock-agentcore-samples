"""Custom resource handler: create/update/delete AgentCore Online Evaluation config.

Uses CDK Provider framework — return a dict on success, raise on failure.
No cfnresponse needed (the Provider framework handles it).
"""

import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """CDK Provider onEvent handler."""
    request_type = event.get("RequestType")
    logger.info("online_eval_provider RequestType=%s", request_type)

    props = event["ResourceProperties"]
    config_name = props["ConfigName"]

    control = boto3.client("bedrock-agentcore-control")

    if request_type == "Delete":
        try:
            control.delete_online_evaluation_config(
                onlineEvaluationConfigName=config_name
            )
            logger.info("Deleted online eval config: %s", config_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("ResourceNotFoundException", "ValidationException"):
                logger.info("Config %s already gone", config_name)
            else:
                logger.warning("Delete failed (continuing): %s", exc)
        return {"PhysicalResourceId": config_name}

    # Create or Update
    evaluators = [{"evaluatorId": eid} for eid in props["Evaluators"]]
    rule = {
        "samplingConfig": {
            "samplingPercentage": float(props.get("SamplingPercentage", 100))
        }
    }
    data_source_config = {
        "cloudWatchLogs": {
            "logGroupNames": [props["LogGroupName"]],
            "serviceNames": [props["ServiceName"]],
        }
    }

    kwargs = dict(
        onlineEvaluationConfigName=config_name,
        description=props.get("Description", "Online evaluation"),
        rule=rule,
        dataSourceConfig=data_source_config,
        evaluators=evaluators,
        evaluationExecutionRoleArn=props["RoleArn"],
        enableOnCreate=True,
    )

    try:
        control.create_online_evaluation_config(**kwargs)
        logger.info("Created online eval config: %s", config_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code != "ConflictException":
            raise
        update_kwargs = dict(kwargs)
        update_kwargs.pop("enableOnCreate", None)
        control.update_online_evaluation_config(**update_kwargs)
        logger.info("Updated online eval config: %s", config_name)

    return {
        "PhysicalResourceId": config_name,
        "Data": {"ConfigName": config_name},
    }
