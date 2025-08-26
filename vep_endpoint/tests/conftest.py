"""
Pytest configuration and shared fixtures for VEP endpoint tests.
"""
import pytest
import warnings
import aws_cdk as cdk
from aws_cdk.assertions import Template
from vep_endpoint.vep_endpoint_stack import VEPEndpointStack, VEPEndpointConfig

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
    """Create a default VEP endpoint configuration for testing."""
    return VEPEndpointConfig()


@pytest.fixture
def test_config():
    """Create a test-specific VEP endpoint configuration."""
    return VEPEndpointConfig(
        instance_type="ml.g5.2xlarge",
        model_id="test-model/test",
        s3_bucket_name="test-bucket-name",
        min_capacity=0,
        max_capacity=3,
        max_concurrent_invocations=2,
        enable_autoscaling=True,
    )


@pytest.fixture
def minimal_config():
    """Create a minimal VEP endpoint configuration for testing."""
    return VEPEndpointConfig(
        instance_type="ml.g5.2xlarge",
        enable_autoscaling=False,
    )


@pytest.fixture
def stack_with_default_config(app, default_config):
    """Create a VEP endpoint stack with default configuration."""
    return VEPEndpointStack(app, "TestVEPStack", config=default_config)


@pytest.fixture
def stack_with_test_config(app, test_config):
    """Create a VEP endpoint stack with test configuration."""
    return VEPEndpointStack(app, "TestVEPStack", config=test_config)


@pytest.fixture
def stack_with_minimal_config(app, minimal_config):
    """Create a VEP endpoint stack with minimal configuration."""
    return VEPEndpointStack(app, "TestVEPStack", config=minimal_config)


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