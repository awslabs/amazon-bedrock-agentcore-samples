"""Custom resource: seed DynamoDB tables, upload KB docs, trigger KB ingestion.

Reads seed JSON from S3 (asset bucket) and writes items into the three
DynamoDB tables. Also kicks off a Bedrock Knowledge Base ingestion job so
the runbooks are searchable immediately after deploy.
"""

import json
import logging
import os
import time

import boto3

from infra_utils import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_s3 = boto3.client("s3")
_ddb = boto3.resource("dynamodb")
_kb = boto3.client("bedrock-agent")


def _seed_table(table_name: str, items_json: str) -> int:
    table = _ddb.Table(table_name)
    items = json.loads(items_json)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    return len(items)


def handler(event, context):
    logger.info("event: %s", event)
    try:
        if event["RequestType"] == "Delete":
            cfnresponse.send(event, context, cfnresponse.SUCCESS)
            return

        props = event["ResourceProperties"]
        seed_bucket = props["SeedBucket"]
        users_table = props["UsersTable"]
        processes_table = props["ProcessesTable"]
        kb_id = props["KnowledgeBaseId"]
        data_source_id = props["DataSourceId"]

        # Seed DDB
        users_json = _s3.get_object(Bucket=seed_bucket, Key="seed/users.json")["Body"].read()
        processes_json = _s3.get_object(Bucket=seed_bucket, Key="seed/processes.json")["Body"].read()
        n_users = _seed_table(users_table, users_json)
        n_processes = _seed_table(processes_table, processes_json)
        logger.info("seeded %d users, %d processes", n_users, n_processes)

        # Trigger KB ingestion
        job = _kb.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=data_source_id)
        job_id = job["ingestionJob"]["ingestionJobId"]
        logger.info("started ingestion job %s", job_id)

        # Wait briefly for ingestion to complete (bounded by Lambda timeout)
        deadline = context.get_remaining_time_in_millis() / 1000 - 30
        start = time.time()
        while time.time() - start < deadline:
            status = _kb.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=data_source_id,
                ingestionJobId=job_id,
            )["ingestionJob"]["status"]
            logger.info("ingestion status %s", status)
            if status in ("COMPLETE", "FAILED"):
                break
            time.sleep(15)

        cfnresponse.send(
            event,
            context,
            cfnresponse.SUCCESS,
            {"UsersSeeded": n_users, "ProcessesSeeded": n_processes, "IngestionJobId": job_id},
            f"seeder-{kb_id}",
        )
    except Exception as exc:
        logger.exception("seeding failed")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(exc)})
