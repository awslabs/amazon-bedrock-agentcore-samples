# AWS Skills

| Information         | Details                                                                  |
|:--------------------|:-------------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                         |
| Agent type          | AWS engineering assistant                                                |
| Agentic Framework   | None (direct boto3)                                                      |
| LLM model           | Anthropic Claude Haiku 4.5                                               |
| Tutorial components | AgentCore harness — `skills` parameter, native `awsSkills` source        |
| Example complexity  | Intermediate                                                             |

## Overview

Give a harness agent native **AWS Skills** — curated capability bundles from the
[AWS Agent Toolkit](https://github.com/aws/agent-toolkit-for-aws) that are baked
into the harness runtime image. You enable them declaratively in the `skills`
parameter; there is nothing to install on the VM.

This is the zero-install counterpart to [05-agent-skills](../05-agent-skills),
which hand-installs custom skills onto the VM with `npx`.

## What are AWS Skills?

Skills bundle instructions, reference docs, and code templates for a specific AWS
domain (serverless, CloudFormation, observability, cost management, ...). They are
especially valuable with smaller/cheaper models that don't carry deep AWS
knowledge — the skill supplies the patterns the model needs.

Each entry in the `skills` array is a union; the `awsSkills` member selects skills
from the toolkit:

```python
# Enable every AWS Skill
skills=[{"awsSkills": {}}]

# Enable a whole category by glob
skills=[{"awsSkills": {"paths": ["core-skills/*"]}}]

# Enable one specific skill
skills=[{"awsSkills": {"paths": [
    "specialized-skills/operations-skills/troubleshooting-application-failures"]}}]

# Mix multiple AWS Skill selections (and other skill sources)
skills=[
    {"awsSkills": {"paths": ["core-skills/aws-serverless"]}},
    {"awsSkills": {"paths": ["core-skills/aws-cdk"]}},
]
```

`core-skills/*` includes domains like `amazon-bedrock`, `aws-cdk`,
`aws-serverless` (Lambda, API Gateway, Step Functions, SAM), `aws-observability`,
`aws-billing-and-cost-management`, and the language SDK usage skills. Skills can be
set on the harness resource (so they apply to every invocation) or passed per
`invoke_harness` call.

## Sample Prompts

**Prompt** (`--mode glob`, default): "What AWS skills do you have available? Give a short bulleted summary by category."
**Expected Behavior**: Agent lists the `core-skills/*` it loaded, grouped by category.

**Prompt** (`--mode mixed`): "Design a Step Functions state machine for order processing and outline the CDK stack."
**Expected Behavior**: Agent draws on the `aws-serverless` and `aws-cdk` skills to propose a design.

## Key Concepts

**Zero install**: Unlike custom skills, AWS Skills require no `npx`/VM step — set them on the harness and they're ready on first invocation.

**Selection modes**: `--mode all | glob | specific | mixed` map to the four `awsSkills` shapes above.

**Resource vs. per-call**: This sample sets skills at create time. You can also pass `skills=` on `invoke_harness` to apply them to a single call.

## Clean Up

```python
control.delete_harness(harnessId=harness_id)
from utils.iam import delete_harness_role
delete_harness_role()
```

The script deletes the harness automatically on exit (pass `--skip-cleanup` to keep it).

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
# Default — enable core-skills/* and summarize
python aws_skills.py

# Enable every AWS Skill
python aws_skills.py --mode all

# One named skill
python aws_skills.py --mode specific \
    --skill-path specialized-skills/operations-skills/troubleshooting-application-failures

# Combine serverless + CDK skills with a build task
python aws_skills.py --mode mixed \
    -m "Design a Step Functions state machine for order processing and outline the CDK stack."
```
