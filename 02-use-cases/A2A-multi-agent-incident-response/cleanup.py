#!/usr/bin/env python3
"""
Cleanup script for A2A Multi-Agent Incident Response System.
This script removes all deployed resources in the correct order.
"""

import sys
import yaml
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def get_input(prompt: str, default: Optional[str] = None, required: bool = True) -> str:
    """Get user input with optional default value"""
    if default:
        display_prompt = f"{Colors.BLUE}{prompt} [{Colors.GREEN}{default}{Colors.BLUE}]: {Colors.END}"
    else:
        display_prompt = f"{Colors.BLUE}{prompt}: {Colors.END}"

    while True:
        value = input(display_prompt).strip()

        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print_error("This field is required. Please provide a value.")


def run_command(cmd: list, capture_output: bool = True) -> tuple:
    """Run a shell command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=30
        )
        return (result.returncode == 0, result.stdout.strip() if capture_output else "")
    except Exception as e:
        return (False, str(e))


def load_config(config_path: Path) -> Optional[Dict[str, Any]]:
    """Load configuration from .a2a.config file"""
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return None


def wait_for_stack_deletion(stack_name: str, region: str) -> bool:
    """Wait for CloudFormation stack to be deleted"""
    print_info(f"Waiting for stack '{stack_name}' to be deleted...")

    max_wait_time = 1800  # 30 minutes
    wait_interval = 15  # 15 seconds
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        success, output = run_command(
            [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                stack_name,
                "--region",
                region,
                "--query",
                "Stacks[0].StackStatus",
                "--output",
                "text",
            ]
        )

        # Stack no longer exists - this is the success case
        if not success:
            # Check for common stack deletion indicators in the output
            output_lower = output.lower()
            if (
                "does not exist" in output_lower
                or "validationerror" in output_lower
                or "stack with id" in output_lower
                or not output.strip()
            ):  # Empty output also means stack is gone
                print_success(f"Stack '{stack_name}' deleted successfully!")
                return True
            else:
                # Some other unexpected error occurred, but continue checking
                # Don't show warnings for empty output
                if output.strip():
                    print_warning(f"Error checking stack status: {output}")
                # Continue to next iteration - stack might be gone

        # Stack still exists, check its status
        if success and output:
            status = output.strip()

            # DELETE_COMPLETE means stack is fully deleted and will disappear soon
            if status == "DELETE_COMPLETE":
                print_success(f"Stack '{stack_name}' deleted successfully!")
                return True
            elif status == "DELETE_FAILED":
                print_error(f"Stack '{stack_name}' deletion failed!")
                print_error("Check the CloudFormation console for details")
                return False
            else:
                print_info(f"Stack status: {status} (waiting...)")

        time.sleep(wait_interval)
        elapsed_time += wait_interval

    print_error(
        f"Timeout waiting for stack '{stack_name}' deletion (waited {max_wait_time}s)"
    )
    return False


def delete_stack(stack_name: str, region: str, step_name: str) -> bool:
    """Delete a CloudFormation stack"""
    print_header(f"Deleting {step_name}")

    # Check if stack exists
    success, output = run_command(
        [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack_name,
            "--region",
            region,
        ]
    )

    if not success:
        # Check if stack doesn't exist (not an error)
        output_lower = output.lower()
        if (
            "does not exist" in output_lower
            or "stack with id" in output_lower
            or "validationerror" in output_lower
            or not output.strip()
        ):
            print_info(f"Stack '{stack_name}' does not exist, skipping")
            return True
        # Some other error
        print_error(f"Error checking stack: {output}")
        return False

    # Delete the stack
    print_info(f"Deleting CloudFormation stack: {stack_name}")
    success, output = run_command(
        [
            "aws",
            "cloudformation",
            "delete-stack",
            "--stack-name",
            stack_name,
            "--region",
            region,
        ]
    )

    if success:
        print_success(f"Stack deletion initiated: {stack_name}")
        return wait_for_stack_deletion(stack_name, region)
    else:
        print_error(f"Failed to delete stack: {output}")
        return False


def empty_s3_bucket(bucket_name: str, region: str) -> bool:
    """Empty all objects from S3 bucket"""
    print_info(f"Checking if bucket '{bucket_name}' exists...")

    # Check if bucket exists
    success, output = run_command(
        ["aws", "s3api", "head-bucket", "--bucket", bucket_name, "--region", region]
    )

    if not success:
        if "404" in output or "Not Found" in output:
            print_warning(f"Bucket '{bucket_name}' does not exist, skipping")
            return True
        print_error(f"Error checking bucket: {output}")
        return False

    print_info(f"Emptying S3 bucket: {bucket_name}")
    success, output = run_command(
        ["aws", "s3", "rm", f"s3://{bucket_name}", "--recursive", "--region", region]
    )

    if success or "remove" in output:
        print_success(f"S3 bucket '{bucket_name}' emptied successfully")
        return True
    else:
        print_warning(f"No objects to delete or error: {output}")
        return True  # Continue even if empty fails


def delete_s3_bucket(bucket_name: str, region: str) -> bool:
    """Delete S3 bucket"""
    print_info(f"Deleting S3 bucket: {bucket_name}")

    success, output = run_command(
        ["aws", "s3", "rb", f"s3://{bucket_name}", "--region", region]
    )

    if success:
        print_success(f"S3 bucket '{bucket_name}' deleted successfully")
        return True
    else:
        if "NoSuchBucket" in output or "does not exist" in output:
            print_warning(f"Bucket '{bucket_name}' does not exist")
            return True
        print_error(f"Failed to delete bucket: {output}")
        return False


def cleanup_s3_bucket(bucket_name: str, region: str) -> bool:
    """Empty and delete S3 bucket"""
    print_header("Step 5: Delete S3 Bucket")

    if not empty_s3_bucket(bucket_name, region):
        print_warning("Failed to empty bucket, but continuing...")

    return delete_s3_bucket(bucket_name, region)


def run_cleanup(config: Dict[str, Any]) -> bool:
    """Run all cleanup steps in reverse order"""
    print_header("Starting Cleanup")
    print_warning("This will DELETE all deployed resources")
    print_warning("This action cannot be undone!")
    print_info("Cleanup will take approximately 10-15 minutes\n")

    confirm = get_input(
        f"{Colors.RED}Are you absolutely sure you want to delete all resources? Type 'DELETE' to confirm{Colors.END}",
        default=None,
        required=True,
    )

    if confirm != "DELETE":
        print_warning("Cleanup cancelled. Resources were not deleted.")
        return False

    print()
    region = config["aws"]["region"]
    all_success = True

    # Step 1: Delete Host Agent (reverse order)
    if not delete_stack(config["stacks"]["host_agent"], region, "Host Agent Stack"):
        print_error("Failed to delete Host Agent stack")
        all_success = False

    print()

    # Step 2: Delete Web Search Agent
    if not delete_stack(
        config["stacks"]["web_search_agent"], region, "Web Search Agent Stack"
    ):
        print_error("Failed to delete Web Search Agent stack")
        all_success = False

    print()

    # Step 3: Delete Monitoring Agent
    if not delete_stack(
        config["stacks"]["monitoring_agent"], region, "Monitoring Agent Stack"
    ):
        print_error("Failed to delete Monitoring Agent stack")
        all_success = False

    print()

    # Step 4: Delete Cognito Stack
    if not delete_stack(config["stacks"]["cognito"], region, "Cognito Stack"):
        print_error("Failed to delete Cognito stack")
        all_success = False

    print()

    # Step 5: Delete S3 Bucket
    if not cleanup_s3_bucket(config["s3"]["smithy_models_bucket"], region):
        print_error("Failed to delete S3 bucket")
        all_success = False

    print()

    # Delete .a2a.config file
    config_path = Path(".a2a.config")
    if config_path.exists():
        try:
            config_path.unlink()
            print_success("Deleted .a2a.config file")
        except Exception as e:
            print_warning(f"Failed to delete .a2a.config: {e}")
            print_info("You can manually delete it if needed")

    print()

    if all_success:
        print_header("Cleanup Complete!")
        print_success("All resources have been deleted successfully!")
        print_info("\nTo deploy again, run: uv run deploy.py")
    else:
        print_header("Cleanup Completed with Errors")
        print_warning("Some resources may not have been deleted successfully")
        print_info(
            "Check the errors above and manually delete remaining resources if needed"
        )
        if config_path.exists():
            print_info("Note: .a2a.config was not deleted due to cleanup errors")

    return all_success


def list_resources(config: Dict[str, Any]):
    """List all resources that will be deleted"""
    print_header("Resources to be Deleted")

    print(f"{Colors.BOLD}CloudFormation Stacks:{Colors.END}")
    print(f"  1. {config['stacks']['host_agent']} (Host Agent)")
    print(f"  2. {config['stacks']['web_search_agent']} (Web Search Agent)")
    print(f"  3. {config['stacks']['monitoring_agent']} (Monitoring Agent)")
    print(f"  4. {config['stacks']['cognito']} (Cognito)")

    print(f"\n{Colors.BOLD}S3 Resources:{Colors.END}")
    print(f"  5. {config['s3']['smithy_models_bucket']} (S3 Bucket + Contents)")

    print(f"\n{Colors.BOLD}Region:{Colors.END} {config['aws']['region']}")
    print()


def main():
    """Main entry point"""
    try:
        print_header("A2A Multi-Agent System - Cleanup Script")

        # Load configuration
        config_path = Path(".a2a.config")
        config = load_config(config_path)

        if not config:
            print_error("Configuration file '.a2a.config' not found!")
            print_info(
                "Make sure you're in the project directory where deployment was run."
            )
            print_info(
                "If you deployed manually, you'll need to delete resources manually as well."
            )
            sys.exit(1)

        print_success("Configuration loaded from .a2a.config")

        # List resources
        list_resources(config)

        # Ask if user wants to proceed
        proceed = get_input(
            "Do you want to proceed with cleanup? (yes/no)", default="no", required=True
        ).lower() in ["yes", "y"]

        if not proceed:
            print_warning("Cleanup cancelled by user.")
            sys.exit(0)

        print()

        # Run cleanup
        if run_cleanup(config):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print_error("\n\nCleanup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
