"""
Pytest configuration and shared fixtures for Lambda function tests.
"""

import sys
import os
from pathlib import Path

# Add the parent directory (lambda_function) to Python path
lambda_function_dir = Path(__file__).parent.parent
sys.path.insert(0, str(lambda_function_dir))

import pytest
import boto3
from moto import mock_s3, mock_sagemaker, mock_cloudwatch
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_lambda_context():
    """Mock Lambda context object."""
    context = Mock()
    context.aws_request_id = "test-request-id-123"
    context.function_name = "test-lambda-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.client_context = None
    return context


@pytest.fixture
def mock_lambda_context_with_tool_name():
    """Mock Lambda context object with tool name in client context."""
    context = Mock()
    context.aws_request_id = "test-request-id-123"
    context.function_name = "test-lambda-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    
    # Mock client context with tool name
    client_context = Mock()
    client_context.custom = {"bedrockAgentCoreToolName": "invoke_endpoint"}
    context.client_context = client_context
    
    return context


@pytest.fixture
def valid_amino_acid_sequence():
    """Valid amino acid sequence for testing."""
    return "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"


@pytest.fixture
def invalid_amino_acid_sequence():
    """Invalid amino acid sequence for testing."""
    return "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGGXZ123"


@pytest.fixture
def valid_invoke_event(valid_amino_acid_sequence):
    """Valid event for invoke_endpoint function."""
    return {
        "tool_name": "invoke_endpoint",
        "sequence": valid_amino_acid_sequence
    }


@pytest.fixture
def valid_get_results_event():
    """Valid event for get_results function."""
    return {
        "tool_name": "get_results",
        "output_id": "test-output-id-123"
    }


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("SAGEMAKER_ENDPOINT_NAME", "test-endpoint")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("S3_INPUT_PREFIX", "async-inference-input")
    monkeypatch.setenv("S3_OUTPUT_PREFIX", "async-inference-output")
    monkeypatch.setenv("S3_FAILURE_PREFIX", "async-inference-failures")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test-lambda-function")


@pytest.fixture
def mock_s3_setup():
    """Set up mock S3 environment."""
    with mock_s3():
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        
        # Create test bucket
        s3_client.create_bucket(Bucket=bucket_name)
        
        yield s3_client, bucket_name


@pytest.fixture
def mock_sagemaker_setup():
    """Set up mock SageMaker environment."""
    with mock_sagemaker():
        sagemaker_client = boto3.client('sagemaker-runtime', region_name='us-east-1')
        yield sagemaker_client


@pytest.fixture
def mock_cloudwatch_setup():
    """Set up mock CloudWatch environment."""
    with mock_cloudwatch():
        cloudwatch_client = boto3.client('cloudwatch', region_name='us-east-1')
        yield cloudwatch_client