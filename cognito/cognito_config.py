# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Configuration classes for Cognito CDK Stack.

This module provides configuration classes for managing Cognito
User Pool, Resource Server, and Client settings.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from aws_cdk import aws_cognito as cognito


@dataclass
class CognitoResourceScope:
    """Configuration for a Cognito Resource Server scope."""

    scope_name: str
    scope_description: str


@dataclass
class CognitoConfig:
    """Configuration for Cognito User Pool and related resources."""

    # User Pool Configuration
    user_pool_name: str = "agentcore-gateway-pool"

    # Resource Server Configuration
    resource_server_identifier: str = "agentcore-gateway-id"
    resource_server_name: str = "agentcore-gateway-name"
    scopes: List[CognitoResourceScope] = None

    # Client Configuration
    client_name: str = "agentcore-gateway-client"
    generate_secret: bool = True

    # Domain Configuration
    domain_prefix: Optional[str] = None  # If None, will auto-generate

    # Password Policy
    min_password_length: int = 8
    require_lowercase: bool = True
    require_uppercase: bool = True
    require_digits: bool = True
    require_symbols: bool = False

    # Threat Protection (replaces deprecated Advanced Security)
    enable_threat_protection: bool = True

    # MFA Configuration
    mfa: cognito.Mfa = cognito.Mfa.OPTIONAL
    mfa_second_factor: Dict[str, bool] = None

    # Account Recovery
    account_recovery: cognito.AccountRecovery = cognito.AccountRecovery.EMAIL_ONLY

    # Auto-verified attributes
    auto_verify: Dict[str, bool] = None

    # Deletion protection - set to True for production deployments
    deletion_protection: bool = False

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.scopes is None:
            self.scopes = [
                CognitoResourceScope(
                    "gateway:read", "Read access to gateway resources"
                ),
                CognitoResourceScope(
                    "gateway:write", "Write access to gateway resources"
                ),
            ]

        if self.mfa_second_factor is None:
            self.mfa_second_factor = {"sms": True, "otp": True}

        if self.auto_verify is None:
            self.auto_verify = {"email": True, "phone": False}

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.min_password_length < 6:
            raise ValueError("Minimum password length must be at least 6 characters")

        if self.min_password_length > 128:
            raise ValueError("Maximum password length cannot exceed 128 characters")

        if not self.user_pool_name:
            raise ValueError("User pool name cannot be empty")

        if not self.resource_server_identifier:
            raise ValueError("Resource server identifier cannot be empty")

        if not self.client_name:
            raise ValueError("Client name cannot be empty")

        if not self.scopes:
            raise ValueError("At least one scope must be defined")

        # Validate scope names
        for scope in self.scopes:
            if not scope.scope_name or not scope.scope_description:
                raise ValueError("Scope name and description cannot be empty")


@dataclass
class CognitoOutputConfig:
    """Configuration for CDK outputs and parameter storage."""

    # SSM Parameter names
    discovery_url_parameter_name: str = "/cognito/discovery-url"
    client_id_parameter_name: str = "/cognito/client-id"
    user_pool_id_parameter_name: str = "/cognito/user-pool-id"
    user_pool_arn_parameter_name: str = "/cognito/user-pool-arn"
    domain_parameter_name: str = "/cognito/domain"

    # Secrets Manager secret name
    client_secret_name: str = "cognito-client-secret"

    # CloudFormation output names
    discovery_url_output_name: str = "CognitoDiscoveryUrl"
    client_id_output_name: str = "CognitoClientId"
    user_pool_id_output_name: str = "CognitoUserPoolId"
    user_pool_arn_output_name: str = "CognitoUserPoolArn"
    domain_output_name: str = "CognitoDomain"
    client_secret_arn_output_name: str = "CognitoClientSecretArn"
