"""
Unit tests for get_results module.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError
from get_results import (
    get_results,
    _check_s3_object_exists,
    _retrieve_s3_results,
    _retrieve_s3_failure_details,
    _success_response,
    _error_response,
    _validate_s3_configuration,
    _validate_s3_bucket_access
)


class TestGetResults:
    """Test get_results function."""

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_success_completed(self, mock_log_event, mock_put_metric, 
                                         mock_lambda_context, mock_environment_variables):
        """Test successful results retrieval for completed prediction."""
        event = {"output_id": "test-output-123"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            # Mock successful result exists
            with patch('get_results._check_s3_object_exists') as mock_check:
                mock_check.return_value = {
                    "exists": True,
                    "last_modified": "2023-01-01T00:00:00Z"
                }
                
                with patch('get_results._retrieve_s3_results') as mock_retrieve:
                    mock_retrieve.return_value = {"prediction": "result_data"}
                    
                    result = get_results(event, mock_lambda_context)
                    
                    assert result["success"] is True
                    assert result["data"]["status"] == "completed"
                    assert result["data"]["results"] == {"prediction": "result_data"}
                    mock_put_metric.assert_any_call("ResultsRetrievalSuccess", 1)

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_in_progress(self, mock_log_event, mock_put_metric, 
                                   mock_lambda_context, mock_environment_variables):
        """Test results retrieval for in-progress prediction."""
        event = {"output_id": "test-output-123"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            # Mock neither success nor failure files exist
            with patch('get_results._check_s3_object_exists') as mock_check:
                mock_check.return_value = {"exists": False}
                
                result = get_results(event, mock_lambda_context)
                
                assert result["success"] is True
                assert result["data"]["status"] == "in_progress"
                assert "check_interval_seconds" in result["data"]

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_failed(self, mock_log_event, mock_put_metric, 
                              mock_lambda_context, mock_environment_variables):
        """Test results retrieval for failed prediction."""
        event = {"output_id": "test-output-123"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            # Mock success file doesn't exist, failure file exists
            def mock_check_side_effect(client, bucket, key):
                if "failure" in key:
                    return {"exists": True, "last_modified": "2023-01-01T00:00:00Z"}
                return {"exists": False}
            
            with patch('get_results._check_s3_object_exists', side_effect=mock_check_side_effect):
                with patch('get_results._retrieve_s3_failure_details') as mock_retrieve_failure:
                    mock_retrieve_failure.return_value = {"error": "Model failed"}
                    
                    result = get_results(event, mock_lambda_context)
                    
                    assert result["success"] is False
                    assert result["error_code"] == "PREDICTION_FAILED"
                    assert result["details"]["status"] == "failed"
                    mock_put_metric.assert_called_with("PredictionFailed", 1)

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_s3_path_input(self, mock_log_event, mock_put_metric, 
                                     mock_lambda_context):
        """Test results retrieval with S3 path as input."""
        event = {"output_id": "s3://test-bucket/async-inference-output/test-123.out"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            with patch('get_results._check_s3_object_exists') as mock_check:
                mock_check.return_value = {
                    "exists": True,
                    "last_modified": "2023-01-01T00:00:00Z"
                }
                
                with patch('get_results._retrieve_s3_results') as mock_retrieve:
                    mock_retrieve.return_value = {"prediction": "result_data"}
                    
                    result = get_results(event, mock_lambda_context)
                    
                    assert result["success"] is True
                    assert result["data"]["status"] == "completed"

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_invalid_s3_path(self, mock_log_event, mock_put_metric, mock_lambda_context):
        """Test results retrieval with invalid S3 path."""
        event = {"output_id": "s3://invalid-path"}
        
        result = get_results(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_S3_PATH"

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_validation_error(self, mock_log_event, mock_put_metric, mock_lambda_context):
        """Test results retrieval with validation error."""
        event = {}  # Missing output_id
        
        result = get_results(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_EVENT_STRUCTURE"
        mock_put_metric.assert_called_with("ValidationError", 1)

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_missing_s3_config(self, mock_log_event, mock_put_metric, 
                                         mock_lambda_context, monkeypatch):
        """Test results retrieval with missing S3 configuration."""
        event = {"output_id": "test-output-123"}
        
        # Don't set S3_BUCKET_NAME
        monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
        
        result = get_results(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "CONFIGURATION_ERROR"

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_s3_client_error(self, mock_log_event, mock_put_metric, 
                                       mock_lambda_context, mock_environment_variables):
        """Test results retrieval with S3 client initialization error."""
        event = {"output_id": "test-output-123"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = Exception("AWS credentials not found")
            
            result = get_results(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "CLIENT_INITIALIZATION_ERROR"

    @patch('get_results.put_simple_metric')
    @patch('get_results.log_event')
    def test_get_results_unexpected_error(self, mock_log_event, mock_put_metric, 
                                        mock_lambda_context, mock_environment_variables):
        """Test results retrieval with unexpected error."""
        event = {"output_id": "test-output-123"}
        
        with patch('get_results.boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = RuntimeError("Unexpected error")
            
            result = get_results(event, mock_lambda_context)
            
            assert result["success"] is False
            # The actual implementation returns CLIENT_INITIALIZATION_ERROR for boto3.client failures
            assert result["error_code"] == "CLIENT_INITIALIZATION_ERROR"


class TestCheckS3ObjectExists:
    """Test S3 object existence checking."""

    def test_check_s3_object_exists_success(self):
        """Test successful object existence check."""
        from datetime import datetime, timezone
        
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "ContentLength": 1024,
            "ETag": '"abc123"'
        }
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is True
        assert result["content_length"] == 1024
        assert result["etag"] == "abc123"

    def test_check_s3_object_not_found(self):
        """Test object not found."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is False
        assert "error" not in result

    def test_check_s3_object_access_denied(self):
        """Test access denied error."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Access denied"}}, "HeadObject"
        )
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is False
        assert result["error"] == "ACCESS_DENIED"

    def test_check_s3_object_bucket_not_found(self):
        """Test bucket not found error."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "HeadObject"
        )
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is False
        assert result["error"] == "BUCKET_NOT_FOUND"

    def test_check_s3_object_service_unavailable(self):
        """Test service unavailable error."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable"}}, "HeadObject"
        )
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is False
        assert result["error"] == "S3_SERVICE_UNAVAILABLE"

    def test_check_s3_object_boto_error(self):
        """Test BotoCore error."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = BotoCoreError()
        
        result = _check_s3_object_exists(mock_s3, "test-bucket", "test-key")
        
        assert result["exists"] is False
        assert result["error"] == "BOTO_CONNECTION_ERROR"


class TestRetrieveS3Results:
    """Test S3 results retrieval."""

    def test_retrieve_s3_results_json_success(self):
        """Test successful JSON results retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b'{"prediction": "result_data"}'
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_results(mock_s3, "test-bucket", "test-key")
        
        assert result == {"prediction": "result_data"}

    def test_retrieve_s3_results_text_content(self):
        """Test text content results retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b'Plain text result'
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_results(mock_s3, "test-bucket", "test-key")
        
        assert result["raw_output"] == "Plain text result"
        assert result["parsing_info"]["format"] == "text"

    def test_retrieve_s3_results_empty_content(self):
        """Test empty content results retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b''
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_results(mock_s3, "test-bucket", "test-key")
        
        assert result["raw_output"] == ""
        assert "warning" in result

    def test_retrieve_s3_results_not_found(self):
        """Test results retrieval when file not found."""
        mock_s3 = Mock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "GetObject"
        )
        
        with pytest.raises(Exception, match="no longer exists"):
            _retrieve_s3_results(mock_s3, "test-bucket", "test-key")

    def test_retrieve_s3_results_access_denied(self):
        """Test results retrieval with access denied."""
        mock_s3 = Mock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "403"}}, "GetObject"
        )
        
        with pytest.raises(Exception, match="Access denied"):
            _retrieve_s3_results(mock_s3, "test-bucket", "test-key")

    def test_retrieve_s3_results_unicode_error(self):
        """Test results retrieval with unicode decode error."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b'\xff\xfe'  # Invalid UTF-8
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        with pytest.raises(Exception, match="invalid character encoding"):
            _retrieve_s3_results(mock_s3, "test-bucket", "test-key")


class TestRetrieveS3FailureDetails:
    """Test S3 failure details retrieval."""

    def test_retrieve_s3_failure_details_json_success(self):
        """Test successful JSON failure details retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b'{"error": "Model failed", "code": 500}'
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_failure_details(mock_s3, "test-bucket", "test-key")
        
        assert result["error"] == "Model failed"
        assert result["code"] == 500
        assert "retrieval_info" in result

    def test_retrieve_s3_failure_details_text_content(self):
        """Test text content failure details retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b'Error: Model execution failed'
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_failure_details(mock_s3, "test-bucket", "test-key")
        
        assert result["error_message"] == "Error: Model execution failed"
        assert result["error_type"] == "text_format"

    def test_retrieve_s3_failure_details_empty_content(self):
        """Test empty failure details retrieval."""
        mock_s3 = Mock()
        mock_response = Mock()
        mock_response.read.return_value = b''
        mock_s3.get_object.return_value = {"Body": mock_response}
        
        result = _retrieve_s3_failure_details(mock_s3, "test-bucket", "test-key")
        
        assert result["error_type"] == "empty_failure_log"
        assert "no error details available" in result["error_message"]

    def test_retrieve_s3_failure_details_not_found(self):
        """Test failure details retrieval when file not found."""
        mock_s3 = Mock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "GetObject"
        )
        
        result = _retrieve_s3_failure_details(mock_s3, "test-bucket", "test-key")
        
        assert result["error_type"] == "failure_log_missing"
        assert "no longer exists" in result["error_message"]


class TestValidateS3Configuration:
    """Test S3 configuration validation."""

    def test_validate_s3_configuration_valid(self):
        """Test valid S3 configuration."""
        result = _validate_s3_configuration(
            "test-bucket", "output-prefix", "failure-prefix"
        )
        
        assert result["is_valid"] is True
        assert result["error_message"] is None

    def test_validate_s3_configuration_invalid_bucket(self):
        """Test invalid bucket name."""
        result = _validate_s3_configuration(
            "ab", "output-prefix", "failure-prefix"  # Too short
        )
        
        assert result["is_valid"] is False
        assert "between 3 and 63 characters" in result["error_message"]

    def test_validate_s3_configuration_same_prefixes(self):
        """Test same output and failure prefixes."""
        result = _validate_s3_configuration(
            "test-bucket", "same-prefix", "same-prefix"
        )
        
        assert result["is_valid"] is False
        assert "cannot be the same" in result["error_message"]

    def test_validate_s3_configuration_empty_bucket(self):
        """Test empty bucket name."""
        result = _validate_s3_configuration("", "output", "failure")
        
        assert result["is_valid"] is False
        assert "non-empty string" in result["error_message"]


class TestValidateS3BucketAccess:
    """Test S3 bucket access validation."""

    def test_validate_s3_bucket_access_success(self):
        """Test successful bucket access validation."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {}
        
        result = _validate_s3_bucket_access(mock_s3, "test-bucket")
        
        assert result["is_accessible"] is True

    def test_validate_s3_bucket_access_not_found(self):
        """Test bucket not found."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "ListObjectsV2"
        )
        
        result = _validate_s3_bucket_access(mock_s3, "test-bucket")
        
        assert result["is_accessible"] is False
        assert result["error_code"] == "BUCKET_NOT_FOUND"


class TestResponseHelpers:
    """Test response helper functions."""

    def test_success_response(self):
        """Test success response creation."""
        data = {"key": "value"}
        response = _success_response(data, "Test message")
        
        assert response["success"] is True
        assert response["message"] == "Test message"
        assert response["data"] == data
        assert "timestamp" in response

    @patch('get_results.log_event')
    def test_error_response(self, mock_log_event):
        """Test error response creation."""
        details = {"key": "value"}
        response = _error_response("TEST_ERROR", "Test message", details)
        
        assert response["success"] is False
        assert response["error_code"] == "TEST_ERROR"
        assert response["message"] == "Test message"
        assert response["details"] == details
        assert "timestamp" in response
        mock_log_event.assert_called_once()