# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
SageMaker async inference result retrieval logic.

This module handles the retrieval of results from S3 for completed
SageMaker async inference requests.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from validators import (
    validate_event_structure,
    create_validation_error_response,
    get_arn_components,
)
from cloudwatch_integration import put_simple_metric, log_event

logger = logging.getLogger(__name__)


def get_results(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Retrieve results from S3 for a completed async inference request.

    Args:
        event: Lambda event object containing output_id
        context: Lambda context object

    Returns:
        Dict containing results or status information
    """
    start_time = datetime.now(timezone.utc)

    try:
        # Log the get_results request
        log_event(
            "get_results_started",
            {
                "request_id": context.aws_request_id,
                "event_keys": (
                    list(event.keys()) if isinstance(event, dict) else "not_dict"
                ),
            },
        )

        # Validate event structure
        structure_validation = validate_event_structure(event, ["output_id"])
        # nosemgrep is-function-without-parentheses
        if not structure_validation.is_valid:
            put_simple_metric("ValidationError", 1)
            return create_validation_error_response(
                structure_validation, "INVALID_EVENT_STRUCTURE"
            )

        # Extract invocation input (parameter name is output_id for backward compatibility)
        output_id = event.get("output_id", "")

        # Handle both invocation ID and S3 output path
        # invocation_input = invocation_arn.strip()

        # Check if this is an S3 path or just an invocation ID
        if output_id.startswith("s3://"):
            # Extract bucket and key from S3 path
            s3_path_parts = output_id.replace("s3://", "").split("/", 1)
            if len(s3_path_parts) != 2:
                return _error_response(
                    "INVALID_S3_PATH",
                    "Invalid S3 path format. Expected: s3://bucket/key",
                )

            s3_bucket_from_path = s3_path_parts[0]
            output_key_from_path = s3_path_parts[1]

            # Extract invocation ID from the file name (assuming UUID format)
            file_name = output_key_from_path.split("/")[-1]
            output_id = file_name.replace(".out", "")

            # Override S3 configuration with values from the path
            s3_bucket = s3_bucket_from_path
            output_key = output_key_from_path

        else:

            # Get environment variables for S3 configuration
            s3_bucket = os.environ.get("S3_BUCKET_NAME")
            s3_output_prefix = os.environ.get(
                "S3_OUTPUT_PREFIX", "async-inference-output"
            )

            if not s3_bucket:
                return _error_response(
                    "CONFIGURATION_ERROR",
                    "S3 bucket name not configured. Check S3_BUCKET_NAME environment variable.",
                )

            # Construct S3 output key
            output_key = f"{s3_output_prefix.rstrip('/')}/{output_id}.out"

        s3_failure_prefix = os.environ.get(
            "S3_FAILURE_PREFIX", "async-inference-failures"
        )

        # Construct failure key
        failure_key = f"{s3_failure_prefix.rstrip('/')}/{output_id}.out"

        # Validate S3 configuration
        config_validation = _validate_s3_configuration(
            s3_bucket, "async-inference-output", s3_failure_prefix
        )
        if not config_validation["is_valid"]:
            return _error_response(
                "S3_CONFIGURATION_ERROR",
                config_validation["error_message"],
                config_validation.get("details", {}),
            )

        # Initialize S3 client
        try:
            s3_client = boto3.client("s3")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            return _error_response(
                "CLIENT_INITIALIZATION_ERROR",
                "Failed to initialize S3 client",
                {"initialization_error": str(e)},
            )

        # Validate S3 bucket accessibility
        bucket_validation = _validate_s3_bucket_access(s3_client, s3_bucket)
        if not bucket_validation["is_accessible"]:
            return _error_response(
                bucket_validation["error_code"],
                bucket_validation["error_message"],
                {
                    "s3_bucket": s3_bucket,
                    "validation_details": bucket_validation.get("details", {}),
                },
            )

        # S3 paths are already constructed above based on input type

        log_event(
            "s3_result_check_started",
            {
                "output_id": output_id,
                "s3_bucket": s3_bucket,
                "output_key": output_key,
                "failure_key": failure_key,
                "request_id": context.aws_request_id,
            },
        )

        # Check for successful results first
        result_status = _check_s3_object_exists(s3_client, s3_bucket, output_key)

        # Handle S3 access errors for output path
        if result_status.get("error") and result_status["error"] not in [
            "ACCESS_DENIED",
            "BUCKET_NOT_FOUND",
            "INVALID_S3_NAME",
            "S3_SERVICE_UNAVAILABLE",
            "BOTO_CONNECTION_ERROR",
        ]:
            # For non-critical errors, continue to check failure path
            logger.warning(
                f"Non-critical S3 error checking output path: {result_status.get('error_message', 'Unknown error')}"
            )
        elif result_status.get("error") in [
            "ACCESS_DENIED",
            "BUCKET_NOT_FOUND",
            "INVALID_S3_NAME",
        ]:
            # Critical configuration errors - return immediately
            return _error_response(
                result_status["error"],
                f"S3 configuration error: {result_status.get('error_message', 'Unknown error')}",
                {
                    # "invocation_arn": invocation_arn,
                    "output_id": output_id,
                    "s3_bucket": s3_bucket,
                    "attempted_path": f"s3://{s3_bucket}/{output_key}",
                },
            )
        elif result_status.get("error") in [
            "S3_SERVICE_UNAVAILABLE",
            "BOTO_CONNECTION_ERROR",
        ]:
            # Temporary service issues - return with retry suggestion
            return _error_response(
                result_status["error"],
                f"S3 service temporarily unavailable: {result_status.get('error_message', 'Unknown error')}",
                {
                    # "invocation_arn": invocation_arn,
                    "output_id": output_id,
                    "retry_suggested": True,
                    "retry_after_seconds": 30,
                },
            )

        if result_status["exists"]:
            # Results are available - retrieve and parse them
            try:
                results_data = _retrieve_s3_results(s3_client, s3_bucket, output_key)

                # Calculate retrieval duration and result size
                retrieval_duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                result_size_bytes = len(str(results_data)) if results_data else 0

                # Record success metrics
                put_simple_metric("ResultsRetrievalSuccess", 1)
                put_simple_metric(
                    "ResultsRetrievalDuration", retrieval_duration_ms, "Milliseconds"
                )
                put_simple_metric("ResultsSize", result_size_bytes, "Bytes")

                log_event(
                    "results_retrieved_success",
                    {
                        "output_id": output_id,
                        "results_size": result_size_bytes,
                        "retrieval_duration_ms": retrieval_duration_ms,
                        "request_id": context.aws_request_id,
                    },
                )

                return _success_response(
                    {
                        "status": "completed",
                        "results": results_data,
                        # "invocation_arn": invocation_arn,
                        "output_id": output_id,
                        "s3_output_path": f"s3://{s3_bucket}/{output_key}",
                        "completion_time": result_status.get("last_modified"),
                    },
                    "Results retrieved successfully",
                )

            except Exception as e:
                logger.error(f"Error retrieving results from S3: {str(e)}")
                put_simple_metric("ResultsRetrievalError", 1)
                return _error_response(
                    "RESULT_RETRIEVAL_ERROR",
                    f"Failed to retrieve results from S3: {str(e)}",
                    {
                        "output_id": output_id,
                        "s3_output_path": f"s3://{s3_bucket}/{output_key}",
                    },
                )

        # Check for failure results
        failure_status = _check_s3_object_exists(s3_client, s3_bucket, failure_key)

        # Handle S3 access errors for failure path
        if failure_status.get("error") and failure_status["error"] not in [
            "ACCESS_DENIED",
            "BUCKET_NOT_FOUND",
            "INVALID_S3_NAME",
            "S3_SERVICE_UNAVAILABLE",
            "BOTO_CONNECTION_ERROR",
        ]:
            # For non-critical errors, continue to in-progress status
            logger.warning(
                f"Non-critical S3 error checking failure path: {failure_status.get('error_message', 'Unknown error')}"
            )
        elif failure_status.get("error") in [
            "ACCESS_DENIED",
            "BUCKET_NOT_FOUND",
            "INVALID_S3_NAME",
        ]:
            # Critical configuration errors - but we already checked output, so this is likely the same issue
            # Continue to in-progress status but log the issue
            logger.error(
                f"S3 configuration error checking failure path: {failure_status.get('error_message', 'Unknown error')}"
            )
        elif failure_status.get("error") in [
            "S3_SERVICE_UNAVAILABLE",
            "BOTO_CONNECTION_ERROR",
        ]:
            # Temporary service issues - we already handled this for output path
            logger.warning(
                f"S3 service issue checking failure path: {failure_status.get('error_message', 'Unknown error')}"
            )

        if failure_status["exists"]:
            # Prediction failed - retrieve error details
            try:
                failure_data = _retrieve_s3_failure_details(
                    s3_client, s3_bucket, failure_key
                )

                # Record failure metrics
                put_simple_metric("PredictionFailed", 1)

                log_event(
                    "failure_detected",
                    {
                        "output_id": output_id,
                        "failure_time": failure_status.get("last_modified"),
                        "request_id": context.aws_request_id,
                    },
                )

                return _error_response(
                    "PREDICTION_FAILED",
                    "Async inference prediction failed",
                    {
                        "status": "failed",
                        # "invocation_arn": invocation_arn,
                        "output_id": output_id,
                        "s3_failure_path": f"s3://{s3_bucket}/{failure_key}",
                        "failure_time": failure_status.get("last_modified"),
                        "error_details": failure_data,
                    },
                )

            except Exception as e:
                logger.error(f"Error retrieving failure details from S3: {str(e)}")
                put_simple_metric("FailureRetrievalError", 1)
                return _error_response(
                    "FAILURE_RETRIEVAL_ERROR",
                    "Prediction failed, but could not retrieve failure details",
                    {
                        "status": "failed",
                        "output_id": output_id,
                        "s3_failure_path": f"s3://{s3_bucket}/{failure_key}",
                        "retrieval_error": str(e),
                    },
                )

        # Neither success nor failure files exist - prediction is still in progress
        log_event(
            "prediction_in_progress",
            {
                "output_id": output_id,
                "checked_paths": {"output_key": output_key, "failure_key": failure_key},
                "request_id": context.aws_request_id,
            },
        )

        # Provide helpful information about the in-progress prediction
        in_progress_data = {
            "status": "in_progress",
            # "invocation_arn": invocation_arn,
            "output_id": output_id,
            "message": "Prediction is still in progress. Please check again later.",
            "expected_paths": {
                "success": f"s3://{s3_bucket}/{output_key}",
                "failure": f"s3://{s3_bucket}/{failure_key}",
            },
            # "estimated_completion": _estimate_completion_time_from_arn(invocation_arn),
            "check_interval_seconds": 30,
        }

        # Add any S3 access warnings to the response
        s3_warnings = []
        if result_status.get("error"):
            s3_warnings.append(
                f"Output path check: {result_status.get('error_message', 'Unknown error')}"
            )
        if failure_status.get("error"):
            s3_warnings.append(
                f"Failure path check: {failure_status.get('error_message', 'Unknown error')}"
            )

        if s3_warnings:
            in_progress_data["s3_warnings"] = s3_warnings

        return _success_response(in_progress_data, "Prediction is still in progress")

    except Exception as e:
        logger.error(f"Unexpected error in get_results: {str(e)}", exc_info=True)
        put_simple_metric("UnexpectedError", 1)
        return _error_response(
            "GET_RESULTS_ERROR", f"Unexpected error in get_results: {str(e)}"
        )


def _check_s3_object_exists(s3_client, bucket: str, key: str) -> Dict[str, Any]:
    """
    Check if an S3 object exists and get its metadata.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Dict with existence status and metadata
    """
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        return {
            "exists": True,
            "last_modified": (
                response.get("LastModified", "").isoformat()
                if response.get("LastModified")
                else None
            ),
            "content_length": response.get("ContentLength", 0),
            "etag": response.get("ETag", "").strip('"'),
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", "")

        if error_code == "404" or error_code == "NoSuchKey":
            # Object doesn't exist - this is expected for in-progress predictions
            return {"exists": False}
        elif error_code == "403" or error_code == "AccessDenied":
            # Access denied - permission issue
            logger.error(f"Access denied to S3 object {bucket}/{key}: {error_message}")
            return {
                "exists": False,
                "error": "ACCESS_DENIED",
                "error_message": "Access denied to S3 object",
            }
        elif error_code == "NoSuchBucket":
            # Bucket doesn't exist - configuration issue
            logger.error(f"S3 bucket does not exist: {bucket}")
            return {
                "exists": False,
                "error": "BUCKET_NOT_FOUND",
                "error_message": f"S3 bucket '{bucket}' does not exist",
            }
        elif error_code in ["InvalidBucketName", "InvalidObjectName"]:
            # Invalid names - configuration issue
            logger.error(f"Invalid S3 bucket or key name: {bucket}/{key}")
            return {
                "exists": False,
                "error": "INVALID_S3_NAME",
                "error_message": "Invalid S3 bucket or object name",
            }
        elif error_code in ["RequestTimeout", "ServiceUnavailable", "SlowDown"]:
            # Temporary S3 service issues
            logger.warning(
                f"Temporary S3 service issue for {bucket}/{key}: {error_code}"
            )
            return {
                "exists": False,
                "error": "S3_SERVICE_UNAVAILABLE",
                "error_message": "S3 service temporarily unavailable",
            }
        else:
            # Other S3 error
            logger.error(
                f"S3 head_object error for {bucket}/{key}: {error_code} - {error_message}"
            )
            return {
                "exists": False,
                "error": error_code,
                "error_message": error_message or "Unknown S3 error",
            }

    except BotoCoreError as e:
        logger.error(f"BotoCore error checking S3 object {bucket}/{key}: {str(e)}")
        return {
            "exists": False,
            "error": "BOTO_CONNECTION_ERROR",
            "error_message": "Failed to connect to S3 service",
        }
    except Exception as e:
        logger.error(f"Unexpected error checking S3 object {bucket}/{key}: {str(e)}")
        return {"exists": False, "error": "UNKNOWN_ERROR", "error_message": str(e)}


def _retrieve_s3_results(s3_client, bucket: str, key: str) -> Dict[str, Any]:
    """
    Retrieve and parse results from S3.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Parsed results data
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        # Validate content is not empty
        if not content.strip():
            logger.warning(f"Empty results file retrieved from {bucket}/{key}")
            return {"raw_output": "", "warning": "Results file is empty"}

        # Try to parse as JSON first
        try:
            results_data = json.loads(content)

            # Validate that we have meaningful results
            if not results_data:
                logger.warning(f"Results from {bucket}/{key} parsed as empty JSON")
                return {
                    "raw_output": content,
                    "warning": "Results parsed as empty JSON",
                }

            return results_data

        except json.JSONDecodeError as json_error:
            # If not JSON, return as text with parsing info
            logger.warning(
                f"Results from {bucket}/{key} are not valid JSON: {str(json_error)}"
            )
            return {
                "raw_output": content,
                "parsing_info": {
                    "format": "text",
                    "json_error": str(json_error),
                    "content_length": len(content),
                },
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "404" or error_code == "NoSuchKey":
            logger.error(f"Results file disappeared during retrieval: {bucket}/{key}")
            raise Exception("Results file no longer exists (may have been deleted)")
        elif error_code == "403" or error_code == "AccessDenied":
            logger.error(f"Access denied retrieving results: {bucket}/{key}")
            raise Exception("Access denied to results file")
        elif error_code in ["InvalidObjectName", "InvalidBucketName"]:
            logger.error(f"Invalid S3 path for results: {bucket}/{key}")
            raise Exception("Invalid S3 path for results file")
        elif error_code in ["RequestTimeout", "ServiceUnavailable"]:
            logger.error(f"S3 service timeout retrieving results: {bucket}/{key}")
            raise Exception("S3 service timeout - please retry")
        else:
            logger.error(
                f"S3 ClientError retrieving results: {error_code} - {error_message}"
            )
            raise Exception(f"S3 error retrieving results: {error_message}")

    except BotoCoreError as e:
        logger.error(f"BotoCore error retrieving results: {str(e)}")
        raise Exception("Failed to connect to S3 service for results retrieval")

    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error for results file {bucket}/{key}: {str(e)}")
        raise Exception("Results file contains invalid character encoding")

    except Exception as e:
        logger.error(f"Unexpected error retrieving results: {str(e)}")
        raise Exception(f"Unexpected error retrieving results: {str(e)}")


def _retrieve_s3_failure_details(s3_client, bucket: str, key: str) -> Dict[str, Any]:
    """
    Retrieve and parse failure details from S3.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Parsed failure details
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        # Validate content is not empty
        if not content.strip():
            logger.warning(f"Empty failure details file retrieved from {bucket}/{key}")
            return {
                "error_message": "Prediction failed but no error details available",
                "error_type": "empty_failure_log",
                "raw_content": "",
            }

        # Try to parse as JSON first
        try:
            failure_data = json.loads(content)

            # Enhance failure data with additional context
            if isinstance(failure_data, dict):
                failure_data["retrieval_info"] = {
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "content_length": len(content),
                    "format": "json",
                }

            return failure_data

        except json.JSONDecodeError as json_error:
            # If not JSON, return as text with basic structure and parsing info
            logger.warning(
                f"Failure details from {bucket}/{key} are not valid JSON: {str(json_error)}"
            )
            return {
                "error_message": content,
                "error_type": "text_format",
                "parsing_info": {
                    "json_error": str(json_error),
                    "content_length": len(content),
                    "format": "text",
                },
                "retrieval_info": {
                    "retrieved_at": datetime.now(timezone.utc).isoformat()
                },
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "404" or error_code == "NoSuchKey":
            logger.error(
                f"Failure details file disappeared during retrieval: {bucket}/{key}"
            )
            return {
                "error_message": "Prediction failed but failure details file no longer exists",
                "error_type": "failure_log_missing",
                "s3_error": error_code,
            }
        elif error_code == "403" or error_code == "AccessDenied":
            logger.error(f"Access denied retrieving failure details: {bucket}/{key}")
            return {
                "error_message": "Prediction failed but access denied to failure details",
                "error_type": "failure_log_access_denied",
                "s3_error": error_code,
            }
        elif error_code in ["RequestTimeout", "ServiceUnavailable"]:
            logger.error(
                f"S3 service timeout retrieving failure details: {bucket}/{key}"
            )
            return {
                "error_message": "Prediction failed and S3 service timeout retrieving failure details",
                "error_type": "failure_log_service_timeout",
                "s3_error": error_code,
                "retry_suggested": True,
            }
        else:
            logger.error(
                f"S3 ClientError retrieving failure details: {error_code} - {error_message}"
            )
            return {
                "error_message": f"Could not retrieve failure details: {error_message}",
                "error_type": "s3_retrieval_error",
                "s3_error": error_code,
            }

    except BotoCoreError as e:
        logger.error(f"BotoCore error retrieving failure details: {str(e)}")
        return {
            "error_message": "Failed to connect to S3 service for failure details",
            "error_type": "boto_connection_error",
        }

    except UnicodeDecodeError as e:
        logger.error(
            f"Unicode decode error for failure details file {bucket}/{key}: {str(e)}"
        )
        return {
            "error_message": "Failure details file contains invalid character encoding",
            "error_type": "encoding_error",
            "decode_error": str(e),
        }

    except Exception as e:
        logger.error(f"Unexpected error retrieving failure details: {str(e)}")
        return {
            "error_message": f"Could not retrieve failure details: {str(e)}",
            "error_type": "unexpected_retrieval_error",
        }


# def _estimate_completion_time_from_arn(invocation_arn: str) -> Optional[str]:
#     """
#     Estimate completion time based on invocation ARN timestamp (if available).

#     Args:
#         invocation_arn: SageMaker invocation ARN

#     Returns:
#         ISO format timestamp estimate or None
#     """
#     try:
#         # For now, provide a generic estimate since we can't extract
#         # the original invocation time from the ARN alone
#         from datetime import timedelta

#         # Assume most predictions complete within 10 minutes
#         estimated_completion = datetime.now(timezone.utc) + timedelta(minutes=10)
#         return estimated_completion.isoformat()

#     except Exception as e:
#         logger.warning(f"Could not estimate completion time: {str(e)}")
#         return None


def _success_response(data: Dict[str, Any], message: str = "Success") -> Dict[str, Any]:
    """
    Create standardized success response format.

    Args:
        data: Response data
        message: Success message

    Returns:
        Standardized success response dictionary
    """
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _error_response(
    error_code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized error response format.

    Args:
        error_code: Error code identifier
        message: Error message
        details: Additional error details

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
    log_event(
        "get_results_error",
        {"error_code": error_code, "message": message, "details": details},
    )

    return error_response


def _validate_s3_configuration(
    bucket: str, output_prefix: str, failure_prefix: str
) -> Dict[str, Any]:
    """
    Validate S3 configuration parameters.

    Args:
        bucket: S3 bucket name
        output_prefix: Output prefix path
        failure_prefix: Failure prefix path

    Returns:
        Dict with validation results
    """
    errors = []

    # Validate bucket name format
    if not bucket or not isinstance(bucket, str):
        errors.append("S3 bucket name must be a non-empty string")
    elif len(bucket) < 3 or len(bucket) > 63:
        errors.append("S3 bucket name must be between 3 and 63 characters")
    elif not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", bucket):
        errors.append("S3 bucket name contains invalid characters")

    # Validate prefixes
    if output_prefix and not isinstance(output_prefix, str):
        errors.append("S3 output prefix must be a string")
    if failure_prefix and not isinstance(failure_prefix, str):
        errors.append("S3 failure prefix must be a string")

    # Check for prefix conflicts
    if (
        output_prefix
        and failure_prefix
        and output_prefix.strip("/") == failure_prefix.strip("/")
    ):
        errors.append("Output and failure prefixes cannot be the same")

    return {
        "is_valid": len(errors) == 0,
        "error_message": "; ".join(errors) if errors else None,
        "details": {
            "bucket": bucket,
            "output_prefix": output_prefix,
            "failure_prefix": failure_prefix,
            "validation_errors": errors,
        },
    }


def _validate_s3_bucket_access(s3_client, bucket: str) -> Dict[str, Any]:
    """
    Validate that the S3 bucket exists and is accessible.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name

    Returns:
        Dict with accessibility results
    """
    try:
        # Try to list objects in the bucket (with limit to minimize cost)
        s3_client.list_objects_v2(Bucket=bucket, MaxKeys=1)

        return {"is_accessible": True, "error_code": None, "error_message": None}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "NoSuchBucket":
            return {
                "is_accessible": False,
                "error_code": "BUCKET_NOT_FOUND",
                "error_message": f"S3 bucket '{bucket}' does not exist",
                "details": {"s3_error": error_code},
            }
        elif error_code == "403" or error_code == "AccessDenied":
            return {
                "is_accessible": False,
                "error_code": "BUCKET_ACCESS_DENIED",
                "error_message": f"Access denied to S3 bucket '{bucket}'",
                "details": {"s3_error": error_code},
            }
        elif error_code in ["InvalidBucketName", "InvalidRequest"]:
            return {
                "is_accessible": False,
                "error_code": "INVALID_BUCKET_NAME",
                "error_message": f"Invalid S3 bucket name: '{bucket}'",
                "details": {"s3_error": error_code},
            }
        else:
            return {
                "is_accessible": False,
                "error_code": "S3_ACCESS_ERROR",
                "error_message": f"Cannot access S3 bucket '{bucket}': {error_message}",
                "details": {"s3_error": error_code},
            }

    except BotoCoreError as e:
        return {
            "is_accessible": False,
            "error_code": "S3_CONNECTION_ERROR",
            "error_message": "Failed to connect to S3 service",
            "details": {"boto_error": str(e)},
        }

    except Exception as e:
        return {
            "is_accessible": False,
            "error_code": "UNKNOWN_S3_ERROR",
            "error_message": f"Unexpected error accessing S3 bucket: {str(e)}",
            "details": {"error": str(e)},
        }


# Note: _log_event function replaced by log_structured_event from cloudwatch_integration
