import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import docker
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool

DEFAULT_DOCKERFILE = """\
FROM python:3.12.11-alpine3.21
VOLUME /ctx
RUN pip install PyYAML
"""


class PythonInterpreterTool:
    def __init__(self, context_dir: Path, dockerfile: str = DEFAULT_DOCKERFILE):
        if "\nVOLUME /ctx\n" not in dockerfile:
            raise ValueError("dockerfile must contain a VOLUME /ctx directive")

        self.context_dir = context_dir.resolve()
        self.docker_client = docker.from_env()

        self.dockerfile = dockerfile
        dockerfile_hash = hashlib.sha256(dockerfile.encode()).hexdigest()[:5]
        docker_image_tag = f"icarus:python_interpreter-{dockerfile_hash}"

        # Build docker image
        with TemporaryDirectory() as tmp_dir:
            ctx_dir = Path(tmp_dir)
            dockerfile_path = ctx_dir / "Dockerfile"
            dockerfile_path.write_text(dockerfile)

            self.docker_image, _ = self.docker_client.images.build(
                path=str(ctx_dir), tag=docker_image_tag, rm=True
            )

    def make_tool(self) -> DecoratedFunctionTool:
        @tool(
            description=(
                "Executes Python code and returns the script's output. "
                "The script has read/write access to any data files located in the /ctx directory. "
                "This tool is useful for data processing, calculations, and file operations. "
                "\n\n"
                "Note that the execution environment is isolated for security using docker "
                "(see the docker image build directives below):\n"
                f"```dockerfile\n{self.dockerfile.strip()}\n```"
                "\n\n"
                "EXAMPLES:\n"
                "- run_python_script(code=\"print('Hello, World!')\")\n"
                "- run_python_script(code=\"import json\\n\\n\\nwith open('/ctx/data.json', 'r') as f:\\n    data = json.load(f)\")"  # pylint:disable=line-too-long
            ),
            inputSchema={
                "json": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": (
                                "The Python script code to execute. "
                                "Must be valid Python syntax. "
                                "Multi-line scripts are supported."
                            ),
                        },
                    },
                    "required": ["code"],
                }
            },
        )
        def run_python_script(code: str) -> dict:
            with TemporaryDirectory() as tmp_dir:
                app_dir = Path(tmp_dir)
                ctx_dir = self.context_dir

                code_path = app_dir / "code.py"
                code_path.write_text(code)

                container = self.docker_client.containers.run(
                    image=self.docker_image,
                    command=["python", f"/app/{code_path.name}"],
                    volumes={
                        str(app_dir): {"bind": "/app", "mode": "ro"},
                        str(ctx_dir): {"bind": "/ctx", "mode": "rw"},
                    },
                    environment={"PYTHONUNBUFFERED": "1"},
                    detach=True,
                    stdout=True,
                    stderr=True,
                )

                container.wait()

                out = container.logs(stdout=True, stderr=False)
                err = container.logs(stdout=False, stderr=True)

                container.remove()

            return {
                "status": "success",
                "content": [
                    {
                        "json": {
                            "stdout": out.decode("utf-8").strip(),
                            "stderr": err.decode("utf-8").strip(),
                        }
                    }
                ],
            }

        return run_python_script
