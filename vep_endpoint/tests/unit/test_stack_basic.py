"""
Basic unit tests for VEP endpoint stack - focused on essential functionality.
"""
import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template
from vep_endpoint.vep_endpoint_stack import VEPEndpointStack, VEPEndpointConfig


class TestStackBasics:
    """Test basic stack functionality without overly strict template matching."""

    def test_stack_synthesizes_without_errors(self, app, default_config):
        """Test that the stack synthesizes without errors."""
        stack = VEPEndpointStack(app, "TestStack", config=default_config)
        template = Template.from_stack(stack)
        
        # Should not raise any exceptions
        assert template is not None

    def test_required_resources_are_created(self, template_from_default_stack):
        """Test that all required AWS resources are created."""
        template = template_from_default_stack
        
        # Check that required resource types exist
        template.resource_count_is("AWS::SageMaker::Model", 1)
        template.resource_count_is("AWS::SageMaker::EndpointConfig", 1)
        template.resource_count_is("AWS::SageMaker::Endpoint", 1)
        template.resource_count_is("AWS::S3::Bucket", 1)
        template.resource_count_is("AWS::IAM::Role", 2)  # SageMaker + Lambda roles
        template.resource_count_is("AWS::Lambda::Function", 1)
        template.resource_count_is("AWS::SSM::Parameter", 2)  # Lambda ARN parameters

    def test_autoscaling_resources_when_enabled(self, app):
        """Test that auto scaling resources are created when enabled."""
        config = VEPEndpointConfig(enable_autoscaling=True)
        stack = VEPEndpointStack(app, "TestStack", config=config)
        template = Template.from_stack(stack)
        
        # Should have auto scaling resources
        template.resource_count_is("AWS::ApplicationAutoScaling::ScalableTarget", 1)
        template.resource_count_is("AWS::ApplicationAutoScaling::ScalingPolicy", 2)
        template.resource_count_is("AWS::CloudWatch::Alarm", 2)

    def test_autoscaling_resources_when_disabled(self, app):
        """Test that auto scaling resources are not created when disabled."""
        config = VEPEndpointConfig(enable_autoscaling=False)
        stack = VEPEndpointStack(app, "TestStack", config=config)
        template = Template.from_stack(stack)
        
        # Should not have auto scaling resources
        template.resource_count_is("AWS::ApplicationAutoScaling::ScalableTarget", 0)
        template.resource_count_is("AWS::ApplicationAutoScaling::ScalingPolicy", 0)
        template.resource_count_is("AWS::CloudWatch::Alarm", 0)

    def test_iam_policies_are_created(self, template_from_default_stack):
        """Test that IAM policies are created."""
        template = template_from_default_stack
        
        # Should have multiple IAM policies for different purposes
        # Exact count may vary, but should have at least 5 policies
        policies = template.find_resources("AWS::IAM::Policy")
        assert len(policies) >= 5, f"Expected at least 5 IAM policies, found {len(policies)}"

    def test_stack_outputs_exist(self, template_from_default_stack):
        """Test that important stack outputs are created."""
        template = template_from_default_stack
        
        outputs = template.find_outputs("*")
        output_keys = list(outputs.keys())
        
        # Should have outputs for key resources
        essential_output_patterns = [
            "EndpointName",
            "S3BucketName", 
            "LambdaFunctionArn",
            "ModelName"
        ]
        
        for pattern in essential_output_patterns:
            matching_outputs = [key for key in output_keys if pattern in key]
            assert len(matching_outputs) > 0, f"No outputs found matching pattern: {pattern}"

    def test_sagemaker_resources_have_correct_names(self, template_from_default_stack):
        """Test that SageMaker resources have expected names."""
        template = template_from_default_stack
        
        # Check SageMaker model
        models = template.find_resources("AWS::SageMaker::Model")
        assert len(models) == 1
        model = list(models.values())[0]
        assert model["Properties"]["ModelName"] == "amplify-vep-model"
        
        # Check endpoint config
        configs = template.find_resources("AWS::SageMaker::EndpointConfig")
        assert len(configs) == 1
        config = list(configs.values())[0]
        assert config["Properties"]["EndpointConfigName"] == "amplify-vep-config"
        
        # Check endpoint
        endpoints = template.find_resources("AWS::SageMaker::Endpoint")
        assert len(endpoints) == 1
        endpoint = list(endpoints.values())[0]
        assert endpoint["Properties"]["EndpointName"] == "amplify-vep-endpoint"

    def test_s3_bucket_has_security_settings(self, template_from_default_stack):
        """Test that S3 bucket has basic security settings."""
        template = template_from_default_stack
        
        buckets = template.find_resources("AWS::S3::Bucket")
        assert len(buckets) == 1
        
        bucket = list(buckets.values())[0]
        props = bucket["Properties"]
        
        # Should have encryption
        assert "BucketEncryption" in props
        
        # Should have public access blocked
        assert "PublicAccessBlockConfiguration" in props

    def test_lambda_function_has_correct_runtime(self, template_from_default_stack):
        """Test that Lambda function has correct runtime."""
        template = template_from_default_stack
        
        functions = template.find_resources("AWS::Lambda::Function")
        assert len(functions) == 1
        
        function = list(functions.values())[0]
        props = function["Properties"]
        
        assert props["Runtime"] == "python3.13"
        assert props["Handler"] == "lambda_function.lambda_handler"

    def test_parameters_are_defined(self, template_from_default_stack):
        """Test that CDK parameters are defined."""
        template = template_from_default_stack
        
        parameters = template.find_parameters("*")
        parameter_names = list(parameters.keys())
        
        required_parameters = [
            "InstanceType",
            "ModelId", 
            "S3BucketNameParam",
            "MinCapacity",
            "MaxCapacity",
            "MaxConcurrentInvocations"
        ]
        
        for param in required_parameters:
            assert param in parameter_names, f"Missing required parameter: {param}"

    def test_different_configurations_work(self):
        """Test that different configurations produce valid stacks."""
        configs = [
            VEPEndpointConfig(instance_type="ml.g5.2xlarge"),
            VEPEndpointConfig(enable_autoscaling=False),
            VEPEndpointConfig(min_capacity=0, max_capacity=5),
            VEPEndpointConfig(model_id="test/model"),
        ]
        
        for i, config in enumerate(configs):
            # Create a new app for each test to avoid synthesis conflicts
            app = cdk.App()
            stack = VEPEndpointStack(app, f"TestStack{i}", config=config)
            template = Template.from_stack(stack)
            
            # Each should synthesize without errors
            assert template is not None
            
            # Each should have the basic required resources
            template.resource_count_is("AWS::SageMaker::Model", 1)
            template.resource_count_is("AWS::SageMaker::EndpointConfig", 1)
            template.resource_count_is("AWS::SageMaker::Endpoint", 1)