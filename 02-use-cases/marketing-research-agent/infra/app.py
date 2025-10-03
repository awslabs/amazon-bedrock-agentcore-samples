import os
import aws_cdk as cdk
from src.marketing_research_stack import MarketingResearchStack


app = cdk.App()

env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1'))

ecr_repository_arn = os.getenv('ECR_REPOSITORY_ARN')
if not ecr_repository_arn:
    raise ValueError("ECR_REPOSITORY_ARN environment variable is not set")

MarketingResearchStack(app, "MarketingResearchStack",
    ecr_repository_arn=ecr_repository_arn,
    env=env
)

app.synth()
