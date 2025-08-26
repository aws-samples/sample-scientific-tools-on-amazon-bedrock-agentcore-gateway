"""
Unit tests for main lambda_function module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from lambda_function import (
    lambda_handler,
    _extract_tool_name,
    _error_response
)


class TestLambdaHandler:
    """Test main Lambda handler function."""

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_invoke_endpoint_success(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test successful invoke_endpoint routing."""
        event = {
            "tool_name": "invoke_endpoint",
            "sequence": "MKTVRQERLK"
        }
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_invoke_module = Mock()
            mock_invoke_module.invoke_endpoint.return_value = {"success": True, "data": {"output_id": "test-123"}}
            mock_import.return_value = mock_invoke_module
            
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is True
            mock_invoke_module.invoke_endpoint.assert_called_once_with(event, mock_lambda_context)
            mock_put_metric.assert_any_call("InvocationSuccess", 1)
            mock_log_event.assert_called()

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_get_results_success(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test successful get_results routing."""
        event = {
            "tool_name": "get_results",
            "output_id": "test-123"
        }
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_get_results_module = Mock()
            mock_get_results_module.get_results.return_value = {"success": True, "data": {"status": "completed"}}
            mock_import.return_value = mock_get_results_module
            
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is True
            mock_get_results_module.get_results.assert_called_once_with(event, mock_lambda_context)
            mock_put_metric.assert_any_call("InvocationSuccess", 1)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_missing_tool_name(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test handler with missing tool name."""
        event = {"sequence": "MKTVRQERLK"}
        
        result = lambda_handler(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "MISSING_TOOL_NAME"
        mock_put_metric.assert_called_with("InvocationError", 1)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_unknown_tool(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test handler with unknown tool name."""
        event = {
            "tool_name": "unknown_tool",
            "sequence": "MKTVRQERLK"
        }
        
        result = lambda_handler(event, mock_lambda_context)
        
        assert result["success"] is False
        assert result["error_code"] == "UNKNOWN_TOOL"
        assert "unknown_tool" in result["message"]
        mock_put_metric.assert_called_with("InvocationError", 1)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_tool_name_with_delimiter(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test handler with tool name containing delimiter."""
        event = {
            "tool_name": "prefix___invoke_endpoint",
            "sequence": "MKTVRQERLK"
        }
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_invoke_module = Mock()
            mock_invoke_module.invoke_endpoint.return_value = {"success": True, "data": {"output_id": "test-123"}}
            mock_import.return_value = mock_invoke_module
            
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is True
            mock_invoke_module.invoke_endpoint.assert_called_once_with(event, mock_lambda_context)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_tool_failure(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test handler when tool returns failure."""
        event = {
            "tool_name": "invoke_endpoint",
            "sequence": "MKTVRQERLK"
        }
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_invoke_module = Mock()
            mock_invoke_module.invoke_endpoint.return_value = {"success": False, "error_code": "VALIDATION_ERROR"}
            mock_import.return_value = mock_invoke_module
            
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is False
            mock_put_metric.assert_any_call("InvocationError", 1)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    @patch('lambda_function.logger')
    def test_lambda_handler_exception(self, mock_logger, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test handler when unexpected exception occurs."""
        event = {
            "tool_name": "invoke_endpoint",
            "sequence": "MKTVRQERLK"
        }
        
        # Mock the dynamic import to raise exception during import itself
        def mock_import_side_effect(name, *args, **kwargs):
            if name == "invoke_endpoint":
                raise Exception("Unexpected error")
            # Allow other imports to work normally
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import_side_effect):
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is False
            assert result["error_code"] == "HANDLER_ERROR"
            assert "Unexpected error" in result["message"]
            mock_put_metric.assert_called_with("InvocationError", 1)

    @patch('lambda_function._extract_tool_name')
    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_extract_from_context(self, mock_put_metric, mock_log_event, mock_extract, mock_lambda_context):
        """Test handler extracting tool name from context."""
        event = {"sequence": "MKTVRQERLK"}
        mock_extract.return_value = "invoke_endpoint"
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_invoke_module = Mock()
            mock_invoke_module.invoke_endpoint.return_value = {"success": True, "data": {"output_id": "test-123"}}
            mock_import.return_value = mock_invoke_module
            
            result = lambda_handler(event, mock_lambda_context)
            
            assert result["success"] is True
            mock_extract.assert_called_once_with(mock_lambda_context)

    @patch('lambda_function.log_event')
    @patch('lambda_function.put_simple_metric')
    def test_lambda_handler_duration_metric(self, mock_put_metric, mock_log_event, mock_lambda_context):
        """Test that duration metric is recorded."""
        event = {
            "tool_name": "invoke_endpoint",
            "sequence": "MKTVRQERLK"
        }
        
        # Mock the dynamic import
        with patch('builtins.__import__') as mock_import:
            mock_invoke_module = Mock()
            mock_invoke_module.invoke_endpoint.return_value = {"success": True, "data": {"output_id": "test-123"}}
            mock_import.return_value = mock_invoke_module
            
            lambda_handler(event, mock_lambda_context)
            
            # Check that Duration metric was called
            duration_calls = [call for call in mock_put_metric.call_args_list 
                            if call[0][0] == "Duration"]
            assert len(duration_calls) == 1
            assert duration_calls[0][0][2] == "Milliseconds"


class TestExtractToolName:
    """Test tool name extraction from context."""

    def test_extract_tool_name_success(self):
        """Test successful tool name extraction."""
        context = Mock()
        client_context = Mock()
        client_context.custom = {"bedrockAgentCoreToolName": "invoke_endpoint"}
        context.client_context = client_context
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name == "invoke_endpoint"

    def test_extract_tool_name_no_client_context(self):
        """Test extraction when client_context is None."""
        context = Mock()
        context.client_context = None
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name is None

    def test_extract_tool_name_no_custom(self):
        """Test extraction when custom is None."""
        context = Mock()
        client_context = Mock()
        client_context.custom = None
        context.client_context = client_context
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name is None

    def test_extract_tool_name_missing_key(self):
        """Test extraction when key is missing from custom."""
        context = Mock()
        client_context = Mock()
        client_context.custom = {"otherKey": "otherValue"}
        context.client_context = client_context
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name is None

    def test_extract_tool_name_no_hasattr_client_context(self):
        """Test extraction when context has no client_context attribute."""
        context = Mock()
        del context.client_context  # Remove the attribute
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name is None

    @patch('lambda_function.logger')
    def test_extract_tool_name_exception(self, mock_logger):
        """Test extraction when exception occurs."""
        context = Mock()
        context.client_context = Mock()
        context.client_context.custom = Mock()
        context.client_context.custom.get.side_effect = Exception("Test error")
        
        tool_name = _extract_tool_name(context)
        
        assert tool_name is None
        mock_logger.error.assert_called_once()


class TestErrorResponse:
    """Test error response creation."""

    @patch('lambda_function.log_event')
    def test_error_response_basic(self, mock_log_event):
        """Test basic error response creation."""
        context = Mock()
        context.aws_request_id = "test-request-123"
        
        response = _error_response("TEST_ERROR", "Test message", context)
        
        assert response["success"] is False
        assert response["error_code"] == "TEST_ERROR"
        assert response["message"] == "Test message"
        assert "timestamp" in response
        mock_log_event.assert_called_once()

    @patch('lambda_function.log_event')
    def test_error_response_with_details(self, mock_log_event):
        """Test error response creation with details."""
        context = Mock()
        context.aws_request_id = "test-request-123"
        details = {"key": "value", "number": 123}
        
        response = _error_response("TEST_ERROR", "Test message", context, details)
        
        assert response["details"] == details
        mock_log_event.assert_called_once()

    @patch('lambda_function.log_event')
    def test_error_response_no_context(self, mock_log_event):
        """Test error response creation with None context."""
        response = _error_response("TEST_ERROR", "Test message", None)
        
        assert response["success"] is False
        assert response["error_code"] == "TEST_ERROR"
        mock_log_event.assert_called_once()
        
        # Check that log_event was called with "unknown" request_id
        call_args = mock_log_event.call_args[0][1]
        assert call_args["request_id"] == "unknown"