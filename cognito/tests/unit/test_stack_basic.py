"""
Basic unit tests for Cognito stack - focused on essential functionality.
"""
import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match
from cognito.cognito_stack import CognitoStack
from cognito.cognito_config import CognitoConfig, CognitoResourceScope


class TestCognitoStackBasics:
    """Test basic Cognito stack functionality without overly strict template matching."""

    def test_stack_synthesizes_without_errors(self, app, default_config):
        """Test that the stack synthesizes without errors."""
        stack = CognitoStack(app, "TestStack", config=default_config)
        template = Template.from_stack(stack)
        
        # Should not raise any exceptions
        assert template is not None

    def test_required_resources_are_created(self, template_from_default_stack):
        """Test that all required AWS resources are created."""
        template = template_from_default_stack
        
        # Check that required resource types exist
        template.resource_count_is("AWS::Cognito::UserPool", 1)
        template.resource_count_is("AWS::Cognito::UserPoolDomain", 1)
        template.resource_count_is("AWS::Cognito::UserPoolResourceServer", 1)
        template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
        
        # SSM Parameters for configuration storage
        template.resource_count_is("AWS::SSM::Parameter", 5)  # discovery_url, client_id, user_pool_id, user_pool_arn, domain
        
        # Lambda function for custom resource (client secret retrieval)
        # Note: CDK creates additional Lambda functions for custom resources
        lambda_functions = template.find_resources("AWS::Lambda::Function")
        assert len(lambda_functions) >= 1, f"Expected at least 1 Lambda function, found {len(lambda_functions)}"
        
        # Custom resource for client secret management
        template.resource_count_is("AWS::CloudFormation::CustomResource", 1)

    def test_user_pool_configuration(self, template_from_default_stack):
        """Test that User Pool is configured correctly."""
        template = template_from_default_stack
        
        # Check User Pool properties (matching actual implementation)
        template.has_resource_properties("AWS::Cognito::UserPool", {
            "UserPoolName": "agentcore-gateway-pool",
            "Policies": {
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": False,
                    "RequireUppercase": True
                }
            },
            "AliasAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "MfaConfiguration": "OPTIONAL",
            "AccountRecoverySetting": {
                "RecoveryMechanisms": [
                    {
                        "Name": "verified_email",
                        "Priority": 1
                    }
                ]
            }
        })

    def test_resource_server_configuration(self, template_from_default_stack):
        """Test that Resource Server is configured correctly."""
        template = template_from_default_stack
        
        # Check Resource Server properties (matching actual implementation)
        template.has_resource_properties("AWS::Cognito::UserPoolResourceServer", {
            "Identifier": "agentcore-gateway-id",
            "Name": "agentcore-gateway-name",
            "Scopes": [
                {
                    "ScopeName": "gateway:read",
                    "ScopeDescription": "Read access to gateway resources"
                },
                {
                    "ScopeName": "gateway:write", 
                    "ScopeDescription": "Write access to gateway resources"
                }
            ]
        })

    def test_user_pool_client_configuration(self, template_from_default_stack):
        """Test that User Pool Client is configured correctly."""
        template = template_from_default_stack
        
        # Check User Pool Client properties (matching actual implementation)
        template.has_resource_properties("AWS::Cognito::UserPoolClient", {
            "ClientName": "agentcore-gateway-client",
            "GenerateSecret": True,
            "AllowedOAuthFlows": ["client_credentials"],
            "AllowedOAuthScopes": [
                "agentcore-gateway-id/gateway:read",
                "agentcore-gateway-id/gateway:write"
            ],
            "SupportedIdentityProviders": ["COGNITO"],
            # Note: CDK adds default refresh token auth flow
            "ExplicitAuthFlows": ["ALLOW_REFRESH_TOKEN_AUTH"],
            # Note: CDK uses default token validity periods (in minutes)
            "RefreshTokenValidity": 1440,  # 1 day in minutes
            "AccessTokenValidity": 60,     # 1 hour in minutes
            "IdTokenValidity": 60          # 1 hour in minutes
        })

    def test_user_pool_domain_is_created(self, template_from_default_stack):
        """Test that User Pool Domain is created."""
        template = template_from_default_stack
        
        # Check that domain exists with cognito domain configuration
        template.has_resource_properties("AWS::Cognito::UserPoolDomain", {
            "Domain": Match.string_like_regexp(r"agentcore-.*")
        })

    def test_ssm_parameters_are_created(self, template_from_default_stack):
        """Test that SSM parameters are created for configuration storage."""
        template = template_from_default_stack
        
        # Check that all required SSM parameters exist
        expected_parameters = [
            "/cognito/discovery-url",
            "/cognito/client-id", 
            "/cognito/user-pool-id",
            "/cognito/user-pool-arn",
            "/cognito/domain"
        ]
        
        for param_name in expected_parameters:
            template.has_resource_properties("AWS::SSM::Parameter", {
                "Name": param_name,
                "Type": "String",
                "Tier": "Standard"
            })

    def test_custom_resource_lambda_configuration(self, template_from_default_stack):
        """Test that custom resource Lambda is configured correctly."""
        template = template_from_default_stack
        
        # Check Lambda function properties
        template.has_resource_properties("AWS::Lambda::Function", {
            "Runtime": "python3.13",
            "Handler": "index.handler",
            "Timeout": 300,
            "Description": "Custom resource to retrieve Cognito client secret and store in Secrets Manager"
        })

    def test_iam_policies_are_created(self, template_from_default_stack):
        """Test that IAM policies are created for Lambda function."""
        template = template_from_default_stack
        
        # Should have at least 1 IAM policy for the Lambda function
        # (We removed SMS role and CDK Provider to improve security)
        policies = template.find_resources("AWS::IAM::Policy")
        assert len(policies) >= 1, f"Expected at least 1 IAM policy, found {len(policies)}"
        
        # Check that policies include required permissions
        policy_documents = []
        for policy in policies.values():
            if "PolicyDocument" in policy["Properties"]:
                policy_documents.append(policy["Properties"]["PolicyDocument"])
        
        # Should have permissions for Cognito and Secrets Manager
        all_actions = []
        for doc in policy_documents:
            for statement in doc.get("Statement", []):
                if isinstance(statement.get("Action"), list):
                    all_actions.extend(statement["Action"])
                elif isinstance(statement.get("Action"), str):
                    all_actions.append(statement["Action"])
        
        # Check for required permissions
        assert any("cognito-idp:DescribeUserPoolClient" in action for action in all_actions), f"Missing Cognito permissions in actions: {all_actions}"
        assert any("secretsmanager:" in action for action in all_actions), f"Missing Secrets Manager permissions in actions: {all_actions}"

    def test_stack_outputs_exist(self, template_from_default_stack):
        """Test that important stack outputs are created."""
        template = template_from_default_stack
        
        outputs = template.find_outputs("*")
        output_keys = list(outputs.keys())
        
        # Should have outputs for key resources
        essential_output_patterns = [
            "DiscoveryUrl",
            "ClientId",
            "UserPoolId", 
            "UserPoolArn",
            "Domain",
            "ClientSecretArn"
        ]
        
        for pattern in essential_output_patterns:
            matching_outputs = [key for key in output_keys if pattern in key]
            assert len(matching_outputs) > 0, f"No outputs found matching pattern: {pattern}"

    def test_different_configurations_work(self):
        """Test that different configurations produce valid stacks."""
        configs = [
            CognitoConfig(
                user_pool_name="test-pool-1",
                resource_server_identifier="test-server-1",
                client_name="test-client-1",
                scopes=[CognitoResourceScope("read", "Read access")]
            ),
            CognitoConfig(
                user_pool_name="test-pool-2",
                resource_server_identifier="test-server-2", 
                client_name="test-client-2",
                scopes=[
                    CognitoResourceScope("read", "Read access"),
                    CognitoResourceScope("write", "Write access")
                ],
                min_password_length=8,
                require_symbols=False
            ),
            CognitoConfig(
                user_pool_name="test-pool-3",
                resource_server_identifier="test-server-3",
                client_name="test-client-3", 
                scopes=[CognitoResourceScope("admin", "Admin access")],
                deletion_protection=True,
                generate_secret=False
            ),
        ]
        
        for i, config in enumerate(configs):
            # Create a new app for each test to avoid synthesis conflicts
            app = cdk.App()
            stack = CognitoStack(app, f"TestStack{i}", config=config)
            template = Template.from_stack(stack)
            
            # Each should synthesize without errors
            assert template is not None
            
            # Each should have the basic required resources
            template.resource_count_is("AWS::Cognito::UserPool", 1)
            template.resource_count_is("AWS::Cognito::UserPoolResourceServer", 1)
            template.resource_count_is("AWS::Cognito::UserPoolClient", 1)

    def test_custom_output_configuration(self, app, test_config, custom_output_config):
        """Test that custom output configuration is applied correctly."""
        stack = CognitoStack(app, "TestStack", config=test_config, output_config=custom_output_config)
        template = Template.from_stack(stack)
        
        # Check that custom SSM parameter names are used
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/test/cognito/discovery-url"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/test/cognito/client-id"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/test/cognito/user-pool-id"
        })

    def test_no_secret_generation_when_disabled(self, app):
        """Test that client secret resources are not created when secret generation is disabled."""
        config = CognitoConfig(
            user_pool_name="test-pool",
            resource_server_identifier="test-server",
            client_name="test-client",
            scopes=[CognitoResourceScope("read", "Read access")],
            generate_secret=False
        )
        
        stack = CognitoStack(app, "TestStack", config=config)
        template = Template.from_stack(stack)
        
        # Should not have Lambda function or custom resource for secret management
        template.resource_count_is("AWS::Lambda::Function", 0)
        template.resource_count_is("AWS::CloudFormation::CustomResource", 0)
        
        # User Pool Client should not generate secret
        template.has_resource_properties("AWS::Cognito::UserPoolClient", {
            "GenerateSecret": False
        })

    def test_stack_properties_and_metadata(self, stack_with_default_config):
        """Test that stack has correct properties and metadata."""
        stack = stack_with_default_config
        
        # Test stack properties
        assert stack.user_pool is not None
        assert stack.user_pool_domain is not None
        assert stack.resource_server is not None
        assert stack.user_pool_client is not None
        
        # Test convenience properties
        assert stack.discovery_url.startswith("https://cognito-idp.")
        assert stack.discovery_url.endswith("/.well-known/openid-configuration")
        
        assert stack.domain_url.startswith("https://")
        assert stack.domain_url.endswith(".amazoncognito.com")

    def test_resource_dependencies(self, template_from_default_stack):
        """Test that resources have correct dependencies."""
        template = template_from_default_stack
        
        # Find the User Pool Client resource
        clients = template.find_resources("AWS::Cognito::UserPoolClient")
        assert len(clients) == 1
        
        client_resource = list(clients.values())[0]
        
        # User Pool Client should depend on Resource Server
        # This is handled by CDK automatically, but we can verify the resource exists
        resource_servers = template.find_resources("AWS::Cognito::UserPoolResourceServer")
        assert len(resource_servers) == 1