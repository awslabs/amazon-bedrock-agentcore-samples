
import asyncio
import json
import os
from typing import Optional

import httpx
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent, tool

# Environment configuration
os.environ["STRANDS_OTEL_ENABLE_CONSOLE_EXPORT"] = "true"
os.environ["OTEL_PYTHON_EXCLUDED_URLS"] = "/ping,/invocations"

# Global token storage (could be improved with a proper state management solution)
github_access_token: Optional[str] = None

app = BedrockAgentCoreApp()


@tool
def inspect_github_repos() -> str:
    """Inspect and list the user's private GitHub repositories.

    Returns:
        str: A JSON string containing the list of repositories and their details,
            or an authentication required message.
    """
    global github_access_token

    if not github_access_token:
        return json.dumps({
            "auth_required": True,
            "message": "GitHub authentication is required. Please wait while we set up the authorization.",
            "events": []
        })

    print(f"Using GitHub access token: {github_access_token[:10]}...")

    headers = {"Authorization": f"Bearer {github_access_token}"}

    try:
        with httpx.Client() as client:
            # Get user information
            user_response = client.get("https://api.github.com/user", headers=headers)
            user_response.raise_for_status()
            username = user_response.json().get("login", "Unknown")
            print(f"✅ User: {username}")

            # Search for user's repositories
            repos_response = client.get(
                f"https://api.github.com/search/repositories?q=user:{username}",
                headers=headers
            )
            repos_response.raise_for_status()
            repos_data = repos_response.json()
            print(f"✅ Found {len(repos_data.get('items', []))} repositories")

            repos = repos_data.get('items', [])
            if not repos:
                return f"No repositories found for {username}."

            # Format repository information
            response_lines = [f"GitHub repositories for {username}:\n"]

            for repo in repos:
                repo_line = f"📁 {repo['name']}"
                if repo.get('language'):
                    repo_line += f" ({repo['language']})"
                repo_line += f" - ⭐ {repo['stargazers_count']}"
                response_lines.append(repo_line)

                if repo.get('description'):
                    response_lines.append(f"   {repo['description']}")
                response_lines.append("")  # Empty line for spacing

            return "\n".join(response_lines)

    except httpx.HTTPStatusError as e:
        return f"GitHub API error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error fetching GitHub repositories: {str(e)}"


class StreamingQueue:
    """Simple async queue for streaming responses."""

    def __init__(self):
        self._queue = asyncio.Queue()
        self._finished = False

    async def put(self, item: str) -> None:
        """Add an item to the queue."""
        await self._queue.put(item)

    async def finish(self) -> None:
        """Mark the queue as finished and add sentinel value."""
        self._finished = True
        await self._queue.put(None)

    async def stream(self):
        """Stream items from the queue until finished."""
        while True:
            item = await self._queue.get()
            if item is None and self._finished:
                break
            yield item


# Initialize streaming queue
queue = StreamingQueue()


async def on_auth_url(url: str) -> None:
    """Callback for authentication URL."""
    print(f"Authorization URL: {url}")
    await queue.put(f"Authorization URL: {url}")


def extract_response_text(response) -> str:
    """Extract text content from agent response."""
    if isinstance(response.message, dict):
        content = response.message.get('content', [])
        if isinstance(content, list):
            return "".join(
                item.get('text', '') for item in content
                if isinstance(item, dict) and 'text' in item
            )
    return str(response.message)


def needs_authentication(response_text: str) -> bool:
    """Check if response indicates authentication is required."""
    auth_keywords = [
        "authentication", "authorize", "authorization", "auth",
        "sign in", "login", "access", "permission", "credential",
        "need authentication", "requires authentication"
    ]
    return any(keyword.lower() in response_text.lower() for keyword in auth_keywords)


async def agent_task(user_message: str) -> None:
    """Execute agent task with authentication handling."""
    global github_access_token

    try:
        await queue.put("Begin agent execution")

        # Initial agent call
        response = agent(user_message)
        response_text = extract_response_text(response)

        # Check if authentication is needed
        if needs_authentication(response_text):
            await queue.put("Authentication required for GitHub access. Starting authorization flow...")

            try:
                github_access_token = await need_token_3LO_async(access_token='')
                await queue.put("Authentication successful! Retrying GitHub request...")

                # Retry with authentication
                response = agent(user_message)
            except Exception as auth_error:
                print(f"Authentication error: {auth_error}")
                await queue.put(f"Authentication failed: {str(auth_error)}")
                return

        await queue.put(response.message)
        await queue.put("End agent execution")

    except Exception as e:
        await queue.put(f"Error: {str(e)}")
    finally:
        await queue.finish()


@requires_access_token(
    provider_name="github-provider",
    scopes=["repo", "read:user"],
    auth_flow='USER_FEDERATION',
    on_auth_url=on_auth_url,
    force_authentication=False,  # ← Changed to False - will use cached token!
    callback_url="http://localhost:9090/oauth2/callback"  # ← Callback URL determined from notebook environment
)
async def need_token_3LO_async(*, access_token: str) -> str:
    """Handle 3LO authentication flow."""
    global github_access_token
    github_access_token = access_token
    return access_token


# Create agent instance
agent = Agent(
    model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    tools=[inspect_github_repos],
    system_prompt="""You are a GitHub assistant. Use the inspect_github_repos tool to fetch private repositories data.
    The inspect_github_repos tool handles token exchange and proper authentication with the GitHub API 
    to obtain private information for the user."""
)


@app.entrypoint
async def agent_invocation(payload):
    """Main entrypoint for agent invocation."""
    user_message = payload.get(
        "prompt",
        "No prompt found in input, please guide customer to create a JSON payload with prompt key"
    )

    # Create and start the agent task
    task = asyncio.create_task(agent_task(user_message))

    async def stream_with_task():
        """Stream results while ensuring task completion."""
        async for item in queue.stream():
            yield item
        await task  # Ensure task completes

    return stream_with_task()


if __name__ == "__main__":
    app.run()
