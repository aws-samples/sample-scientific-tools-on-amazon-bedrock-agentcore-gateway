#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Amazon Bedrock AgentCore Gateway Deployment Script

This script deploys an Amazon Bedrock AgentCore Gateway using boto3.
It retrieves configuration from Systems Manager Parameter Store and Secrets Manager,
creates the necessary IAM role, and sets up the gateway with Cognito JWT authorization.

Note: This script will no longer be necessary once AgentCore receives CloudFormation/CDK support.

Prerequisites:
- AWS CLI configured with appropriate permissions
- AgentCore Gateway IAM role stack deployed (provides IAM role ARN)
- Cognito stack deployed (provides client ID, discovery URL, and client secret)
- SageMaker async inference stack deployed (optional, for Lambda targets)
  Note: The SageMaker stack must be deployed with the updated CDK template that stores
  the Lambda function ARN in Systems Manager Parameter Store

Usage:
    # First deploy the IAM role stack
    cd gateway && cdk deploy AgentCoreGatewayRole
    
    # Then deploy the gateway
    python deploy_agentcore_gateway.py [--gateway-name my-gateway]
"""

import argparse
import boto3
import json
import logging
import os
import sys

from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentCoreGatewayDeployer:
    """Handles deployment of Amazon Bedrock AgentCore Gateway."""

    def __init__(self, region: Optional[str] = None):
        """Initialize the deployer with AWS clients."""
        self.region = region or boto3.Session().region_name

        # Initialize AWS clients
        try:
            self.ssm_client = boto3.client("ssm", region_name=self.region)
            self.secrets_client = boto3.client(
                "secretsmanager", region_name=self.region
            )
            self.iam_client = boto3.client("iam", region_name=self.region)
            self.sts_client = boto3.client("sts", region_name=self.region)
            self.agentcore_client = boto3.client(
                "bedrock-agentcore-control", region_name=self.region
            )

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

    def get_cognito_configuration(self) -> Dict[str, str]:
        """Retrieve Cognito configuration from SSM Parameter Store and Secrets Manager."""
        logger.info("Retrieving Cognito configuration...")

        config = {}

        try:
            # Get client ID from SSM Parameter Store
            client_id_param = f"/cognito/client-id"
            response = self.ssm_client.get_parameter(Name=client_id_param)
            config["client_id"] = response["Parameter"]["Value"]
            logger.info(f"Retrieved client ID from {client_id_param}")

            # Get discovery URL from SSM Parameter Store
            discovery_url_param = f"/cognito/discovery-url"
            response = self.ssm_client.get_parameter(Name=discovery_url_param)
            config["discovery_url"] = response["Parameter"]["Value"]
            logger.info(f"Retrieved discovery URL from {discovery_url_param}")

            # Get user pool ID from SSM Parameter Store
            user_pool_id_param = f"/cognito/user-pool-id"
            response = self.ssm_client.get_parameter(Name=user_pool_id_param)
            config["user_pool_id"] = response["Parameter"]["Value"]
            logger.info(f"Retrieved user pool ID from {user_pool_id_param}")

            # Get client secret from Secrets Manager
            secret_name = f"cognito-client-secret"
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])
            config["client_secret"] = secret_data["client_secret"]
            logger.info(f"Retrieved client secret from {secret_name}")

            return config

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ParameterNotFound":
                logger.error(
                    f"SSM Parameter not found. Make sure the Cognito stack is deployed"
                )
            elif error_code == "ResourceNotFoundException":
                logger.error(
                    f"Secrets Manager secret not found. Make sure the Cognito stack is deployed"
                )
            else:
                logger.error(f"AWS error retrieving Cognito configuration: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error retrieving Cognito configuration: {e}")
            sys.exit(1)

    def get_agentcore_gateway_role_arn(self) -> str:
        """Retrieve IAM role ARN from SSM Parameter Store (created by CDK stack)."""
        logger.info(
            "Retrieving AgentCore Gateway IAM role ARN from SSM Parameter Store..."
        )

        try:
            # Get role ARN from SSM Parameter Store
            role_arn_param = f"/agentcore-gateway/role-arn"
            response = self.ssm_client.get_parameter(Name=role_arn_param)
            role_arn = response["Parameter"]["Value"]
            logger.info(f"Retrieved role ARN from {role_arn_param}: {role_arn}")
            return role_arn

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ParameterNotFound":
                logger.error(
                    f"SSM Parameter not found: {role_arn_param}\n"
                    f"Make sure to deploy the AgentCore Gateway role stack first:\n"
                    f"  cd gateway && cdk deploy AgentCoreGatewayRole"
                )
            else:
                logger.error(f"AWS error retrieving role ARN: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error retrieving role ARN: {e}")
            sys.exit(1)

    def create_gateway(
        self,
        gateway_name: str,
        role_arn: str,
        cognito_config: Dict[str, str],
        use_existing: bool = False,
    ) -> Dict[str, Any]:
        """Create the AgentCore Gateway with Cognito JWT authorization."""
        logger.info(f"Creating AgentCore Gateway: {gateway_name}")

        # Configure JWT authorizer with Cognito
        auth_config = {
            "customJWTAuthorizer": {
                "discoveryUrl": cognito_config["discovery_url"],
                "allowedClients": [cognito_config["client_id"]],
            }
        }

        try:
            # Create the gateway
            response = self.agentcore_client.create_gateway(
                name=gateway_name,
                description=f"AgentCore Gateway",
                roleArn=role_arn,
                protocolType="MCP",
                authorizerType="CUSTOM_JWT",
                authorizerConfiguration=auth_config,
                protocolConfiguration={
                    "mcp": {
                        "searchType": "SEMANTIC"  # Enable semantic search for better tool discovery
                    }
                },
            )

            gateway_id = response["gatewayId"]
            gateway_url = response["gatewayUrl"]

            logger.info(f"Successfully created gateway:")
            logger.info(f"  Gateway ID: {gateway_id}")
            logger.info(f"  Gateway URL: {gateway_url}")

            return {
                "gateway_id": gateway_id,
                "gateway_url": gateway_url,
                "response": response,
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConflictException":
                if use_existing:
                    logger.info(
                        f"Gateway '{gateway_name}' already exists, using existing gateway"
                    )
                    return self._get_existing_gateway(gateway_name)
                else:
                    logger.error(
                        f"Gateway with name '{gateway_name}' already exists. Use --use-existing to use the existing gateway."
                    )
            elif error_code == "ValidationException":
                logger.error(f"Invalid gateway configuration: {e}")
            else:
                logger.error(f"AWS error creating gateway: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error creating gateway: {e}")
            sys.exit(1)

    def _get_existing_gateway(self, gateway_name: str) -> Dict[str, Any]:
        """Get information about an existing gateway."""
        try:
            # List gateways to find the one with matching name
            response = self.agentcore_client.list_gateways()

            for gateway in response.get("items", []):
                if gateway["name"] == gateway_name:
                    gateway_id = gateway["gatewayId"]

                    # Get detailed gateway information to get the URL
                    gateway_details = self.agentcore_client.get_gateway(
                        gatewayIdentifier=gateway_id
                    )
                    gateway_url = gateway_details["gatewayUrl"]

                    logger.info(f"Found existing gateway:")
                    logger.info(f"  Gateway ID: {gateway_id}")
                    logger.info(f"  Gateway URL: {gateway_url}")

                    return {
                        "gateway_id": gateway_id,
                        "gateway_url": gateway_url,
                        "response": gateway_details,
                    }

            # If we get here, the gateway wasn't found in the list
            logger.error(
                f"Gateway '{gateway_name}' exists but couldn't be found in gateway list"
            )
            logger.error(
                f"Available gateways: {[g['name'] for g in response.get('items', [])]}"
            )
            sys.exit(1)

        except Exception as e:
            logger.error(f"Error retrieving existing gateway information: {e}")
            sys.exit(1)

    def get_access_token(self, cognito_config: Dict[str, str]) -> str:
        """Get access token from Cognito for testing the gateway."""
        logger.info("Requesting access token from Cognito...")

        try:
            # Use user pool ID directly from SSM Parameter Store
            user_pool_id = cognito_config["user_pool_id"]

            # Build token endpoint URL
            user_pool_id_without_underscore = user_pool_id.replace("_", "")
            token_url = f"https://{user_pool_id_without_underscore}.auth.{self.region}.amazoncognito.com/oauth2/token"

            # Prepare token request
            import requests

            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "grant_type": "client_credentials",
                "client_id": cognito_config["client_id"],
                "client_secret": cognito_config["client_secret"],
                "scope": "agentcore-gateway-id/gateway:read agentcore-gateway-id/gateway:write",
            }

            response = requests.post(token_url, headers=headers, data=data, timeout=5)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data["access_token"]

            logger.info("Successfully obtained access token")
            return access_token

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Failed to get access token (this may be expected if domain is still propagating): {e}"
            )
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting access token: {e}")
            return None

    def get_lambda_function_arn(self) -> Optional[str]:
        """Get Lambda function ARN from Systems Manager Parameter Store."""
        logger.info(
            "Retrieving Lambda function ARN from Systems Manager Parameter Store..."
        )

        # Try different possible parameter names
        possible_parameter_names = [
            f"/protein-agent/lambda-function-arn",
            f"/sagemaker-async/lambda-function-arn",
        ]

        for param_name in possible_parameter_names:
            try:
                logger.info(f"Checking parameter: {param_name}")
                response = self.ssm_client.get_parameter(Name=param_name)
                lambda_arn = response["Parameter"]["Value"]
                logger.info(f"Found Lambda function ARN: {lambda_arn}")
                return lambda_arn

            except ClientError as e:
                if e.response["Error"]["Code"] == "ParameterNotFound":
                    logger.debug(f"Parameter {param_name} not found, trying next...")
                    continue
                else:
                    logger.warning(f"Error checking parameter {param_name}: {e}")
                    continue
            except Exception as e:
                logger.warning(f"Unexpected error checking parameter {param_name}: {e}")
                continue

        logger.warning(
            "Could not find Lambda function ARN in Systems Manager Parameter Store"
        )
        logger.info(
            "Make sure the SageMaker async inference stack is deployed with the updated CDK template"
        )
        return None

    def _get_existing_lambda_target(
        self, gateway_id: str, target_name: str, lambda_arn: str
    ) -> Dict[str, Any]:
        """Get information about an existing Lambda target."""
        try:
            # List gateway targets to find the one with matching name
            response = self.agentcore_client.list_gateway_targets(
                gatewayIdentifier=gateway_id
            )

            for target in response.get("items", []):
                if target["name"] == target_name:
                    target_id = target["targetId"]

                    logger.info(f"Found existing Lambda target:")
                    logger.info(f"  Target ID: {target_id}")
                    logger.info(f"  Lambda ARN: {lambda_arn}")

                    return {
                        "target_id": target_id,
                        "lambda_arn": lambda_arn,
                        "response": target,
                    }

            # If we get here, the target wasn't found in the list
            # nosemgrep logging-error-without-handling
            logger.error(
                f"Lambda target '{target_name}' exists but couldn't be found in target list"
            )
            raise Exception(f"Target '{target_name}' not found")

        
        except Exception as e:
            # nosemgrep logging-error-without-handling
            logger.error(f"Error retrieving existing Lambda target information: {e}")
            raise

    def create_lambda_target(self, gateway_id: str, lambda_arn: str) -> Dict[str, Any]:
        """Create a Lambda target for the AgentCore Gateway."""
        logger.info(f"Creating Lambda target for gateway {gateway_id}")

        # Define the tool schema for the protein engineering Lambda function
        tool_schema = {
            "inlinePayload": [
                {
                    "name": "invoke_endpoint",
                    "description": "Submit a job to predict the variant effects for an amino acid sequence",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "sequence": {
                                "type": "string",
                                "description": "Amino acid sequence",
                            }
                        },
                        "required": ["sequence"],
                    },
                },
                {
                    "name": "get_results",
                    "description": "Check if a variant effect prediction job has completed and, if so, retrieve the results.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "output_id": {
                                "type": "string",
                                "description": "output_id returned by the invoke_endpoint request",
                            }
                        },
                        "required": ["output_id"],
                    },
                },
            ]
        }

        try:
            # Create the Lambda target
            response = self.agentcore_client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name="protein-engineering-lambda",
                description="Lambda function for protein variant effect prediction",
                targetConfiguration={
                    "mcp": {
                        "lambda": {"lambdaArn": lambda_arn, "toolSchema": tool_schema}
                    }
                },
                credentialProviderConfigurations=[
                    {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                ],
            )

            target_id = response["targetId"]
            logger.info(f"Successfully created Lambda target: {target_id}")

            return {
                "target_id": target_id,
                "lambda_arn": lambda_arn,
                "response": response,
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConflictException":
                logger.info(
                    f"Lambda target 'protein-engineering-lambda' already exists for gateway '{gateway_id}', using existing target"
                )
                # Get existing target information
                return self._get_existing_lambda_target(
                    gateway_id, "protein-engineering-lambda", lambda_arn
                )
            elif error_code == "ValidationException":
                logger.error(f"Invalid target configuration: {e}")
            else:
                logger.error(f"AWS error creating Lambda target: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating Lambda target: {e}")
            raise

    def deploy(self, gateway_name: str, use_existing: bool = False) -> Dict[str, Any]:
        """Deploy the complete AgentCore Gateway setup."""
        logger.info(f"Starting deployment of AgentCore Gateway: {gateway_name}")

        # Step 1: Get Cognito configuration
        cognito_config = self.get_cognito_configuration()

        # Step 2: Get IAM role ARN from CDK stack
        role_arn = self.get_agentcore_gateway_role_arn()

        # Step 3: Create gateway
        gateway_info = self.create_gateway(
            gateway_name, role_arn, cognito_config, use_existing
        )

        # Step 4: Create Lambda target (if Lambda function is available)
        lambda_target_info = None
        lambda_arn = self.get_lambda_function_arn()
        if lambda_arn:
            try:
                lambda_target_info = self.create_lambda_target(
                    gateway_info["gateway_id"], lambda_arn
                )
                logger.info("Lambda target created successfully")
            except Exception as e:
                logger.warning(
                    f"Failed to create Lambda target (gateway still functional): {e}"
                )
        else:
            logger.warning(
                "Lambda function ARN not found - gateway created without Lambda target"
            )

        # Step 5: Get access token for testing (optional)
        access_token = self.get_access_token(cognito_config)

        # Prepare deployment summary
        deployment_result = {
            "gateway_id": gateway_info["gateway_id"],
            "gateway_url": gateway_info["gateway_url"],
            "role_arn": role_arn,
            "region": self.region,
            "cognito_config": {
                "client_id": cognito_config["client_id"],
                "user_pool_id": cognito_config["user_pool_id"],
                "discovery_url": cognito_config["discovery_url"],
            },
            "lambda_target": lambda_target_info,
            "access_token": access_token,
        }

        # Print deployment summary
        self._print_deployment_summary(deployment_result)

        return deployment_result

    def _print_deployment_summary(self, result: Dict[str, Any]) -> None:
        """Print a formatted deployment summary."""
        print("\n" + "=" * 80)
        print("🚀 AGENTCORE GATEWAY DEPLOYMENT SUCCESSFUL")
        print("=" * 80)
        print(f"Region:          {result['region']}")
        print(f"Gateway ID:      {result['gateway_id']}")
        print(f"Gateway URL:     {result['gateway_url']}")
        print(f"IAM Role ARN:    {result['role_arn']}")
        print()
        print("📋 COGNITO CONFIGURATION")
        print("-" * 40)
        print(f"Client ID:       {result['cognito_config']['client_id']}")
        print(f"User Pool ID:    {result['cognito_config']['user_pool_id']}")
        print(f"Discovery URL:   {result['cognito_config']['discovery_url']}")
        print()

        if result.get("lambda_target"):
            print("🔧 LAMBDA TARGET")
            print("-" * 40)
            print(f"Target ID:       {result['lambda_target']['target_id']}")
            print(f"Lambda ARN:      {result['lambda_target']['lambda_arn']}")
            print("Available Tools: invoke_endpoint, get_results")
            print()
        else:
            print("⚠️  LAMBDA TARGET")
            print("-" * 40)
            print("No Lambda target configured - you can add targets manually")
            print()

        if result.get("access_token"):
            print("🔑 ACCESS TOKEN (for testing)")
            print("-" * 40)
            print(f"Token:           {result['access_token'][:50]}...")
            print()

        print("📝 NEXT STEPS")
        print("-" * 40)
        if result.get("lambda_target"):
            print("1. Test the gateway endpoint with the provided access token")
            print("2. Configure your MCP client to use the gateway URL")
            print("3. Try the available tools: invoke_endpoint, get_results")
            print("4. Monitor gateway performance in CloudWatch")
        else:
            print("1. Add targets to your gateway using the AWS Console or CLI")
            print("2. Test the gateway endpoint with the provided access token")
            print("3. Configure your MCP client to use the gateway URL")
            print("4. Monitor gateway performance in CloudWatch")
        print()
        print("📚 USEFUL COMMANDS")
        print("-" * 40)
        print(f"# Deploy/update IAM role stack")
        print(f"cd gateway && cdk deploy AgentCoreGatewayRole")
        print()
        print(f"# List gateways")
        print(
            f"aws bedrock-agentcore-control list-gateways --region {result['region']}"
        )
        print()
        print(f"# Get gateway details")
        print(
            f"aws bedrock-agentcore-control get-gateway --gateway-id {result['gateway_id']} --region {result['region']}"
        )
        print()
        if result.get("lambda_target"):
            print(f"# List gateway targets")
            print(
                f"aws bedrock-agentcore-control list-gateway-targets --gateway-id {result['gateway_id']} --region {result['region']}"
            )
            print()
        print(f"# Test gateway connectivity (if you have curl)")
        if result.get("access_token"):
            print(
                f"curl -H 'Authorization: Bearer {result['access_token'][:20]}...' \\"
            )
            print(f"     '{result['gateway_url']}'")
        print("=" * 80)


def main():
    """Main entry point for the deployment script."""
    parser = argparse.ArgumentParser(
        description="Deploy Amazon Bedrock AgentCore Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First deploy the IAM role stack
  cd gateway && cdk deploy AgentCoreGatewayRole
  
  # Then deploy the gateway
  python deploy_agentcore_gateway.py                                    # Deploy with defaults
  python deploy_agentcore_gateway.py --gateway-name my-custom-gateway   # Custom gateway name
  python deploy_agentcore_gateway.py --gateway-name test-gw --region us-west-2
        """,
    )

    parser.add_argument(
        "--gateway-name",
        "-n",
        default=None,
        help="Gateway name (default: agentcore-gateway)",
    )

    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region (default: current session region)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--use-existing",
        action="store_true",
        help="Use existing gateway if it exists instead of creating a new one",
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set default gateway name if not provided
    gateway_name = args.gateway_name or f"agentcore-gateway"

    try:
        # Initialize deployer
        deployer = AgentCoreGatewayDeployer(region=args.region)

        # Deploy gateway
        result = deployer.deploy(gateway_name, args.use_existing)

        # Save deployment info to file (excluding non-serializable response objects)
        output_file = f"gateway-deployment.json"
        serializable_result = {
            "gateway_id": result["gateway_id"],
            "gateway_url": result["gateway_url"],
            "role_arn": result["role_arn"],
            "region": result["region"],
            "cognito_config": result["cognito_config"],
            "lambda_target": (
                {
                    "target_id": result["lambda_target"]["target_id"],
                    "lambda_arn": result["lambda_target"]["lambda_arn"],
                }
                if result.get("lambda_target")
                else None
            ),
            "access_token": result.get("access_token"),
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(serializable_result, f, indent=2)

        logger.info(f"Deployment information saved to: {output_file}")

    except KeyboardInterrupt:
        logger.info("Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
