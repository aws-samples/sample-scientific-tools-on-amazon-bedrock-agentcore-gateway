# SageMaker Async Inference Lambda Function

## Overview

This Lambda function provides a unified interface for interacting with SageMaker async inference endpoints, specifically designed for the AMPLIFY protein variant effect prediction model. The function supports two primary operations:

- **invoke_endpoint**: Submit protein sequences for async inference
- **get_results**: Retrieve prediction results from completed inference jobs

The function is designed to be compatible with AWS Bedrock Agent Core Gateway integration, using a tool-based routing system that parses the tool name from the Lambda context object.

## Architecture

The Lambda function integrates with the following AWS services:

- **SageMaker**: For async endpoint invocation
- **S3**: For input/output data storage and retrieval
- **CloudWatch**: For basic logging and metrics (simplified integration)

```
Client Request → Lambda Function → Tool Router → invoke_endpoint/get_results → AWS Services
```

## Function Structure

```
lambda_function/
├── lambda_function.py           # Main handler and routing logic
├── invoke_endpoint.py           # Endpoint invocation implementation
├── get_results.py               # Results retrieval implementation
├── validators.py                # Input validation utilities
├── cloudwatch_integration.py   # Simplified CloudWatch logging and metrics
└── requirements.txt             # Lambda dependencies
```

## Usage Examples

### Invoking the Endpoint

To submit a protein sequence for prediction:

```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Event payload
event = {
    "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
}

# Context with tool name (simulated for direct Lambda invocation)
# In actual Bedrock AgentCore usage, this would be set automatically
context_custom = {
    "bedrockagentcoreToolName": "invoke_endpoint"
}

response = lambda_client.invoke(
    FunctionName='your-lambda-function-name',
    Payload=json.dumps(event),
    ClientContext=json.dumps({"custom": context_custom})
)

result = json.loads(response['Payload'].read())
if result['success']:
    print(f"Output ID: {result['data']['output_id']}")
    print(f"S3 Output Path: {result['data']['s3_output_path']}")
else:
    print(f"Error: {result['message']}")
```

### Retrieving Results

To check for and retrieve prediction results:

```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Event payload with output_id from previous call
event = {
    "output_id": "abc123-def456"
}

# Context with tool name
context_custom = {
    "bedrockagentcoreToolName": "get_results"
}

response = lambda_client.invoke(
    FunctionName='your-lambda-function-name',
    Payload=json.dumps(event),
    ClientContext=json.dumps({"custom": context_custom})
)

result = json.loads(response['Payload'].read())
if result['success'] and result['data']['status'] == 'completed':
    print(f"Predictions: {result['data']['results']['predictions']}")
elif result['success'] and result['data']['status'] == 'in_progress':
    print("Prediction still in progress, check again later")
else:
    print(f"Error: {result['message']}")
```

## Event and Context Object Formats

### invoke_endpoint Tool

**Event Object:**

```json
{
  "sequence": "ACDEFGHIKLMNPQRSTVWY"
}
```

**Context Object (client_context.custom):**

```json
{
  "bedrockagentcoreToolName": "invoke_endpoint"
}
```

**Success Response:**

```json
{
  "success": true,
  "message": "Async inference request submitted successfully",
  "data": {
    "s3_output_path": "s3://bucket/async-inference-output/invocation-id.out",
    "output_id": "invocation-id",
    "sequence_length": 65,
    "estimated_completion_time": "2024-01-01T12:05:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Error Response:**

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Sequence contains invalid amino acid characters",
  "details": {
    "invalid_characters": ["X", "B"],
    "valid_characters": "ACDEFGHIKLMNPQRSTVWY"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### get_results Tool

**Event Object:**

```json
{
  "output_id": "invocation-id"
}
```

Note: The `output_id` can be either:

- A simple invocation ID (e.g., "abc123-def456")
- A full S3 output path (e.g., "s3://bucket/async-inference-output/abc123-def456.out")

**Context Object (client_context.custom):**

```json
{
  "bedrockagentcoreToolName": "get_results"
}
```

**Completed Response:**

```json
{
  "success": true,
  "message": "Results retrieved successfully",
  "data": {
    "status": "completed",
    "results": {
      "predictions": [
        {
          "position": 1,
          "original_aa": "M",
          "variant_aa": "L",
          "effect_score": 0.85,
          "confidence": 0.92
        }
      ],
      "metadata": {
        "model_version": "amplify-v1.0",
        "processing_time": "45.2s"
      }
    },
    "output_id": "invocation-id",
    "s3_output_path": "s3://bucket/async-inference-output/invocation-id.out",
    "completion_time": "2024-01-01T12:04:30Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**In Progress Response:**

```json
{
  "success": true,
  "message": "Prediction is still in progress",
  "data": {
    "status": "in_progress",
    "output_id": "invocation-id",
    "message": "Prediction is still in progress. Please check again later.",
    "expected_paths": {
      "success": "s3://bucket/async-inference-output/invocation-id.out",
      "failure": "s3://bucket/async-inference-failures/invocation-id.out"
    },
    "check_interval_seconds": 30
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Failed Response:**

```json
{
  "success": false,
  "error_code": "PREDICTION_FAILED",
  "message": "Async inference prediction failed",
  "details": {
    "status": "failed",
    "output_id": "invocation-id",
    "s3_failure_path": "s3://bucket/async-inference-failures/invocation-id.out",
    "failure_time": "2024-01-01T12:03:15Z",
    "error_details": {
      "error_message": "Model inference failed: Out of memory error during prediction",
      "error_type": "model_error"
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Sample Payloads

### Valid Protein Sequences

```python
# Short sequence
{
  "sequence": "MKTVRQERLK"
}

# Medium sequence (typical use case)
{
  "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
}

# Long sequence (near maximum)
{
  "sequence": "M" + "ACDEFGHIKLMNPQRSTVWY" * 499  # 9999 characters total
}
```

### Invalid Sequences (will return validation errors)

```python
# Empty sequence
{
  "sequence": ""
}

# Invalid characters
{
  "sequence": "MKTVRQERLKXBZ"  # X, B, Z are invalid
}

# Too long
{
  "sequence": "A" * 10001  # Exceeds 10000 character limit
}

# Non-string input
{
  "sequence": 12345
}
```

## Environment Variables

The Lambda function uses the following environment variables (automatically configured by CDK):

| Variable | Description | Example |
|----------|-------------|---------|
| `SAGEMAKER_ENDPOINT_NAME` | Name of the SageMaker async endpoint | `amplify-async-endpoint` |
| `S3_BUCKET_NAME` | S3 bucket for async inference data | `sagemaker-async-bucket-abc123` |
| `S3_INPUT_PREFIX` | S3 prefix for input data | `async-inference-input/` |
| `S3_OUTPUT_PREFIX` | S3 prefix for output data | `async-inference-output/` |
| `S3_FAILURE_PREFIX` | S3 prefix for failure logs | `async-inference-failures/` |
| `AWS_REGION` | AWS region for service calls | `us-east-1` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Error Codes

The function returns structured error codes for different failure scenarios:

| Error Code | Description | Common Causes |
|------------|-------------|---------------|
| `INVALID_EVENT_STRUCTURE` | Event validation failed | Missing required fields |
| `INVALID_SEQUENCE` | Sequence validation failed | Invalid amino acids, length issues |
| `CONFIGURATION_ERROR` | Environment configuration error | Missing environment variables |
| `CLIENT_INITIALIZATION_ERROR` | AWS client setup failed | Permission or network issues |
| `S3_UPLOAD_ERROR` | S3 upload failed | Permission issues, bucket not found |
| `SAGEMAKER_VALIDATION_ERROR` | SageMaker input validation failed | Invalid endpoint configuration |
| `SAGEMAKER_MODEL_ERROR` | Model execution error | Model runtime issues |
| `SAGEMAKER_INTERNAL_ERROR` | SageMaker service error | Internal service failures |
| `SAGEMAKER_SERVICE_UNAVAILABLE` | SageMaker temporarily unavailable | Service capacity or maintenance |
| `AWS_CONNECTION_ERROR` | AWS service connection failed | Network or credential issues |
| `INVOCATION_ERROR` | Unexpected invocation error | Various runtime issues |
| `RESULT_RETRIEVAL_ERROR` | Failed to retrieve results | S3 access or parsing issues |
| `PREDICTION_FAILED` | Async inference failed | Model prediction errors |
| `MISSING_TOOL_NAME` | Tool name not found | Context object format issues |
| `UNKNOWN_TOOL` | Invalid tool name | Unsupported tool requested |
| `HANDLER_ERROR` | Lambda handler error | Unexpected runtime errors |

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. "Unknown tool" Error

**Error Message:**

```json
{
  "success": false,
  "error_code": "UNKNOWN_TOOL",
  "message": "Unknown tool: invalid_tool_name. Supported tools are: invoke_endpoint, get_results"
}
```

**Cause:** The tool name in the context object is not recognized.

**Solution:**

- Ensure the context object contains `bedrockAgentCoreToolName` set to either `"invoke_endpoint"` or `"get_results"`
- Check that the context is properly formatted in the client_context.custom field
- Verify the tool name doesn't have extra prefixes (the function handles `___` delimiter automatically)

#### 2. Sequence Validation Errors

**Error Message:**

```json
{
  "success": false,
  "error_code": "INVALID_SEQUENCE",
  "message": "Sequence contains invalid amino acid characters",
  "details": {
    "errors": ["Invalid characters found: X, B, Z"],
    "valid_characters": "ACDEFGHIKLMNPQRSTVWY"
  }
}
```

**Cause:** The protein sequence contains characters other than the 20 standard amino acids.

**Solution:**

- Use only these characters: `ACDEFGHIKLMNPQRSTVWY`
- Remove any spaces, numbers, or special characters
- Ensure sequence length is between 1 and 10,000 characters

#### 3. SageMaker Endpoint Not Found

**Error Message:**

```json
{
  "success": false,
  "error_code": "SAGEMAKER_VALIDATION_ERROR",
  "message": "SageMaker validation error: Could not find endpoint \"endpoint-name\""
}
```

**Cause:** The SageMaker endpoint is not deployed or has a different name.

**Solution:**

- Verify the CDK stack has been deployed successfully
- Check that the `SAGEMAKER_ENDPOINT_NAME` environment variable is correct
- Ensure the endpoint is in the "InService" state

#### 4. S3 Access Denied

**Error Message:**

```json
{
  "success": false,
  "error_code": "S3_UPLOAD_ERROR",
  "message": "Failed to upload input data to S3: Access Denied"
}
```

**Cause:** Lambda execution role lacks S3 permissions.

**Solution:**

- Verify the Lambda execution role has the required S3 permissions
- Check that the S3 bucket exists and is in the same region
- Ensure bucket policies allow access from the Lambda execution role

#### 5. Results Not Available

**Response:**

```json
{
  "success": true,
  "message": "Prediction is still in progress",
  "data": {
    "status": "in_progress",
    "output_id": "invocation-id",
    "check_interval_seconds": 30
  }
}
```

**Cause:** The async inference job is still running.

**Solution:**

- Wait for the prediction to complete (typically 1-5 minutes)
- Check again using the same `output_id`
- If stuck for >10 minutes, check CloudWatch logs for errors

#### 6. Lambda Timeout

**Error:** Lambda function times out after 5 minutes.

**Cause:** Network issues or service unavailability.

**Solution:**

- Check AWS service status for SageMaker and S3
- Verify network connectivity from Lambda to AWS services
- Review CloudWatch logs for detailed error information

### Debugging Steps

1. **Check CloudWatch Logs:**

   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/your-function-name \
     --start-time $(date -d '1 hour ago' +%s)000
   ```

2. **Verify SageMaker Endpoint Status:**

   ```bash
   aws sagemaker describe-endpoint \
     --endpoint-name your-endpoint-name
   ```

3. **Check S3 Bucket Access:**

   ```bash
   aws s3 ls s3://your-bucket-name/async-inference-output/
   ```

4. **Test Lambda Function Directly:**

   ```bash
   # Test invoke_endpoint
   aws lambda invoke \
     --function-name your-function-name \
     --payload '{"sequence": "MKTVRQERLK"}' \
     --client-context '{"custom": {"bedrockAgentCoreToolName": "invoke_endpoint"}}' \
     response.json
   
   # Test get_results
   aws lambda invoke \
     --function-name your-function-name \
     --payload '{"output_id": "your-output-id"}' \
     --client-context '{"custom": {"bedrockAgentCoreToolName": "get_results"}}' \
     response.json
   ```

### Performance Considerations

- **Cold Start:** First invocation may take 2-3 seconds longer
- **Concurrent Executions:** Function supports up to 1000 concurrent executions by default
- **Memory Usage:** Function uses ~128MB memory, configured with 256MB for safety margin
- **Timeout:** 5-minute timeout allows for AWS service call completion
- **CloudWatch Integration:** Simplified metrics reduce overhead and improve performance

### Security Considerations

- Function follows least-privilege IAM permissions
- All inputs are validated before processing
- Sensitive data is not logged to CloudWatch
- S3 access is restricted to specific prefixes only
- CloudWatch metrics contain only non-sensitive operational data

### Monitoring and Observability

The function includes simplified CloudWatch integration that provides:

- **Basic Metrics:** Success/failure counts, duration, sequence length
- **Structured Logging:** JSON-formatted logs for easy parsing
- **Error Tracking:** Categorized error metrics for monitoring
- **Performance Metrics:** Invocation duration and result sizes

Key metrics available in CloudWatch:

- `InvocationSuccess` / `InvocationError`
- `Duration` (milliseconds)
- `ValidationError`, `ConfigurationError`, `SageMakerError`
- `SequenceLength`, `ResultsSize`

## Integration with Bedrock Agent Core

This Lambda function is designed for future integration with AWS Bedrock Agent Core Gateway. The tool-based interface structure supports:

- **Tool Schema Definition:** Function signature matches expected tool schema format
- **Context Parsing:** Handles `bedrockagentcoreToolName` from context object
- **Response Format:** Returns JSON responses compatible with gateway expectations
- **Error Handling:** Provides structured error responses for gateway consumption

For Bedrock Agent Core integration, the function will be registered as a target with appropriate tool schemas defining the input/output formats for each tool.

## Support and Maintenance

For issues or questions:

1. Check this documentation and troubleshooting guide
2. Review CloudWatch logs for detailed error information
3. Verify AWS service status and quotas
4. Test with minimal examples to isolate issues

## Version History

- **v1.0.0:** Initial implementation with invoke_endpoint and get_results tools
- **v1.0.1:** Added comprehensive error handling and validation
- **v1.0.2:** Enhanced logging and monitoring capabilities
- **v1.1.0:** Simplified CloudWatch integration, improved performance and maintainability
  - Replaced complex monitoring with basic metrics and structured logging
  - Eliminated code duplication across modules
  - Improved cold start performance
  - Standardized response formats
