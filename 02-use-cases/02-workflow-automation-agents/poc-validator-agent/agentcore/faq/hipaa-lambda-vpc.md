# Why does a HIPAA workload need Lambda inside a VPC?

Lambda functions that touch PHI (protected health information) — reading from
or writing to an RDS instance, a DynamoDB table storing patient records, or
any data store classified as in-scope for HIPAA — must run inside a VPC with
private subnets, not the default Lambda execution environment.

**Why it matters:** outside a VPC, a Lambda function's outbound traffic
traverses the public AWS network path rather than a customer-controlled
network boundary. HIPAA's Security Rule (45 CFR 164.312) expects
demonstrable access controls and network segmentation around ePHI. Reviewers
and auditors treat "Lambda not in VPC, but touches PHI" as a finding on
every HIPAA-scoped review, not an edge case.

**What to check for:** the Lambda function's VPC configuration
(`VpcConfig.SubnetIds`, `VpcConfig.SecurityGroupIds`) must be set, the
subnets must be private (no route to an Internet Gateway), and if the
function needs to reach other AWS services (S3, Secrets Manager, KMS) it
needs VPC endpoints or a NAT Gateway — otherwise the function will deploy
successfully and then fail at runtime with a timeout, which is a much more
confusing failure to debug than catching the missing VPC config at review
time.
