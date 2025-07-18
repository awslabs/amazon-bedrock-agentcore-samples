#!/usr/bin/python

import json
import click
from bedrock_agentcore.memory import MemoryClient
from strands import Agent
from strands_tools import calculator
import sys
import os
import uuid
import time
from strands.models import BedrockModel
import boto3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent_config.memory_hook_provider import MemoryHook
from scripts.utils import get_ssm_parameter

# Session & actor configuration
ACTOR_ID = "default"
SESSION_ID = str(uuid.uuid4())
MEMORY_ID = get_ssm_parameter("/app/customersupport/agentcore/memory_id")

model = BedrockModel(
    model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
)

memory_client = boto3.client("bedrock-agentcore")


def setup_agent():
    """Setup agent with memory and tools"""
    memory_client = MemoryClient()
    memory_hooks = MemoryHook(
        memory_client=memory_client,
        memory_id=MEMORY_ID,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
    )

    agent = Agent(
        hooks=[memory_hooks],
        tools=[calculator],
        system_prompt="You are a helpful personal assistant.",
        model=model,
        callback_handler=None,
    )

    return agent, memory_client


@click.group()
def cli():
    """Memory Testing CLI for Customer Support Assistant"""
    pass


@cli.command()
def load_conversation():
    """Load and execute predefined mock conversations to test long-term memory"""
    conversations = [
        "Hi, how are you doing?",
        "My name is John Smith and I'm having trouble with my account login. Can you help me?",
        "I'm trying to reset my password but I'm not receiving the verification email.",
        "My email address is john.smith@email.com and my account was created about 6 months ago.",
        "Actually, let me also mention that I have a premium subscription plan.",
        "Can you calculate what 15% of 240 would be? I need to figure out my discount.",
        "Great! Now back to my login issue - I remember my username is johnsmith123.",
        "I also want to update my billing address to 123 Main Street, New York, NY 10001.",
        "By the way, do you remember what my subscription plan type is?",
        "Perfect! Can you summarize all the information we discussed about my account today?",
    ]

    click.echo("=== Testing Long-term Memory with Mock Conversations ===")
    click.echo(f"Session ID: {SESSION_ID}")
    click.echo(f"Actor ID: {ACTOR_ID}")
    click.echo("=" * 60)

    for i, conversation in enumerate(conversations, 1):
        agent, _ = setup_agent()
        click.echo(f"\n[{i}/10] You > {conversation}")

        try:
            response = str(agent(conversation))
            click.echo(f"Agent > {response}")
        except Exception as e:
            click.echo(f"❌ Error: {e}")

        # Add a small delay between conversations to simulate real interaction
        time.sleep(1)

    click.echo("\n" + "=" * 60)
    click.echo("=== Memory Test Complete ===")


@cli.command()
@click.argument("prompt", type=str)
def load_prompt(prompt):
    """Load a custom prompt from user input and execute it with memory"""
    click.echo("=== Processing Custom Prompt ===")
    click.echo(f"Session ID: {SESSION_ID}")
    click.echo(f"Actor ID: {ACTOR_ID}")
    click.echo("=" * 40)

    agent, _ = setup_agent()

    click.echo(f"You > {prompt}")

    try:
        response = agent(prompt)
        click.echo(f"Agent > {response}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

    click.echo("=" * 40)
    click.echo("✓ Custom prompt processed successfully")


@cli.command()
def list_memory():
    """List all memory entries (not implemented yet)"""
    click.echo("=== Memory List Command ===")
    click.echo(f"Session ID: {SESSION_ID}")
    click.echo(f"Actor ID: {ACTOR_ID}")
    click.echo("=" * 30)

    list_sessions = memory_client.list_sessions(
        memoryId=MEMORY_ID, actorId=ACTOR_ID, maxResults=3
    )

    click.echo("All Sessions")
    first_session = None
    for list_session in list_sessions["sessionSummaries"]:
        click.echo(f"Session ID: {list_session['sessionId']}")
        if not first_session:
            first_session = list_session["sessionId"]

    click.echo("=" * 30)

    click.echo(f"Events for session: {first_session}")
    list_events = memory_client.list_events(
        memoryId=MEMORY_ID,
        sessionId=first_session,
        actorId=ACTOR_ID,
        includePayloads=True,
    )
    click.echo(json.dumps(list_events["events"], indent=2, default=str))
    # for list_event in list_events["events"]:
    #     click.echo(f"Session ID: {list_session['sessionId']}")
    #     if not first_session:
    #         first_session = list_session["sessionId"]

    click.echo("=" * 30)

    click.echo(f"Actor facts {ACTOR_ID}")
    list_memory_records = memory_client.list_memory_records(
        memoryId=MEMORY_ID,
        namespace=f"support/user/{ACTOR_ID}/facts",
    )

    for list_memory_record in list_memory_records["memoryRecordSummaries"]:
        click.echo(f"Content: {list_memory_record['content']['text']}")

    click.echo("=" * 30)

    click.echo(f"Conversation Summary for {first_session}")
    list_memory_records = memory_client.list_memory_records(
        memoryId=MEMORY_ID,
        namespace=f"support/user/{ACTOR_ID}/{first_session}",
    )

    for list_memory_record in list_memory_records["memoryRecordSummaries"]:
        click.echo(f"Content: {list_memory_record['content']['text'][:200]}...")

    click.echo("=" * 30)

    click.echo(f"User Preferences {ACTOR_ID}")
    list_memory_records = memory_client.list_memory_records(
        memoryId=MEMORY_ID,
        namespace=f"support/user/{ACTOR_ID}/preferences",
    )

    for list_memory_record in list_memory_records["memoryRecordSummaries"]:
        click.echo(f"Content: {list_memory_record['content']['text']}")

    click.echo("=" * 30)


if __name__ == "__main__":
    cli()
