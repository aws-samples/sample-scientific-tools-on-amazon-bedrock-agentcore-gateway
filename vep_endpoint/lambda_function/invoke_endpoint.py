"""
SageMaker async endpoint invocation logic.

This module handles the invocation of SageMaker async inference endpoints
with protein sequence data.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import re

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from validators import (
    validate_amino_acid_sequence,
    validate_event_structure,
    create_validation_error_response,
    get_cleaned_sequence,
)
from cloudwatch_integration import put_simple_metric, log_event

logger = logging.getLogger(__name__)


def invoke_endpoint(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Invoke SageMaker async endpoint with protein sequence.

    Args:
        event: Lambda event object containing sequence data
        context: Lambda context object

    Returns:
        Dict containing invocation response or error information
    """
    start_time = datetime.now(timezone.utc)

    try:
        # Log the invocation request
        log_event(
            "invoke_endpoint_started",
            {
                "request_id": context.aws_request_id,
                "event_keys": (
                    list(event.keys()) if isinstance(event, dict) else "not_dict"
                ),
            },
        )

        # Validate event structure
        structure_validation = validate_event_structure(event, ["sequence"])
        if not structure_validation.is_valid:
            put_simple_metric("ValidationError", 1)
            return create_validation_error_response(
                structure_validation, "INVALID_EVENT_STRUCTURE"
            )

        # Extract and validate amino acid sequence
        raw_sequence = event.get("sequence", "")
        sequence_validation = validate_amino_acid_sequence(raw_sequence)
        if not sequence_validation.is_valid:
            put_simple_metric("ValidationError", 1)
            return create_validation_error_response(
                sequence_validation, "INVALID_SEQUENCE"
            )

        # Get cleaned sequence for processing
        cleaned_sequence = get_cleaned_sequence(raw_sequence)

        # Get environment variables
        endpoint_name = os.environ.get("SAGEMAKER_ENDPOINT_NAME")
        s3_bucket = os.environ.get("S3_BUCKET_NAME")
        s3_input_prefix = os.environ.get("S3_INPUT_PREFIX", "async-inference-input")
        s3_output_prefix = os.environ.get("S3_OUTPUT_PREFIX", "async-inference-output")

        if not endpoint_name:
            put_simple_metric("ConfigurationError", 1)
            return _error_response(
                "CONFIGURATION_ERROR",
                "SageMaker endpoint name not configured. Check SAGEMAKER_ENDPOINT_NAME environment variable.",
            )

        if not s3_bucket:
            put_simple_metric("ConfigurationError", 1)
            return _error_response(
                "CONFIGURATION_ERROR",
                "S3 bucket name not configured. Check S3_BUCKET_NAME environment variable.",
            )

        # Initialize AWS clients
        try:
            sagemaker_client = boto3.client("sagemaker-runtime")
            s3_client = boto3.client("s3")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            put_simple_metric("ClientError", 1)
            return _error_response(
                "CLIENT_INITIALIZATION_ERROR", "Failed to initialize AWS clients"
            )

        # Prepare input data for the model
        input_data = {"sequence": cleaned_sequence}

        # Generate unique invocation ID for tracking
        invocation_id = str(uuid.uuid4())

        # Construct S3 paths
        s3_input_key = f"{s3_input_prefix.rstrip('/')}/{invocation_id}.json"
        s3_input_path = f"s3://{s3_bucket}/{s3_input_key}"
        s3_output_path = (
            f"s3://{s3_bucket}/{s3_output_prefix.rstrip('/')}/{invocation_id}.out"
        )

        # Upload input data to S3 first (required for async inference)
        try:
            input_json = json.dumps(input_data)
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_input_key,
                Body=input_json,
                ContentType="application/json",
            )
            logger.info(f"Successfully uploaded input data to S3: {s3_input_path}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 upload error: {error_code} - {error_message}")
            put_simple_metric("S3Error", 1)
            return _error_response(
                "S3_UPLOAD_ERROR", f"Failed to upload input data to S3: {error_message}"
            )

        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {str(e)}")
            put_simple_metric("S3Error", 1)
            return _error_response(
                "S3_UPLOAD_ERROR",
                f"Unexpected error uploading input data to S3: {str(e)}",
            )

        # Invoke SageMaker async endpoint
        try:
            log_event(
                "sagemaker_invocation_started",
                {
                    "endpoint_name": endpoint_name,
                    "invocation_id": invocation_id,
                    "sequence_length": len(cleaned_sequence),
                    "s3_input_path": s3_input_path,
                    "s3_output_path": s3_output_path,
                    "request_id": context.aws_request_id,
                },
            )

            response = sagemaker_client.invoke_endpoint_async(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Accept="application/json",
                InputLocation=s3_input_path,
                InvocationTimeoutSeconds=3600,  # 1 hour timeout
                RequestTTLSeconds=21600,  # 6 hours TTL
                CustomAttributes=json.dumps(
                    {
                        "invocation_id": invocation_id,
                        "sequence_length": len(cleaned_sequence),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )

            # Parse successful response
            # invocation_arn = response.get('InferenceId')
            invocation_id = invocation_arn = response.get("InferenceId")
            output_location = response.get("OutputLocation", s3_output_path)
            output_id = re.search(r".*\/(.*)\.out", output_location).group(1)

            # if not invocation_arn:
            if not invocation_id:
                logger.error("SageMaker response missing InferenceId")
                return _error_response(
                    "SAGEMAKER_RESPONSE_ERROR",
                    "SageMaker response missing inference ID",
                )

            # Calculate invocation duration
            invocation_duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Record success metrics
            put_simple_metric("InvocationSuccess", 1)
            put_simple_metric(
                "InvocationDuration", invocation_duration_ms, "Milliseconds"
            )
            put_simple_metric("SequenceLength", len(cleaned_sequence))

            # Log successful invocation
            log_event(
                "sagemaker_invocation_success",
                {
                    "s3_output_path": output_location,
                    "output_id": output_id,
                    "invocation_id": invocation_id,
                    "sequence_length": len(cleaned_sequence),
                    "endpoint_name": endpoint_name,
                    "duration_ms": invocation_duration_ms,
                    "request_id": context.aws_request_id,
                },
            )

            # Return success response
            return _success_response(
                {
                    "s3_output_path": output_location,
                    "output_id": output_id,
                    "sequence_length": len(cleaned_sequence),
                    "estimated_completion_time": _estimate_completion_time(
                        len(cleaned_sequence)
                    ),
                },
                "Async inference request submitted successfully",
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            logger.error(f"SageMaker ClientError: {error_code} - {error_message}")

            # Map specific SageMaker errors to user-friendly messages and record metrics
            put_simple_metric("SageMakerError", 1)

            if error_code == "ValidationException":
                return _error_response(
                    "SAGEMAKER_VALIDATION_ERROR",
                    f"SageMaker validation error: {error_message}",
                )
            elif error_code == "ModelError":
                return _error_response(
                    "SAGEMAKER_MODEL_ERROR", "Model error occurred during invocation"
                )
            elif error_code == "InternalFailure":
                return _error_response(
                    "SAGEMAKER_INTERNAL_ERROR", "SageMaker internal error occurred"
                )
            elif error_code == "ServiceUnavailable":
                return _error_response(
                    "SAGEMAKER_SERVICE_UNAVAILABLE",
                    "SageMaker service is temporarily unavailable",
                )
            else:
                return _error_response(
                    "SAGEMAKER_ERROR", f"SageMaker error: {error_message}"
                )

        except BotoCoreError as e:
            logger.error(f"BotoCore error during SageMaker invocation: {str(e)}")
            put_simple_metric("ConnectionError", 1)
            return _error_response(
                "AWS_CONNECTION_ERROR", "Failed to connect to AWS services"
            )

        except Exception as e:
            logger.error(
                f"Unexpected error during SageMaker invocation: {str(e)}", exc_info=True
            )
            put_simple_metric("UnexpectedError", 1)
            return _error_response(
                "INVOCATION_ERROR",
                f"Unexpected error during endpoint invocation: {str(e)}",
            )

    except Exception as e:
        logger.error(f"Unexpected error in invoke_endpoint: {str(e)}", exc_info=True)
        put_simple_metric("UnexpectedError", 1)
        return _error_response(
            "INVOKE_ENDPOINT_ERROR", f"Unexpected error in invoke_endpoint: {str(e)}"
        )


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
        "invoke_endpoint_error",
        {"error_code": error_code, "message": message, "details": details},
    )

    return error_response


# Note: Using simplified CloudWatch integration


def _estimate_completion_time(sequence_length: int) -> str:
    """
    Estimate completion time based on sequence length.

    Args:
        sequence_length: Length of the amino acid sequence

    Returns:
        ISO format timestamp estimate
    """
    # Simple estimation: ~1 minute per 600 amino acids, minimum 1 minutes
    estimated_minutes = max(1, sequence_length // 600 + 1)

    from datetime import timedelta

    estimated_completion = datetime.now(timezone.utc) + timedelta(
        minutes=estimated_minutes
    )

    return estimated_completion.isoformat()
