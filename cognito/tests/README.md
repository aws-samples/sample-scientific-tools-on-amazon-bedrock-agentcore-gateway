# Cognito Stack Tests

This directory contains comprehensive tests for the AWS Cognito CDK stack implementation.

## Test Structure

```
cognito/tests/
├── conftest.py              # Shared fixtures and test configuration
├── pytest.ini              # pytest configuration
├── README.md               # This file
└── unit/                   # Unit tests
    ├── __init__.py
    ├── test_config_validation.py    # Configuration validation tests
    ├── test_cognito_config.py       # Configuration class tests
    └── test_stack_basic.py          # CDK stack synthesis tests
```

## Running Tests

### All Cognito Tests

```bash
# Run all Cognito tests
uv run pytest cognito/tests/ -v

# Run with coverage
uv run pytest cognito/tests/ --cov=cognito --cov-report=html --cov-report=term-missing
```

### Specific Test Categories

```bash
# Run only unit tests
uv run pytest cognito/tests/unit/ -v

# Run configuration validation tests
uv run pytest cognito/tests/unit/test_config_validation.py -v

# Run stack synthesis tests
uv run pytest cognito/tests/unit/test_stack_basic.py -v

# Run configuration class tests
uv run pytest cognito/tests/unit/test_cognito_config.py -v
```

### Specific Test Methods

```bash
# Run a specific test class
uv run pytest cognito/tests/unit/test_stack_basic.py::TestCognitoStackBasics -v

# Run a specific test method
uv run pytest cognito/tests/unit/test_config_validation.py::TestCognitoConfigValidation::test_default_config_is_valid -v
```

## Test Categories

### Configuration Validation Tests (`test_config_validation.py`)

Tests the validation logic in `CognitoConfig`, `CognitoOutputConfig`, and `CognitoResourceScope` classes:

- **Parameter validation**: User pool names, resource server identifiers, client names
- **Scope validation**: Scope names, descriptions, uniqueness
- **Password policy validation**: Length requirements, character requirements
- **Domain prefix validation**: Format and length constraints
- **SSM parameter validation**: Parameter name formats
- **Secret name validation**: Secrets Manager naming requirements

### Configuration Class Tests (`test_cognito_config.py`)

Tests the configuration classes themselves:

- **Default values**: Verify default configuration values are correct
- **Custom configuration**: Test setting custom values
- **Validation integration**: Ensure validation is called appropriately
- **Object behavior**: String representation, equality, immutability

### Stack Synthesis Tests (`test_stack_basic.py`)

Tests CDK stack synthesis and resource creation:

- **Stack synthesis**: Verify stack synthesizes without errors
- **Resource creation**: Verify all required AWS resources are created
- **Resource configuration**: Verify resources have correct properties
- **Dependencies**: Verify resource dependencies are correct
- **Outputs**: Verify CloudFormation outputs are created
- **Different configurations**: Test various configuration combinations

## Test Fixtures

The `conftest.py` file provides shared fixtures:

- **`app`**: CDK App instance for testing
- **`default_config`**: Default CognitoConfig for standard tests
- **`test_config`**: Custom CognitoConfig for specific test scenarios
- **`minimal_config`**: Minimal CognitoConfig for edge case testing
- **`custom_output_config`**: Custom CognitoOutputConfig for output testing
- **Stack fixtures**: Pre-configured stacks with different configurations
- **Template fixtures**: CloudFormation templates from synthesized stacks

## Test Data

Tests use realistic but safe test data:

- **User pool names**: `test-user-pool`, `minimal-pool`
- **Resource server identifiers**: `test-resource-server`, `minimal-server`
- **Client names**: `test-client`, `minimal-client`
- **Scopes**: `read`, `write`, `admin` with descriptive descriptions
- **Parameter names**: `/test/cognito/*` prefixes for testing
- **Secret names**: `test-cognito-client-secret`

## Coverage Goals

- **Minimum 80% code coverage** for all Cognito stack components
- **100% coverage** for configuration validation logic
- **Edge case testing** for all validation scenarios
- **Error path testing** for all failure modes

## Common Test Patterns

### Configuration Validation Pattern

```python
def test_parameter_validation(self):
    # Valid values should not raise
    config = CognitoConfig(parameter="valid-value")
    config.validate()  # Should not raise
    
    # Invalid values should raise with specific message
    with pytest.raises(ValueError, match="specific error message"):
        config = CognitoConfig(parameter="invalid-value")
        config.validate()
```

### Stack Resource Testing Pattern

```python
def test_resource_creation(self, template_from_default_stack):
    template = template_from_default_stack
    
    # Check resource count
    template.resource_count_is("AWS::Cognito::UserPool", 1)
    
    # Check resource properties
    template.has_resource_properties("AWS::Cognito::UserPool", {
        "UserPoolName": "expected-name"
    })
```

### Multiple Configuration Testing Pattern

```python
def test_different_configurations_work(self):
    configs = [config1, config2, config3]
    
    for i, config in enumerate(configs):
        app = cdk.App()
        stack = CognitoStack(app, f"TestStack{i}", config=config)
        template = Template.from_stack(stack)
        
        # Verify each configuration works
        assert template is not None
```

## Debugging Test Failures

### CDK Synthesis Issues

```bash
# Synthesize template to inspect CloudFormation
uv run cdk synth CognitoStack > debug-cognito-template.yaml

# Run specific failing test with detailed output
uv run pytest cognito/tests/unit/test_stack_basic.py::TestCognitoStackBasics::test_required_resources_are_created -v -s --tb=long
```

### Configuration Validation Issues

```bash
# Run validation tests with detailed output
uv run pytest cognito/tests/unit/test_config_validation.py -v -s --tb=long

# Test specific validation scenario
uv run pytest cognito/tests/unit/test_config_validation.py -k "password_policy" -v -s
```

## Integration with Project Testing

These tests integrate with the overall project testing strategy:

- Follow the same patterns as `vep_endpoint/tests/`
- Use consistent fixture naming and structure
- Maintain the same coverage standards
- Support the same pytest execution patterns

Run all project tests including Cognito:

```bash
# Run all tests across the entire project
uv run pytest vep_endpoint/ cognito/tests/ -v

# Run with comprehensive coverage
uv run pytest vep_endpoint/ cognito/tests/ --cov=vep_endpoint --cov=cognito --cov-report=html
```