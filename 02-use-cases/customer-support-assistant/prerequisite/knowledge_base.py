# Copyright 2024 Amazon.com and its affiliates; all rights reserved.
# This file is AWS Content and may not be duplicated or distributed without permission

"""
This module contains a helper class for building and using Knowledge Bases for Amazon Bedrock.
The KnowledgeBasesForAmazonBedrock class provides a convenient interface for working with Knowledge Bases.
It includes methods for creating, updating, and invoking Knowledge Bases, as well as managing
IAM roles and OpenSearch Serverless.
"""

import json
import boto3
import time
import uuid
from botocore.exceptions import ClientError
from opensearchpy import (
    OpenSearch,
    RequestsHttpConnection,
    AWSV4SignerAuth,
    RequestError,
)
import pprint
from retrying import retry
import random
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
          (including OSS, IAM roles and Permissions and S3 bucket)
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
        self.aoss_client = boto3_session.client(
            "opensearchserverless", region_name=self.region_name
        )
        self.s3_client = boto3.client("s3", region_name=self.region_name)
        self.bedrock_agent_client = boto3.client(
            "bedrock-agent", region_name=self.region_name
        )
        self.bedrock_agent_client = boto3.client(
            "bedrock-agent", region_name=self.region_name
        )
        credentials = boto3.Session().get_credentials()
        self.awsauth = AWSV4SignerAuth(credentials, self.region_name, "aoss")
        self.oss_client = None
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
            # self.embedding_model = embedding_model
            encryption_policy_name = f"{kb_name}-sp-{self.suffix}"
            network_policy_name = f"{kb_name}-np-{self.suffix}"
            access_policy_name = f"{kb_name}-ap-{self.suffix}"
            kb_execution_role_name = (
                f"AmazonBedrockExecutionRoleForKnowledgeBase_{self.suffix}"
            )
            fm_policy_name = (
                f"AmazonBedrockFoundationModelPolicyForKnowledgeBase_{self.suffix}"
            )
            s3_policy_name = f"AmazonBedrockS3PolicyForKnowledgeBase_{self.suffix}"
            oss_policy_name = f"AmazonBedrockOSSPolicyForKnowledgeBase_{self.suffix}"
            vector_store_name = f"{kb_name}-{self.suffix}"
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
            print(
                "========================================================================================"
            )
            print(f"Step 3 - Creating OSS encryption, network and data access policies")
            encryption_policy, network_policy, access_policy = (
                self.create_policies_in_oss(
                    encryption_policy_name,
                    vector_store_name,
                    network_policy_name,
                    bedrock_kb_execution_role,
                    access_policy_name,
                )
            )
            print(
                "========================================================================================"
            )
            print(
                f"Step 4 - Creating OSS Collection (this step takes a couple of minutes to complete)"
            )
            host, collection, collection_id, collection_arn = self.create_oss(
                vector_store_name, oss_policy_name, bedrock_kb_execution_role
            )
            # Build the OpenSearch client
            self.oss_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=self.awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=300,
            )

            print(
                "========================================================================================"
            )
            print(f"Step 5 - Creating OSS Vector Index")
            self.create_vector_index(index_name)
            print(
                "========================================================================================"
            )
            print(f"Step 6 - Creating Knowledge Base")
            knowledge_base, data_source = self.create_knowledge_base(
                collection_arn,
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
        except ClientError as e:
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

    def create_oss_policy_attach_bedrock_execution_role(
        self, collection_id: str, oss_policy_name: str, bedrock_kb_execution_role: str
    ):
        """
        Create OpenSearch Serverless policy and attach it to the Knowledge Base Execution role.
        If policy already exists, attaches it
        Args:
            collection_id: collection id
            oss_policy_name: opensearch serverless policy name
            bedrock_kb_execution_role: knowledge base execution role

        Returns:
            created: bool - boolean to indicate if role was created
        """
        # define oss policy document
        oss_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["aoss:APIAccessAll"],
                    "Resource": [
                        f"arn:aws:aoss:{self.region_name}:{self.account_number}:collection/{collection_id}"
                    ],
                }
            ],
        }

        oss_policy_arn = f"arn:aws:iam::{self.account_number}:policy/{oss_policy_name}"
        created = False
        try:
            self.iam_client.create_policy(
                PolicyName=oss_policy_name,
                PolicyDocument=json.dumps(oss_policy_document),
                Description="Policy for accessing opensearch serverless",
            )
            created = True
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            print(f"Policy {oss_policy_arn} already exists, updating it")
        print("Opensearch serverless arn: ", oss_policy_arn)

        self.iam_client.attach_role_policy(
            RoleName=bedrock_kb_execution_role["Role"]["RoleName"],
            PolicyArn=oss_policy_arn,
        )
        return created

    def create_policies_in_oss(
        self,
        encryption_policy_name: str,
        vector_store_name: str,
        network_policy_name: str,
        bedrock_kb_execution_role: str,
        access_policy_name: str,
    ):
        """
        Create OpenSearch Serverless encryption, network and data access policies.
        If policies already exist, retrieve them
        Args:
            encryption_policy_name: name of the data encryption policy
            vector_store_name: name of the vector store
            network_policy_name: name of the network policy
            bedrock_kb_execution_role: name of the knowledge base execution role
            access_policy_name: name of the data access policy

        Returns:
            encryption_policy, network_policy, access_policy
        """
        try:
            encryption_policy = self.aoss_client.create_security_policy(
                name=encryption_policy_name,
                policy=json.dumps(
                    {
                        "Rules": [
                            {
                                "Resource": ["collection/" + vector_store_name],
                                "ResourceType": "collection",
                            }
                        ],
                        "AWSOwnedKey": True,
                    }
                ),
                type="encryption",
            )
        except self.aoss_client.exceptions.ConflictException:
            print(f"{encryption_policy_name} already exists, retrieving it!")
            encryption_policy = self.aoss_client.get_security_policy(
                name=encryption_policy_name, type="encryption"
            )

        try:
            network_policy = self.aoss_client.create_security_policy(
                name=network_policy_name,
                policy=json.dumps(
                    [
                        {
                            "Rules": [
                                {
                                    "Resource": ["collection/" + vector_store_name],
                                    "ResourceType": "collection",
                                }
                            ],
                            "AllowFromPublic": True,
                        }
                    ]
                ),
                type="network",
            )
        except self.aoss_client.exceptions.ConflictException:
            print(f"{network_policy_name} already exists, retrieving it!")
            network_policy = self.aoss_client.get_security_policy(
                name=network_policy_name, type="network"
            )

        try:
            access_policy = self.aoss_client.create_access_policy(
                name=access_policy_name,
                policy=json.dumps(
                    [
                        {
                            "Rules": [
                                {
                                    "Resource": ["collection/" + vector_store_name],
                                    "Permission": [
                                        "aoss:CreateCollectionItems",
                                        "aoss:DeleteCollectionItems",
                                        "aoss:UpdateCollectionItems",
                                        "aoss:DescribeCollectionItems",
                                    ],
                                    "ResourceType": "collection",
                                },
                                {
                                    "Resource": ["index/" + vector_store_name + "/*"],
                                    "Permission": [
                                        "aoss:CreateIndex",
                                        "aoss:DeleteIndex",
                                        "aoss:UpdateIndex",
                                        "aoss:DescribeIndex",
                                        "aoss:ReadDocument",
                                        "aoss:WriteDocument",
                                    ],
                                    "ResourceType": "index",
                                },
                            ],
                            "Principal": [
                                self.identity,
                                bedrock_kb_execution_role["Role"]["Arn"],
                            ],
                            "Description": "Easy data policy",
                        }
                    ]
                ),
                type="data",
            )
        except self.aoss_client.exceptions.ConflictException:
            print(f"{access_policy_name} already exists, retrieving it!")
            access_policy = self.aoss_client.get_access_policy(
                name=access_policy_name, type="data"
            )
        return encryption_policy, network_policy, access_policy

    def create_oss(
        self,
        vector_store_name: str,
        oss_policy_name: str,
        bedrock_kb_execution_role: str,
    ):
        """
        Create OpenSearch Serverless Collection. If already existent, retrieve
        Args:
            vector_store_name: name of the vector store
            oss_policy_name: name of the opensearch serverless access policy
            bedrock_kb_execution_role: name of the knowledge base execution role
        """
        try:
            collection = self.aoss_client.create_collection(
                name=vector_store_name, type="VECTORSEARCH"
            )
            collection_id = collection["createCollectionDetail"]["id"]
            collection_arn = collection["createCollectionDetail"]["arn"]
        except self.aoss_client.exceptions.ConflictException:
            collection = self.aoss_client.batch_get_collection(
                names=[vector_store_name]
            )["collectionDetails"][0]
            pp.pprint(collection)
            collection_id = collection["id"]
            collection_arn = collection["arn"]
        pp.pprint(collection)

        # Get the OpenSearch serverless collection URL
        host = collection_id + "." + self.region_name + ".aoss.amazonaws.com"
        print(host)
        # wait for collection creation
        # This can take couple of minutes to finish
        response = self.aoss_client.batch_get_collection(names=[vector_store_name])
        # Periodically check collection status
        while (response["collectionDetails"][0]["status"]) == "CREATING":
            print("Creating collection...")
            interactive_sleep(30)
            response = self.aoss_client.batch_get_collection(names=[vector_store_name])
        print("\nCollection successfully created:")
        pp.pprint(response["collectionDetails"])
        # create opensearch serverless access policy and attach it to Bedrock execution role
        try:
            created = self.create_oss_policy_attach_bedrock_execution_role(
                collection_id, oss_policy_name, bedrock_kb_execution_role
            )
            if created:
                # It can take up to a minute for data access rules to be enforced
                print(
                    "Sleeping for a minute to ensure data access rules have been enforced"
                )
                interactive_sleep(60)
            return host, collection, collection_id, collection_arn
        except Exception as e:
            print("Policy already exists")
            pp.pprint(e)

    def create_vector_index(self, index_name: str):
        """
        Create OpenSearch Serverless vector index. If existent, ignore
        Args:
            index_name: name of the vector index
        """
        body_json = {
            "settings": {
                "index.knn": "true",
                "number_of_shards": 1,
                "knn.algo_param.ef_search": 512,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "vector": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "engine": "faiss",
                            "space_type": "l2",
                        },
                    },
                    "text": {"type": "text"},
                    "text-metadata": {"type": "text"},
                }
            },
        }

        # Create index
        try:
            response = self.oss_client.indices.create(
                index=index_name, body=json.dumps(body_json)
            )
            print("\nCreating index:")
            pp.pprint(response)

            # index creation can take up to a minute
            interactive_sleep(60)
        except RequestError as e:
            # you can delete the index if its already exists
            # oss_client.indices.delete(index=index_name)
            print(
                f"Error while trying to create the index, with error {e.error}\nyou may unmark the delete above to "
                f"delete, and recreate the index"
            )

    @retry(wait_random_min=1000, wait_random_max=2000, stop_max_attempt_number=7)
    def create_knowledge_base(
        self,
        collection_arn: str,
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
            collection_arn: ARN of the opensearch serverless collection
            index_name: name of the opensearch serverless index
            bucket_name: name of the s3 bucket containing the knowledge base data
            embedding_model: id of the embedding model used
            kb_name: knowledge base name
            kb_description: knowledge base description
            bedrock_kb_execution_role: knowledge base execution role

        Returns:
            knowledge base object,
            data source object
        """
        opensearch_serverless_configuration = {
            "collectionArn": collection_arn,
            "vectorIndexName": index_name,
            "fieldMapping": {
                "vectorField": "vector",
                "textField": "text",
                "metadataField": "text-metadata",
            },
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
                    "type": "OPENSEARCH_SERVERLESS",
                    "opensearchServerlessConfiguration": opensearch_serverless_configuration,
                },
            )
            kb = create_kb_response["knowledgeBase"]
            pp.pprint(kb)
        except self.bedrock_agent_client.exceptions.ConflictException:
            kbs = self.bedrock_agent_client.list_knowledge_bases(maxResults=100)
            kb_id = None
            for kb in kbs["knowledgeBaseSummaries"]:
                if kb["name"] == kb_name:
                    kb_id = kb["knowledgeBaseId"]
            response = self.bedrock_agent_client.get_knowledge_base(
                knowledgeBaseId=kb_id
            )
            kb = response["knowledgeBase"]
            pp.pprint(kb)

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
        delete_aoss: bool = True,
    ):
        """
        Delete the Knowledge Base resources
        Args:
            kb_name: name of the knowledge base to delete
            delete_s3_bucket (bool): boolean to indicate if s3 bucket should also be deleted
            delete_iam_roles_and_policies (bool): boolean to indicate if IAM roles and Policies should also be deleted
            delete_aoss: boolean to indicate if amazon opensearch serverless resources should also be deleted
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
        collection_id = kb_details["knowledgeBase"]["storageConfiguration"][
            "opensearchServerlessConfiguration"
        ]["collectionArn"].split("/")[1]
        index_name = kb_details["knowledgeBase"]["storageConfiguration"][
            "opensearchServerlessConfiguration"
        ]["vectorIndexName"]

        encryption_policies = self.aoss_client.list_security_policies(
            maxResults=100, type="encryption"
        )
        encryption_policy_name = None
        for ep in encryption_policies["securityPolicySummaries"]:
            if ep["name"].startswith(kb_name):
                encryption_policy_name = ep["name"]

        network_policies = self.aoss_client.list_security_policies(
            maxResults=100, type="network"
        )
        network_policy_name = None
        for np in network_policies["securityPolicySummaries"]:
            if np["name"].startswith(kb_name):
                network_policy_name = np["name"]

        data_policies = self.aoss_client.list_access_policies(
            maxResults=100, type="data"
        )
        access_policy_name = None
        for dp in data_policies["accessPolicySummaries"]:
            if dp["name"].startswith(kb_name):
                access_policy_name = dp["name"]

        ds_available = self.bedrock_agent_client.list_data_sources(
            knowledgeBaseId=kb_id,
            maxResults=100,
        )
        for ds in ds_available["dataSourceSummaries"]:
            if kb_id == ds["knowledgeBaseId"]:
                ds_id = ds["dataSourceId"]
        ds_details = self.bedrock_agent_client.get_data_source(
            dataSourceId=ds_id,
            knowledgeBaseId=kb_id,
        )
        bucket_name = ds_details["dataSource"]["dataSourceConfiguration"][
            "s3Configuration"
        ]["bucketArn"].replace("arn:aws:s3:::", "")
        try:
            self.bedrock_agent_client.delete_data_source(
                dataSourceId=ds_id, knowledgeBaseId=kb_id
            )
            print("Data Source deleted successfully!")
        except Exception as e:
            print(e)
        try:
            self.bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=kb_id)
            print("Knowledge Base deleted successfully!")
        except Exception as e:
            print(e)
        if delete_aoss:
            try:
                self.oss_client.indices.delete(index=index_name)
                print("OpenSource Serveless Index deleted successfully!")
            except Exception as e:
                print(e)
            try:
                self.aoss_client.delete_collection(id=collection_id)
                print("OpenSource Collection Index deleted successfully!")
            except Exception as e:
                print(e)
            try:
                self.aoss_client.delete_access_policy(
                    type="data", name=access_policy_name
                )
                print("OpenSource Serveless access policy deleted successfully!")
            except Exception as e:
                print(e)
            try:
                self.aoss_client.delete_security_policy(
                    type="network", name=network_policy_name
                )
                print("OpenSource Serveless network policy deleted successfully!")
            except Exception as e:
                print(e)
            try:
                self.aoss_client.delete_security_policy(
                    type="encryption", name=encryption_policy_name
                )
                print("OpenSource Serveless encryption policy deleted successfully!")
            except Exception as e:
                print(e)
        if delete_s3_bucket:
            try:
                self.delete_s3(bucket_name)
                print("Knowledge Base S3 bucket deleted successfully!")
            except Exception as e:
                print(e)
        if delete_iam_roles_and_policies:
            try:
                self.delete_iam_roles_and_policies(kb_role)
                print("Knowledge Base Roles and Policies deleted successfully!")
            except Exception as e:
                print(e)
        print("Resources deleted successfully!")

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
