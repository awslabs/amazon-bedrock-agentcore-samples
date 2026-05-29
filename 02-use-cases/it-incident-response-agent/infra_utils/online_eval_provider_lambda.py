"""Custom resource: create/update/delete an AgentCore Online Evaluation config.

AgentCore Online Evaluation continuously samples runtime traces (from the
runtime's CloudWatch log group) and runs LLM-as-a-judge evaluators against
them. We register the config here so it stands up alongside the runtime.

There is no L1 construct yet for online evaluation, so this resource calls
`bedrock-agentcore-control:create_online_evaluation_config` directly.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

from infra_utils import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    request_type = event.get("RequestType")
    logger.info("online_eval_provider_lambda RequestType=%s", request_type)
    try:
        props = event["ResourceProperties"]
        config_name = props["ConfigName"]
        physical_id = config_name
        control = boto3.client("bedrock-agentcore-control")

        if request_type == "Delete":
            try:
                control.delete_online_evaluation_config(
                    onlineEvaluationConfigName=config_name
                )
                logger.info("deleted online eval config %s", config_name)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("ResourceNotFoundException", "ValidationException"):
                    logger.info("config %s already gone", config_name)
                else:
                    logger.warning("delete failed (continuing): %s", exc)
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, physicalResourceId=physical_id
            )
            return

        evaluators = [
            {"evaluatorId": eid} for eid in props["BuiltinEvaluators"]
        ]
        rule = {
            "samplingConfig": {
                "samplingPercentage": float(props.get("SamplingPercentage", 20))
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
            description=props.get("Description", "Online evaluation for IT incident agent"),
            rule=rule,
            dataSourceConfig=data_source_config,
            evaluators=evaluators,
            evaluationExecutionRoleArn=props["RoleArn"],
            enableOnCreate=True,
        )

        try:
            resp = control.create_online_evaluation_config(**kwargs)
            logger.info("created online eval config %s", config_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code != "ConflictException":
                raise
            update_kwargs = dict(kwargs)
            update_kwargs.pop("enableOnCreate", None)
            resp = control.update_online_evaluation_config(**update_kwargs)
            logger.info("updated online eval config %s", config_name)

        data = {
            "ConfigName": config_name,
            "ConfigArn": resp.get("onlineEvaluationConfigArn", ""),
        }
        cfnresponse.send(
            event, context, cfnresponse.SUCCESS, data, physicalResourceId=physical_id
        )
    except Exception as exc:
        logger.exception("online eval config operation failed")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(exc)})
