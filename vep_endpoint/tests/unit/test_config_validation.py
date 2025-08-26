"""
Unit tests for VEPEndpointConfig validation logic.
"""
import pytest
from aws_cdk import RemovalPolicy
from vep_endpoint.vep_endpoint_stack import VEPEndpointConfig


class TestVEPEndpointConfigValidation:
    """Test configuration validation in VEPEndpointConfig."""

    def test_default_config_is_valid(self):
        """Test that default configuration is valid."""
        config = VEPEndpointConfig()
        # Should not raise any exceptions
        assert config.instance_type == "ml.g6.2xlarge"
        assert config.model_id == "chandar-lab/AMPLIFY_350M"
        assert config.min_capacity == 1
        assert config.max_capacity == 2
        assert config.max_concurrent_invocations == 4
        assert config.enable_autoscaling is True

    def test_valid_instance_types(self):
        """Test that all valid instance types are accepted."""
        valid_types = [
            "ml.g6.2xlarge", "ml.g6.4xlarge", "ml.g6.8xlarge", "ml.g6.12xlarge",
            "ml.g6e.2xlarge", "ml.g6e.4xlarge", "ml.g6e.8xlarge", "ml.g6e.12xlarge",
            "ml.g5.2xlarge", "ml.g5.4xlarge", "ml.g5.8xlarge", "ml.g5.12xlarge",
            "ml.p4d.24xlarge", "ml.p3.2xlarge", "ml.p3.8xlarge", "ml.p3.16xlarge",
        ]
        
        for instance_type in valid_types:
            config = VEPEndpointConfig(instance_type=instance_type)
            assert config.instance_type == instance_type

    def test_invalid_instance_type_raises_error(self):
        """Test that invalid instance types raise ValueError."""
        invalid_types = [
            "ml.t3.medium",  # CPU instance
            "ml.m5.large",   # CPU instance
            "ml.c5.xlarge",  # CPU instance
            "invalid-type",  # Completely invalid
        ]
        
        for instance_type in invalid_types:
            with pytest.raises(ValueError, match="Instance type must be GPU-enabled"):
                VEPEndpointConfig(instance_type=instance_type)

    def test_capacity_validation(self):
        """Test capacity parameter validation."""
        # Valid capacity settings
        config = VEPEndpointConfig(min_capacity=0, max_capacity=5)
        assert config.min_capacity == 0
        assert config.max_capacity == 5

        # Negative min_capacity should raise error
        with pytest.raises(ValueError, match="Minimum capacity cannot be negative"):
            VEPEndpointConfig(min_capacity=-1)

        # Zero max_capacity should raise error
        with pytest.raises(ValueError, match="Maximum capacity must be at least 1"):
            VEPEndpointConfig(max_capacity=0)

        # min_capacity > max_capacity should raise error
        with pytest.raises(ValueError, match="Minimum capacity .* cannot exceed maximum capacity"):
            VEPEndpointConfig(min_capacity=5, max_capacity=3)

    def test_concurrent_invocations_validation(self):
        """Test max_concurrent_invocations validation."""
        # Valid values
        config = VEPEndpointConfig(max_concurrent_invocations=10)
        assert config.max_concurrent_invocations == 10

        # Zero should raise error
        with pytest.raises(ValueError, match="Maximum concurrent invocations must be at least 1"):
            VEPEndpointConfig(max_concurrent_invocations=0)

        # Negative should raise error
        with pytest.raises(ValueError, match="Maximum concurrent invocations must be at least 1"):
            VEPEndpointConfig(max_concurrent_invocations=-1)

        # Too high should raise error
        with pytest.raises(ValueError, match="Maximum concurrent invocations cannot exceed 1000"):
            VEPEndpointConfig(max_concurrent_invocations=1001)

    def test_model_id_validation(self):
        """Test model_id validation."""
        # Valid model ID
        config = VEPEndpointConfig(model_id="valid/model-id")
        assert config.model_id == "valid/model-id"

        # Empty model ID should raise error
        with pytest.raises(ValueError, match="Model ID cannot be empty"):
            VEPEndpointConfig(model_id="")

        # Whitespace-only model ID should raise error
        with pytest.raises(ValueError, match="Model ID cannot be empty"):
            VEPEndpointConfig(model_id="   ")

    def test_s3_bucket_name_validation(self):
        """Test S3 bucket name validation."""
        # Valid bucket names
        valid_names = [
            "valid-bucket-name",
            "test123",
            "my-test-bucket-2024",
            "a" * 63,  # Maximum length
        ]
        
        for bucket_name in valid_names:
            config = VEPEndpointConfig(s3_bucket_name=bucket_name)
            assert config.s3_bucket_name == bucket_name

        # None should be accepted (auto-generated)
        config = VEPEndpointConfig(s3_bucket_name=None)
        assert config.s3_bucket_name is None

        # Too short
        with pytest.raises(ValueError, match="S3 bucket name must be between 3 and 63 characters"):
            VEPEndpointConfig(s3_bucket_name="ab")

        # Too long
        with pytest.raises(ValueError, match="S3 bucket name must be between 3 and 63 characters"):
            VEPEndpointConfig(s3_bucket_name="a" * 64)

        # Invalid format
        with pytest.raises(ValueError, match="Invalid S3 bucket name format"):
            VEPEndpointConfig(s3_bucket_name="Invalid_Bucket_Name")

        # Consecutive hyphens
        with pytest.raises(ValueError, match="S3 bucket name cannot contain consecutive hyphens"):
            VEPEndpointConfig(s3_bucket_name="bucket--name")

        # Uppercase (caught by regex pattern)
        with pytest.raises(ValueError, match="Invalid S3 bucket name format"):
            VEPEndpointConfig(s3_bucket_name="BucketName")

    def test_removal_policy_configuration(self):
        """Test removal policy configuration."""
        config = VEPEndpointConfig(logs_removal_policy=RemovalPolicy.RETAIN)
        assert config.logs_removal_policy == RemovalPolicy.RETAIN

        config = VEPEndpointConfig(logs_removal_policy=RemovalPolicy.DESTROY)
        assert config.logs_removal_policy == RemovalPolicy.DESTROY