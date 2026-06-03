"""Emit the application's OpenAPI 3.1 schema to stdout (or a file).

Used to feed AgentCore Gateway's openApiSchema target during deploys.
"""

import json
import sys

from ecommerce.main import app


def main() -> None:
    schema = app.openapi()
    out = sys.argv[1] if len(sys.argv) > 1 else None
    payload = json.dumps(schema, indent=2)
    if out:
        with open(out, "w") as f:
            f.write(payload)
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
