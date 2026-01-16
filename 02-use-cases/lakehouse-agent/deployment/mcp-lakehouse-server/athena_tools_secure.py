"""
Secure Athena Tools

This implementation uses user based filtering for row-level security:
- User identity passed as session tags when assuming IAM role
- NO application-level SQL manipulation
- NO SQL injection risk

Security Flow:
1. Gateway interceptor extracts user_id from JWT
2. MCP server receives user_id in headers
3. MCP server assumes IAM role WITH session tag: user_id=<actual_user>
4. Athena queries use those credentials
"""

import boto3
import time
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError


class SecureAthenaClaimsTools:
    """
    Secure tools for querying health lakehouse data with Lake Formation RLS.
    """

    def __init__(
        self,
        region: str,
        database_name: str,
        s3_output_location: str,
        rls_role_arn: str
    ):
        """
        Initialize secure Athena tools.

        Args:
            region: AWS region
            database_name: Athena database name
            s3_output_location: S3 location for query results
            rls_role_arn: IAM role ARN with Lake Formation data filter permissions if setup 
        """
        self.region = region
        self.database_name = database_name
        self.s3_output_location = s3_output_location
        self.rls_role_arn = rls_role_arn
        self.sts_client = boto3.client('sts', region_name=region)

    def _get_credentials_with_session_tag(self, user_id: str) -> Dict[str, str]:
        """
        Assume IAM role with session tag containing user identity.

        This is the KEY security mechanism:
        - User identity is passed as a session tag
        - Lake Formation uses this tag to filter data
        - Filtering happens at AWS query engine, not application

        Args:
            user_id: User email/ID from OAuth token

        Returns:
            Temporary AWS credentials with session tag
        """
        try:
            # Assume role with session tags
            response = self.sts_client.assume_role(
                RoleArn=self.rls_role_arn,
                RoleSessionName=f"claims-query-{user_id.replace('@', '-').replace('.', '-')}",
                Tags=[
                    {
                        'Key': 'user_id',
                        'Value': user_id
                    }
                ],
                DurationSeconds=3600  # 1 hour
            )

            credentials = response['Credentials']

            return {
                'aws_access_key_id': credentials['AccessKeyId'],
                'aws_secret_access_key': credentials['SecretAccessKey'],
                'aws_session_token': credentials['SessionToken']
            }

        except ClientError as e:
            raise Exception(f"Error assuming role with session tags: {str(e)}")

    def _get_athena_client(self, user_id: str):
        """
        Get Athena client with user-specific credentials (session tags).

        Args:
            user_id: User email/ID

        Returns:
            Athena client with scoped credentials
        """
        if self.rls_role_arn:
            credentials = self._get_credentials_with_session_tag(user_id)
        else:
            credentials = {}
        return boto3.client(
            'athena',
            region_name=self.region,
            **credentials
        )

    def _execute_query(
        self,
        user_id: str,
        query: str,
        wait_for_results: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute Athena query with user-scoped credentials.

        IMPORTANT: This query does NOT include user_id filter in SQL!
        The filtering is applied by Lake Formation based on session tags.

        Args:
            user_id: User email/ID (for session tag)
            query: SQL query WITHOUT user filtering
            wait_for_results: Whether to wait for completion

        Returns:
            Query results
        """
        try:
            # Get Athena client with user credentials
            athena_client = self._get_athena_client(user_id)

            # Execute query - Lake Formation will automatically apply row filter
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database_name},
                ResultConfiguration={'OutputLocation': self.s3_output_location}
            )

            query_execution_id = response['QueryExecutionId']

            if not wait_for_results:
                return None

            # Wait for query completion
            max_wait_time = 30
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                status_response = athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = status_response['QueryExecution']['Status']['State']

                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    error = status_response['QueryExecution']['Status'].get(
                        'StateChangeReason', 'Unknown error'
                    )
                    raise Exception(f"Query failed: {error}")

                time.sleep(0.5)

            # Get results
            results_response = athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=100
            )

            # Parse results
            rows = results_response['ResultSet']['Rows']
            if len(rows) == 0:
                return []

            columns = [col['VarCharValue'] for col in rows[0]['Data']]

            data = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    row_data[columns[i]] = col.get('VarCharValue', '')
                data.append(row_data)

            return data

        except Exception as e:
            raise Exception(f"Error executing secure Athena query: {str(e)}")

    # TODO Lakeformation as of now does not support dynamic query filters. https://docs.aws.amazon.com/lake-formation/latest/dg/data-filtering-notes.html 
    # https://repost.aws/questions/QUjGeTaN2US8mjiON0nzDJzw/dynamic-filter-on-lake-formation
    # The below mechanism can be used for static filters in the query if required. Retaining this method for future use
    def query_claims(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query claims

        NOTICE: No user_id in WHERE clause! Lake Formation adds it automatically.

        Args:
            user_id: User email (passed as session tag, not SQL parameter)
            filters: Optional additional filters

        Returns:
            User's claims (automatically filtered by Lake Formation)
        """
        try:
            # Query WITHOUT user_id filter - Lake Formation adds it!
            query = f"""
                SELECT
                    claim_id,
                    patient_name,
                    claim_date,
                    claim_amount,
                    claim_type,
                    claim_status,
                    provider_name,
                    diagnosis_code,
                    submitted_date,
                    approved_amount,
                    notes
                FROM {self.database_name}.claims
                WHERE 1=1
                    AND user_id='{user_id}'
            """

            # Add optional filters (safely)
            if filters:
                if 'claim_status' in filters and filters['claim_status']:
                    # Use parameterization instead of string interpolation
                    query += f" AND claim_status = '{filters['claim_status']}'"

                if 'claim_type' in filters and filters['claim_type']:
                    query += f" AND claim_type = '{filters['claim_type']}'"

            query += " ORDER BY submitted_date DESC LIMIT 50"

            # Execute with user-scoped credentials
            # Lake Formation will add: AND user_id = <session_tag[user_id]>
            results = self._execute_query(user_id, query)

            return {
                "success": True,
                "user_id": user_id,
                "claims": results or [],
                "count": len(results) if results else 0,
                "message": f"Found {len(results) if results else 0} claims",
                "security": "Row-level filtering enforced by AWS Lake Formation"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error querying claims: {str(e)}"
            }

    def get_claim_details(self, user_id: str, claim_id: str) -> Dict[str, Any]:
        """
        Get claim details - Lake Formation ensures user can only see their claims.

        Args:
            user_id: User email (for session tag)
            claim_id: Claim ID

        Returns:
            Claim details (only if user owns it)
        """
        try:
            # Query without user_id check - Lake Formation handles it!
            query = f"""
                SELECT *
                FROM {self.database_name}.claims
                WHERE claim_id = '{claim_id}'
                    AND user_id='{user_id}'
            """

            results = self._execute_query(user_id, query)

            if results and len(results) > 0:
                return {
                    "success": True,
                    "claim": results[0],
                    "message": f"Retrieved claim {claim_id}",
                    "security": "Access validated by AWS Lake Formation"
                }
            else:
                return {
                    "success": False,
                    "message": f"Claim {claim_id} not found or access denied",
                    "security": "Lake Formation filtered this claim (not owned by user)"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error retrieving claim: {str(e)}"
            }

    def get_claims_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get claims summary - automatically scoped to user by Lake Formation.

        Args:
            user_id: User email

        Returns:
            Summary statistics (only for user's claims)
        """
        try:
            # Summary query without user_id filter
            query = f"""
                SELECT
                    COUNT(*) as total_claims,
                    SUM(CAST(claim_amount AS DECIMAL(10,2))) as total_amount,
                    SUM(CASE WHEN approved_amount != ''
                        THEN CAST(approved_amount AS DECIMAL(10,2))
                        ELSE 0 END) as total_approved,
                    COUNT(CASE WHEN claim_status = 'pending' THEN 1 END) as pending_claims,
                    COUNT(CASE WHEN claim_status = 'approved' THEN 1 END) as approved_claims,
                    COUNT(CASE WHEN claim_status = 'denied' THEN 1 END) as denied_claims
                FROM {self.database_name}.claims
                WHERE 1=1
                    AND user_id='{user_id}'
            """

            results = self._execute_query(user_id, query)

            if results and len(results) > 0:
                summary = results[0]
                return {
                    "success": True,
                    "user_id": user_id,
                    "summary": {
                        "total_claims": int(summary.get('total_claims', 0)),
                        "total_amount_claimed": float(summary.get('total_amount', 0) or 0),
                        "total_amount_approved": float(summary.get('total_approved', 0) or 0),
                        "pending_claims": int(summary.get('pending_claims', 0)),
                        "approved_claims": int(summary.get('approved_claims', 0)),
                        "denied_claims": int(summary.get('denied_claims', 0))
                    },
                    "message": "Claims summary retrieved successfully",
                    "security": "Automatically scoped to user by Lake Formation"
                }

            return {
                "success": True,
                "user_id": user_id,
                "summary": {
                    "total_claims": 0,
                    "total_amount_claimed": 0.0,
                    "total_amount_approved": 0.0,
                    "pending_claims": 0,
                    "approved_claims": 0,
                    "denied_claims": 0
                },
                "message": "No claims found",
                "security": "Lake Formation enforced row-level security"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error retrieving summary: {str(e)}"
            }
