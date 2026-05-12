#!/usr/bin/env python3
"""Export files from an AgentCore Code Interpreter session into the local workspace."""

from __future__ import annotations

import ast
import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from heurist_finance_agent.config import PROJECT_DIR

ARTIFACTS_DIR = PROJECT_DIR / "artifacts"

# Cap the amount of base64 payload we accept from the code interpreter so a
# runaway script cannot fill the local disk via this helper.
MAX_EXPORT_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB base64 blob
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_artifact_path(raw_name: str) -> Path:
    """Return a path inside ``ARTIFACTS_DIR`` that cannot escape it.

    The LLM agent supplies ``local_filename``. Without sanitization a value
    like ``../../etc/passwd`` would resolve outside the artifacts directory.
    We strip any directory components, reject empty / dot-only names, and
    allow-list a small set of characters safe for cross-platform filenames.
    """
    if not raw_name:
        raise ValueError("Artifact filename must not be empty")
    base = Path(raw_name).name  # drops any directory components
    base = _SAFE_FILENAME_RE.sub("_", base).strip("._") or ""
    if not base or base in {".", ".."}:
        raise ValueError(f"Unsafe artifact filename: {raw_name!r}")
    candidate = (ARTIFACTS_DIR / base).resolve()
    artifacts_root = ARTIFACTS_DIR.resolve()
    # Belt-and-suspenders: make sure the resolved path is still inside
    # the artifacts directory.
    try:
        candidate.relative_to(artifacts_root)
    except ValueError as exc:
        raise ValueError(
            f"Artifact path escapes artifacts directory: {raw_name!r}"
        ) from exc
    return candidate


def _extract_text_payload(tool_result: dict[str, Any]) -> str:
    content = tool_result.get("content", [])
    if not content:
        raise ValueError(f"Missing tool content: {tool_result}")
    text_blob = content[0].get("text")
    if not text_blob:
        raise ValueError(f"Missing text payload: {tool_result}")
    parsed = ast.literal_eval(text_blob)
    if not parsed or "text" not in parsed[0]:
        raise ValueError(f"Unexpected tool payload: {tool_result}")
    return parsed[0]["text"]


def _as_dict(value: Any) -> dict[str, Any] | None:
    """Return ``value`` if it is a dict, otherwise ``None``."""
    return value if isinstance(value, dict) else None


def _extract_json_payload(text: str) -> dict[str, Any]:
    """Parse ``text`` into a JSON object.

    The Code Interpreter runs our own script that does ``print(json.dumps(payload))``,
    so the output is always well-formed JSON. We parse it directly and reject
    non-dict top-level values so errors surface here with a clear message.
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty payload text")
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not parse JSON payload from Code Interpreter output: {text[:500]}"
        ) from exc
    if not isinstance(result, dict):
        raise ValueError(
            f"Expected a JSON object from Code Interpreter, got {type(result).__name__}: {text[:200]}"
        )
    return result


def export_code_interpreter_file(
    code_interpreter,
    remote_path: str,
    session_name: str,
    local_filename: str | None = None,
) -> dict[str, Any]:
    """Read a remote file as base64 within the interpreter and persist it locally."""
    export_code = f"""
import base64
import json
import mimetypes
from pathlib import Path

p = Path({remote_path!r})
if not p.exists():
    raise FileNotFoundError(str(p))

payload = {{
    "path": str(p),
    "name": p.name,
    "mime_type": mimetypes.guess_type(str(p))[0],
    "base64": base64.b64encode(p.read_bytes()).decode(),
}}
print(json.dumps(payload))
"""
    result = code_interpreter.code_interpreter(
        {
            "action": {
                "type": "executeCode",
                "session_name": session_name,
                "language": "python",
                "code": export_code,
            }
        }
    )
    payload_text = _extract_text_payload(result)
    payload = _extract_json_payload(payload_text)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_name = local_filename or payload.get("name")
    if not isinstance(output_name, str) or not output_name:
        raise ValueError("Exported payload did not include a usable filename")

    local_path = safe_artifact_path(output_name)

    encoded = payload.get("base64", "")
    if not isinstance(encoded, str):
        raise ValueError("Exported payload 'base64' field must be a string")
    if len(encoded) > MAX_EXPORT_PAYLOAD_BYTES:
        raise ValueError(
            f"Exported payload is {len(encoded)} bytes which exceeds the "
            f"{MAX_EXPORT_PAYLOAD_BYTES} byte limit."
        )
    local_path.write_bytes(base64.b64decode(encoded))

    return {
        "status": "success",
        "remote_path": payload.get("path"),
        "local_path": str(local_path),
        "mime_type": payload.get("mime_type")
        or mimetypes.guess_type(local_path.name)[0],
        "size_bytes": local_path.stat().st_size,
    }
