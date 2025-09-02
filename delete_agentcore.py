#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Amazon Bedrock AgentCore Gateway Deletion Script

This script deletes an Amazon Bedrock AgentCore Gateway and all its associated targets.
It provides a clean way to remove the gateway infrastructure deployed by deploy_agentcore.py.

Usage:
    python delete_agentcore.py [--gateway-name my-gateway]
    python delete_agentcore.py --gateway-id gateway-12345
    python delete_agentcore.py --all  # Delete all gateways
"""

import argparse
import boto3
import json
import logging
import sys
import time

from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentCoreGatewayDeleter:
    """Handles deletion of Amazon Bedrock AgentCore Gateway and its targets."""

    def __init__(self, region: Optional[str] = None):
        """Initialize the deleter with AWS clients."""
        self.region = region or boto3.Session().region_name

        # Initialize AWS clients
        try:
            self.agentcore_client = boto3.client(
                "bedrock-agentcore-control", region_name=self.region
            )
            self.sts_client = boto3.client("sts", region_name=self.region)

            # Get account ID
            self.account_id = self.sts_client.get_caller_identity()["Account"]
            logger.info(
                f"Initialized AWS clients for account {self.account_id} in region {self.region}"
            )

        except NoCredentialsError:
            logger.error(
                "AWS credentials not found. Please configure AWS CLI or set environment variables."
            )
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            sys.exit(1)

    def list_gateways(self) -> List[Dict[str, Any]]:
        """List all gateways in the account."""
        try:
            response = self.agentcore_client.list_gateways()
            gateways = response.get("items", [])
            logger.info(f"Found {len(gateways)} gateways in region {self.region}")
            return gateways
        except ClientError as e:
            logger.error(f"Failed to list gateways: {e}")
            return []

    def find_gateway_by_name(self, gateway_name: str) -> Optional[Dict[str, Any]]:
        """Find a gateway by name."""
        gateways = self.list_gateways()
        for gateway in gateways:
            if gateway.get("name") == gateway_name:
                return gateway
        return None

    def get_gateway_details(self, gateway_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a gateway."""
        try:
            response = self.agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(f"Gateway {gateway_id} not found")
                return None
            logger.error(f"Failed to get gateway details: {e}")
            return None

    def list_gateway_targets(self, gateway_id: str) -> List[Dict[str, Any]]:
        """List all targets for a gateway."""
        try:
            response = self.agentcore_client.list_gateway_targets(
                gatewayIdentifier=gateway_id
            )
            targets = response.get("items", [])
            logger.info(f"Found {len(targets)} targets for gateway {gateway_id}")
            return targets
        except ClientError as e:
            logger.error(f"Failed to list gateway targets: {e}")
            return []

    def delete_gateway_target(self, gateway_id: str, target_id: str) -> bool:
        """Delete a specific gateway target."""
        try:
            logger.info(f"Deleting target {target_id} from gateway {gateway_id}")
            self.agentcore_client.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id
            )
            logger.info(f"Successfully deleted target {target_id}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(f"Target {target_id} not found (may already be deleted)")
                return True
            logger.error(f"Failed to delete target {target_id}: {e}")
            return False

    def delete_all_gateway_targets(self, gateway_id: str) -> bool:
        """Delete all targets for a gateway."""
        targets = self.list_gateway_targets(gateway_id)

        if not targets:
            logger.info(f"No targets found for gateway {gateway_id}")
            return True

        success = True
        for target in targets:
            target_id = target["targetId"]
            target_name = target.get("name", "unnamed")
            logger.info(f"Deleting target: {target_name} ({target_id})")

            if not self.delete_gateway_target(gateway_id, target_id):
                success = False
            else:
                # Wait a moment between deletions to avoid rate limiting
                time.sleep(1)

        return success

    def delete_gateway(self, gateway_id: str) -> bool:
        """Delete a gateway after removing all its targets."""
        try:
            # First, get gateway details for logging
            gateway_details = self.get_gateway_details(gateway_id)
            gateway_name = (
                gateway_details.get("name", "unknown") if gateway_details else "unknown"
            )

            logger.info(f"Starting deletion of gateway: {gateway_name} ({gateway_id})")

            # Step 1: Delete all targets
            logger.info("Step 1: Deleting all gateway targets...")
            if not self.delete_all_gateway_targets(gateway_id):
                logger.error(
                    "Failed to delete some targets. Gateway deletion may fail."
                )
                return False

            # Step 2: Wait for targets to be fully deleted
            logger.info("Step 2: Waiting for targets to be fully deleted...")
            max_wait_time = 60  # seconds
            wait_interval = 5  # seconds
            waited = 0

            while waited < max_wait_time:
                remaining_targets = self.list_gateway_targets(gateway_id)
                if not remaining_targets:
                    logger.info("All targets successfully deleted")
                    break

                logger.info(
                    f"Waiting for {len(remaining_targets)} targets to be deleted..."
                )
                time.sleep(wait_interval)
                waited += wait_interval
            else:
                logger.warning(
                    "Timeout waiting for targets to be deleted, proceeding with gateway deletion"
                )

            # Step 3: Delete the gateway
            logger.info("Step 3: Deleting gateway...")
            self.agentcore_client.delete_gateway(gatewayIdentifier=gateway_id)
            logger.info(f"Successfully initiated deletion of gateway {gateway_id}")

            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(
                    f"Gateway {gateway_id} not found (may already be deleted)"
                )
                return True
            logger.error(f"Failed to delete gateway {gateway_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting gateway {gateway_id}: {e}")
            return False

    def delete_gateway_by_name(self, gateway_name: str) -> Optional[str]:
        """Delete a gateway by name. Returns gateway_id if successful, None if failed."""
        gateway = self.find_gateway_by_name(gateway_name)
        if not gateway:
            logger.error(f"Gateway with name '{gateway_name}' not found")
            available_gateways = [
                g.get("name", "unnamed") for g in self.list_gateways()
            ]
            if available_gateways:
                logger.info(f"Available gateways: {', '.join(available_gateways)}")
            return None

        gateway_id = gateway["gatewayId"]
        if self.delete_gateway(gateway_id):
            return gateway_id
        return None

    def delete_all_gateways(self) -> bool:
        """Delete all gateways in the account."""
        gateways = self.list_gateways()

        if not gateways:
            logger.info("No gateways found to delete")
            return True

        logger.warning(
            f"This will delete ALL {len(gateways)} gateways in region {self.region}"
        )

        success = True
        for gateway in gateways:
            gateway_id = gateway["gatewayId"]
            gateway_name = gateway.get("name", "unnamed")

            logger.info(f"Deleting gateway: {gateway_name} ({gateway_id})")
            if not self.delete_gateway(gateway_id):
                success = False
            else:
                # Wait between gateway deletions
                time.sleep(2)

        return success

    def load_deployment_info(
        self, file_path: str = "gateway-deployment.json"
    ) -> Optional[Dict[str, Any]]:
        """Load deployment information from the deployment file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                deployment_info = json.load(f)
            logger.info(f"Loaded deployment information from {file_path}")
            return deployment_info
        except FileNotFoundError:
            logger.warning(f"Deployment file {file_path} not found")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in deployment file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading deployment file {file_path}: {e}")
            return None

    def print_deletion_summary(self, deleted_gateways: List[str]) -> None:
        """Print a summary of deleted gateways."""
        print("\n" + "=" * 80)
        if deleted_gateways:
            print("🗑️  AGENTCORE GATEWAY DELETION COMPLETED")
            print("=" * 80)
            print(f"Region:              {self.region}")
            print(f"Deleted Gateways:    {len(deleted_gateways)}")
            print()
            for gateway_id in deleted_gateways:
                print(f"  ✓ {gateway_id}")
            print()
            print("📝 CLEANUP COMPLETED")
            print("-" * 40)
            print("• All gateway targets have been deleted")
            print("• All specified gateways have been deleted")
            print("• No further cleanup required")
        else:
            print("⚠️  NO GATEWAYS DELETED")
            print("=" * 80)
            print("No gateways were found or deleted.")
            print("This may be because:")
            print("• The specified gateway doesn't exist")
            print("• The gateway was already deleted")
            print("• There was an error during deletion")
        print("=" * 80)


def main():
    """Main entry point for the deletion script."""
    parser = argparse.ArgumentParser(
        description="Delete Amazon Bedrock AgentCore Gateway and targets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
            # Delete gateway by name (default name)
            python delete_agentcore.py
            
            # Delete gateway by custom name
            python delete_agentcore.py --gateway-name my-custom-gateway
            
            # Delete gateway by ID
            python delete_agentcore.py --gateway-id gateway-12345
            
            # Delete all gateways (use with caution!)
            python delete_agentcore.py --all
            
            # Use deployment file to find gateway
            python delete_agentcore.py --from-deployment gateway-deployment.json
        """,
    )

    parser.add_argument(
        "--gateway-name",
        "-n",
        default=None,
        help="Gateway name to delete (default: agentcore-gateway)",
    )

    parser.add_argument(
        "--gateway-id",
        "-i",
        default=None,
        help="Gateway ID to delete (takes precedence over name)",
    )

    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region (default: current session region)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Delete ALL gateways in the region (use with caution!)",
    )

    parser.add_argument(
        "--from-deployment",
        "-f",
        default=None,
        help="Load gateway ID from deployment file (default: gateway-deployment.json)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize deleter
        deleter = AgentCoreGatewayDeleter(region=args.region)
        deleted_gateways = []

        if args.dry_run:
            logger.info("DRY RUN MODE - No resources will be deleted")

        # Determine what to delete
        if args.all:
            # Delete all gateways
            if args.dry_run:
                gateways = deleter.list_gateways()
                logger.info(f"Would delete {len(gateways)} gateways:")
                for gateway in gateways:
                    logger.info(
                        f"  - {gateway.get('name', 'unnamed')} ({gateway['gatewayId']})"
                    )
            else:
                # Confirm deletion of all gateways
                gateways = deleter.list_gateways()
                if gateways:
                    print(
                        f"\n⚠️  WARNING: This will delete ALL {len(gateways)} gateways in region {deleter.region}"
                    )
                    for gateway in gateways:
                        print(
                            f"  - {gateway.get('name', 'unnamed')} ({gateway['gatewayId']})"
                        )

                    confirm = input(
                        "\nAre you sure you want to continue? (type 'yes' to confirm): "
                    )
                    if confirm.lower() != "yes":
                        logger.info("Deletion cancelled by user")
                        sys.exit(0)

                if deleter.delete_all_gateways():
                    deleted_gateways = [g["gatewayId"] for g in gateways]

        elif args.from_deployment:
            # Load from deployment file
            deployment_file = (
                args.from_deployment
                if args.from_deployment != True
                else "gateway-deployment.json"
            )
            deployment_info = deleter.load_deployment_info(deployment_file)

            if deployment_info and "gateway_id" in deployment_info:
                gateway_id = deployment_info["gateway_id"]
                logger.info(f"Found gateway ID in deployment file: {gateway_id}")

                if args.dry_run:
                    gateway_details = deleter.get_gateway_details(gateway_id)
                    if gateway_details:
                        logger.info(
                            f"Would delete gateway: {gateway_details.get('name', 'unnamed')} ({gateway_id})"
                        )
                        targets = deleter.list_gateway_targets(gateway_id)
                        logger.info(f"Would delete {len(targets)} targets")
                else:
                    if deleter.delete_gateway(gateway_id):
                        deleted_gateways.append(gateway_id)
            else:
                logger.error("No gateway_id found in deployment file")
                sys.exit(1)

        elif args.gateway_id:
            # Delete by gateway ID
            if args.dry_run:
                gateway_details = deleter.get_gateway_details(args.gateway_id)
                if gateway_details:
                    logger.info(
                        f"Would delete gateway: {gateway_details.get('name', 'unnamed')} ({args.gateway_id})"
                    )
                    targets = deleter.list_gateway_targets(args.gateway_id)
                    logger.info(f"Would delete {len(targets)} targets")
                else:
                    logger.error(f"Gateway {args.gateway_id} not found")
            else:
                if deleter.delete_gateway(args.gateway_id):
                    deleted_gateways.append(args.gateway_id)

        else:
            # Delete by name (default or specified)
            gateway_name = args.gateway_name or "agentcore-gateway"

            if args.dry_run:
                gateway = deleter.find_gateway_by_name(gateway_name)
                if gateway:
                    gateway_id = gateway["gatewayId"]
                    logger.info(f"Would delete gateway: {gateway_name} ({gateway_id})")
                    targets = deleter.list_gateway_targets(gateway_id)
                    logger.info(f"Would delete {len(targets)} targets")
                else:
                    logger.error(f"Gateway '{gateway_name}' not found")
            else:
                deleted_gateway_id = deleter.delete_gateway_by_name(gateway_name)
                if deleted_gateway_id:
                    deleted_gateways.append(deleted_gateway_id)

        # Print summary
        if not args.dry_run:
            deleter.print_deletion_summary(deleted_gateways)

        if deleted_gateways or args.dry_run:
            logger.info("Operation completed successfully")
        else:
            logger.warning("No gateways were deleted")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Deletion cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deletion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
