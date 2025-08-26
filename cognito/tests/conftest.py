"""
Pytest configuration and shared fixtures for Cognito stack tests.
"""

import pytest
import warnings
import aws_cdk as cdk
from aws_cdk.assertions import Template
from cognito.cognito_stack import CognitoStack
from cognito.cognito_config import (
    CognitoConfig,
    CognitoOutputConfig,
    CognitoResourceScope,
)

# Suppress warnings at the module level
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

# Suppress specific AWS/CDK warnings
warnings.filterwarnings("ignore", message=".*deprecated.*")
warnings.filterwarnings("ignore", message=".*Boto3.*")
warnings.filterwarnings("ignore", message=".*botocore.*")
warnings.filterwarnings("ignore", message=".*jsii.*")
warnings.filterwarnings("ignore", message=".*constructs.*")
warnings.filterwarnings("ignore", message=".*CDK.*")


@pytest.fixture(autouse=True)
def suppress_warnings():
    """Automatically suppress warnings for all tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


@pytest.fixture
def app():
    """Create a CDK app for testing."""
    return cdk.App()


@pytest.fixture
def default_config():
    """Create a default Cognito configuration for testing."""
    return CognitoConfig()


@pytest.fixture
def test_config():
    """Create a test-specific Cognito configuration."""
    return CognitoConfig(
        user_pool_name="test-user-pool",
        resource_server_identifier="test-resource-server",
        resource_server_name="Test Resource Server",
        client_name="test-client",
        scopes=[
            CognitoResourceScope("read", "Read access to test resources"),
            CognitoResourceScope("write", "Write access to test resources"),
            CognitoResourceScope("admin", "Administrative access to test resources"),
        ],
        min_password_length=10,
        require_symbols=False,
        deletion_protection=False,
        enable_threat_protection=False,
    )


@pytest.fixture
def minimal_config():
    """Create a minimal Cognito configuration for testing."""
    return CognitoConfig(
        user_pool_name="minimal-pool",
        resource_server_identifier="minimal-server",
        client_name="minimal-client",
        scopes=[
            CognitoResourceScope("basic", "Basic access"),
        ],
        deletion_protection=False,
    )


@pytest.fixture
def custom_output_config():
    """Create a custom output configuration for testing."""
    return CognitoOutputConfig(
        discovery_url_parameter_name="/test/cognito/discovery-url",
        client_id_parameter_name="/test/cognito/client-id",
        user_pool_id_parameter_name="/test/cognito/user-pool-id",
        user_pool_arn_parameter_name="/test/cognito/user-pool-arn",
        domain_parameter_name="/test/cognito/domain",
        client_secret_name="test-cognito-client-secret",
    )


@pytest.fixture
def stack_with_default_config(app, default_config):
    """Create a Cognito stack with default configuration."""
    return CognitoStack(app, "TestCognitoStack", config=default_config)


@pytest.fixture
def stack_with_test_config(app, test_config):
    """Create a Cognito stack with test configuration."""
    return CognitoStack(app, "TestCognitoStack", config=test_config)


@pytest.fixture
def stack_with_minimal_config(app, minimal_config):
    """Create a Cognito stack with minimal configuration."""
    return CognitoStack(app, "TestCognitoStack", config=minimal_config)


@pytest.fixture
def stack_with_custom_output_config(app, test_config, custom_output_config):
    """Create a Cognito stack with custom output configuration."""
    return CognitoStack(
        app, "TestCognitoStack", config=test_config, output_config=custom_output_config
    )


@pytest.fixture
def template_from_default_stack(stack_with_default_config):
    """Create a CloudFormation template from the default stack."""
    return Template.from_stack(stack_with_default_config)


@pytest.fixture
def template_from_test_stack(stack_with_test_config):
    """Create a CloudFormation template from the test stack."""
    return Template.from_stack(stack_with_test_config)


@pytest.fixture
def template_from_minimal_stack(stack_with_minimal_config):
    """Create a CloudFormation template from the minimal stack."""
    return Template.from_stack(stack_with_minimal_config)


@pytest.fixture
def template_from_custom_output_stack(stack_with_custom_output_config):
    """Create a CloudFormation template from the custom output stack."""
    return Template.from_stack(stack_with_custom_output_config)
