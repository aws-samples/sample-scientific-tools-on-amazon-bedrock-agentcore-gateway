"""
Unit tests for cloudwatch_integration module.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from cloudwatch_integration import (
    get_cloudwatch_client,
    put_simple_metric,
    log_event
)


class TestGetCloudWatchClient:
    """Test CloudWatch client initialization."""

    @patch('cloudwatch_integration.boto3.client')
    def test_get_cloudwatch_client_success(self, mock_boto_client):
        """Test successful CloudWatch client initialization."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Reset global client
        import cloudwatch_integration
        cloudwatch_integration._cloudwatch_client = None
        
        client = get_cloudwatch_client()
        
        assert client == mock_client
        mock_boto_client.assert_called_once_with('cloudwatch')

    @patch('cloudwatch_integration.boto3.client')
    def test_get_cloudwatch_client_cached(self, mock_boto_client):
        """Test CloudWatch client caching."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Reset global client
        import cloudwatch_integration
        cloudwatch_integration._cloudwatch_client = None
        
        # First call
        client1 = get_cloudwatch_client()
        # Second call
        client2 = get_cloudwatch_client()
        
        assert client1 == client2
        # Should only be called once due to caching
        mock_boto_client.assert_called_once_with('cloudwatch')

    @patch('cloudwatch_integration.boto3.client')
    @patch('cloudwatch_integration.logger')
    def test_get_cloudwatch_client_failure(self, mock_logger, mock_boto_client):
        """Test CloudWatch client initialization failure."""
        mock_boto_client.side_effect = Exception("AWS credentials not found")
        
        # Reset global client
        import cloudwatch_integration
        cloudwatch_integration._cloudwatch_client = None
        
        client = get_cloudwatch_client()
        
        assert client is None
        mock_logger.warning.assert_called_once()


class TestPutSimpleMetric:
    """Test CloudWatch metric publishing."""

    @patch('cloudwatch_integration.get_cloudwatch_client')
    @patch('cloudwatch_integration.os.environ.get')
    def test_put_simple_metric_success(self, mock_env_get, mock_get_client):
        """Test successful metric publishing."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_env_get.return_value = "test-function"
        
        put_simple_metric("TestMetric", 1.0, "Count")
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args[1]
        
        assert call_args['Namespace'] == 'SageMaker/AsyncEndpoint'
        assert len(call_args['MetricData']) == 1
        
        metric_data = call_args['MetricData'][0]
        assert metric_data['MetricName'] == 'TestMetric'
        assert metric_data['Value'] == 1.0
        assert metric_data['Unit'] == 'Count'
        assert len(metric_data['Dimensions']) == 1
        assert metric_data['Dimensions'][0]['Name'] == 'FunctionName'
        assert metric_data['Dimensions'][0]['Value'] == 'test-function'

    @patch('cloudwatch_integration.get_cloudwatch_client')
    def test_put_simple_metric_no_client(self, mock_get_client):
        """Test metric publishing when client is None."""
        mock_get_client.return_value = None
        
        # Should not raise exception
        put_simple_metric("TestMetric", 1.0)

    @patch('cloudwatch_integration.get_cloudwatch_client')
    @patch('cloudwatch_integration.logger')
    def test_put_simple_metric_client_error(self, mock_logger, mock_get_client):
        """Test metric publishing when client raises exception."""
        mock_client = Mock()
        mock_client.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_get_client.return_value = mock_client
        
        put_simple_metric("TestMetric", 1.0)
        
        mock_logger.warning.assert_called_once()

    @patch('cloudwatch_integration.get_cloudwatch_client')
    @patch('cloudwatch_integration.os.environ.get')
    def test_put_simple_metric_default_unit(self, mock_env_get, mock_get_client):
        """Test metric publishing with default unit."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_env_get.return_value = "test-function"
        
        put_simple_metric("TestMetric", 5.0)
        
        call_args = mock_client.put_metric_data.call_args[1]
        metric_data = call_args['MetricData'][0]
        assert metric_data['Unit'] == 'Count'

    @patch('cloudwatch_integration.get_cloudwatch_client')
    @patch('cloudwatch_integration.os.environ.get')
    def test_put_simple_metric_custom_unit(self, mock_env_get, mock_get_client):
        """Test metric publishing with custom unit."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_env_get.return_value = "test-function"
        
        put_simple_metric("TestMetric", 100.0, "Milliseconds")
        
        call_args = mock_client.put_metric_data.call_args[1]
        metric_data = call_args['MetricData'][0]
        assert metric_data['Unit'] == 'Milliseconds'

    @patch('cloudwatch_integration.get_cloudwatch_client')
    @patch('cloudwatch_integration.os.environ.get')
    def test_put_simple_metric_unknown_function(self, mock_env_get, mock_get_client):
        """Test metric publishing when function name is unknown."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        # Mock os.environ.get to return 'unknown' as the default value
        mock_env_get.return_value = 'unknown'
        
        put_simple_metric("TestMetric", 1.0)
        
        call_args = mock_client.put_metric_data.call_args[1]
        metric_data = call_args['MetricData'][0]
        assert metric_data['Dimensions'][0]['Value'] == 'unknown'


class TestLogEvent:
    """Test structured event logging."""

    @patch('cloudwatch_integration.logger')
    @patch('cloudwatch_integration.datetime')
    def test_log_event_success(self, mock_datetime, mock_logger):
        """Test successful event logging."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00Z"
        
        event_data = {"key1": "value1", "key2": 123}
        log_event("test_event", event_data)
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        assert logged_data["event_type"] == "test_event"
        assert logged_data["data"] == event_data
        assert logged_data["timestamp"] == "2023-01-01T00:00:00Z"

    @patch('cloudwatch_integration.logger')
    def test_log_event_empty_data(self, mock_logger):
        """Test event logging with empty data."""
        log_event("test_event", {})
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        assert logged_data["event_type"] == "test_event"
        assert logged_data["data"] == {}

    @patch('cloudwatch_integration.logger')
    def test_log_event_complex_data(self, mock_logger):
        """Test event logging with complex data structures."""
        event_data = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "boolean": True,
            "null": None
        }
        
        log_event("complex_event", event_data)
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        assert logged_data["data"] == event_data

    @patch('cloudwatch_integration.logger')
    def test_log_event_special_characters(self, mock_logger):
        """Test event logging with special characters."""
        event_data = {"message": "Test with special chars: àáâãäå"}
        
        log_event("special_chars", event_data)
        
        mock_logger.info.assert_called_once()
        # Should not raise JSON encoding errors
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        assert logged_data["data"]["message"] == "Test with special chars: àáâãäå"