#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions


app = cdk.App()

project_name = app.node.try_get_context("project_name") or "protein-engineering"

# Configure AWS environment
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)
##########################
# SageMaker Stack
##########################

from vep_endpoint.vep_endpoint_stack import (
    VEPEndpointStack,
    VEPEndpointConfig,
)

# Stack tags for resource management
stack_tags = {
    "Project": project_name,
    "ManagedBy": "CDK",
    "Repository": "protein-engineering-agent",
}

# Configure SageMaker Async Inference Stack
sagemaker_config = VEPEndpointConfig(
    instance_type="ml.g6.2xlarge",
    model_id="chandar-lab/AMPLIFY_350M",
    s3_bucket_name=None,  # Will create default bucket
    min_capacity=1,  # Update this to 0 to enable complete autoscaling to 0
    max_capacity=2,
    max_concurrent_invocations=4,
    enable_autoscaling=True,
)

# Deploy the SageMaker Async Inference Stack
sagemaker_stack = VEPEndpointStack(
    app,
    f"VEPEndpointStack",
    config=sagemaker_config,
    description=f"SageMaker Async Inference infrastructure for variant effect prediction",
    tags=stack_tags,
)

# Add stack-level metadata for resource management
sagemaker_stack.add_metadata("StackType", "SageMakerAsyncInference")
sagemaker_stack.add_metadata("Version", "1.0.0")
sagemaker_stack.add_metadata("Owner", "MLOps")
sagemaker_stack.add_metadata("ModelType", "AMPLIFY")

##########################
# Cognito Stack
##########################

from cognito.cognito_stack import CognitoStack
from cognito.cognito_config import (
    CognitoConfig,
    CognitoOutputConfig,
    CognitoResourceScope,
)
from aws_cdk import aws_cognito as cognito

# Create custom configuration
config = CognitoConfig(
    user_pool_name="agentcore-gateway-pool",
    resource_server_identifier="agentcore-gateway",
    resource_server_name="AgentCore Gateway",
    client_name="agentcore-gateway-client",
    scopes=[
        CognitoResourceScope("gateway:read", "Read access to gateway resources"),
        CognitoResourceScope("gateway:write", "Write access to gateway resources"),
        CognitoResourceScope(
            "gateway:admin", "Administrative access to gateway resources"
        ),
    ],
    # Security settings
    min_password_length=12,
    require_symbols=True,
    deletion_protection=False,
    enable_threat_protection=False,  # Advanced security requires Cognito Plus plan
    # Disable MFA for machine-to-machine authentication
    mfa=cognito.Mfa.OFF,
    mfa_second_factor={"sms": False, "otp": False},
)

# Create custom output configuration
output_config = CognitoOutputConfig(
    discovery_url_parameter_name="/cognito/discovery-url",
    client_id_parameter_name="/cognito/client-id",
    user_pool_id_parameter_name="/cognito/user-pool-id",
    user_pool_arn_parameter_name="/cognito/user-pool-arn",
    domain_parameter_name="/cognito/domain",
    client_secret_name="cognito-client-secret",
)

# Create the Cognito stack
cognito_stack = CognitoStack(
    app,
    "CognitoStack",
    config=config,
    output_config=output_config,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
    description=f"Cognito User Pool stack for AgentCore Gateway",
)

# Add tags to the stack
cdk.Tags.of(cognito_stack).add("Project", "AgentCore Gateway")
cdk.Tags.of(cognito_stack).add("Component", "Authentication")

##########################
# Gateway Stack
##########################

from gateway.gateway_stack import AgentCoreGatewayStack

# Deploy the Gateway role
gateway_stack = AgentCoreGatewayStack(
    app,
    "AgentCoreGatewayRole",
    env=cdk.Environment(account=app.account, region=app.region),
)

# Add explicit dependency to ensure VEP stack deploys first
gateway_stack.add_dependency(sagemaker_stack)

# Apply CDK Nag security checks
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# Add application-level CDK Nag suppressions for legitimate use cases
NagSuppressions.add_stack_suppressions(
    sagemaker_stack,
    [
        {
            "id": "AwsSolutions-IAM4",
            "reason": "AWS managed policy AWSLambdaBasicExecutionRole is used for Lambda functions. SageMaker execution role now uses scoped-down inline policies.",
            "applies_to": [
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            ],
        },
        {
            "id": "AwsSolutions-IAM5",
            "reason": "Wildcard permissions are necessary for SageMaker async inference operations including S3 prefix-based access patterns and CloudWatch logging.",
            "applies_to": [
                "Resource::*",  # ecr:GetAuthorizationToken does not accept resources
                "Resource::<AsyncInferenceBucketDB97A432.Arn>/async-inference-input/*",  # Access limited to only async inference bucket
                "Resource::<AsyncInferenceBucketDB97A432.Arn>/async-inference-output/*",  # Access limited to only async inference bucket
                "Resource::<AsyncInferenceBucketDB97A432.Arn>/async-inference-failures/*",  # Access limited to only async inference bucket
                "Resource::<AsyncInferenceBucketDB97A432.Arn>/model-artifacts/*",  # Access limited to only async inference bucket
                "Resource::<AsyncInferenceBucketDB97A432.Arn>/inference-code/*",  # Access limited to only async inference bucket
                "Resource::arn:aws:s3:::cdk-*-assets-<AWS::AccountId>-<AWS::Region>/*",  # Access limited to only CDK deployment bucket
                "Resource::arn:aws:s3:::cdk-*-assets-<AWS::AccountId>-<AWS::Region>",  # Access limited to only CDK deployment bucket
                "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/sagemaker/Endpoints/protein-agent-*",  # Access limited to only endpoint logs
                "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/sagemaker/Endpoints/protein-agent-*:*",  # Access limited to only endpoint logs
            ],
        },
    ],
)

NagSuppressions.add_stack_suppressions(
    cognito_stack,
    [
        {
            "id": "AwsSolutions-COG2",
            "reason": "MFA is not required for machine-to-machine authentication using client credentials flow. This is a service-to-service authentication pattern.",
        },
        {
            "id": "AwsSolutions-COG3",
            "reason": "Advanced security mode requires Cognito Plus feature plan which incurs additional costs. For development environments, basic security is sufficient.",
        },
        {
            "id": "AwsSolutions-IAM4",
            "reason": "AWS managed policy AWSLambdaBasicExecutionRole is used for Lambda functions that manage Cognito client secrets.",
            "applies_to": [
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ],
        },
    ],
)

app.synth()
