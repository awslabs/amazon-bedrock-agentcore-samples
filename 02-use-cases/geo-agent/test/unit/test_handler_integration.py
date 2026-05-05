"""Integration tests for geo_content_handler with mocked AWS services.

Tests cache hit, cache miss (passthrough/async), purge, forbidden access,
and stale processing record recovery.
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infra", "lambda"))

# Set env vars before import
os.environ["ORIGIN_VERIFY_SECRET"] = "test-secret"
os.environ["DEFAULT_ORIGIN_HOST"] = "example.com"
os.environ["GENERATOR_FUNCTION_NAME"] = "test-generator"
os.environ["GEO_TTL_SECONDS"] = "86400"
os.environ["PROCESSING_TIMEOUT_SECONDS"] = "300"
os.environ["CF_DISTRIBUTION_ID"] = ""


def _make_event(path="/test", mode=None, purge=False, ua_genaibot=False):
    """Build a mock Lambda Function URL event dictionary."""
    params = {}
    if mode:
        params["mode"] = mode
    if purge:
        params["purge"] = "true"
    if ua_genaibot:
        params["ua"] = "genaibot"
    return {
        "rawPath": path,
        "headers": {"x-origin-verify": "test-secret", "host": "example.com"},
        "queryStringParameters": params or None,
    }


class TestHandlerForbidden:
    def setup_method(self):
        self.mock_table = MagicMock()
        self.mock_dynamodb = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.patcher = patch("geo_content_handler.dynamodb", self.mock_dynamodb)
        self.patcher2 = patch("geo_content_handler.table", self.mock_table)
        self.patcher.start()
        self.patcher2.start()

        if "geo_content_handler" in sys.modules:
            import importlib
            importlib.reload(sys.modules["geo_content_handler"])
        import geo_content_handler
        self.handler = geo_content_handler.handler

    def teardown_method(self):
        self.patcher.stop()
        self.patcher2.stop()

    def test_missing_verify_header(self):
        event = {"rawPath": "/test", "headers": {}, "queryStringParameters": None}
        result = self.handler(event, None)
        assert result["statusCode"] == 403

    def test_wrong_verify_header(self):
        event = {
            "rawPath": "/test",
            "headers": {"x-origin-verify": "wrong-secret"},
            "queryStringParameters": None,
        }
        result = self.handler(event, None)
        assert result["statusCode"] == 403


class TestHandlerCacheHit:
    def setup_method(self):
        self.mock_table = MagicMock()
        self.patcher = patch("geo_content_handler.table", self.mock_table)
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()

    def test_returns_geo_content(self):
        self.mock_table.get_item.return_value = {
            "Item": {
                "url_path": "/test",
                "status": "ready",
                "geo_content": "<html>GEO optimized</html>",
                "content_type": "text/html",
                "created_at": "2025-01-01T00:00:00Z",
            }
        }
        import geo_content_handler
        result = geo_content_handler.handler(_make_event(), None)
        assert result["statusCode"] == 200
        assert result["headers"]["X-GEO-Optimized"] == "true"
        assert result["headers"]["X-GEO-Source"] == "cache"
        assert "GEO optimized" in result["body"]


class TestHandlerPurge:
    def setup_method(self):
        self.mock_table = MagicMock()
        self.patcher = patch("geo_content_handler.table", self.mock_table)
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()

    def test_purge_deletes_and_returns_200(self):
        self.mock_table.delete_item.return_value = {}
        import geo_content_handler
        result = geo_content_handler.handler(_make_event(purge=True), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "purged"
        self.mock_table.delete_item.assert_called_once()


class TestHandlerPassthrough:
    def setup_method(self):
        self.mock_table = MagicMock()
        self.mock_lambda = MagicMock()
        self.patcher1 = patch("geo_content_handler.table", self.mock_table)
        self.patcher2 = patch("geo_content_handler.lambda_client", self.mock_lambda)
        self.patcher1.start()
        self.patcher2.start()

    def teardown_method(self):
        self.patcher1.stop()
        self.patcher2.stop()

    @patch("geo_content_handler._fetch_original")
    def test_cache_miss_passthrough(self, mock_fetch):
        # No item in DDB
        self.mock_table.get_item.return_value = {}
        self.mock_table.put_item.return_value = {}
        mock_fetch.return_value = ("<html>Original</html>", "text/html")

        import geo_content_handler
        result = geo_content_handler.handler(_make_event(), None)
        assert result["statusCode"] == 200
        assert result["headers"]["X-GEO-Source"] == "passthrough"
        assert "Original" in result["body"]

    @patch("geo_content_handler._fetch_original")
    def test_async_mode_returns_202(self, mock_fetch):
        self.mock_table.get_item.return_value = {}
        self.mock_table.put_item.return_value = {}

        import geo_content_handler
        result = geo_content_handler.handler(_make_event(mode="async"), None)
        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert body["status"] == "generating"


class TestHandlerStaleProcessing:
    def setup_method(self):
        self.mock_table = MagicMock()
        self.mock_lambda = MagicMock()
        self.patcher1 = patch("geo_content_handler.table", self.mock_table)
        self.patcher2 = patch("geo_content_handler.lambda_client", self.mock_lambda)
        self.patcher1.start()
        self.patcher2.start()

    def teardown_method(self):
        self.patcher1.stop()
        self.patcher2.stop()

    @patch("geo_content_handler._fetch_original")
    def test_stale_processing_retriggers(self, mock_fetch):
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        self.mock_table.get_item.return_value = {
            "Item": {
                "url_path": "/test",
                "status": "processing",
                "created_at": old_time,
            }
        }
        self.mock_table.put_item.return_value = {}
        self.mock_table.delete_item.return_value = {}
        mock_fetch.return_value = ("<html>Original</html>", "text/html")

        import geo_content_handler
        result = geo_content_handler.handler(_make_event(), None)
        assert result["statusCode"] == 200
        # Should have deleted the stale record
        self.mock_table.delete_item.assert_called()
