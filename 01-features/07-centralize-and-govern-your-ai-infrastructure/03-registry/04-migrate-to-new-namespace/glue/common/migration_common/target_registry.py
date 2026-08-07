"""Derive each target registry's configuration from the Preview registry it will replace.

This tool migrates *records*. The registry itself is not created for you, because its
``discoveryConfiguration`` decides who may read it and its ``approvalConfiguration`` decides what
happens to submitted records -- decisions, not data to be copied. What this module removes is the
guesswork: it reads a source registry (read-only) and returns the equivalent target ``CreateRegistry``
input with the preview shape already translated:

* top-level ``authorizerType`` / ``authorizerConfiguration`` nested under ``discoveryConfiguration``
* ``approvalConfiguration.autoApproval: true`` becomes ``autoApprovalRules: ["APPROVE_ALL"]``

Nothing here writes to any registry. The migration calls only record-level operations, so creating
the registry is one ``aws agent-registry-control create-registry`` call the operator makes with the
payload below.
"""

from __future__ import annotations

import logging
from typing import Any

from .aws_auth import invoker_for_endpoint
from .registry_api import PreviewRegistryClient
from .transform import transform_registry_configuration

LOGGER = logging.getLogger("agent-registry-migration.target-registry")

#: Endpoint template for the command an operator runs with a derived payload.
TARGET_CONTROL_ENDPOINT = "https://agent-registry-control.{region}.api.aws"


def derive_create_registry_inputs(
    settings: dict[str, Any],
    mappings: list[dict[str, Any]],
    *,
    mapping_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return one entry per mapping describing the target registry to create.

    Each entry carries ``mappingId``, the ``source`` endpoint it was derived from, the target
    ``region`` the registry belongs in, and either a ``payload`` (the ``CreateRegistry`` input) or
    an ``error`` explaining why that mapping could not be described. Failures are per mapping so
    one unreachable registry does not hide the others.
    """
    api_config = settings["api"]["preview"]
    selected = [mapping for mapping in mappings if not mapping_ids or str(mapping.get("id")) in set(mapping_ids)]
    results: list[dict[str, Any]] = []
    for mapping in selected:
        mapping_id = str(mapping.get("id"))
        source = mapping["source"]
        target = mapping.get("target") or {}
        entry: dict[str, Any] = {
            "mappingId": mapping_id,
            "source": {
                "accountId": source.get("accountId"),
                "region": source.get("region"),
                "registryId": source.get("registryId"),
            },
            # Where the target registry has to be created for this mapping to load into it.
            "region": target.get("region") or source.get("region"),
            "payload": None,
            # What about this payload needs a decision before it is applied -- a preview-only
            # authorizer field that had to be dropped, or an audience naming the old registry.
            "warnings": [],
            "error": None,
        }
        try:
            invoker = invoker_for_endpoint(source, run_id=None, purpose="target-config")
            client = PreviewRegistryClient(invoker, api_config, str(source["region"]))
            preview_registry = client.describe_registry(registry_id=str(source["registryId"]))
            warnings: list[str] = []
            entry["payload"] = transform_registry_configuration(
                preview_registry,
                warnings=warnings,
                source_registry_id=str(source["registryId"]),
            )
            entry["warnings"] = warnings
        except Exception as error:
            entry["error"] = str(error)
            # The message goes in the report; the traceback goes to the log. Without it an
            # unexpected failure here is a one-line string with no way to find out what raised it.
            LOGGER.debug(
                "Could not derive the target registry configuration for mapping %s",
                mapping_id,
                exc_info=True,
            )
        results.append(entry)
    return results


def create_registry_command(entry: dict[str, Any], payload_path: str) -> str:
    """Return the single AWS CLI command that creates the registry described by ``entry``."""
    return (
        "aws agent-registry-control create-registry"
        f" --cli-input-json file://{payload_path}"
        f" --endpoint-url {TARGET_CONTROL_ENDPOINT.format(region=entry.get('region'))}"
        " --query registryArn --output text"
    )


def create_registry_prerequisite() -> str:
    """The step that has to happen before the command above will run at all.

    ``aws agent-registry-control`` is not a service the AWS CLI knows yet, so the command fails with
    ``Invalid choice: 'agent-registry-control'`` until its model is installed. Installing it is the
    operator's step either way: the migration calls only record-level operations, and creating a
    registry is a decision rather than data to be copied.

    Printed with the command rather than left in the documentation, because the command is meant to
    be copied and run, and a copied command that cannot run is worse than no command at all.
    """
    return (
        "The AWS CLI does not ship the new Registry service model yet, so the command above fails with\n"
        "\"Invalid choice: 'agent-registry-control'\" until you install it once:\n"
        "\n"
        "  mkdir -p ~/.aws/models/agent-registry-control/2025-12-01\n"
        "  cp agent-registry-control-2025-12-01.normal.json \\\n"
        "     ~/.aws/models/agent-registry-control/2025-12-01/service-2.json\n"
        "\n"
        "The same model is what boto3 needs for this tool to reach the target control plane, so\n"
        "installing it once covers both."
    )


def unknown_mapping_ids(
    mappings: list[dict[str, Any]],
    mapping_ids: list[str] | None,
) -> list[str]:
    """Return the requested mapping ids that do not exist, so a typo is named rather than ignored."""
    if not mapping_ids:
        return []
    known = {str(mapping.get("id")) for mapping in mappings}
    return sorted(set(mapping_ids) - known)
