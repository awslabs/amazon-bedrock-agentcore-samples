# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Assert that the ``GIT_ASKPASS`` script and its sidecar token file are
created with owner-only permission bits.

The credential-vaulting story for this sample depends on the token
never being readable by any other principal on the container (no
``group`` bits, no ``other`` bits). Verifying the mode with ``os.stat``
locks that invariant into the test suite so a refactor of
``_create_askpass_script`` cannot silently relax it.

Covers the PCSR Holmes finding on ``git_clone.py`` token file
permissions (Rule 8, "Data Security and Encryption Implementation").
The finding is technically a false positive (the file is already
created with ``0o400`` via an explicit ``os.open`` mode argument) but
the assertion is worth having regardless.
"""

from __future__ import annotations

import os
import stat

from container.lib.git_askpass import _create_askpass_script


# Mask off the file-type bits; leave only the permission bits.
_MODE_MASK = 0o777


def _cleanup(script_path: str) -> None:
    sidecar = script_path + ".token"
    for path in (sidecar, script_path):
        if os.path.exists(path):
            os.remove(path)


def test_sidecar_token_file_is_owner_read_only() -> None:
    """The sidecar ``<script>.token`` file must be mode 0o400.

    No group or other bits are allowed. Read-only for the owner is the
    minimum permission git needs: the askpass shell script reads the
    file via ``cat "$0.token"``, which only requires read access.
    """
    script_path = _create_askpass_script("ghp_testtoken_abc123")
    try:
        sidecar = script_path + ".token"
        assert os.path.exists(sidecar), "sidecar token file was not created"

        mode = os.stat(sidecar).st_mode & _MODE_MASK
        assert mode == 0o400, (
            f"sidecar token file mode must be 0o400 (owner-read-only); "
            f"got {oct(mode)}. File={sidecar}"
        )

        # Belt and suspenders: explicit bit-level assertions. If anyone
        # relaxes the mode they hit both the value check above and the
        # bitwise check below.
        assert mode & stat.S_IRUSR, "owner must have read permission"
        assert not (mode & stat.S_IWUSR), "owner write bit must not be set"
        assert not (mode & stat.S_IXUSR), "owner execute bit must not be set"
        assert not (mode & (stat.S_IRWXG | stat.S_IRWXO)), (
            f"no group or other bits may be set on the token file; "
            f"got {oct(mode)}"
        )
    finally:
        _cleanup(script_path)


def test_askpass_script_is_owner_read_and_execute_only() -> None:
    """The askpass shell script itself must be mode 0o500.

    git invokes the script as a subprocess, so it needs owner execute.
    It does not need write (it is never modified after creation) and it
    must not be readable or executable by any other principal.
    """
    script_path = _create_askpass_script("ghp_testtoken_def456")
    try:
        mode = os.stat(script_path).st_mode & _MODE_MASK
        assert mode == 0o500, (
            f"askpass script mode must be 0o500 (owner read+execute only); "
            f"got {oct(mode)}. File={script_path}"
        )
        assert mode & stat.S_IRUSR, "owner must have read permission"
        assert mode & stat.S_IXUSR, "owner must have execute permission"
        assert not (mode & stat.S_IWUSR), "owner write bit must not be set"
        assert not (mode & (stat.S_IRWXG | stat.S_IRWXO)), (
            f"no group or other bits may be set on the askpass script; "
            f"got {oct(mode)}"
        )
    finally:
        _cleanup(script_path)
