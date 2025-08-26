"""
Main Lambda handler for SageMaker async endpoint integration.

This module provides the main entry point for the Lambda function that handles
tool-based requests for invoking SageMaker async endpoints and retrieving results.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from cloudwatch_integration import put_simple_metric, log_event

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler that routes requests based on tool name.

    Args:
        event: Lambda event object containing request data
        context: Lambda context object containing runtime information

    Returns:
        Dict containing response data or error information
    """
    start_time = datetime.now(timezone.utc)

    try:
        # Log incoming request
        log_event("lambda_request_received", {"tool_name": event.get("tool_name")})

        # Parse tool name from context object or event object
        tool_name = event.get("tool_name") or _extract_tool_name(context)

        print(f"Original tool_name: {tool_name}")
        delimiter = "___"
        if tool_name and delimiter in tool_name:
            tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
        print(f"Converted tool_name: {tool_name}")

        if not tool_name:
            put_simple_metric("InvocationError", 1)
            return _error_response(
                "MISSING_TOOL_NAME",
                "Tool name not found in context object.",
                context,
            )

        # Route to appropriate method based on tool name
        if tool_name == "invoke_endpoint":
            from invoke_endpoint import invoke_endpoint
            result = invoke_endpoint(event, context)
            
        elif tool_name == "get_results":
            from get_results import get_results
            result = get_results(event, context)
            
        else:
            put_simple_metric("InvocationError", 1)
            return _error_response(
                "UNKNOWN_TOOL",
                f"Unknown tool: {tool_name}. Supported tools are: invoke_endpoint, get_results",
                context,
            )

        # Record duration
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        put_simple_metric("Duration", duration_ms, "Milliseconds")
        
        # Record success if result indicates success
        if result.get("success", False):
            put_simple_metric("InvocationSuccess", 1)
        else:
            put_simple_metric("InvocationError", 1)
            
        return result

    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        put_simple_metric("InvocationError", 1)
        return _error_response(
            "HANDLER_ERROR", 
            f"Unexpected error occurred: {str(e)}", 
            context
        )


def _extract_tool_name(context: Any) -> Optional[str]:
    """
    Extract tool name from Lambda context object.

    Args:
        context: Lambda context object

    Returns:
        Tool name if found, None otherwise
    """
    try:
        # Check if client_context exists and has custom attributes
        if hasattr(context, "client_context") and context.client_context:
            if (
                hasattr(context.client_context, "custom")
                and context.client_context.custom
            ):
                tool_name = context.client_context.custom.get(
                    "bedrockAgentCoreToolName"
                )
                if tool_name:
                    logger.info(f"Tool name extracted from context: {tool_name}")
                    return tool_name

        # Log context structure for debugging
        logger.warning("Tool name not found in context. Context structure:")
        logger.warning(f"Has client_context: {hasattr(context, 'client_context')}")
        if hasattr(context, "client_context") and context.client_context:
            logger.warning(f"Has custom: {hasattr(context.client_context, 'custom')}")
            if hasattr(context.client_context, "custom"):
                logger.warning(
                    f"Custom keys: {list(context.client_context.custom.keys()) if context.client_context.custom else 'None'}"
                )

        return None

    except Exception as e:
        logger.error(f"Error extracting tool name from context: {str(e)}")
        return None


def _error_response(
    error_code: str,
    message: str,
    context: Any,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized error response.

    Args:
        error_code: Error code identifier
        message: Human-readable error message
        context: Lambda context object
        details: Optional additional error details

    Returns:
        Standardized error response dictionary
    """
    error_response = {
        "success": False,
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if details:
        error_response["details"] = details

    # Log error
    log_event("lambda_error", {
        "error_code": error_code, 
        "message": message,
        "request_id": context.aws_request_id if context else "unknown"
    })

    return error_response

