# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AWS CDK Stack for Cognito User Pool with Resource Server and Client.

This stack creates a complete Cognito setup including:
- User Pool with security best practices
- User Pool Domain
- Resource Server with custom scopes
- Machine-to-Machine Client with client credentials flow
- SSM Parameters for discovery URL and client ID
- Secrets Manager secret for client secret
"""

from typing import Optional
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    CustomResource,
    aws_cognito as cognito,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr,
)
from constructs import Construct

from .cognito_config import CognitoConfig, CognitoOutputConfig


class CognitoStack(Stack):
    """CDK Stack for AWS Cognito User Pool with Resource Server and Client."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Optional[CognitoConfig] = None,
        output_config: Optional[CognitoOutputConfig] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Initialize configurations
        self.config = config or CognitoConfig()
        self.output_config = output_config or CognitoOutputConfig()

        # Validate configuration
        self.config.validate()

        # Create Cognito resources
        self.user_pool = self._create_user_pool()
        self.user_pool_domain = self._create_user_pool_domain()
        self.resource_server = self._create_resource_server()
        self.user_pool_client = self._create_user_pool_client()

        # Store outputs in SSM and Secrets Manager
        self._create_ssm_parameters()
        self._create_secrets()

        # Create CloudFormation outputs
        self._create_outputs()

    def _create_user_pool(self) -> cognito.UserPool:
        """Create Cognito User Pool with security best practices."""

        # Configure password policy
        password_policy = cognito.PasswordPolicy(
            min_length=self.config.min_password_length,
            require_lowercase=self.config.require_lowercase,
            require_uppercase=self.config.require_uppercase,
            require_digits=self.config.require_digits,
            require_symbols=self.config.require_symbols,
        )

        # Configure sign-in aliases
        sign_in_aliases = cognito.SignInAliases(email=True, username=True)

        # Configure auto-verified attributes
        auto_verify = cognito.AutoVerifiedAttrs(
            email=self.config.auto_verify.get("email", False),
            phone=self.config.auto_verify.get("phone", False),
        )

        # Configure MFA settings
        mfa_second_factor = cognito.MfaSecondFactor(
            sms=self.config.mfa_second_factor.get("sms", False),
            otp=self.config.mfa_second_factor.get("otp", False),
        )

        # Only create SMS role if MFA with SMS is enabled
        sms_role = None
        if self.config.mfa != cognito.Mfa.OFF and self.config.mfa_second_factor.get(
            "sms", False
        ):
            # Use AWS managed policy for SMS role to avoid wildcard permissions
            sms_role = iam.Role(
                self,
                "CognitoSMSRole",
                assumed_by=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
                description="Role for Cognito User Pool to send SMS messages",
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "service-role/AmazonCognitoIdpSMSRole"
                    )
                ],
            )

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=self.config.user_pool_name,
            password_policy=password_policy,
            sign_in_aliases=sign_in_aliases,
            auto_verify=auto_verify,
            mfa=self.config.mfa,
            mfa_second_factor=mfa_second_factor,
            account_recovery=self.config.account_recovery,
            deletion_protection=self.config.deletion_protection,
            removal_policy=(
                RemovalPolicy.RETAIN
                if self.config.deletion_protection
                else RemovalPolicy.DESTROY
            ),
            sms_role=sms_role,
        )

        # Add tags for better resource management
        cdk.Tags.of(user_pool).add("Component", "Authentication")
        cdk.Tags.of(user_pool).add("Purpose", "AgentCore Gateway")

        return user_pool

    def _create_user_pool_domain(self) -> cognito.UserPoolDomain:
        """Create Cognito User Pool Domain."""

        # Generate domain prefix if not provided
        domain_prefix = self.config.domain_prefix
        if not domain_prefix:
            # Generate a unique domain prefix using uuid
            import uuid

            # Create a short unique suffix
            unique_suffix = str(uuid.uuid4())[:8]
            domain_prefix = f"agentcore-{unique_suffix}"

        domain = cognito.UserPoolDomain(
            self,
            "UserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=domain_prefix),
        )

        return domain

    def _create_resource_server(self) -> cognito.UserPoolResourceServer:
        """Create Cognito Resource Server with custom scopes."""

        # Convert scope configuration to CDK format
        scopes = []
        for scope_config in self.config.scopes:
            scopes.append(
                cognito.ResourceServerScope(
                    scope_name=scope_config.scope_name,
                    scope_description=scope_config.scope_description,
                )
            )

        resource_server = cognito.UserPoolResourceServer(
            self,
            "ResourceServer",
            identifier=self.config.resource_server_identifier,
            user_pool=self.user_pool,
            user_pool_resource_server_name=self.config.resource_server_name,
            scopes=scopes,
        )

        return resource_server

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        """Create Cognito User Pool Client for machine-to-machine authentication."""

        # Build OAuth scopes for the client
        oauth_scopes = []
        for scope_config in self.config.scopes:
            scope_name = (
                f"{self.config.resource_server_identifier}/{scope_config.scope_name}"
            )
            oauth_scopes.append(cognito.OAuthScope.custom(scope_name))

        client = cognito.UserPoolClient(
            self,
            "UserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name=self.config.client_name,
            generate_secret=self.config.generate_secret,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True), scopes=oauth_scopes
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            auth_flows=cognito.AuthFlow(
                user_password=False,
                user_srp=False,
                custom=False,
                admin_user_password=False,
            ),
            # Disable refresh token auth for M2M clients
            refresh_token_validity=cdk.Duration.days(1),
            access_token_validity=cdk.Duration.hours(1),
            id_token_validity=cdk.Duration.hours(1),
        )

        # Add dependency to ensure resource server is created first
        client.node.add_dependency(self.resource_server)

        return client

    def _create_ssm_parameters(self) -> None:
        """Create SSM Parameters for Cognito configuration."""

        # Discovery URL
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"

        ssm.StringParameter(
            self,
            "DiscoveryUrlParameter",
            parameter_name=self.output_config.discovery_url_parameter_name,
            string_value=discovery_url,
            description="Cognito User Pool OpenID Connect Discovery URL",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Client ID
        ssm.StringParameter(
            self,
            "ClientIdParameter",
            parameter_name=self.output_config.client_id_parameter_name,
            string_value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            tier=ssm.ParameterTier.STANDARD,
        )

        # User Pool ID
        ssm.StringParameter(
            self,
            "UserPoolIdParameter",
            parameter_name=self.output_config.user_pool_id_parameter_name,
            string_value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            tier=ssm.ParameterTier.STANDARD,
        )

        # User Pool ARN
        ssm.StringParameter(
            self,
            "UserPoolArnParameter",
            parameter_name=self.output_config.user_pool_arn_parameter_name,
            string_value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Domain
        domain_url = f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com"
        ssm.StringParameter(
            self,
            "DomainParameter",
            parameter_name=self.output_config.domain_parameter_name,
            string_value=domain_url,
            description="Cognito User Pool Domain URL",
            tier=ssm.ParameterTier.STANDARD,
        )

    def _create_secrets(self) -> None:
        """Create Secrets Manager secret for client secret using a custom resource."""

        if self.config.generate_secret:
            # Create the custom resource to retrieve and store the client secret
            self._create_client_secret_custom_resource()

    def _create_client_secret_custom_resource(self) -> None:
        """Create a custom resource to automatically retrieve and store the client secret."""

        # Create the Lambda function for the custom resource
        client_secret_lambda = lambda_.Function(
            self,
            "ClientSecretLambda",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline(self._get_client_secret_lambda_code()),
            timeout=cdk.Duration.minutes(5),
            description="Custom resource to retrieve Cognito client secret and store in Secrets Manager",
        )

        # Grant permissions to the Lambda function
        client_secret_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cognito-idp:DescribeUserPoolClient"],
                resources=[self.user_pool.user_pool_arn],
            )
        )

        # Add specific Secrets Manager permissions
        # Note: AWS Secrets Manager automatically appends a 6-character suffix to secret names
        client_secret_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:PutSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{self.output_config.client_secret_name}-??????"
                ],
            )
        )

        # Create the custom resource directly using the Lambda function
        # This avoids the CDK Provider construct which creates additional Lambda functions
        client_secret_resource = CustomResource(
            self,
            "ClientSecretResource",
            service_token=client_secret_lambda.function_arn,
            properties={
                "UserPoolId": self.user_pool.user_pool_id,
                "ClientId": self.user_pool_client.user_pool_client_id,
                "SecretName": self.output_config.client_secret_name,
                "Region": self.region,
            },
        )

        # Grant CloudFormation permission to invoke the Lambda function
        client_secret_lambda.add_permission(
            "AllowCloudFormationInvoke",
            principal=iam.ServicePrincipal("cloudformation.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        # Ensure the custom resource runs after the client is created
        client_secret_resource.node.add_dependency(self.user_pool_client)

        # Create a reference to the secret for outputs
        self.client_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "ClientSecret", secret_name=self.output_config.client_secret_name
        )

    def _get_client_secret_lambda_code(self) -> str:
        """Get the Lambda function code for the client secret custom resource."""
        return '''
import json
import boto3
import logging
import urllib3
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_response(event, context, response_status, response_data=None, physical_resource_id=None, reason=None):
    """Send response to CloudFormation."""
    response_data = response_data or {}
    
    response_body = {
        'Status': response_status,
        'Reason': reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    logger.info(f"Response body: {json.dumps(response_body)}")
    
    try:
        http = urllib3.PoolManager()
        response = http.request(
            'PUT',
            event['ResponseURL'],
            body=json.dumps(response_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        logger.info(f"CloudFormation response status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {str(e)}")
        raise e

def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Custom resource handler to retrieve Cognito client secret and store in Secrets Manager.
    """
    logger.info(f"Event: {json.dumps(event, default=str)}")
    
    try:
        request_type = event['RequestType']
        properties = event['ResourceProperties']
        
        user_pool_id = properties['UserPoolId']
        client_id = properties['ClientId']
        secret_name = properties['SecretName']
        region = properties['Region']
        
        cognito = boto3.client('cognito-idp', region_name=region)
        secrets = boto3.client('secretsmanager', region_name=region)
        
        physical_resource_id = f"{secret_name}-{client_id}"
        
        if request_type in ['Create', 'Update']:
            # Get the client secret from Cognito
            logger.info(f"Retrieving client secret for client {client_id}")
            response = cognito.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            
            client_secret = response['UserPoolClient'].get('ClientSecret')
            if not client_secret:
                raise ValueError("Client secret not found - client may not be configured to generate secrets")
            
            # Create the discovery URL
            discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
            
            # Create the secret value as JSON
            secret_value = {
                "client_secret": client_secret,
                "client_id": client_id,
                "user_pool_id": user_pool_id,
                "discovery_url": discovery_url,
                "created_by": "cognito-cdk-stack",
                "region": region
            }
            
            # Store in Secrets Manager
            try:
                logger.info(f"Creating secret {secret_name}")
                secrets.create_secret(
                    Name=secret_name,
                    Description="Cognito User Pool Client Secret",
                    SecretString=json.dumps(secret_value)
                )
                logger.info(f"Successfully created secret {secret_name}")
            except secrets.exceptions.ResourceExistsException:
                logger.info(f"Secret {secret_name} already exists, updating...")
                secrets.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_value)
                )
                logger.info(f"Successfully updated secret {secret_name}")
            
            response_data = {
                'SecretName': secret_name,
                'SecretArn': f"arn:aws:secretsmanager:{region}:{context.invoked_function_arn.split(':')[4]}:secret:{secret_name}"
            }
            
            send_response(event, context, 'SUCCESS', response_data, physical_resource_id)
            
        elif request_type == 'Delete':
            # Optionally delete the secret (commented out to preserve data)
            # logger.info(f"Deleting secret {secret_name}")
            # try:
            #     secrets.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
            #     logger.info(f"Successfully deleted secret {secret_name}")
            # except secrets.exceptions.ResourceNotFoundException:
            #     logger.info(f"Secret {secret_name} not found, nothing to delete")
            
            logger.info(f"Skipping deletion of secret {secret_name} to preserve data")
            send_response(event, context, 'SUCCESS', {}, physical_resource_id)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        send_response(event, context, 'FAILED', {}, None, str(e))
        raise e
'''

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # Discovery URL
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"
        CfnOutput(
            self,
            self.output_config.discovery_url_output_name,
            value=discovery_url,
            description="Cognito User Pool OpenID Connect Discovery URL",
            export_name=f"{self.stack_name}-DiscoveryUrl",
        )

        # Client ID
        CfnOutput(
            self,
            self.output_config.client_id_output_name,
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name=f"{self.stack_name}-ClientId",
        )

        # User Pool ID
        CfnOutput(
            self,
            self.output_config.user_pool_id_output_name,
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name=f"{self.stack_name}-UserPoolId",
        )

        # User Pool ARN
        CfnOutput(
            self,
            self.output_config.user_pool_arn_output_name,
            value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN",
            export_name=f"{self.stack_name}-UserPoolArn",
        )

        # Domain URL
        domain_url = f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com"
        CfnOutput(
            self,
            self.output_config.domain_output_name,
            value=domain_url,
            description="Cognito User Pool Domain URL",
            export_name=f"{self.stack_name}-Domain",
        )

        # Client Secret ARN (if secret is generated)
        if self.config.generate_secret and hasattr(self, "client_secret"):
            secret_arn = f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{self.output_config.client_secret_name}"
            CfnOutput(
                self,
                self.output_config.client_secret_arn_output_name,
                value=secret_arn,
                description="Cognito User Pool Client Secret ARN in Secrets Manager",
                export_name=f"{self.stack_name}-ClientSecretArn",
            )

    @property
    def discovery_url(self) -> str:
        """Get the OpenID Connect discovery URL."""
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"

    @property
    def domain_url(self) -> str:
        """Get the Cognito domain URL."""
        return f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com"
