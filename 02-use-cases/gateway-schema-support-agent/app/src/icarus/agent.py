import json
from pathlib import Path

from strands import Agent
from strands.experimental.hooks import BeforeToolInvocationEvent
from strands.hooks import HookProvider
from strands.hooks import HookRegistry
from strands.hooks.events import MessageAddedEvent
from strands.models.litellm import LiteLLMModel
from strands.types.content import Messages

from icarus.tools.convert_openapi_schema_version import ConvertSchemaVersionTool
from icarus.tools.python_interpreter import PythonInterpreterTool
from icarus.tools.schema_editor import SchemaEditorTool
from icarus.tools.schema_graph import SchemaGraphActions
from icarus.tools.validate_openapi_schema import ValidateSchemaTool
from icarus.utils.time_machine import TimeMachine

DEFAULT_MODEL_ID = "bedrock/converse/us.anthropic.claude-3-7-sonnet-20250219-v1:0"

SYSTEM_PROMPT = """\
You are an expert OpenAPI schema validation specialist. Your mission is to systematically identify and fix all validation errors in the provided OpenAPI schema file.

**Workflow:**
1. First, run the validate_openapi_schema tool to identify all current errors
2. For each error, use schema_editor preview command to examine the problematic sections (read small chunks, not entire file)
3. Alternatively, use schema_editor search command to locate specific patterns or related issues
4. Fix errors using appropriate methods:
   - Direct file editing for simple fixes
   - Python scripts via run_python_script tool for pattern-based bulk changes
5. Re-validate after each fix or batch of fixes
6. Continue until validate_openapi_schema returns no errors

**Important constraints:**
- If the OpenAPI version is incorrect, use the convert_openapi_schema_version tool first to convert the schema, and validate again
- The schema file may be extremely large - always read small sections only
- Ignore any validation warnings and focus only on fixing the validation errors
- Do not stop until ALL validation errors are resolved
- Verify each fix doesn't introduce new errors

**Schema file location (for run_python_script tool):**
/ctx/schema.yaml"""

DEFAULT_USER_MESSAGE = "Validate my OpenAPI schema and repair it if needed."


class TimeMachineCommitHook(HookProvider):
    def __init__(self, tm: TimeMachine):
        self.tm = tm

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(BeforeToolInvocationEvent, self.before_tool_invocation)

    def before_tool_invocation(
        self, event: BeforeToolInvocationEvent  # pylint:disable=unused-argument
    ):
        self.tm.commit()


class SaveMessagesHook(HookProvider):
    MESSAGES_FILE = "messages.json"

    def __init__(self, session_dir: Path):
        self.messages_path = session_dir / self.MESSAGES_FILE

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(MessageAddedEvent, self.save_messages)

    def save_messages(self, event: MessageAddedEvent):
        messages = event.agent.messages
        if len(messages):
            self.messages_path.write_text(json.dumps(messages, indent=2))


def init_agent(session_dir: Path, model_id: str = DEFAULT_MODEL_ID) -> Agent:
    session_dir = session_dir.resolve()
    schema_path = session_dir / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(schema_path)

    messages: Messages | None = None
    messages_path = session_dir / SaveMessagesHook.MESSAGES_FILE
    if messages_path.exists():
        messages = json.loads(messages_path.read_text())

    schema_graph_actions = SchemaGraphActions(context_dir=session_dir)

    model = LiteLLMModel(model_id=model_id)
    agent = Agent(
        model=model,
        messages=messages,
        system_prompt=SYSTEM_PROMPT,
        hooks=[TimeMachineCommitHook(tm=TimeMachine(schema_path)), SaveMessagesHook(session_dir)],
        state=dict(session_dir=str(session_dir)),
        tools=[
            ValidateSchemaTool(mount_dir=session_dir).validate_openapi_schema,
            ConvertSchemaVersionTool(workdir=session_dir).convert_openapi_schema_version,
            SchemaEditorTool(context_dir=session_dir).schema_editor,
            PythonInterpreterTool(context_dir=session_dir).make_tool(),
            schema_graph_actions.list_paths_related_to_component,
            schema_graph_actions.update_schema_extract_paths,
        ],
    )
    return agent
