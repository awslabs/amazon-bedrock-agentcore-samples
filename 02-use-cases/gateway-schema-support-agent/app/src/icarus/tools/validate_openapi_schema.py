from pathlib import Path

import docker
from strands import tool

from icarus.utils.string_utils import preview_text


class ValidateSchemaTool:
    def __init__(self, mount_dir: Path):
        self.mount_dir = mount_dir.resolve()
        self.docker_client = docker.from_env()

        self.schema_path = self.mount_dir / "schema.yaml"
        self.ruleset_path = self.mount_dir / ".spectral.yaml"

    @tool(
        description="Validate the OpenAPI schema file (schema.yaml).",
        inputSchema={
            "json": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": (
                            "The maximum number of validation errors to return. [default: 100]"
                        ),
                        "default": 100,
                    },
                    "filter_keyword": {
                        "type": "string",
                        "description": (
                            "If provided, only return validation errors "
                            "that contain this keyword. [default: null]"
                        ),
                        "default": None,
                    },
                },
            }
        },
    )
    def validate_openapi_schema(self, limit: int = 100, filter_keyword: str | None = None) -> str:
        assert limit > 0, "limit must be greater than 0"

        for p in [self.ruleset_path, self.schema_path]:
            if not p.exists():
                raise FileNotFoundError(p.name)

        container = self.docker_client.containers.run(
            image="stoplight/spectral:latest",
            command=[
                "lint",
                "--verbose",
                "--ruleset",
                f"/tmp/{self.ruleset_path.name}",
                f"/tmp/{self.schema_path.name}",
            ],
            volumes={str(self.mount_dir): {"bind": "/tmp", "mode": "ro"}},
            detach=True,
            stdout=True,
            stderr=True,
        )

        container.wait()
        raw_output = container.logs(stdout=True, stderr=True).decode("utf-8").strip()
        container.remove()

        raw_output_lines = raw_output.strip().split("\n")
        raw_output_lines = [
            line.strip() for line in raw_output_lines if "/tmp/" not in line and line != ""
        ]

        status_line = raw_output_lines.pop()

        if filter_keyword is not None:
            raw_output_lines = [line for line in raw_output_lines if filter_keyword in line]

        raw_output_lines = [*raw_output_lines, status_line]

        return preview_text(
            text="\n".join(raw_output_lines),
            num_lines_start=min(limit, len(raw_output_lines) - 1),
            num_lines_end=1,  # always include the last line as it is the summary
        )
