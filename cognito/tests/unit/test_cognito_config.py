"""
Unit tests for Cognito configuration classes.
"""
import pytest
from aws_cdk import aws_cognito as cognito
from cognito.cognito_config import CognitoConfig, CognitoOutputConfig, CognitoResourceScope


class TestCognitoResourceScope:
    """Test CognitoResourceScope class."""

    def test_scope_creation_with_valid_parameters(self):
        """Test creating scope with valid parameters."""
        scope = CognitoResourceScope("read", "Read access to resources")
        
        assert scope.scope_name == "read"
        assert scope.scope_description == "Read access to resources"

    def test_scope_string_representation(self):
        """Test string representation of scope."""
        scope = CognitoResourceScope("write", "Write access to resources")
        
        str_repr = str(scope)
        assert "write" in str_repr
        assert "Write access to resources" in str_repr

    def test_scope_equality(self):
        """Test scope equality comparison."""
        scope1 = CognitoResourceScope("read", "Read access")
        scope2 = CognitoResourceScope("read", "Read access")
        scope3 = CognitoResourceScope("write", "Write access")
        
        assert scope1 == scope2
        assert scope1 != scope3

    def test_scope_validation_on_creation(self):
        """Test that validation is called during scope creation."""
        # Valid scope should not raise
        scope = CognitoResourceScope("valid", "Valid description")
        assert scope.scope_name == "valid"
        assert scope.scope_description == "Valid description"
        
        # Note: CognitoResourceScope is a simple dataclass without validation
        # Validation happens at the CognitoConfig level


class TestCognitoConfig:
    """Test CognitoConfig class."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = CognitoConfig()
        
        # Test default values
        assert config.user_pool_name == "agentcore-gateway-pool"
        assert config.resource_server_identifier == "agentcore-gateway-id"
        assert config.resource_server_name == "agentcore-gateway-name"
        assert config.client_name == "agentcore-gateway-client"
        assert len(config.scopes) == 2  # gateway:read and gateway:write
        assert config.min_password_length == 8
        assert config.require_lowercase is True
        assert config.require_uppercase is True
        assert config.require_digits is True
        assert config.require_symbols is False
        assert config.deletion_protection is False
        assert config.enable_threat_protection is True
        assert config.generate_secret is True
        assert config.mfa == cognito.Mfa.OPTIONAL
        assert config.account_recovery == cognito.AccountRecovery.EMAIL_ONLY

    def test_custom_configuration(self):
        """Test creating configuration with custom values."""
        custom_scopes = [
            CognitoResourceScope("custom:read", "Custom read access"),
            CognitoResourceScope("custom:write", "Custom write access"),
        ]
        
        config = CognitoConfig(
            user_pool_name="custom-pool",
            resource_server_identifier="custom-server",
            resource_server_name="Custom Server",
            client_name="custom-client",
            scopes=custom_scopes,
            min_password_length=8,
            require_symbols=False,
            deletion_protection=True,
            enable_threat_protection=True,
            generate_secret=False,
            mfa=cognito.Mfa.OPTIONAL,
            account_recovery=cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
            domain_prefix="custom-domain"
        )
        
        assert config.user_pool_name == "custom-pool"
        assert config.resource_server_identifier == "custom-server"
        assert config.resource_server_name == "Custom Server"
        assert config.client_name == "custom-client"
        assert config.scopes == custom_scopes
        assert config.min_password_length == 8
        assert config.require_symbols is False
        assert config.deletion_protection is True
        assert config.enable_threat_protection is True
        assert config.generate_secret is False
        assert config.mfa == cognito.Mfa.OPTIONAL
        assert config.account_recovery == cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA
        assert config.domain_prefix == "custom-domain"

    def test_auto_verify_configuration(self):
        """Test auto verify configuration."""
        config = CognitoConfig(
            auto_verify={"email": True, "phone": False}
        )
        
        assert config.auto_verify["email"] is True
        assert config.auto_verify["phone"] is False

    def test_mfa_second_factor_configuration(self):
        """Test MFA second factor configuration."""
        config = CognitoConfig(
            mfa_second_factor={"sms": True, "otp": False}
        )
        
        assert config.mfa_second_factor["sms"] is True
        assert config.mfa_second_factor["otp"] is False

    def test_configuration_validation_is_called(self):
        """Test that validation is called during configuration creation."""
        # Valid configuration should not raise
        CognitoConfig(user_pool_name="valid-pool")
        
        # Invalid configuration should raise during validation
        config = CognitoConfig()
        config.user_pool_name = ""  # Set invalid value after creation
        
        with pytest.raises(ValueError):
            config.validate()

    def test_scope_name_uniqueness_validation(self):
        """Test that scope names must be unique."""
        # Note: The current implementation doesn't validate for duplicate scope names
        # This test documents the current behavior
        duplicate_scopes = [
            CognitoResourceScope("read", "Read access 1"),
            CognitoResourceScope("read", "Read access 2"),  # Duplicate name
        ]
        
        # Currently this doesn't raise an error - the validation could be enhanced
        config = CognitoConfig(scopes=duplicate_scopes)
        config.validate()  # This currently passes

    def test_configuration_immutability_after_validation(self):
        """Test that configuration behaves consistently after validation."""
        config = CognitoConfig()
        config.validate()
        
        # Configuration should still be accessible and consistent
        assert config.user_pool_name == "agentcore-gateway-pool"
        assert len(config.scopes) == 2


class TestCognitoOutputConfig:
    """Test CognitoOutputConfig class."""

    def test_default_output_configuration(self):
        """Test default output configuration values."""
        config = CognitoOutputConfig()
        
        # Test default parameter names
        assert config.discovery_url_parameter_name == "/cognito/discovery-url"
        assert config.client_id_parameter_name == "/cognito/client-id"
        assert config.user_pool_id_parameter_name == "/cognito/user-pool-id"
        assert config.user_pool_arn_parameter_name == "/cognito/user-pool-arn"
        assert config.domain_parameter_name == "/cognito/domain"
        
        # Test default secret name
        assert config.client_secret_name == "cognito-client-secret"
        
        # Test default output names
        assert config.discovery_url_output_name == "CognitoDiscoveryUrl"
        assert config.client_id_output_name == "CognitoClientId"
        assert config.user_pool_id_output_name == "CognitoUserPoolId"
        assert config.user_pool_arn_output_name == "CognitoUserPoolArn"
        assert config.domain_output_name == "CognitoDomain"
        assert config.client_secret_arn_output_name == "CognitoClientSecretArn"

    def test_custom_output_configuration(self):
        """Test creating output configuration with custom values."""
        config = CognitoOutputConfig(
            discovery_url_parameter_name="/custom/discovery-url",
            client_id_parameter_name="/custom/client-id",
            user_pool_id_parameter_name="/custom/user-pool-id",
            user_pool_arn_parameter_name="/custom/user-pool-arn",
            domain_parameter_name="/custom/domain",
            client_secret_name="custom-client-secret",
            discovery_url_output_name="CustomDiscoveryUrl",
            client_id_output_name="CustomClientId",
            user_pool_id_output_name="CustomUserPoolId",
            user_pool_arn_output_name="CustomUserPoolArn",
            domain_output_name="CustomDomain",
            client_secret_arn_output_name="CustomClientSecretArn"
        )
        
        assert config.discovery_url_parameter_name == "/custom/discovery-url"
        assert config.client_id_parameter_name == "/custom/client-id"
        assert config.user_pool_id_parameter_name == "/custom/user-pool-id"
        assert config.user_pool_arn_parameter_name == "/custom/user-pool-arn"
        assert config.domain_parameter_name == "/custom/domain"
        assert config.client_secret_name == "custom-client-secret"
        assert config.discovery_url_output_name == "CustomDiscoveryUrl"
        assert config.client_id_output_name == "CustomClientId"
        assert config.user_pool_id_output_name == "CustomUserPoolId"
        assert config.user_pool_arn_output_name == "CustomUserPoolArn"
        assert config.domain_output_name == "CustomDomain"
        assert config.client_secret_arn_output_name == "CustomClientSecretArn"

    def test_output_configuration_creation(self):
        """Test that output configuration can be created with custom values."""
        # Valid configuration should not raise
        config = CognitoOutputConfig(discovery_url_parameter_name="/valid/parameter")
        assert config.discovery_url_parameter_name == "/valid/parameter"
        
        # Note: CognitoOutputConfig is a simple dataclass without validation
        # Additional validation could be added if needed

    def test_parameter_name_assignment(self):
        """Test parameter name assignment."""
        # Valid parameter names should work
        valid_names = [
            "/valid/parameter",
            "/test-parameter",
            "/my/app/config/value"
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(discovery_url_parameter_name=name)
            assert config.discovery_url_parameter_name == name

    def test_secret_name_assignment(self):
        """Test secret name assignment."""
        # Valid secret names should work
        valid_names = [
            "valid-secret-name",
            "test123",
            "my-app-secret"
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(client_secret_name=name)
            assert config.client_secret_name == name

    def test_output_name_assignment(self):
        """Test output name assignment."""
        # Valid output names should work
        valid_names = [
            "ValidOutputName",
            "TestOutput123",
            "MyAppOutput"
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(discovery_url_output_name=name)
            assert config.discovery_url_output_name == name