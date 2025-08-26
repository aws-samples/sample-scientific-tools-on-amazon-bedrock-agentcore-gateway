# VEP Endpoint Tests

This directory contains comprehensive tests for the VEP (Variant Effect Prediction) endpoint CDK stack.

## Quick Start

```bash
# Run all unit tests
uv run pytest vep_endpoint/tests/unit/ -v

# Run quietly  
uv run pytest vep_endpoint/tests/unit/ -q

# Run with coverage
uv run pytest vep_endpoint/tests/unit/ --cov=vep_endpoint --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py                    # Shared test fixtures and configuration
└── unit/                          # Unit tests (fast, no AWS resources)
    ├── test_config_validation.py  # Configuration validation tests
    └── test_stack_basic.py        # Basic stack synthesis and resource tests

```

## Running Tests

### Prerequisites: Python Environment

Ensure you have Python 3.13+ with required dependencies:

   ```bash
   uv sync
   ```

### Unit Tests

Unit tests are fast and don't require AWS resources. They test configuration validation, CDK synthesis, and resource definitions.

```bash
# Run all unit tests
uv run pytest vep_endpoint/tests/unit/ -v

# Run configuration validation tests only
uv run pytest vep_endpoint/tests/unit/test_config_validation.py -v

# Run stack synthesis tests only
uv run pytest vep_endpoint/tests/unit/test_stack_basic.py -v

# Run with coverage
uv run pytest vep_endpoint/tests/unit/ --cov=vep_endpoint --cov-report=html

# Quick run (quiet output)
uv run pytest vep_endpoint/tests/unit/ -q
```

### Test Categories

Tests are marked with pytest markers:

- `@pytest.mark.integration`: Tests that deploy real AWS resources
- `@pytest.mark.slow`: Tests that take a long time to run

## Test Coverage

### Unit Tests Cover

1. **Configuration Validation** (`test_config_validation.py`):
   - VEPEndpointConfig parameter validation
   - Instance type validation
   - Capacity settings validation
   - S3 bucket name validation
   - Model ID validation
   - Removal policy configuration

2. **Stack Basics** (`test_stack_basic.py`):
   - CDK stack synthesis without errors
   - Required AWS resources creation
   - SageMaker model, endpoint config, and endpoint
   - S3 bucket security configuration
   - Lambda function configuration
   - IAM roles and policies
   - Resource tagging
   - Auto scaling resource creation
   - Stack outputs and parameters
   - Different configuration scenarios

## Test Data and Fixtures

### Shared Fixtures (`conftest.py`)

- `app`: CDK App instance
- `default_config`: Default VEPEndpointConfig
- `test_config`: Test-specific configuration
- `minimal_config`: Minimal configuration
- Various stack and template fixtures

## Best Practices

### Writing Tests

1. **Use descriptive test names** that clearly indicate what is being tested
2. **Test one concept per test method** to make failures easy to diagnose
3. **Use appropriate fixtures** to avoid code duplication
4. **Mock external dependencies** in unit tests
5. **Clean up resources** in integration tests

### Test Organization

1. **Unit tests** should be fast and test individual components
2. **Integration tests** should test end-to-end functionality
3. **Use markers** to categorize tests appropriately
4. **Group related tests** in classes for better organization

### Error Handling

1. **Test both success and failure cases**
2. **Verify error messages** are meaningful
3. **Test edge cases** and boundary conditions
4. **Ensure graceful degradation** where appropriate

## Contributing

When adding new tests:

1. **Follow the existing patterns** and naming conventions
2. **Add appropriate markers** (`@pytest.mark.integration`, etc.)
3. **Update this README** if adding new test categories
4. **Ensure tests are deterministic** and don't depend on external state
5. **Add cleanup procedures** for any resources created in integration tests
