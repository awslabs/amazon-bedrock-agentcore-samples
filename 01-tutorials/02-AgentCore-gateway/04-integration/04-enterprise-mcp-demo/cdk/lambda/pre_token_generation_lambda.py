import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Cognito Pre-Token Generation Lambda Trigger
    Adds custom claims to the ID token based on user's email
    """

    logger.info(f"Pre-token generation event: {json.dumps(event)}")

    try:
        # Extract user attributes from the event
        user_attributes = event["request"]["userAttributes"]
        email = user_attributes.get("email", "")

        logger.info(f"Processing token for user with email: {email}")

        # Add custom claims based on email domain or specific rules
        # Example: Add a custom tag based on email domain
        custom_tag = "default_user"

        if email == "vscode-admin@example.com":
            # Example: Set custom tag based on email
            custom_tag = "admin_user"
        else:
            custom_tag = "regular_user"

        # Add custom claims to the ID token
        # Note: You can add to claimsOverrideDetails for ID token
        if (
            "claimsOverrideDetails" not in event["response"]
            or event["response"]["claimsOverrideDetails"] is None
        ):
            event["response"]["claimsOverrideDetails"] = {}

        if "claimsToAddOrOverride" not in event["response"]["claimsOverrideDetails"]:
            event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] = {}

        # Add custom claims to ID token
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"][
            "user_tag"
        ] = custom_tag
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["email"] = (
            email
        )

        # Add custom claims to the Access token (V2 trigger)
        if (
            "claimsAndScopeOverrideDetails" not in event["response"]
            or event["response"]["claimsAndScopeOverrideDetails"] is None
        ):
            event["response"]["claimsAndScopeOverrideDetails"] = {}

        if (
            "accessTokenGeneration"
            not in event["response"]["claimsAndScopeOverrideDetails"]
        ):
            event["response"]["claimsAndScopeOverrideDetails"][
                "accessTokenGeneration"
            ] = {}

        if (
            "claimsToAddOrOverride"
            not in event["response"]["claimsAndScopeOverrideDetails"][
                "accessTokenGeneration"
            ]
        ):
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"][
                "claimsToAddOrOverride"
            ] = {}

        # Add email and user_tag to access token
        event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"][
            "claimsToAddOrOverride"
        ]["email"] = email
        event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"][
            "claimsToAddOrOverride"
        ]["user_tag"] = custom_tag

        logger.info(
            f"Added custom claims to ID token and Access token: "
            f"user_tag={custom_tag}, email={email}"
        )

    except Exception as e:
        logger.error(f"Error in pre-token generation: {str(e)}", exc_info=True)
        # Don't fail the authentication, just log the error
        pass

    return event
