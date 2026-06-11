# Copyright 2024 Amazon.com and its affiliates; all rights reserved.
# This file is AWS Content and may not be duplicated or distributed without permission

"""
This module contains a helper class for building and using Knowledge Bases for Amazon Bedrock.
The KnowledgeBasesForAmazonBedrock class provides a convenient interface for working with Knowledge Bases.
It includes methods for creating, updating, and invoking Knowledge Bases, as well as managing
IAM roles and S3 Vectors.
"""

import json
import boto3
import time
import uuid
from botocore.exceptions import ClientError
import pprint
from retrying import retry
import yaml
import os
import argparse

valid_embedding_models = [
    "cohere.embed-multilingual-v3",
    "cohere.embed-english-v3",
    "amazon.titan-embed-text-v1",
    "amazon.titan-embed-text-v2:0",
]
pp = pprint.PrettyPrinter(indent=2)


def read_yaml_file(file_path: str):
    """
    read and process a yaml file
    Args:
        file_path: the path to the yaml file
    """
    with open(file_path, "r") as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            print(f"Error reading YAML file: {e}")
            return None


def interactive_sleep(seconds: int):
    """
    Support functionality to induce an artificial 'sleep' to the code in order to wait for resources to be available
    Args:
        seconds (int): number of seconds to sleep for
    """
    dots = ""
    for i in range(seconds):
        dots += "."
        print(dots, end="\r")
        time.sleep(1)


class KnowledgeBasesForAmazonBedrock:
    """
    Support class that allows for:
        - creation (or retrieval) of a Knowledge Base for Amazon Bedrock with all its pre-requisites
          (including S3 Vectors, IAM roles and Permissions and S3 bucket)
        - Ingestion of data into the Knowledge Base
        - Deletion of all resources created
    """

    def __init__(self, suffix=None):
        """
        Class initializer
        """
        boto3_session = boto3.session.Session()
        self.region_name = boto3_session.region_name
        self.iam_client = boto3_session.client("iam", region_name=self.region_name)
        self.account_number = (
            boto3.client("sts", region_name=self.region_name)
            .get_caller_identity()
            .get("Account")
        )
        if suffix is not None:
            self.suffix = suffix
        else:
            self.suffix = str(uuid.uuid4())[:4]
        self.identity = boto3.client(
            "sts", region_name=self.region_name
        ).get_caller_identity()["Arn"]
        self.s3_vectors_client = boto3_session.client(
            "s3vectors", region_name=self.region_name
        )
        self.s3_client = boto3.client("s3", region_name=self.region_name)
        self.bedrock_agent_client = boto3.client(
            "bedrock-agent", region_name=self.region_name
        )
        self.vector_bucket_name = None
        self.index_name = None
        self.data_bucket_name = None

    def create_or_retrieve_knowledge_base(
        self,
        kb_name: str,
        kb_description: str = None,
        data_bucket_name: str = None,
        embedding_model: str = "amazon.titan-embed-text-v2:0",
    ):
        """
        Function used to create a new Knowledge Base or retrieve an existent one

        Args:
            kb_name: Knowledge Base Name
            kb_description: Knowledge Base Description
            data_bucket_name: Name of s3 Bucket containing Knowledge Base Data
            embedding_model: Name of Embedding model to be used on Knowledge Base creation

        Returns:
            kb_id: str - Knowledge base id
            ds_id: str - Data Source id
        """
        kb_id = None
        ds_id = None
        kbs_available = self.bedrock_agent_client.list_knowledge_bases(
            maxResults=100,
        )
        for kb in kbs_available["knowledgeBaseSummaries"]:
            if kb_name == kb["name"]:
                kb_id = kb["knowledgeBaseId"]
        if kb_id is not None:
            ds_available = self.bedrock_agent_client.list_data_sources(
                knowledgeBaseId=kb_id,
                maxResults=100,
            )
            for ds in ds_available["dataSourceSummaries"]:
                if kb_id == ds["knowledgeBaseId"]:
                    ds_id = ds["dataSourceId"]
                    if not data_bucket_name:
                        self.data_bucket_name = self._get_knowledge_base_s3_bucket(
                            kb_id, ds_id
                        )
            print(f"Knowledge Base {kb_name} already exists.")
            print(f"Retrieved Knowledge Base Id: {kb_id}")
            print(f"Retrieved Data Source Id: {ds_id}")
        else:
            print(f"Creating KB {kb_name}")
            # self.kb_name = kb_name
            # self.kb_description = kb_description
            if data_bucket_name is None:
                kb_name_temp = kb_name.replace("_", "-")
                data_bucket_name = f"{kb_name_temp}-{self.suffix}"
                print(
                    f"KB bucket name not provided, creating a new one called: {data_bucket_name}"
                )
            if embedding_model not in valid_embedding_models:
                valid_embeddings_str = str(valid_embedding_models)
                raise ValueError(
                    f"Invalid embedding model. Your embedding model should be one of {valid_embeddings_str}"
                )
            kb_execution_role_name = (
                f"AmazonBedrockExecutionRoleForKnowledgeBase_{self.suffix}"
            )
            fm_policy_name = (
                f"AmazonBedrockFoundationModelPolicyForKnowledgeBase_{self.suffix}"
            )
            s3_policy_name = f"AmazonBedrockS3PolicyForKnowledgeBase_{self.suffix}"
            s3_vectors_policy_name = (
                f"AmazonBedrockS3VectorsPolicyForKnowledgeBase_{self.suffix}"
            )
            vector_bucket_name = f"{kb_name}-vectors-{self.suffix}"
            index_name = f"{kb_name}-index-{self.suffix}"
            print(
                "========================================================================================"
            )
            print(
                f"Step 1 - Creating or retrieving {data_bucket_name} S3 bucket for Knowledge Base documents"
            )
            self.create_s3_bucket(data_bucket_name)
            print(
                "========================================================================================"
            )
            print(
                f"Step 2 - Creating Knowledge Base Execution Role ({kb_execution_role_name}) and Policies"
            )
            bedrock_kb_execution_role = self.create_bedrock_kb_execution_role(
                embedding_model,
                data_bucket_name,
                fm_policy_name,
                s3_policy_name,
                kb_execution_role_name,
            )
            print(time.sleep(10))
            print(
                "========================================================================================"
            )
            print("Step 3 - Creating S3 Vectors Bucket and Index")
            vector_bucket_arn, index_arn = self.create_s3_vectors_bucket_and_index(
                vector_bucket_name, index_name, bedrock_kb_execution_role
            )
            print(
                "========================================================================================"
            )
            print("Step 4 - Creating S3 Vectors Policy")
            self.create_s3_vectors_policy(
                s3_vectors_policy_name, vector_bucket_arn, bedrock_kb_execution_role
            )
            print(
                "========================================================================================"
            )
            print("Step 5 - Creating Knowledge Base")
            knowledge_base, data_source = self.create_knowledge_base(
                vector_bucket_arn,
                index_arn,
                index_name,
                data_bucket_name,
                embedding_model,
                kb_name,
                kb_description,
                bedrock_kb_execution_role,
            )
            interactive_sleep(60)
            print(
                "========================================================================================"
            )
            kb_id = knowledge_base["knowledgeBaseId"]
            ds_id = data_source["dataSourceId"]
        return kb_id, ds_id

    def create_s3_bucket(self, bucket_name: str):
        """
        Check if bucket exists, and if not create S3 bucket for knowledge base data source
        Args:
            bucket_name: s3 bucket name
        """
        self.data_bucket_name = bucket_name
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            print(f"Bucket {bucket_name} already exists - retrieving it!")
        except ClientError:
            print(f"Creating bucket {bucket_name}")
            if self.region_name == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region_name},
                )

    def upload_directory(self, s3_path, bucket_name):
        """
        Upload files from a local path to s3
            s3_path: local path of the document
            bucket_name: bucket name
        """
        for root, dirs, files in os.walk(s3_path):
            for file in files:
                file_to_upload = os.path.join(root, file)
                print(f"uploading file {file_to_upload} to {bucket_name}")
                self.s3_client.upload_file(file_to_upload, bucket_name, file)

    def get_data_bucket_name(self):
        """
        get the name of the data bucket
        """
        return self.data_bucket_name

    def _get_knowledge_base_s3_bucket(self, knowledge_base_id, data_source_id):
        """Get the s3 bucket associated with a knowledge base, if there is one"""
        try:
            # Get the data source details
            response = self.bedrock_agent_client.get_data_source(
                knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id
            )

            # Extract the S3 bucket information from the data source configuration
            data_source_config = response["dataSource"]["dataSourceConfiguration"]

            if data_source_config["type"] == "S3":
                s3_config = data_source_config["s3Configuration"]
                bucket_arn = s3_config["bucketArn"]

                # Extract bucket name from ARN
                bucket_name = bucket_arn.split(":")[-1]
                return bucket_name
            else:
                return "Data source is not an S3 bucket"

        except Exception as e:
            print(f"Error retrieving data source information: {str(e)}")
            return None

    def create_bedrock_kb_execution_role(
        self,
        embedding_model: str,
        bucket_name: str,
        fm_policy_name: str,
        s3_policy_name: str,
        kb_execution_role_name: str,
    ):
        """
        Create Knowledge Base Execution IAM Role and its required policies.
        If role and/or policies already exist, retrieve them
        Args:
            embedding_model: the embedding model used by the knowledge base
            bucket_name: the bucket name used by the knowledge base
            fm_policy_name: the name of the foundation model access policy
            s3_policy_name: the name of the s3 access policy
            kb_execution_role_name: the name of the knowledge base execution role

        Returns:
            IAM role created
        """
        foundation_model_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock:{self.region_name}::foundation-model/{embedding_model}"
                    ],
                }
            ],
        }

        s3_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*",
                    ],
                    "Condition": {
                        "StringEquals": {
                            "aws:ResourceAccount": f"{self.account_number}"
                        }
                    },
                }
            ],
        }

        assume_role_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": f"{self.account_number}"},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock:{self.region_name}:{self.account_number}:knowledge-base/*"
                        },
                    },
                }
            ],
        }

        try:
            # create policies based on the policy documents
            fm_policy = self.iam_client.create_policy(
                PolicyName=fm_policy_name,
                PolicyDocument=json.dumps(foundation_model_policy_document),
                Description="Policy for accessing foundation model",
            )
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            print(f"{fm_policy_name} already exists, retrieving it!")
            fm_policy = self.iam_client.get_policy(
                PolicyArn=f"arn:aws:iam::{self.account_number}:policy/{fm_policy_name}"
            )

        try:
            s3_policy = self.iam_client.create_policy(
                PolicyName=s3_policy_name,
                PolicyDocument=json.dumps(s3_policy_document),
                Description="Policy for reading documents from s3",
            )
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            print(f"{s3_policy_name} already exists, retrieving it!")
            s3_policy = self.iam_client.get_policy(
                PolicyArn=f"arn:aws:iam::{self.account_number}:policy/{s3_policy_name}"
            )
        # create bedrock execution role
        try:
            bedrock_kb_execution_role = self.iam_client.create_role(
                RoleName=kb_execution_role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy_document),
                Description="Amazon Bedrock Knowledge Base Execution Role for accessing OSS and S3",
                MaxSessionDuration=3600,
            )
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            print(f"{kb_execution_role_name} already exists, retrieving it!")
            bedrock_kb_execution_role = self.iam_client.get_role(
                RoleName=kb_execution_role_name
            )
        # fetch arn of the policies and role created above
        s3_policy_arn = s3_policy["Policy"]["Arn"]
        fm_policy_arn = fm_policy["Policy"]["Arn"]

        # attach policies to Amazon Bedrock execution role
        self.iam_client.attach_role_policy(
            RoleName=bedrock_kb_execution_role["Role"]["RoleName"],
            PolicyArn=fm_policy_arn,
        )
        self.iam_client.attach_role_policy(
            RoleName=bedrock_kb_execution_role["Role"]["RoleName"],
            PolicyArn=s3_policy_arn,
        )
        return bedrock_kb_execution_role

    def create_s3_vectors_bucket_and_index(
        self,
        vector_bucket_name: str,
        index_name: str,
        bedrock_kb_execution_role: str,
    ):
        """
        Create S3 Vectors bucket and index.
        Args:
            vector_bucket_name: name of the S3 vectors bucket
            index_name: name of the vector index
            bedrock_kb_execution_role: knowledge base execution role

        Returns:
            vector_bucket_arn, index_arn
        """
        self.vector_bucket_name = vector_bucket_name
        self.index_name = index_name

        # Create S3 Vectors bucket
        try:
            self.s3_vectors_client.create_vector_bucket(
                vectorBucketName=vector_bucket_name,
                encryptionConfiguration={"sseType": "AES256"},
            )
            get_response = self.s3_vectors_client.get_vector_bucket(
                vectorBucketName=vector_bucket_name
            )
            vector_bucket_arn = get_response["vectorBucket"]["vectorBucketArn"]
            print(f"Created S3 Vectors bucket: {vector_bucket_name}")
        except self.s3_vectors_client.exceptions.ConflictException:
            print(f"S3 Vectors bucket {vector_bucket_name} already exists")
            # Get the bucket ARN
            vector_bucket_arn = f"arn:aws:s3vectors:{self.region_name}:{self.account_number}:vector-bucket/{vector_bucket_name}"
        except Exception as e:
            print(f"Error creating S3 vectors bucket: {e}")
            raise

        # Create vector index
        try:
            self.s3_vectors_client.create_index(
                vectorBucketName=vector_bucket_name,
                indexName=index_name,
                dataType="float32",
                dimension=1024,  # Matching the OpenSearch configuration
                distanceMetric="cosine",
                metadataConfiguration={
                    "nonFilterableMetadataKeys": [
                        "AMAZON_BEDROCK_TEXT",
                    ]
                },
            )
            get_index_response = self.s3_vectors_client.get_index(
                vectorBucketName=vector_bucket_name,
                indexName=index_name,
            )
            time.sleep(10)
            index_arn = get_index_response["index"]["indexArn"]
            print(f"Created S3 Vectors index: {index_name}")
        except self.s3_vectors_client.exceptions.ConflictException:
            print(f"S3 Vectors index {index_name} already exists")
            # Get the index ARN
            index_arn = f"arn:aws:s3vectors:{self.region_name}:{self.account_number}:index/{vector_bucket_name}/{index_name}"
        except Exception as e:
            print(f"Error creating S3 vectors index: {e}")
            raise

        return vector_bucket_arn, index_arn

    def create_s3_vectors_policy(
        self,
        s3_vectors_policy_name: str,
        vector_bucket_arn: str,
        bedrock_kb_execution_role: str,
    ):
        """
        Create S3 Vectors policy and attach it to the Knowledge Base Execution role.
        Args:
            s3_vectors_policy_name: name of the S3 vectors policy
            vector_bucket_arn: ARN of the S3 vectors bucket
            bedrock_kb_execution_role: knowledge base execution role
        """
        # Define S3 Vectors policy document
        s3_vectors_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3VectorsPermissions",
                    "Effect": "Allow",
                    "Action": [
                        "s3vectors:GetIndex",
                        "s3vectors:QueryVectors",
                        "s3vectors:PutVectors",
                        "s3vectors:GetVectors",
                        "s3vectors:DeleteVectors",
                    ],
                    "Resource": f"{vector_bucket_arn}/index/*",
                    "Condition": {
                        "StringEquals": {
                            "aws:ResourceAccount": f"{self.account_number}"
                        }
                    },
                }
            ],
        }

        try:
            s3_vectors_policy = self.iam_client.create_policy(
                PolicyName=s3_vectors_policy_name,
                PolicyDocument=json.dumps(s3_vectors_policy_document),
                Description="Policy for accessing S3 vectors",
            )
            print(f"Created S3 Vectors policy: {s3_vectors_policy_name}")
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            print(f"S3 Vectors policy {s3_vectors_policy_name} already exists")
            s3_vectors_policy = self.iam_client.get_policy(
                PolicyArn=f"arn:aws:iam::{self.account_number}:policy/{s3_vectors_policy_name}"
            )

        # Attach policy to Bedrock execution role
        s3_vectors_policy_arn = s3_vectors_policy["Policy"]["Arn"]
        self.iam_client.attach_role_policy(
            RoleName=bedrock_kb_execution_role["Role"]["RoleName"],
            PolicyArn=s3_vectors_policy_arn,
        )
        print(
            f"Attached S3 Vectors policy to role: {bedrock_kb_execution_role['Role']['RoleName']}"
        )

    @retry(wait_random_min=1000, wait_random_max=2000, stop_max_attempt_number=7)
    def create_knowledge_base(
        self,
        vector_bucket_arn: str,
        index_arn: str,
        index_name: str,
        bucket_name: str,
        embedding_model: str,
        kb_name: str,
        kb_description: str,
        bedrock_kb_execution_role: str,
    ):
        """
        Create Knowledge Base and its Data Source. If existent, retrieve
        Args:
            vector_bucket_arn: ARN of the S3 vectors bucket
            index_arn: ARN of the S3 vectors index
            index_name: name of the S3 vectors index
            bucket_name: name of the s3 bucket containing the knowledge base data
            embedding_model: id of the embedding model used
            kb_name: knowledge base name
            kb_description: knowledge base description
            bedrock_kb_execution_role: knowledge base execution role

        Returns:
            knowledge base object,
            data source object
        """
        print(vector_bucket_arn)
        print(index_name)
        s3_vectors_configuration = {
            "vectorBucketArn": vector_bucket_arn,
            # "indexName": index_name,
            "indexArn": index_arn,
        }

        # Ingest strategy - How to ingest data from the data source
        chunking_strategy_configuration = {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {
                "maxTokens": 512,
                "overlapPercentage": 20,
            },
        }

        # The data source to ingest documents from, into the OpenSearch serverless knowledge base index
        s3_configuration = {
            "bucketArn": f"arn:aws:s3:::{bucket_name}",
            # "inclusionPrefixes": [
            #     "policies"
            # ],  # you can use this if you want to create a KB using data within s3 prefixes.
        }

        # The embedding model used by Bedrock to embed ingested documents, and realtime prompts
        embedding_model_arn = (
            f"arn:aws:bedrock:{self.region_name}::foundation-model/{embedding_model}"
        )
        print(
            str(
                {
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": embedding_model_arn
                    },
                }
            )
        )
        try:
            print(bedrock_kb_execution_role["Role"]["Arn"])
            create_kb_response = self.bedrock_agent_client.create_knowledge_base(
                name=kb_name,
                description=kb_description,
                roleArn=bedrock_kb_execution_role["Role"]["Arn"],
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": embedding_model_arn
                    },
                },
                storageConfiguration={
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": s3_vectors_configuration,
                },
            )
            kb = create_kb_response["knowledgeBase"]
            pp.pprint(kb)
        except Exception as e:
            # kbs = self.bedrock_agent_client.list_knowledge_bases(maxResults=100)
            # kb_id = None
            # for kb in kbs["knowledgeBaseSummaries"]:
            #     if kb["name"] == kb_name:
            #         kb_id = kb["knowledgeBaseId"]
            # response = self.bedrock_agent_client.get_knowledge_base(
            #     knowledgeBaseId=kb_id
            # )
            # kb = response["knowledgeBase"]
            # pp.pprint(kb)
            print(e)

        # Create a DataSource in KnowledgeBase
        try:
            create_ds_response = self.bedrock_agent_client.create_data_source(
                name=kb_name,
                description=kb_description,
                knowledgeBaseId=kb["knowledgeBaseId"],
                dataDeletionPolicy="RETAIN",
                dataSourceConfiguration={
                    "type": "S3",
                    "s3Configuration": s3_configuration,
                },
                vectorIngestionConfiguration={
                    "chunkingConfiguration": chunking_strategy_configuration
                },
            )
            ds = create_ds_response["dataSource"]
            pp.pprint(ds)
        except self.bedrock_agent_client.exceptions.ConflictException:
            ds_id = self.bedrock_agent_client.list_data_sources(
                knowledgeBaseId=kb["knowledgeBaseId"], maxResults=100
            )["dataSourceSummaries"][0]["dataSourceId"]
            get_ds_response = self.bedrock_agent_client.get_data_source(
                dataSourceId=ds_id, knowledgeBaseId=kb["knowledgeBaseId"]
            )
            ds = get_ds_response["dataSource"]
            pp.pprint(ds)
        return kb, ds

    def synchronize_data(self, kb_id, ds_id):
        """
        Start an ingestion job to synchronize data from an S3 bucket to the Knowledge Base
        and waits for the job to be completed
        Args:
            kb_id: knowledge base id
            ds_id: data source id
        """
        # ensure that the kb is available
        i_status = ["CREATING", "DELETING", "UPDATING"]
        while (
            self.bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)[
                "knowledgeBase"
            ]["status"]
            in i_status
        ):
            time.sleep(10)
        # Start an ingestion job
        start_job_response = self.bedrock_agent_client.start_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id
        )
        job = start_job_response["ingestionJob"]
        pp.pprint(job)
        # Get job
        while job["status"] != "COMPLETE" and job["status"] != "FAILED":
            get_job_response = self.bedrock_agent_client.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job["ingestionJobId"],
            )
            job = get_job_response["ingestionJob"]
            interactive_sleep(5)
        pp.pprint(job)
        # interactive_sleep(40)

    def get_kb(self, kb_id):
        """
        Get KB details
        Args:
            kb_id: knowledge base id
        """
        get_job_response = self.bedrock_agent_client.get_knowledge_base(
            knowledgeBaseId=kb_id
        )
        return get_job_response

    def delete_kb(
        self,
        kb_name: str,
        delete_s3_bucket: bool = True,
        delete_iam_roles_and_policies: bool = True,
        delete_s3_vector: bool = True,
    ):
        """
        Delete the Knowledge Base resources
        Args:
            kb_name: name of the knowledge base to delete
            delete_s3_bucket (bool): boolean to indicate if s3 bucket should also be deleted
            delete_iam_roles_and_policies (bool): boolean to indicate if IAM roles and Policies should also be deleted
            delete_s3_vector: boolean to indicate if amazon Amazon S3 Vector
        """
        kbs_available = self.bedrock_agent_client.list_knowledge_bases(
            maxResults=100,
        )
        kb_id = None
        ds_id = None
        for kb in kbs_available["knowledgeBaseSummaries"]:
            if kb_name == kb["name"]:
                kb_id = kb["knowledgeBaseId"]
        kb_details = self.bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb_role = kb_details["knowledgeBase"]["roleArn"].split("/")[1]

        vector_bucket_arn = kb_details["knowledgeBase"]["storageConfiguration"][
            "s3VectorsConfiguration"
        ]["vectorBucketArn"]
        # index_name = kb_details["knowledgeBase"]["storageConfiguration"][
        #     "s3VectorsConfiguration"
        # ]["indexName"]
        index_arn = kb_details["knowledgeBase"]["storageConfiguration"][
            "s3VectorsConfiguration"
        ]["indexArn"]

        ds_available = self.bedrock_agent_client.list_data_sources(
            knowledgeBaseId=kb_id,
            maxResults=100,
        )
        for ds in ds_available["dataSourceSummaries"]:
            if kb_id == ds["knowledgeBaseId"]:
                ds_id = ds["dataSourceId"]
        self.bedrock_agent_client.get_data_source(
            dataSourceId=ds_id,
            knowledgeBaseId=kb_id,
        )

        if (
            delete_s3_vector
        ):  # Renamed for backward compatibility, but now handles S3 vectors
            self.s3_vectors_client.delete_index(
                # vectorBucketName=vector_bucket_name,
                # vectorBucketArn=vector_bucket_arn,
                # indexName=index_name,
                indexArn=index_arn,
            )
            print("S3 Vectors index deleted successfully!")

            self.s3_vectors_client.delete_vector_bucket(
                vectorBucketArn=vector_bucket_arn,
            )
            print("S3 Vectors bucket deleted successfully!")

        if delete_iam_roles_and_policies:
            self.delete_iam_roles_and_policies(kb_role)
            print("Knowledge Base Roles and Policies deleted successfully!")

        print("Resources deleted successfully!")

        self.bedrock_agent_client.delete_data_source(
            dataSourceId=ds_id, knowledgeBaseId=kb_id
        )
        print("Data Source deleted successfully!")

        self.bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=kb_id)
        print("Knowledge Base deleted successfully!")

    def delete_iam_roles_and_policies(self, kb_execution_role_name: str):
        """
        Delete IAM Roles and policies used by the Knowledge Base
        Args:
            kb_execution_role_name: knowledge base execution role
        """
        attached_policies = self.iam_client.list_attached_role_policies(
            RoleName=kb_execution_role_name, MaxItems=100
        )
        policies_arns = []
        for policy in attached_policies["AttachedPolicies"]:
            policies_arns.append(policy["PolicyArn"])
        for policy in policies_arns:
            self.iam_client.detach_role_policy(
                RoleName=kb_execution_role_name, PolicyArn=policy
            )
            self.iam_client.delete_policy(PolicyArn=policy)
        self.iam_client.delete_role(RoleName=kb_execution_role_name)
        return 0

    def delete_s3(self, bucket_name: str):
        """
        Delete the objects contained in the Knowledge Base S3 bucket.
        Once the bucket is empty, delete the bucket
        Args:
            bucket_name: bucket name

        """
        objects = self.s3_client.list_objects(Bucket=bucket_name)
        if "Contents" in objects:
            for obj in objects["Contents"]:
                self.s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
        self.s3_client.delete_bucket(Bucket=bucket_name)


if __name__ == "__main__":
    kb = KnowledgeBasesForAmazonBedrock()
    smm_client = boto3.client("ssm")
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Example usage:
    config_path = f"{current_dir}/prereqs_config.yaml"
    data = read_yaml_file(config_path)

    parser = argparse.ArgumentParser(description="Knowledge Base handler")
    parser.add_argument(
        "--mode",
        required=True,
        help="Knowledge Base helper model. One for: create or delete.",
    )

    args = parser.parse_args()

    print(data)
    if args.mode == "create":
        kb_id, ds_id = kb.create_or_retrieve_knowledge_base(
            data["knowledge_base_name"], data["knowledge_base_description"]
        )
        print(f"Knowledge Base ID: {kb_id}")
        print(f"Data Source ID: {ds_id}")

        kb.upload_directory(
            f"{current_dir}/{data['kb_files_path']}", kb.get_data_bucket_name()
        )
        kb.synchronize_data(kb_id, ds_id)

        smm_client.put_parameter(
            Name="/app/customersupport/knowledge_base/knowledge_base_id",
            Description=f"{data['knowledge_base_name']} kb id",
            Value=kb_id,
            Type="String",
            Overwrite=True,
        )

    if args.mode == "delete":
        kb.delete_kb(data["knowledge_base_name"])
        smm_client.delete_parameter(
            Name="/app/customersupport/knowledge_base/knowledge_base_id"
        )
