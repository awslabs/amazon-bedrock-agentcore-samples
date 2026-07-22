#!/usr/bin/env python3
"""
IdP provider flag helper for the consolidated lakehouse-agent tutorial.

This tutorial runs on either Amazon Cognito or Okta, selected by a single
top-level flag ``IDP_PROVIDER`` with allowed values ``"cognito"`` or ``"okta"``.

Flag persistence (see design "Flag-Persistence Mechanism"):
    1. The author sets ``IDP_PROVIDER=cognito|okta`` in ``.env`` (loaded into the
       environment by the existing ``load_env_credentials`` loader).
    2. Notebook ``01`` calls ``set_idp_provider(...)`` once to validate the value
       and mirror it into SSM at ``/app/lakehouse-agent/idp-provider``.
    3. Every downstream notebook / script calls ``get_idp_provider(...)`` to read
       the flag back from SSM (the demo's existing cross-cell coordination
       substrate) and fails fast if it is missing.

No new dependency is introduced: this reuses the ``.env`` loader and the
``/app/lakehouse-agent/*`` SSM contract already used throughout the tutorial.

Usage in notebook 01 (set once, after ``.env`` is loaded):
    from utils.idp_config import set_idp_provider
    IDP_PROVIDER = set_idp_provider(ssm_client)   # reads .env, defaults to cognito

Usage in every downstream notebook (read the persisted flag):
    from utils.idp_config import get_idp_provider
    IDP_PROVIDER = get_idp_provider(ssm_client)
    if IDP_PROVIDER == "okta":
        ...
"""

import os
from typing import Optional

# The flag contract. Cognito is the default so an unmodified checkout reproduces
# the upstream (Cognito-only) tutorial behavior.
FLAG_NAME = "IDP_PROVIDER"
ALLOWED_VALUES = ("cognito", "okta")
DEFAULT_VALUE = "cognito"
SSM_PARAM_NAME = "/app/lakehouse-agent/idp-provider"


def validate_idp_provider(value: Optional[str]) -> str:
    """
    Validate an IDP_PROVIDER value and return it normalized (lower-case).

    Fails fast (ValueError) on a missing or invalid value, naming the flag and
    its allowed values so the tutorial reader knows exactly what to fix.

    Args:
        value: The candidate flag value (e.g. from .env or SSM).

    Returns:
        The normalized value, one of ALLOWED_VALUES.

    Raises:
        ValueError: If value is None/empty or not one of ALLOWED_VALUES.
    """
    if value is None or str(value).strip() == "":
        raise ValueError(
            f"{FLAG_NAME} is not set. Set {FLAG_NAME} to one of "
            f"{list(ALLOWED_VALUES)} (e.g. in your .env file: {FLAG_NAME}={DEFAULT_VALUE})."
        )

    normalized = str(value).strip().lower()
    if normalized not in ALLOWED_VALUES:
        raise ValueError(
            f"{FLAG_NAME}={value!r} is invalid. Allowed values are "
            f"{list(ALLOWED_VALUES)}."
        )
    return normalized


def set_idp_provider(ssm_client, value: Optional[str] = None, verbose: bool = True) -> str:
    """
    Resolve, validate, and persist the IDP_PROVIDER flag to SSM (notebook 01).

    Resolution order:
        1. Explicit ``value`` argument, if provided.
        2. The ``IDP_PROVIDER`` environment variable (loaded from .env).
        3. The default (``"cognito"``) so an unmodified checkout reproduces the
           upstream tutorial.

    The resolved value is validated, then written to SSM at
    ``/app/lakehouse-agent/idp-provider`` so every downstream cell can read it.

    Args:
        ssm_client: A boto3 SSM client.
        value: Optional explicit flag value; overrides the .env / default lookup.
        verbose: If True, print a short confirmation.

    Returns:
        The normalized flag value that was persisted.

    Raises:
        ValueError: If the resolved value is invalid.
    """
    if value is None:
        value = os.environ.get(FLAG_NAME)
    if value is None or str(value).strip() == "":
        # Unset -> fall back to the Cognito default (upstream behavior preserved).
        value = DEFAULT_VALUE

    normalized = validate_idp_provider(value)

    ssm_client.put_parameter(
        Name=SSM_PARAM_NAME,
        Value=normalized,
        Type="String",
        Overwrite=True,
    )

    if verbose:
        print(f"✅ {FLAG_NAME} = '{normalized}' (persisted to SSM {SSM_PARAM_NAME})")

    return normalized


def get_idp_provider(ssm_client) -> str:
    """
    Read the persisted IDP_PROVIDER flag from SSM (every downstream notebook).

    Fails fast if the flag has not been set yet (i.e. notebook 01 was not run)
    or if the stored value is invalid.

    Args:
        ssm_client: A boto3 SSM client.

    Returns:
        The normalized flag value, one of ALLOWED_VALUES.

    Raises:
        ValueError: If the flag is missing from SSM or holds an invalid value.
    """
    try:
        value = ssm_client.get_parameter(Name=SSM_PARAM_NAME)["Parameter"]["Value"]
    except ssm_client.exceptions.ParameterNotFound as e:
        raise ValueError(
            f"{FLAG_NAME} not found in SSM ({SSM_PARAM_NAME}). "
            f"Run notebook 01 first to set {FLAG_NAME} to one of {list(ALLOWED_VALUES)}."
        ) from e

    return validate_idp_provider(value)
