"""
Unit tests for CognitoConfig validation logic.
"""
import pytest
from aws_cdk import aws_cognito as cognito
from cognito.cognito_config import CognitoConfig, CognitoOutputConfig, CognitoResourceScope


class TestCognitoConfigValidation:
    """Test configuration validation in CognitoConfig."""

    def test_default_config_is_valid(self):
        """Test that default configuration is valid."""
        config = CognitoConfig()
        # Should not raise any exceptions
        config.validate()
        
        assert config.user_pool_name == "agentcore-gateway-pool"
        assert config.resource_server_identifier == "agentcore-gateway-id"
        assert config.resource_server_name == "agentcore-gateway-name"
        assert config.client_name == "agentcore-gateway-client"
        assert len(config.scopes) == 2
        assert config.min_password_length == 8
        assert config.require_symbols is False
        assert config.deletion_protection is False

    def test_user_pool_name_validation(self):
        """Test user pool name validation."""
        # Valid names
        valid_names = [
            "valid-pool-name",
            "test123",
            "my-test-pool-2024",
        ]
        
        for pool_name in valid_names:
            config = CognitoConfig(user_pool_name=pool_name)
            config.validate()  # Should not raise

        # Empty name should raise error
        with pytest.raises(ValueError, match="User pool name cannot be empty"):
            config = CognitoConfig(user_pool_name="")
            config.validate()

        # Note: The current implementation doesn't validate whitespace-only names
        # This could be enhanced in the future

    def test_resource_server_identifier_validation(self):
        """Test resource server identifier validation."""
        # Valid identifiers
        valid_identifiers = [
            "valid-identifier",
            "test123",
            "my.test.server",
            "https://example.com/api",
        ]
        
        for identifier in valid_identifiers:
            config = CognitoConfig(resource_server_identifier=identifier)
            config.validate()  # Should not raise

        # Empty identifier should raise error
        with pytest.raises(ValueError, match="Resource server identifier cannot be empty"):
            config = CognitoConfig(resource_server_identifier="")
            config.validate()

        # Note: The current implementation doesn't validate whitespace-only identifiers
        # This could be enhanced in the future

    def test_client_name_validation(self):
        """Test client name validation."""
        # Valid names
        valid_names = [
            "valid-client-name",
            "test123",
            "my-test-client-2024",
        ]
        
        for client_name in valid_names:
            config = CognitoConfig(client_name=client_name)
            config.validate()  # Should not raise

        # Empty name should raise error
        with pytest.raises(ValueError, match="Client name cannot be empty"):
            config = CognitoConfig(client_name="")
            config.validate()

        # Note: The current implementation doesn't validate length limits
        # This could be enhanced in the future

    def test_scopes_validation(self):
        """Test scopes validation."""
        # Valid scopes
        valid_scopes = [
            CognitoResourceScope("read", "Read access"),
            CognitoResourceScope("write", "Write access"),
            CognitoResourceScope("admin", "Admin access"),
        ]
        
        config = CognitoConfig(scopes=valid_scopes)
        config.validate()  # Should not raise

        # Empty scopes list should raise error
        with pytest.raises(ValueError, match="At least one scope must be defined"):
            config = CognitoConfig(scopes=[])
            config.validate()

        # Note: The current implementation doesn't validate for duplicate scope names
        # This could be enhanced in the future

    def test_password_policy_validation(self):
        """Test password policy validation."""
        # Valid password length
        config = CognitoConfig(min_password_length=8)
        config.validate()  # Should not raise

        config = CognitoConfig(min_password_length=99)
        config.validate()  # Should not raise

        # Too short password length should raise error
        with pytest.raises(ValueError, match="Minimum password length must be at least 6 characters"):
            config = CognitoConfig(min_password_length=5)
            config.validate()

        # Too long password length should raise error
        with pytest.raises(ValueError, match="Maximum password length cannot exceed 128 characters"):
            config = CognitoConfig(min_password_length=129)
            config.validate()

    def test_mfa_configuration_validation(self):
        """Test MFA configuration validation."""
        # Valid MFA configurations
        config = CognitoConfig(mfa=cognito.Mfa.OFF)
        config.validate()  # Should not raise

        config = CognitoConfig(mfa=cognito.Mfa.OPTIONAL)
        config.validate()  # Should not raise

        config = CognitoConfig(mfa=cognito.Mfa.REQUIRED)
        config.validate()  # Should not raise

    def test_account_recovery_validation(self):
        """Test account recovery configuration validation."""
        # Valid account recovery configurations
        config = CognitoConfig(account_recovery=cognito.AccountRecovery.EMAIL_ONLY)
        config.validate()  # Should not raise

        config = CognitoConfig(account_recovery=cognito.AccountRecovery.PHONE_ONLY_WITHOUT_MFA)
        config.validate()  # Should not raise

        config = CognitoConfig(account_recovery=cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA)
        config.validate()  # Should not raise

    def test_domain_prefix_validation(self):
        """Test domain prefix validation."""
        # Valid domain prefixes
        valid_prefixes = [
            "valid-prefix",
            "test123",
            "my-domain-2024",
        ]
        
        for prefix in valid_prefixes:
            config = CognitoConfig(domain_prefix=prefix)
            config.validate()  # Should not raise

        # None should be accepted (auto-generated)
        config = CognitoConfig(domain_prefix=None)
        config.validate()  # Should not raise

        # Note: The current implementation doesn't validate domain prefix format
        # This could be enhanced in the future


class TestCognitoResourceScopeValidation:
    """Test CognitoResourceScope validation."""

    def test_valid_scope_creation(self):
        """Test valid scope creation."""
        scope = CognitoResourceScope("read", "Read access to resources")
        assert scope.scope_name == "read"
        assert scope.scope_description == "Read access to resources"

    def test_scope_name_validation(self):
        """Test scope name validation."""
        # Valid scope names
        valid_names = ["read", "write", "admin", "user:profile", "api:access"]
        
        for name in valid_names:
            scope = CognitoResourceScope(name, "Description")
            assert scope.scope_name == name

        # Note: CognitoResourceScope is a simple dataclass without validation
        # Validation happens at the CognitoConfig level during validate()

    def test_scope_description_validation(self):
        """Test scope description validation."""
        # Valid descriptions
        valid_descriptions = [
            "Read access",
            "Write access to all resources",
            "Administrative privileges for the application",
        ]
        
        for description in valid_descriptions:
            scope = CognitoResourceScope("test", description)
            assert scope.scope_description == description

        # Note: CognitoResourceScope is a simple dataclass without validation
        # Validation happens at the CognitoConfig level during validate()


class TestCognitoOutputConfigValidation:
    """Test CognitoOutputConfig validation."""

    def test_default_output_config_is_valid(self):
        """Test that default output configuration is valid."""
        config = CognitoOutputConfig()
        # Note: CognitoOutputConfig doesn't have a validate() method
        
        assert config.discovery_url_parameter_name == "/cognito/discovery-url"
        assert config.client_id_parameter_name == "/cognito/client-id"
        assert config.user_pool_id_parameter_name == "/cognito/user-pool-id"
        assert config.user_pool_arn_parameter_name == "/cognito/user-pool-arn"
        assert config.domain_parameter_name == "/cognito/domain"
        assert config.client_secret_name == "cognito-client-secret"

    def test_parameter_name_assignment(self):
        """Test parameter name assignment."""
        # Valid parameter names
        valid_names = [
            "/valid/parameter/name",
            "/test-parameter",
            "/my/app/config",
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(discovery_url_parameter_name=name)
            assert config.discovery_url_parameter_name == name

        # Note: CognitoOutputConfig is a simple dataclass without validation
        # Additional validation could be added if needed

    def test_secret_name_assignment(self):
        """Test secret name assignment."""
        # Valid secret names
        valid_names = [
            "valid-secret-name",
            "test123",
            "my-secret-2024",
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(client_secret_name=name)
            assert config.client_secret_name == name

        # Note: CognitoOutputConfig is a simple dataclass without validation
        # Additional validation could be added if needed

    def test_output_name_assignment(self):
        """Test output name assignment."""
        # Valid output names
        valid_names = [
            "ValidOutputName",
            "TestOutput123",
            "MyAppOutput",
        ]
        
        for name in valid_names:
            config = CognitoOutputConfig(discovery_url_output_name=name)
            assert config.discovery_url_output_name == name

        # Note: CognitoOutputConfig is a simple dataclass without validation
        # Additional validation could be added if needed