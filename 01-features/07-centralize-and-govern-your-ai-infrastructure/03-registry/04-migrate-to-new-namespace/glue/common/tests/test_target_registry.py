"""The target registry configuration derived from each Preview registry.

``target_registry`` is what ``agent-registry-migration target-config`` (and ``init``) drives: it
reads a source registry read-only and returns the ``CreateRegistry`` input an operator applies by
hand. It had no test coverage at all, which mattered most for two of its decisions:

* **which region** the target registry belongs in -- ``target.region or source.region``. Get that wrong
  and the operator creates the registry in the wrong place, then cannot load into it.
* **per-mapping failure isolation** -- one unreachable registry must not hide the others, because
  the whole point of the command is to answer for every mapping at once.

``transform_registry_configuration`` itself is covered thoroughly in test_transform.py; this is
about the module that drives it.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import ClassVar

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from migration_common import (
    registry_api,
    target_registry,
)

PREVIEW_API = {
    "serviceName": "bedrock-agentcore-control",
    "transport": "sigv4RestJson",
    "signingName": "bedrock-agentcore",
    "endpointUrlTemplate": "https://bedrock-agentcore-control.{region}.amazonaws.com",
    "allowedEndpointHosts": [],
    "endpointUrl": None,
}

SETTINGS = {"api": {"preview": PREVIEW_API}}


def _mapping(mapping_id: str, *, source_region: str, target_region: str | None) -> dict:
    target: dict = {"accountId": "111122223333", "registryId": "reg-new"}
    if target_region is not None:
        target["region"] = target_region
    return {
        "id": mapping_id,
        "source": {
            "accountId": "111122223333",
            "region": source_region,
            "registryId": f"reg-{mapping_id}",
        },
        "target": target,
    }


class _FakePreviewClient:
    """Returns a canned registry, or raises, per source registryId."""

    registries: ClassVar[dict[str, dict]] = {}
    errors: ClassVar[dict[str, Exception]] = {}
    describe_calls: ClassVar[list[str]] = []

    @classmethod
    def reset(cls) -> None:
        cls.registries = {}
        cls.errors = {}
        cls.describe_calls = []

    def __init__(self, invoker, api_config, region) -> None:
        self.region = region

    def describe_registry(self, *, registry_id: str) -> dict:
        type(self).describe_calls.append(registry_id)
        if registry_id in type(self).errors:
            raise type(self).errors[registry_id]
        return type(self).registries[registry_id]


class DeriveCreateRegistryInputs(unittest.TestCase):
    def setUp(self) -> None:
        _FakePreviewClient.reset()
        self._original_client = target_registry.PreviewRegistryClient
        self._original_invoker = target_registry.invoker_for_endpoint
        target_registry.PreviewRegistryClient = _FakePreviewClient
        target_registry.invoker_for_endpoint = lambda endpoint, run_id, purpose: "invoker"
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        target_registry.PreviewRegistryClient = self._original_client
        target_registry.invoker_for_endpoint = self._original_invoker

    @staticmethod
    def _preview_registry(name: str = "src") -> dict:
        return {
            "name": name,
            "registryId": "reg-a",
            "authorizerType": "CUSTOM_JWT",
            "authorizerConfiguration": {
                "customJWTAuthorizer": {
                    "discoveryUrl": "https://example.test/.well-known/openid-configuration",
                    "allowedAudience": ["aud"],
                }
            },
        }

    def test_the_payload_is_derived_from_the_source_registry(self):
        _FakePreviewClient.registries = {"reg-a": self._preview_registry()}
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS, [_mapping("a", source_region="us-east-1", target_region="us-west-2")]
        )
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIsNone(entry["error"])
        self.assertEqual(entry["payload"]["name"], "src")
        # The preview shape's top-level authorizer is nested under discoveryConfiguration in the new version.
        self.assertEqual(entry["payload"]["discoveryConfiguration"]["authorizerType"], "CUSTOM_JWT")

    def test_the_region_is_the_targets_not_the_sources(self):
        """The target registry has to be created where the mapping loads into."""
        _FakePreviewClient.registries = {"reg-a": self._preview_registry()}
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS, [_mapping("a", source_region="us-east-1", target_region="eu-west-1")]
        )
        self.assertEqual(entries[0]["region"], "eu-west-1")

    def test_the_region_falls_back_to_the_source_when_the_target_has_none(self):
        _FakePreviewClient.registries = {"reg-a": self._preview_registry()}
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS, [_mapping("a", source_region="ap-south-1", target_region=None)]
        )
        self.assertEqual(entries[0]["region"], "ap-south-1")

    def test_one_unreachable_registry_does_not_hide_the_others(self):
        _FakePreviewClient.registries = {
            "reg-a": self._preview_registry("first"),
            "reg-c": self._preview_registry("third"),
        }
        _FakePreviewClient.errors = {"reg-b": registry_api.RegistryApiError("AccessDeniedException: nope")}
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS,
            [
                _mapping("a", source_region="us-east-1", target_region="us-east-1"),
                _mapping("b", source_region="us-east-1", target_region="us-east-1"),
                _mapping("c", source_region="us-east-1", target_region="us-east-1"),
            ],
        )
        by_id = {entry["mappingId"]: entry for entry in entries}
        self.assertEqual(sorted(by_id), ["a", "b", "c"])
        self.assertIsNone(by_id["a"]["error"])
        self.assertIsNone(by_id["c"]["error"])
        self.assertIn("AccessDenied", by_id["b"]["error"])
        self.assertIsNone(by_id["b"]["payload"])

    def test_warnings_reach_the_caller(self):
        """A dropped authorizer field is an access-control decision, so it must not be silent."""
        registry = self._preview_registry()
        registry["authorizerConfiguration"]["customJWTAuthorizer"]["advertisedScopeMapping"] = {"a": "b"}
        _FakePreviewClient.registries = {"reg-a": registry}
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS, [_mapping("a", source_region="us-east-1", target_region="us-east-1")]
        )
        self.assertTrue(entries[0]["warnings"])
        self.assertIn("advertisedScopeMapping", " ".join(entries[0]["warnings"]))

    def test_mapping_ids_filter_which_registries_are_read(self):
        _FakePreviewClient.registries = {
            "reg-a": self._preview_registry("first"),
            "reg-b": self._preview_registry("second"),
        }
        entries = target_registry.derive_create_registry_inputs(
            SETTINGS,
            [
                _mapping("a", source_region="us-east-1", target_region="us-east-1"),
                _mapping("b", source_region="us-east-1", target_region="us-east-1"),
            ],
            mapping_ids=["b"],
        )
        self.assertEqual([entry["mappingId"] for entry in entries], ["b"])
        # Only the selected mapping's registry was contacted.
        self.assertEqual(_FakePreviewClient.describe_calls, ["reg-b"])

    def test_the_source_is_reported_without_its_external_id(self):
        """Reports must never echo the cross-account trust secret."""
        _FakePreviewClient.registries = {"reg-a": self._preview_registry()}
        mapping = _mapping("a", source_region="us-east-1", target_region="us-east-1")
        mapping["source"]["roleArn"] = "arn:aws:iam::444455556666:role/Reader"
        mapping["source"]["externalId"] = "shared-secret"
        entries = target_registry.derive_create_registry_inputs(SETTINGS, [mapping])
        self.assertNotIn("externalId", entries[0]["source"])
        self.assertNotIn("shared-secret", str(entries[0]))


class UnknownMappingIds(unittest.TestCase):
    def test_a_typo_is_named_rather_than_ignored(self):
        mappings = [_mapping("a", source_region="us-east-1", target_region="us-east-1")]
        self.assertEqual(target_registry.unknown_mapping_ids(mappings, ["a", "b"]), ["b"])

    def test_no_selection_means_nothing_is_unknown(self):
        mappings = [_mapping("a", source_region="us-east-1", target_region="us-east-1")]
        self.assertEqual(target_registry.unknown_mapping_ids(mappings, None), [])
        self.assertEqual(target_registry.unknown_mapping_ids(mappings, []), [])


class CreateRegistryCommand(unittest.TestCase):
    def test_the_command_names_the_targets_regional_endpoint(self):
        payload_path = os.path.join(tempfile.gettempdir(), "a.json")
        command = target_registry.create_registry_command({"mappingId": "a", "region": "eu-west-1"}, payload_path)
        self.assertIn("aws agent-registry-control create-registry", command)
        self.assertIn("--endpoint-url https://agent-registry-control.eu-west-1.api.aws", command)
        self.assertIn(f"file://{payload_path}", command)


class TheCreateRegistryCommandCarriesItsPrerequisite(unittest.TestCase):
    """The emitted command does not run on a stock AWS CLI, so it has to say so.

    `aws agent-registry-control` is not a service the CLI knows yet: the command fails with
    "Invalid choice: 'agent-registry-control'" until the target service model is installed by hand. A command
    printed to be copied and run must therefore arrive with the step that makes it runnable.
    """

    def test_the_prerequisite_names_the_failure_and_the_fix(self):
        note = target_registry.create_registry_prerequisite()
        # The symptom, so it is recognisable when someone has already hit it.
        self.assertIn("Invalid choice", note)
        # The fix, copy-pasteable.
        self.assertIn("~/.aws/models/agent-registry-control/2025-12-01", note)
        self.assertIn("mkdir -p", note)
        # And that installing it serves boto3 as well, so it is done once rather than twice.
        self.assertIn("boto3", note)

    def test_the_target_client_really_does_lack_create_registry(self):
        """Pins the reason the prerequisite exists, so the note cannot outlive its cause.

        Asked of a ``boto3`` client, which is the only way this tool ever reaches the control plane
        -- not of a model file, which no longer exists here and which callers have no reason to know
        about. Skips where the SDK cannot model the service: that is the same condition the tool
        itself fails on, and it is reported there rather than here. If a later SDK adds
        CreateRegistry this fails, and the note should be revisited rather than left telling people
        to install something they no longer need.
        """
        import boto3

        try:
            client = boto3.client("agent-registry-control", region_name="us-east-1")
        except Exception as error:  # noqa: BLE001 - an unmodelled service is the skip condition
            self.skipTest(f"SDK cannot model agent-registry-control: {error}")
        self.assertNotIn("CreateRegistry", set(client.meta.service_model.operation_names))


if __name__ == "__main__":
    unittest.main()
