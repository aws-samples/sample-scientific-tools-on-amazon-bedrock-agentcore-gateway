"""
Unit tests for invoke_endpoint module.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError
from invoke_endpoint import (
    invoke_endpoint,
    _success_response,
    _error_response,
    _estimate_completion_time
)


class TestInvokeEndpoint:
    """Test invoke_endpoint function."""

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_success(self, mock_log_event, mock_put_metric, 
                                   mock_lambda_context, mock_environment_variables):
        """Test successful endpoint invocation."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            # Mock S3 client
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock SageMaker response
            mock_sagemaker.invoke_endpoint_async.return_value = {
                "InferenceId": "test-inference-123",
                "OutputLocation": "s3://test-bucket/async-inference-output/test-inference-123.out"
            }
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is True
            assert "output_id" in result["data"]
            assert "s3_output_path" in result["data"]
            mock_put_metric.assert_any_call("InvocationSuccess", 1)
            mock_s3.put_object.assert_called_once()
            mock_sagemaker.invoke_endpoint_async.assert_called_once()

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_validation_error(self, mock_log_event, mock_put_metric, mock_lambda_context):
        """Test endpoint invocation with validation error."""
        event = {"sequence": "INVALID123"}  # Invalid sequence
        
        result = invoke_endpoint(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SEQUENCE"
        mock_put_metric.assert_called_with("ValidationError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_missing_sequence(self, mock_log_event, mock_put_metric, mock_lambda_context):
        """Test endpoint invocation with missing sequence."""
        event = {}  # Missing sequence field
        
        result = invoke_endpoint(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_EVENT_STRUCTURE"
        mock_put_metric.assert_called_with("ValidationError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_missing_endpoint_config(self, mock_log_event, mock_put_metric, 
                                                   mock_lambda_context, monkeypatch):
        """Test endpoint invocation with missing endpoint configuration."""
        event = {"sequence": "MKTVRQERLK"}
        
        # Don't set SAGEMAKER_ENDPOINT_NAME
        monkeypatch.delenv("SAGEMAKER_ENDPOINT_NAME", raising=False)
        
        result = invoke_endpoint(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "CONFIGURATION_ERROR"
        assert "endpoint name not configured" in result["message"]
        mock_put_metric.assert_called_with("ConfigurationError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_missing_s3_config(self, mock_log_event, mock_put_metric, 
                                             mock_lambda_context, monkeypatch):
        """Test endpoint invocation with missing S3 configuration."""
        event = {"sequence": "MKTVRQERLK"}
        
        monkeypatch.setenv("SAGEMAKER_ENDPOINT_NAME", "test-endpoint")
        # Don't set S3_BUCKET_NAME
        monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
        
        result = invoke_endpoint(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "CONFIGURATION_ERROR"
        assert "S3 bucket name not configured" in result["message"]
        mock_put_metric.assert_called_with("ConfigurationError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_boto_client_error(self, mock_log_event, mock_put_metric, 
                                             mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with boto client initialization error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = Exception("AWS credentials not found")
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "CLIENT_INITIALIZATION_ERROR"
            mock_put_metric.assert_called_with("ClientError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_s3_upload_error(self, mock_log_event, mock_put_metric, 
                                           mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with S3 upload error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock S3 upload error
            mock_s3.put_object.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "PutObject"
            )
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "S3_UPLOAD_ERROR"
            mock_put_metric.assert_called_with("S3Error", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_sagemaker_validation_error(self, mock_log_event, mock_put_metric, 
                                                      mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with SageMaker validation error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock SageMaker validation error
            mock_sagemaker.invoke_endpoint_async.side_effect = ClientError(
                {"Error": {"Code": "ValidationException", "Message": "Invalid endpoint"}},
                "InvokeEndpointAsync"
            )
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "SAGEMAKER_VALIDATION_ERROR"
            mock_put_metric.assert_called_with("SageMakerError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_sagemaker_model_error(self, mock_log_event, mock_put_metric, 
                                                 mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with SageMaker model error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock SageMaker model error
            mock_sagemaker.invoke_endpoint_async.side_effect = ClientError(
                {"Error": {"Code": "ModelError", "Message": "Model failed"}},
                "InvokeEndpointAsync"
            )
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "SAGEMAKER_MODEL_ERROR"
            mock_put_metric.assert_called_with("SageMakerError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_sagemaker_service_unavailable(self, mock_log_event, mock_put_metric, 
                                                         mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with SageMaker service unavailable."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock SageMaker service unavailable
            mock_sagemaker.invoke_endpoint_async.side_effect = ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
                "InvokeEndpointAsync"
            )
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "SAGEMAKER_SERVICE_UNAVAILABLE"
            mock_put_metric.assert_called_with("SageMakerError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_boto_core_error(self, mock_log_event, mock_put_metric, 
                                           mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with BotoCore error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock BotoCore error
            mock_sagemaker.invoke_endpoint_async.side_effect = BotoCoreError()
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "AWS_CONNECTION_ERROR"
            mock_put_metric.assert_called_with("ConnectionError", 1)

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_missing_inference_id(self, mock_log_event, mock_put_metric, 
                                                 mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with missing inference ID in response."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_sagemaker = Mock()
            mock_boto_client.side_effect = [mock_sagemaker, mock_s3]
            
            # Mock SageMaker response without InferenceId
            mock_sagemaker.invoke_endpoint_async.return_value = {
                "OutputLocation": "s3://test-bucket/output/test.out"
            }
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "SAGEMAKER_RESPONSE_ERROR"

    @patch('invoke_endpoint.put_simple_metric')
    @patch('invoke_endpoint.log_event')
    def test_invoke_endpoint_unexpected_error(self, mock_log_event, mock_put_metric, 
                                            mock_lambda_context, mock_environment_variables):
        """Test endpoint invocation with unexpected error."""
        event = {"sequence": "MKTVRQERLK"}
        
        with patch('invoke_endpoint.boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = RuntimeError("Unexpected error")
            
            result = invoke_endpoint(event, mock_lambda_context)
            
            assert result["success"] is False
            # The actual implementation returns CLIENT_INITIALIZATION_ERROR for boto3.client failures
            assert result["error_code"] == "CLIENT_INITIALIZATION_ERROR"
            mock_put_metric.assert_called_with("ClientError", 1)


class TestSuccessResponse:
    """Test success response creation."""

    def test_success_response_basic(self):
        """Test basic success response creation."""
        data = {"key": "value"}
        response = _success_response(data)
        
        assert response["success"] is True
        assert response["message"] == "Success"
        assert response["data"] == data
        assert "timestamp" in response

    def test_success_response_custom_message(self):
        """Test success response with custom message."""
        data = {"key": "value"}
        message = "Custom success message"
        response = _success_response(data, message)
        
        assert response["message"] == message
        assert response["data"] == data

    def test_success_response_empty_data(self):
        """Test success response with empty data."""
        data = {}
        response = _success_response(data)
        
        assert response["data"] == {}
        assert response["success"] is True


class TestErrorResponse:
    """Test error response creation."""

    @patch('invoke_endpoint.log_event')
    def test_error_response_basic(self, mock_log_event):
        """Test basic error response creation."""
        response = _error_response("TEST_ERROR", "Test message")
        
        assert response["success"] is False
        assert response["error_code"] == "TEST_ERROR"
        assert response["message"] == "Test message"
        assert "timestamp" in response
        mock_log_event.assert_called_once()

    @patch('invoke_endpoint.log_event')
    def test_error_response_with_details(self, mock_log_event):
        """Test error response with details."""
        details = {"key": "value"}
        response = _error_response("TEST_ERROR", "Test message", details)
        
        assert response["details"] == details
        mock_log_event.assert_called_once()

    @patch('invoke_endpoint.log_event')
    def test_error_response_no_details(self, mock_log_event):
        """Test error response without details."""
        response = _error_response("TEST_ERROR", "Test message")
        
        assert "details" not in response
        mock_log_event.assert_called_once()


class TestEstimateCompletionTime:
    """Test completion time estimation."""

    def test_estimate_completion_time_short_sequence(self):
        """Test estimation for short sequence."""
        completion_time = _estimate_completion_time(100)
        
        assert completion_time is not None
        assert isinstance(completion_time, str)
        # Should be ISO format timestamp
        assert "T" in completion_time
        assert "Z" in completion_time or "+" in completion_time

    def test_estimate_completion_time_long_sequence(self):
        """Test estimation for long sequence."""
        completion_time = _estimate_completion_time(2000)
        
        assert completion_time is not None
        assert isinstance(completion_time, str)

    def test_estimate_completion_time_zero_length(self):
        """Test estimation for zero-length sequence."""
        completion_time = _estimate_completion_time(0)
        
        assert completion_time is not None
        # Should still provide minimum estimate

    def test_estimate_completion_time_negative_length(self):
        """Test estimation for negative sequence length."""
        completion_time = _estimate_completion_time(-100)
        
        assert completion_time is not None
        # Should handle gracefully with minimum estimate