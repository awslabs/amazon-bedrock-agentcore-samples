import click
import boto3
from botocore.exceptions import ClientError
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType

# AWS clients
ssm = boto3.client("ssm")
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
def cli():
    """CLI for managing Bedrock Agent Memory"""
    pass


@cli.command()
@click.option(
    "--memory-name",
    default="CustomerSupportMemory",
    help="Name of the memory resource.",
)
@click.option(
    "--ssm-param",
    default="/app/customersupport/agentcore/memory_id",
    help="SSM parameter to store memory_id.",
)
def create(memory_name, ssm_param):
    """Create Bedrock Agent memory and store memory_id in SSM."""
    strategies = [
        {
            StrategyType.SUMMARY.value: {
                "name": "conversation_summary",
                "description": "Captures summaries of conversations",
                "namespaces": ["summaries/{actorId}/{sessionId}"],
            }
        }
    ]

    try:
        memory = memory_client.create_memory_and_wait(
            name=memory_name,
            strategies=strategies,
            description="Memory for customer support agent",
            event_expiry_days=30,
        )
        memory_id = memory["memoryId"]
        click.echo(f"✅ Created memory: {memory_id}")
    except Exception as e:
        if "already exists" in str(e):
            memories = memory_client.list_memories()
            memory_id = next(
                (m["memoryId"] for m in memories if memory_name in m["id"]), None
            )
            click.echo(f"✅ Using existing memory: {memory_id}")
        else:
            raise click.ClickException(f"❌ Error creating memory: {e}")

    store_memory_id_in_ssm(ssm_param, memory_id)


@cli.command()
@click.option("--memory-id", default=None, help="Memory ID to delete directly.")
@click.option(
    "--ssm-param",
    default="/app/customersupport/agentcore/memory_id",
    help="SSM parameter to retrieve memory_id from.",
)
@click.option(
    "--skip-ssm-delete", is_flag=True, help="Skip deleting the SSM parameter."
)
def delete(memory_id, ssm_param, skip_ssm_delete):
    """Delete Bedrock Agent memory by ID or via SSM. Optionally remove SSM parameter."""
    if not memory_id:
        try:
            memory_id = get_memory_id_from_ssm(ssm_param)
            click.echo(f"📥 Retrieved memory ID from SSM: {memory_id}")
        except Exception:
            click.echo(
                "⚠️ No memory ID provided and no SSM parameter found. Nothing to delete."
            )
            return

    try:
        memory_client.delete_memory(memory_id=memory_id)
        click.echo(f"✅ Deleted memory resource: {memory_id}")
    except Exception as e:
        click.echo(f"❌ Error deleting memory: {e}")

    if not skip_ssm_delete:
        delete_ssm_param(ssm_param)
    else:
        click.echo("⚠️ Skipping SSM parameter deletion as requested.")


@cli.command("list")
def list_memories():
    """List all Bedrock memory resources."""
    try:
        memories = memory_client.list_memories()
        if not memories:
            click.echo("ℹ️ No memory resources found.")
            return

        click.echo("🧠 Existing Memory Resources:")
        for mem in memories:
            click.echo(f"- Arn: {mem['arn']}, ID: {mem['memoryId']}")
    except Exception as e:
        raise click.ClickException(f"❌ Error listing memories: {e}")


if __name__ == "__main__":
    cli()
