"""cdk-nag suppressions for the IT Incident Response Agent sample.

This is an educational sample. Production deployments should review and
address every finding rather than rely on these blanket suppressions.
"""

from cdk_nag import NagSuppressions

SAMPLE_SUPPRESSIONS = [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "AWS managed policies used for sample simplicity",
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Wildcard resources used for sample clarity; restrict in production",
    },
    {"id": "AwsSolutions-L1", "reason": "Lambda runtime acceptable for sample"},
    {"id": "AwsSolutions-Lambda4", "reason": "DLQ not required for sample Lambda"},
    {"id": "AwsSolutions-Lambda6", "reason": "Reserved concurrency not set for sample"},
    {"id": "AwsSolutions-S1", "reason": "S3 access logging not required for sample"},
    {"id": "AwsSolutions-S10", "reason": "Public-access deny simplified for sample"},
    {"id": "AwsSolutions-DDB3", "reason": "PITR not required for sample data"},
    {"id": "AwsSolutions-SNS2", "reason": "SNS encryption-in-transit only for sample"},
    {"id": "AwsSolutions-SNS3", "reason": "SNS topic-level KMS optional for sample"},
    {"id": "AwsSolutions-SMG4", "reason": "Secret rotation not required for sample"},
    {"id": "AwsSolutions-CWL3", "reason": "Log group KMS CMK optional for sample"},
]


def apply_nag_suppressions(stack) -> None:
    NagSuppressions.add_stack_suppressions(stack, SAMPLE_SUPPRESSIONS)
