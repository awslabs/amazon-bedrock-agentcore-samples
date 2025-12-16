import difflib
import re
from pathlib import Path

from strands import tool

# pylint:disable=line-too-long


TOOL_DESCRIPTION = """\
Editor tool designed to do changes iteratively on the schema.yaml file.

This tool provides a comprehensive interface for file operations on the schema.yaml file,
including viewing, modifying, and searching contents with rich output formatting.

COMMANDS:
--------------
1. preview:
    - Displays a preview of schema.yaml
    - By default, the first 50 lines will be shown when no parameters are specified
    - Supports viewing specific line ranges with `start_line` and `end_line`

2. search:
    - Finds lines matching `search_text`
    - Alternatively, specify regex `pattern` instead of `search_text` for matching regular expressions in each line
    - Shows `context_lines` around found lines

3. replace:
    - Replaces exact string matches (multi-line) from `old_str` to `new_str`
    - Alternatively, specify regex `pattern` instead of `old_str` for matching regular expressions in each line
    - Shows `context_lines` around replacements

4. insert:
    - Inserts text after a specified `insert_line` number
    - Supports finding insertion points by `insert_line` number or `search_text`
    - Shows `context_lines` around insertion point"""


TOOL_SCHEMA = {
    "json": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to be run: `preview`, `search`, `replace`, `insert`.",
                "enum": ["preview", "search", "replace", "insert"],
            },
            "old_str": {
                "type": "string",
                "description": "Optional parameter of `replace` command containing the exact string (multi-line) to replace.",
            },
            "new_str": {
                "type": "string",
                "description": "Required parameter containing the new string (multi-line) for `replace` and `insert` commands.",
            },
            "pattern": {
                "type": "string",
                "description": "Optional parameter of `search` and `replace` commands containing the regex pattern to match in each line.",
            },
            "search_text": {
                "type": "string",
                "description": "Exact text to search for in `search` command.",
            },
            "insert_line": {
                "type": "integer",
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line`.",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional parameter of `preview` command. Should ALWAYS be accompanied by `end_line`. Line range to show [start_line, end_line].",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional parameter of `preview` command. Should ALWAYS be accompanied by `start_line`. Line range to show [start_line, end_line].",
            },
            "context_lines": {
                "type": "integer",
                "description": "Optional parameter of `search`, `replace` and `insert` commands. Number of additional context lines to show around relevant lines.",
                "default": 2,
            },
        },
        "required": ["command"],
    }
}


def _format_lines(
    text_lines: list[str],
    start_line: int,
    end_line: int,
    context_lines: int,
    mark_relevant: bool = False,
) -> str:
    # Ensure start_line and end_line are within bounds
    relevant_index_start = max(0, start_line - 1)
    relevant_index_end = min(len(text_lines), end_line)

    # Adjust start_line and end_line based on context_lines
    context_index_start = max(0, relevant_index_start - context_lines)
    context_index_end = min(len(text_lines), relevant_index_end + context_lines)

    # Create a new list with context lines
    context = [
        f"{i + 1}: {line}"
        for i, line in zip(
            range(context_index_start, context_index_end),
            text_lines[context_index_start:context_index_end],
            strict=True,
        )
    ]

    if mark_relevant:
        prefix = [
            "→ " if relevant_index_start <= i < relevant_index_end else "  "
            for i in range(context_index_start, context_index_end)
        ]
        context = [f"{p}{line}" for p, line in zip(prefix, context, strict=True)]

    return "\n".join(context)


def _show_diff(old: list[str], new: list[str], context_lines: int = 2) -> str:
    diff = difflib.unified_diff(
        a=old, b=new, fromfile="Original", tofile="Modified", lineterm="", n=context_lines
    )
    return "\n".join(diff)


def preview(schema_path: Path, start_line: int | None = None, end_line: int | None = None) -> str:
    text_lines = schema_path.read_text().splitlines()

    if start_line is not None:
        if end_line is None:
            raise ValueError("end_line must be specified if start_line is specified")
        return _format_lines(text_lines, start_line, end_line, context_lines=0)

    num_lines = len(text_lines)
    num_lines_shown = min(50, num_lines)
    num_lines_skipped = num_lines - num_lines_shown

    suffix = f"\n... {num_lines_skipped} more lines ..." if num_lines_skipped > 0 else ""

    return _format_lines(text_lines, 1, 50, context_lines=0) + suffix


def search(
    schema_path: Path,
    search_text: str | None = None,
    pattern: str | None = None,
    context_lines: int = 2,
) -> list[str]:
    if search_text is None and pattern is None:
        raise ValueError("Either `search_text` or `pattern` must be specified")

    if search_text is not None and pattern is not None:
        raise ValueError("Cannot specify both `search_text` and `pattern`")

    search_results: list[str] = []

    text_lines = schema_path.read_text().splitlines()
    for i, line in enumerate(text_lines):
        if (search_text is not None and search_text in line) or (
            pattern is not None and re.search(pattern, line) is not None
        ):
            line_num = i + 1
            search_results.append(
                _format_lines(
                    text_lines,
                    start_line=line_num,
                    end_line=line_num,
                    context_lines=context_lines,
                    mark_relevant=True,
                )
            )

    return search_results


def replace(
    schema_path: Path,
    old_str: str | None = None,
    new_str: str | None = None,
    pattern: str | None = None,
    context_lines: int = 2,
) -> str:
    if old_str is None and pattern is None:
        raise ValueError("Either `old_str` or `pattern` must be specified")

    if old_str is not None and pattern is not None:
        raise ValueError("Cannot specify both `old_str` and `pattern`")

    if new_str is None:
        raise ValueError("`new_str` must be specified")

    text_lines = schema_path.read_text().splitlines()
    text_modified = "\n".join(text_lines)

    if old_str is not None:
        text_modified = text_modified.replace(old_str, new_str)

    if pattern is not None:
        text_modified = re.sub(pattern, new_str, text_modified)

    schema_path.write_text(text_modified)

    return _show_diff(old=text_lines, new=text_modified.splitlines(), context_lines=context_lines)


def insert(
    schema_path: Path,
    insert_line: int | None = None,
    new_str: str | None = None,
    context_lines: int = 2,
) -> str:
    if insert_line is None:
        raise ValueError("`insert_line` must be specified")

    if new_str is None:
        raise ValueError("`new_str` must be specified")

    new_str_lines = new_str.split("\n")

    original_text_lines = schema_path.read_text().splitlines()
    modified_text_lines = (
        original_text_lines[:insert_line] + new_str_lines + original_text_lines[insert_line:]
    )

    schema_path.write_text("\n".join(modified_text_lines))

    return _show_diff(old=original_text_lines, new=modified_text_lines, context_lines=context_lines)


class SchemaEditorTool:
    def __init__(self, context_dir: Path):
        self.context_dir = context_dir
        self.schema_path = context_dir / "schema.yaml"

        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

    @tool(description=TOOL_DESCRIPTION, inputSchema=TOOL_SCHEMA)
    def schema_editor(
        self,
        command: str,
        old_str: str | None = None,
        new_str: str | None = None,
        pattern: str | None = None,
        search_text: str | None = None,
        insert_line: int | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        context_lines: int = 2,
    ) -> dict:
        try:
            if command == "preview":
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": preview(
                                schema_path=self.schema_path,
                                start_line=start_line,
                                end_line=end_line,
                            )
                        }
                    ],
                }

            elif command == "search":
                search_results = search(
                    schema_path=self.schema_path,
                    search_text=search_text,
                    pattern=pattern,
                    context_lines=context_lines,
                )

                return {
                    "status": "success",
                    "content": (
                        [{"text": result} for result in search_results]
                        if len(search_results) > 0
                        else [{"text": "No matches found."}]
                    ),
                }

            elif command == "replace":
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": replace(
                                schema_path=self.schema_path,
                                old_str=old_str,
                                new_str=new_str,
                                pattern=pattern,
                                context_lines=context_lines,
                            )
                        }
                    ],
                }

            elif command == "insert":
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": insert(
                                schema_path=self.schema_path,
                                insert_line=insert_line,
                                new_str=new_str,
                                context_lines=context_lines,
                            )
                        }
                    ],
                }

            else:
                raise ValueError(f"Unknown command: {command}")

        except Exception as e:  # pylint:disable=broad-exception-caught
            return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}
