from pathlib import Path

import requests
from strands import tool


class ConvertSchemaVersionTool:
    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()
        self.schema_path = self.workdir / "schema.yaml"

    @tool(description="Convert the OpenAPI schema file (schema.yaml) to OpenAPI 3.0.1 format.")
    def convert_openapi_schema_version(self) -> str:
        if not self.schema_path.exists():
            raise FileNotFoundError(self.schema_path.name)

        schema_content = self.schema_path.read_text()

        response = requests.post(
            "https://converter.swagger.io/api/convert",
            data=schema_content,
            headers={"Content-Type": "application/yaml", "Accept": "application/yaml"},
            timeout=120,
        )

        if response.status_code == 200:
            self.schema_path.write_text(response.text)
            return "Successfully converted schema.yaml to OpenAPI 3.0.1 format."
        else:
            return f"Conversion failed: {response.text}"
