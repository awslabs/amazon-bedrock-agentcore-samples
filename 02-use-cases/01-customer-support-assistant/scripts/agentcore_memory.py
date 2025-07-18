#!/usr/bin/python
import click
import boto3
import sys
from botocore.exceptions import ClientError
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from utils import get_aws_region

# AWS clients
REGION = get_aws_region()
ssm = boto3.client("ssm", region_name=REGION)
memory_client = MemoryClient()


def store_memory_id_in_ssm(param_name: str, memory_id: str):
    ssm.put_parameter(Name=param_name, Value=memory_id, Type="String", Overwrite=True)
    click.echo(f"🔐 Stored memory_id in SSM: {param_name}")


def get_memory_id_from_ssm(param_name: str):
    try:
        response = ssm.get_parameter(Name=param_name)
        return response["Parameter"]["Value"]
    except ClientError as e:
        raise click.ClickException(f"❌ Could not retrieve memory_id from SSM: {e}")


def delete_ssm_param(param_name: str):
    try:
        ssm.delete_parameter(Name=param_name)
        click.echo(f"🧹 Deleted SSM parameter: {param_name}")
    except ClientError as e:
        click.echo(f"⚠️ Failed to delete SSM parameter: {e}")


@click.group()
@click.pass_context
def cli(ctx):
    """AgentCore Memory Management CLI.

    Create and delete AgentCore memory resources for the customer support application.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--name", default="CustomerSupportMemory", help="Name of the memory resource"
)
@click.option(
    "--ssm-param",
    default="/app/customersupport/agentcore/memory_id",
    help="SSM parameter to store memory_id",
)
@click.option(
    "--event-expiry-days",
    default=30,
    type=int,
    help="Number of days before events expire (default: 30)",
)
def create(name, ssm_param, event_expiry_days):
    """Create a new AgentCore memory resource."""
    click.echo(f"🚀 Creating AgentCore memory: {name}")
    click.echo(f"📍 Region: {REGION}")
    click.echo(f"⏱️  Event expiry: {event_expiry_days} days")

    strategies = [
        {
            StrategyType.SEMANTIC.value: {
                "name": "fact_extractor",
                "description": "Extracts and stores factual information",
                "namespaces": ["support/user/{actorId}/facts"],
            },
        },
        {
            StrategyType.SUMMARY.value: {
                "name": "conversation_summary",
                "description": "Captures summaries of conversations",
                "namespaces": ["support/user/{actorId}/{sessionId}"],
            },
        },
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "user_preferences",
                "description": "Captures user preferences and settings",
                "namespaces": ["support/user/{actorId}/preferences"],
            },
        },
    ]

    try:
        click.echo("🔄 Creating memory resource...")
        memory = memory_client.create_memory_and_wait(
            name=name,
            strategies=strategies,
            description="Memory for customer support agent",
            event_expiry_days=event_expiry_days,
        )
        memory_id = memory["memoryId"]
        click.echo(f"✅ Memory created successfully: {memory_id}")

    except Exception as e:
        if "already exists" in str(e):
            click.echo("📋 Memory already exists, finding existing resource...")
            memories = memory_client.list_memories()
            memory_id = next(
                (m["memoryId"] for m in memories if name in m.get("name", "")), None
            )
            if memory_id:
                click.echo(f"✅ Using existing memory: {memory_id}")
            else:
                click.echo("❌ Could not find existing memory resource", err=True)
                sys.exit(1)
        else:
            click.echo(f"❌ Error creating memory: {str(e)}", err=True)
            sys.exit(1)

    try:
        store_memory_id_in_ssm(ssm_param, memory_id)
        click.echo("🎉 Memory setup completed successfully!")
        click.echo(f"   Memory ID: {memory_id}")
        click.echo(f"   SSM Parameter: {ssm_param}")

    except Exception as e:
        click.echo(f"⚠️  Memory created but failed to store in SSM: {str(e)}", err=True)


@cli.command()
@click.option(
    "--memory-id",
    help="Memory ID to delete (if not provided, will read from SSM parameter)",
)
@click.option(
    "--ssm-param",
    default="/app/customersupport/agentcore/memory_id",
    help="SSM parameter to retrieve memory_id from",
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete(memory_id, ssm_param, confirm):
    """Delete an AgentCore memory resource."""

    # If no memory ID provided, try to read from SSM
    if not memory_id:
        try:
            memory_id = get_memory_id_from_ssm(ssm_param)
            click.echo(f"📖 Using memory ID from SSM: {memory_id}")
        except Exception:
            click.echo(
                "❌ No memory ID provided and couldn't read from SSM parameter",
                err=True,
            )
            sys.exit(1)

    # Confirmation prompt
    if not confirm:
        if not click.confirm(
            f"⚠️  Are you sure you want to delete memory {memory_id}? This action cannot be undone."
        ):
            click.echo("❌ Operation cancelled")
            sys.exit(0)

    click.echo(f"🗑️  Deleting memory: {memory_id}")

    try:
        memory_client.delete_memory(memory_id=memory_id)
        click.echo(f"✅ Memory deleted successfully: {memory_id}")
    except Exception as e:
        click.echo(f"❌ Error deleting memory: {str(e)}", err=True)
        sys.exit(1)

    # Always delete SSM parameter
    delete_ssm_param(ssm_param)
    click.echo("🎉 Memory and SSM parameter deleted successfully")


if __name__ == "__main__":
    cli()
