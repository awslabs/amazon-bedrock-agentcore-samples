"""Custom resource: trigger and wait for the agent CodeBuild project."""

import logging
import time

import boto3

from infra_utils import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info("event: %s", event)
    try:
        if event["RequestType"] == "Delete":
            cfnresponse.send(event, context, cfnresponse.SUCCESS)
            return

        project_name = event["ResourceProperties"]["ProjectName"]
        cb = boto3.client("codebuild")
        build_id = cb.start_build(projectName=project_name)["build"]["id"]
        logger.info("started build %s", build_id)

        deadline = context.get_remaining_time_in_millis() / 1000 - 30
        start = time.time()
        while True:
            if time.time() - start > deadline:
                cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": "build timeout"})
                return
            status = cb.batch_get_builds(ids=[build_id])["builds"][0]["buildStatus"]
            if status == "SUCCEEDED":
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {"BuildId": build_id})
                return
            if status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
                cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": status})
                return
            logger.info("build %s status %s", build_id, status)
            time.sleep(20)
    except Exception as exc:
        logger.exception("build trigger failed")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(exc)})
