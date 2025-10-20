#!/usr/bin/env python3

"""
Entry point for the monitoring agent module.
This allows the agent to be run with: python -m monitoring_agent
"""

from monitoring_agent import parse_arguments, interactive_cli, app, logger

if __name__ == "__main__":
    args = parse_arguments()
    logger.info(f"Arguments: {args}")
    session_id = args.session_id

    if args.interactive:
        interactive_cli(session_id)
    else:
        app.run()