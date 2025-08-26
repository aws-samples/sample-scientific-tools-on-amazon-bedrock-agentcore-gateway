"""
Input validation utilities for Lambda function.

This module provides validation functions for amino acid sequences,
invocation ARNs, and other input parameters.
"""

import re
import logging
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    errors: List[str]


def validate_amino_acid_sequence(sequence: str) -> ValidationResult:
    """
    Validate amino acid sequence format and content.

    Args:
        sequence: Amino acid sequence string

    Returns:
        ValidationResult with validation status and any errors
    """
    errors = []

    # Check if sequence is a string first
    if not isinstance(sequence, str):
        errors.append("Amino acid sequence must be a string")
        return ValidationResult(is_valid=False, errors=errors)

    # Check if sequence is provided (empty string check)
    if not sequence:
        errors.append("Amino acid sequence cannot be empty")
        return ValidationResult(is_valid=False, errors=errors)

    # Remove whitespace and convert to uppercase
    cleaned_sequence = sequence.strip().upper()

    # Check minimum length (at least 1 amino acid)
    if len(cleaned_sequence) < 1:
        errors.append("Amino acid sequence must contain at least 1 amino acid")

    # Check maximum length (reasonable limit for processing)
    if len(cleaned_sequence) > 10000:
        errors.append("Amino acid sequence too long (maximum 10,000 characters)")

    # Validate amino acid characters (standard 20 amino acids)
    valid_amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    invalid_chars = set(cleaned_sequence) - valid_amino_acids

    if invalid_chars:
        invalid_chars_str = ", ".join(sorted(invalid_chars))
        errors.append(
            f"Invalid amino acid characters found: {invalid_chars_str}. "
            f"Only standard 20 amino acids are allowed: {', '.join(sorted(valid_amino_acids))}"
        )

    # Check for common formatting issues
    if any(char.isdigit() for char in cleaned_sequence):
        errors.append("Amino acid sequence should not contain numbers")

    if any(char in ".,;:!?()[]{}" for char in cleaned_sequence):
        errors.append("Amino acid sequence should not contain punctuation marks")

    is_valid = len(errors) == 0

    if is_valid:
        logger.info(
            f"Valid amino acid sequence provided (length: {len(cleaned_sequence)})"
        )
    else:
        logger.warning(f"Invalid amino acid sequence: {'; '.join(errors)}")

    return ValidationResult(is_valid=is_valid, errors=errors)


def validate_event_structure(
    event: Dict[str, Any], required_fields: List[str]
) -> ValidationResult:
    """
    Validate that the event contains all required fields.

    Args:
        event: Lambda event dictionary
        required_fields: List of required field names

    Returns:
        ValidationResult with validation status and any errors
    """
    errors = []

    if not isinstance(event, dict):
        errors.append("Event must be a dictionary")
        return ValidationResult(is_valid=False, errors=errors)

    for field in required_fields:
        if field not in event:
            errors.append(f"Missing required field: '{field}'")
        elif event[field] is None:
            errors.append(f"Required field '{field}' cannot be null")
        elif isinstance(event[field], str) and not event[field].strip():
            errors.append(f"Required field '{field}' cannot be empty")

    is_valid = len(errors) == 0

    if is_valid:
        logger.info(f"Event structure validation passed for fields: {required_fields}")
    else:
        logger.warning(f"Event structure validation failed: {'; '.join(errors)}")

    return ValidationResult(is_valid=is_valid, errors=errors)




def create_validation_error_response(
    validation_result: ValidationResult, error_code: str = "VALIDATION_ERROR"
) -> Dict[str, Any]:
    """
    Create a standardized error response for validation failures.

    Args:
        validation_result: ValidationResult containing errors
        error_code: Error code to include in response

    Returns:
        Dictionary containing error response
    """
    from datetime import datetime, timezone

    return {
        "success": False,
        "error_code": error_code,
        "message": "Input validation failed",
        "errors": validation_result.errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_cleaned_sequence(sequence: str) -> str:
    """
    Clean and normalize amino acid sequence.

    Args:
        sequence: Raw amino acid sequence

    Returns:
        Cleaned sequence (uppercase, no whitespace)
    """
    if not isinstance(sequence, str):
        return ""

    return sequence.strip().upper()


def get_arn_components(invocation_id: str) -> Dict[str, str]:
    """
    Extract components from a SageMaker invocation ID.

    Since SageMaker async inference returns just a UUID as InferenceId,
    we return the ID itself as the invocation_id component.

    Args:
        invocation_id: SageMaker invocation ID (UUID)

    Returns:
        Dictionary containing ID components
    """
    try:
        # Validate it's a proper UUID
        import uuid

        uuid_obj = uuid.UUID(invocation_id.strip())

        return {
            "invocation_id": str(uuid_obj),
            "uuid_version": uuid_obj.version,
            "is_valid_uuid": True,
        }
    except Exception:
        return {
            "invocation_id": (
                invocation_id.strip() if isinstance(invocation_id, str) else ""
            ),
            "is_valid_uuid": False,
        }
