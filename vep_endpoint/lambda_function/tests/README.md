# Lambda Function Unit Tests

This directory contains comprehensive unit tests for the AWS Lambda function modules used in the SageMaker Async Inference endpoint.

## Test Structure

- `test_lambda_function.py` - Tests for the main Lambda handler and routing logic
- `test_invoke_endpoint.py` - Tests for SageMaker endpoint invocation functionality
- `test_get_results.py` - Tests for S3 results retrieval functionality
- `test_validators.py` - Tests for input validation utilities
- `test_cloudwatch_integration.py` - Tests for CloudWatch logging and metrics
- `conftest.py` - Shared pytest fixtures and configuration
- `requirements-test.txt` - Test dependencies

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# From the lambda_function directory
pytest test/ -v

# Or from the test directory
cd test
pytest -v
```

### Run Specific Test Files

```bash
pytest test/test_validators.py -v
pytest test/test_lambda_function.py -v
```

### Run with Coverage

```bash
pytest test/ --cov=. --cov-report=html --cov-report=term-missing
```

This will generate an HTML coverage report in `htmlcov/` directory.

### Run Specific Test Classes or Methods

```bash
# Run specific test class
pytest test/test_validators.py::TestValidateAminoAcidSequence -v

# Run specific test method
pytest test/test_validators.py::TestValidateAminoAcidSequence::test_valid_sequence -v
```

## Test Categories

### Unit Tests

- **Validation Tests**: Test input validation for amino acid sequences and event structures
- **Handler Tests**: Test main Lambda handler routing and error handling
- **Endpoint Tests**: Test SageMaker endpoint invocation with various scenarios
- **Results Tests**: Test S3 results retrieval for different prediction states
- **CloudWatch Tests**: Test logging and metrics functionality

### Mock Usage

Tests use `moto` library to mock AWS services:

- **S3**: Mock bucket operations and object storage
- **SageMaker**: Mock endpoint invocations and responses
- **CloudWatch**: Mock metrics and logging

### Test Fixtures

Common fixtures in `conftest.py`:

- `mock_lambda_context`: Mock Lambda context object
- `valid_amino_acid_sequence`: Valid test sequence
- `mock_environment_variables`: Mock environment configuration
- `mock_s3_setup`: Mock S3 environment with test bucket

## Test Coverage Goals

- **Minimum 80% code coverage** across all modules
- **100% coverage** for critical validation logic
- **Error path testing** for all AWS service interactions
- **Edge case testing** for input validation

## Common Test Patterns

### Testing AWS Service Errors

```python
@patch('module.boto3.client')
def test_aws_service_error(self, mock_boto_client):
    mock_client = Mock()
    mock_client.operation.side_effect = ClientError(
        {"Error": {"Code": "ServiceError", "Message": "Service failed"}},
        "Operation"
    )
    mock_boto_client.return_value = mock_client
    
    result = function_under_test()
    
    assert result["success"] is False
    assert result["error_code"] == "EXPECTED_ERROR_CODE"
```

### Testing Validation Logic

```python
def test_validation_success(self):
    result = validate_function("valid_input")
    assert result.is_valid is True
    assert len(result.errors) == 0

def test_validation_failure(self):
    result = validate_function("invalid_input")
    assert result.is_valid is False
    assert "expected error message" in result.errors[0]
```

### Testing Response Formats

```python
def test_success_response_format(self):
    response = function_under_test()
    
    assert response["success"] is True
    assert "data" in response
    assert "timestamp" in response
    assert isinstance(response["timestamp"], str)
```

## Debugging Tests

### Verbose Output

```bash
pytest test/ -v -s
```

### Stop on First Failure

```bash
pytest test/ -x
```

### Run Only Failed Tests

```bash
pytest test/ --lf
```

### Debug with PDB

```bash
pytest test/ --pdb
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines with:

- Fast execution (< 30 seconds for full suite)
- No external dependencies (all AWS services mocked)
- Clear failure reporting
- Coverage reporting integration

## Adding New Tests

When adding new functionality:

1. **Create test file** following naming convention `test_<module_name>.py`
2. **Add test class** for each major function or class
3. **Test success paths** with valid inputs
4. **Test error paths** with invalid inputs and service failures
5. **Add fixtures** to `conftest.py` for reusable test data
6. **Update coverage goals** if adding new modules

## Best Practices

- **One assertion per test** when possible
- **Descriptive test names** that explain what is being tested
- **Mock external dependencies** to ensure test isolation
- **Test edge cases** and boundary conditions
- **Use fixtures** for common test setup
- **Clean up resources** in test teardown when needed
