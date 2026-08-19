"""Helper functions for CDK constructs"""

from aws_cdk import aws_apigateway as apigateway


def add_cors_options(resource: apigateway.Resource, methods: list[str]) -> None:
    """
    Add CORS OPTIONS method to an API Gateway resource.

    Args:
        resource: The API Gateway resource to add CORS to
        methods: List of HTTP methods to allow (e.g., ['GET', 'POST', 'OPTIONS'])
    """
    methods_str = ",".join(methods)

    resource.add_method(
        "OPTIONS",
        apigateway.MockIntegration(
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                        "method.response.header.Access-Control-Allow-Origin": "'*'",
                        "method.response.header.Access-Control-Allow-Methods": f"'{methods_str}'",
                    },
                )
            ],
            passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
            request_templates={"application/json": '{"statusCode": 200}'},
        ),
        method_responses=[
            apigateway.MethodResponse(
                status_code="200",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Headers": True,
                    "method.response.header.Access-Control-Allow-Origin": True,
                    "method.response.header.Access-Control-Allow-Methods": True,
                },
            )
        ],
    )
