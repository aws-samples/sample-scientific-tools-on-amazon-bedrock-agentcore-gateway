"""
Unit tests for validators module.
"""

import pytest
from validators import (
    validate_amino_acid_sequence,
    validate_event_structure,
    create_validation_error_response,
    get_cleaned_sequence,
    get_arn_components,
    ValidationResult
)


class TestValidateAminoAcidSequence:
    """Test amino acid sequence validation."""

    def test_valid_sequence(self):
        """Test validation of valid amino acid sequence."""
        sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_valid_sequence_with_whitespace(self):
        """Test validation handles whitespace correctly."""
        sequence = "  MKTVRQERLK  "
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_valid_sequence_lowercase(self):
        """Test validation handles lowercase correctly."""
        sequence = "mktvrqerlk"
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_empty_sequence(self):
        """Test validation of empty sequence."""
        result = validate_amino_acid_sequence("")
        
        assert result.is_valid is False
        assert "cannot be empty" in result.errors[0]

    def test_none_sequence(self):
        """Test validation of None sequence."""
        result = validate_amino_acid_sequence(None)
        
        assert result.is_valid is False
        assert "must be a string" in result.errors[0]

    def test_non_string_sequence(self):
        """Test validation of non-string sequence."""
        result = validate_amino_acid_sequence(123)
        
        assert result.is_valid is False
        assert "must be a string" in result.errors[0]

    def test_sequence_with_invalid_characters(self):
        """Test validation of sequence with invalid characters."""
        sequence = "MKTVRQERLKXZ"  # X and Z are not standard amino acids
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is False
        assert "Invalid amino acid characters" in result.errors[0]
        assert "X" in result.errors[0]
        assert "Z" in result.errors[0]

    def test_sequence_with_numbers(self):
        """Test validation of sequence with numbers."""
        sequence = "MKTVRQERLK123"
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is False
        assert any("should not contain numbers" in error for error in result.errors)

    def test_sequence_with_punctuation(self):
        """Test validation of sequence with punctuation."""
        sequence = "MKTVRQERLK.,"
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is False
        assert any("should not contain punctuation" in error for error in result.errors)

    def test_sequence_too_long(self):
        """Test validation of sequence that's too long."""
        sequence = "A" * 10001  # Exceeds 10,000 character limit
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is False
        assert any("too long" in error for error in result.errors)

    def test_whitespace_only_sequence(self):
        """Test validation of whitespace-only sequence."""
        sequence = "   "
        result = validate_amino_acid_sequence(sequence)
        
        assert result.is_valid is False
        assert any("must contain at least 1 amino acid" in error for error in result.errors)


class TestValidateEventStructure:
    """Test event structure validation."""

    def test_valid_event_structure(self):
        """Test validation of valid event structure."""
        event = {"sequence": "MKTVRQERLK", "tool_name": "invoke_endpoint"}
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_required_field(self):
        """Test validation when required field is missing."""
        event = {"tool_name": "invoke_endpoint"}
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert "Missing required field: 'sequence'" in result.errors

    def test_null_required_field(self):
        """Test validation when required field is null."""
        event = {"sequence": None}
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert "cannot be null" in result.errors[0]

    def test_empty_string_required_field(self):
        """Test validation when required field is empty string."""
        event = {"sequence": ""}
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert "cannot be empty" in result.errors[0]

    def test_whitespace_only_required_field(self):
        """Test validation when required field is whitespace only."""
        event = {"sequence": "   "}
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert "cannot be empty" in result.errors[0]

    def test_non_dict_event(self):
        """Test validation when event is not a dictionary."""
        event = "not a dict"
        required_fields = ["sequence"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert "must be a dictionary" in result.errors[0]

    def test_multiple_missing_fields(self):
        """Test validation when multiple required fields are missing."""
        event = {}
        required_fields = ["sequence", "output_id"]
        
        result = validate_event_structure(event, required_fields)
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert any("sequence" in error for error in result.errors)
        assert any("output_id" in error for error in result.errors)


class TestCreateValidationErrorResponse:
    """Test validation error response creation."""

    def test_create_validation_error_response(self):
        """Test creation of validation error response."""
        validation_result = ValidationResult(
            is_valid=False,
            errors=["Test error 1", "Test error 2"]
        )
        
        response = create_validation_error_response(validation_result)
        
        assert response["success"] is False
        assert response["error_code"] == "VALIDATION_ERROR"
        assert response["message"] == "Input validation failed"
        assert response["errors"] == ["Test error 1", "Test error 2"]
        assert "timestamp" in response

    def test_create_validation_error_response_custom_code(self):
        """Test creation of validation error response with custom error code."""
        validation_result = ValidationResult(
            is_valid=False,
            errors=["Custom error"]
        )
        
        response = create_validation_error_response(validation_result, "CUSTOM_ERROR")
        
        assert response["error_code"] == "CUSTOM_ERROR"
        assert response["errors"] == ["Custom error"]


class TestGetCleanedSequence:
    """Test sequence cleaning functionality."""

    def test_clean_valid_sequence(self):
        """Test cleaning of valid sequence."""
        sequence = "  mktvrqerlk  "
        cleaned = get_cleaned_sequence(sequence)
        
        assert cleaned == "MKTVRQERLK"

    def test_clean_empty_sequence(self):
        """Test cleaning of empty sequence."""
        cleaned = get_cleaned_sequence("")
        
        assert cleaned == ""

    def test_clean_none_sequence(self):
        """Test cleaning of None sequence."""
        cleaned = get_cleaned_sequence(None)
        
        assert cleaned == ""

    def test_clean_non_string_sequence(self):
        """Test cleaning of non-string sequence."""
        cleaned = get_cleaned_sequence(123)
        
        assert cleaned == ""

    def test_clean_sequence_with_mixed_case(self):
        """Test cleaning of sequence with mixed case."""
        sequence = "MkTvRqErLk"
        cleaned = get_cleaned_sequence(sequence)
        
        assert cleaned == "MKTVRQERLK"


class TestGetArnComponents:
    """Test ARN component extraction."""

    def test_valid_uuid(self):
        """Test extraction from valid UUID."""
        uuid_str = "123e4567-e89b-12d3-a456-426614174000"
        components = get_arn_components(uuid_str)
        
        assert components["is_valid_uuid"] is True
        assert components["invocation_id"] == uuid_str
        assert "uuid_version" in components

    def test_invalid_uuid(self):
        """Test extraction from invalid UUID."""
        invalid_uuid = "not-a-uuid"
        components = get_arn_components(invalid_uuid)
        
        assert components["is_valid_uuid"] is False
        assert components["invocation_id"] == invalid_uuid

    def test_uuid_with_whitespace(self):
        """Test extraction from UUID with whitespace."""
        uuid_str = "  123e4567-e89b-12d3-a456-426614174000  "
        components = get_arn_components(uuid_str)
        
        assert components["is_valid_uuid"] is True
        assert components["invocation_id"] == uuid_str.strip()

    def test_empty_string(self):
        """Test extraction from empty string."""
        components = get_arn_components("")
        
        assert components["is_valid_uuid"] is False
        assert components["invocation_id"] == ""

    def test_none_input(self):
        """Test extraction from None input."""
        components = get_arn_components(None)
        
        assert components["is_valid_uuid"] is False
        assert components["invocation_id"] == ""