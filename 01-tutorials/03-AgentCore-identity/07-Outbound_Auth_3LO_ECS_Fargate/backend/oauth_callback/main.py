# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""OAuth callback service entry point."""

from backend.oauth_callback.app.main import app

__all__ = ["app"]
