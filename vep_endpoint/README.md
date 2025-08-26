# VEP Endpoint Stack - SageMaker Async Inference for Protein Variant Effect Prediction

This CDK stack provides Infrastructure as Code for deploying SageMaker asynchronous inference endpoints specifically designed for the AMPLIFY protein variant effect prediction model. The stack includes comprehensive resource management, autoscaling, monitoring, and Lambda integration for seamless protein engineering workflows.

## Overview

The VEP (Variant Effect Prediction) Endpoint Stack creates:

- **SageMaker Async Inference Endpoint** with AMPLIFY model for protein variant prediction
- **Lambda Function** with dual tools (`invoke_endpoint` and `get_results`) for MCP integration
- **S3 Bucket** for input/output data with proper security and lifecycle policies
- **Auto Scaling Configuration** with scale-to-zero capability for cost optimization
- **IAM Roles and Policies** following least-privilege security principles
- **CloudWatch Monitoring** with custom metrics and alarms
- **SSM Parameter Store** integration for service discovery

## Architecture

```
Client Request → Lambda Function → SageMaker Async Endpoint → S3 Results
                      ↓
                 Tool Router (invoke_endpoint/get_results)
                      ↓
                 AWS Services (SageMaker, S3, CloudWatch)
```

## Configuration and Parameters

### Stack Parameters

The stack accepts the following parameters that can be configured at deployment time:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `InstanceType` | String | `ml.g6.2xlarge` | EC2 instance type for SageMaker endpoint |
| `ModelId` | String | `chandar-lab/AMPLIFY_350M` | HuggingFace model identifier |
| `S3BucketNameParam` | String | `""` | Optional S3 bucket name (creates default if empty) |
| `MinCapacity` | Number | `1` | Minimum number of instances for auto scaling |
| `MaxCapacity` | Number | `2` | Maximum number of instances for auto scaling |
| `MaxConcurrentInvocations` | Number | `4` | Maximum concurrent invocations per instance |

### Configuration Methods

#### 1. Default Configuration

Deploy with all default settings:

```python
import aws_cdk as cdk
from vep_endpoint.vep_endpoint_stack import VEPEndpointStack

app = cdk.App()
VEPEndpointStack(app, "VEPEndpointStack")
app.synth()
```

#### 2. Custom Configuration Object

Use a configuration object for programmatic control:

```python
from vep_endpoint.vep_endpoint_stack import VEPEndpointConfig, VEPEndpointStack

custom_config = VEPEndpointConfig(
    instance_type="ml.g6.4xlarge",
    model_id="chandar-lab/AMPLIFY_350M",
    s3_bucket_name="my-protein-analysis-bucket",
    min_capacity=1,
    max_capacity=5,
    max_concurrent_invocations=8,
    enable_autoscaling=True
)

app = cdk.App()
VEPEndpointStack(app, "VEPEndpointStackCustom", config=custom_config)
app.synth()
```

#### 3. Parameter Overrides at Deployment

Override parameters at deployment time:

```bash
uv run cdk deploy --parameters InstanceType=ml.g6.8xlarge --parameters MaxCapacity=8
```

#### 4. Context-Based Configuration

Use CDK context for environment-specific deployments:

```bash
uv run cdk deploy --context project_name=my-protein-project
```

### Resource Naming Convention

All resources follow a consistent naming pattern:

- **Resource Prefix**: `{project_name}-{timestamp}`
- **S3 Bucket**: Auto-generated with CDK naming for uniqueness
- **Model**: `amplify-vep-model`
- **Endpoint Config**: `amplify-vep-config`
- **Endpoint**: `amplify-vep-endpoint`
- **Lambda Function**: `{resource_prefix}-async-endpoint-lambda`

## Deployment

### Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.9+ with uv package manager
- Node.js 18+ and npm for CDK CLI
- AWS CDK CLI: `npm install -g aws-cdk`

### Basic Deployment

```bash
# Install dependencies
uv sync

# Bootstrap CDK (first time only)
uv run cdk bootstrap

# Deploy the stack
uv run cdk deploy VEPEndpointStack

# View stack outputs
uv run cdk deploy VEPEndpointStack --outputs-file outputs.json
```

### Development Deployment

```bash
# Deploy with development settings
uv run cdk deploy VEPEndpointStack \
  --parameters MinCapacity=0 \
  --parameters MaxCapacity=1 \
  --context project_name=dev-protein-agent
```

### Production Deployment

```bash
# Deploy with production settings
uv run cdk deploy VEPEndpointStack \
  --parameters InstanceType=ml.g6.4xlarge \
  --parameters MinCapacity=1 \
  --parameters MaxCapacity=10 \
  --context project_name=prod-protein-agent
```

## Usage Examples

The stack includes comprehensive examples for different use cases and integration patterns.

### 1. Lambda Function Integration

The deployed Lambda function provides two tools for protein variant analysis:

#### Finding Your Lambda Function

```bash
# List Lambda functions related to protein analysis
aws lambda list-functions --query 'Functions[?contains(FunctionName, `async-endpoint`)].FunctionName' --output table

# Get function details
aws lambda get-function --function-name your-function-name
```

#### Tool 1: invoke_endpoint

Submit protein sequences for async inference:

```python
# Example event payload
{
    "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
}
```

#### Tool 2: get_results

Retrieve prediction results from completed inference jobs:

```python
# Example event payload
{
    "output_id": "your-output-id-from-invoke-response"
}
```

### 2. Direct Lambda Invocation Example

Use the provided example script to test the Lambda function:

```bash
# Basic usage with default sequence
uv run vep_endpoint/examples/invoke_lambda.py your-lambda-function-name

# Custom sequence with different polling settings
uv run vep_endpoint/examples/invoke_lambda.py your-lambda-function-name \
  --sequence "MKTVRQERLK" \
  --max-attempts 30 \
  --poll-interval 10

# Show help and options
uv run vep_endpoint/examples/invoke_lambda.py --help
```

**Example Output:**

```
🧬 SageMaker Async Inference Lambda Function Demo
🔧 Using Lambda function: protein-agent-1756142024-async-endpoint-lambda
✅ Lambda function found and accessible

============================================================
 STEP 1: INVOKING SAGEMAKER ENDPOINT
============================================================
🔬 Protein sequence: MKTVRQERLK
📏 Sequence length: 10 amino acids

🚀 Invoking SageMaker async endpoint...
✅ Success! Async inference request submitted
🆔 Output ID: 062d5aeb-9be7-4938-ad1f-3419e162b34a

============================================================
 🎉 RESULTS READY!
============================================================
✅ Prediction completed successfully!
📊 Results summary:
   🔥 Heatmap dimensions: 20 x 10
   📈 Number of outliers detected: 4

   🔝 Top beneficial mutations:
      1. Lys9Ala 2.100179672241211
      2. Lys9Leu 1.8011579513549805

   ⚠️  Most harmful mutations:
      1. Met0Cys -5.280786454677582
      2. Met0His -5.1352404952049255
```

### 3. Direct SageMaker Endpoint Usage

Use the SageMaker client example for direct endpoint interaction:

```bash
# Run the SageMaker endpoint example
uv run vep_endpoint/examples/invoke_endpoint.py \
  --endpoint-name amplify-vep-endpoint \
  --bucket-name your-s3-bucket-name \
  --sequence "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
```

### 4. MCP (Model Context Protocol) Integration

The Lambda function is designed for MCP integration with proper tool routing:

```json
{
  "mcpServers": {
    "protein-engineering": {
      "command": "your-mcp-server-command",
      "args": ["--lambda-function", "your-lambda-function-name"],
      "env": {
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

## Monitoring and Observability

### CloudWatch Metrics

The stack automatically creates CloudWatch alarms and metrics for:

- **HasBacklogWithoutCapacity**: Triggers auto-scaling when requests are queued
- **InvocationsPerInstance**: Monitors endpoint utilization
- **ModelLatency**: Tracks inference performance
- **Lambda Duration**: Monitors Lambda function performance
- **Lambda Errors**: Tracks Lambda function failures

### Auto Scaling

The endpoint automatically scales based on:

- **Scale Up**: When `HasBacklogWithoutCapacity >= 1` for 2 consecutive minutes
- **Scale Down**: When `HasBacklogWithoutCapacity < 1` for 5 consecutive minutes
- **Cooldown Periods**: 5 minutes for scale up, 10 minutes for scale down

### Logging

Comprehensive logging is available in CloudWatch:

- **SageMaker Endpoint Logs**: `/aws/sagemaker/Endpoints/amplify-vep-endpoint`
- **Lambda Function Logs**: `/aws/lambda/your-lambda-function-name`
- **Auto Scaling Events**: Application Auto Scaling service logs

## Cost Optimization

### Scale-to-Zero Configuration

For development environments, configure scale-to-zero:

```python
config = VEPEndpointConfig(
    min_capacity=0,  # Scale to zero when idle
    max_capacity=2,
    enable_autoscaling=True
)
```

### S3 Lifecycle Policies

The S3 bucket includes lifecycle policies for cost optimization:

- **Input files**: Deleted after 7 days
- **Output files**: Transitioned to IA after 30 days, archived after 90 days
- **Failure files**: Retained for debugging, deleted after 30 days

### Instance Type Recommendations

| Use Case | Instance Type | Cost | Performance |
|----------|---------------|------|-------------|
| Development | `ml.g6.2xlarge` | Low | Good |
| Production | `ml.g6.4xlarge` | Medium | Better |
| High Throughput | `ml.g6.8xlarge` | High | Best |

## Security

### IAM Policies

The stack implements least-privilege access:

- **SageMaker Execution Role**: Access only to required S3 prefixes and ECR repositories
- **Lambda Execution Role**: Access only to specific SageMaker endpoint and S3 paths
- **Auto Scaling Role**: Service-linked role with minimal permissions

### S3 Security

- **Encryption**: Server-side encryption (SSE-S3) enabled by default
- **Public Access**: Blocked at bucket level
- **Access Logging**: Enabled for audit trails
- **Versioning**: Disabled to prevent accidental retention

### Network Security

- **VPC**: Optional VPC configuration for enhanced isolation
- **Security Groups**: Restrictive rules for SageMaker endpoint access
- **IAM Conditions**: Resource-based access controls

## Troubleshooting

### Common Issues

#### Lambda Function Not Found

```bash
# Check if function exists
aws lambda list-functions --query 'Functions[?contains(FunctionName, `async-endpoint`)].FunctionName'

# Verify deployment outputs
uv run cdk deploy VEPEndpointStack --outputs-file outputs.json
cat outputs.json | jq '.VEPEndpointStack.LambdaFunctionName'
```

#### SageMaker Endpoint Issues

```bash
# Check endpoint status
aws sagemaker describe-endpoint --endpoint-name amplify-vep-endpoint

# Review endpoint logs
aws logs filter-log-events --log-group-name /aws/sagemaker/Endpoints/amplify-vep-endpoint

# Check auto scaling status
aws application-autoscaling describe-scalable-targets --service-namespace sagemaker
```

#### S3 Access Issues

```bash
# Verify bucket permissions
aws s3 ls s3://your-bucket-name/

# Check IAM role permissions
aws iam simulate-principal-policy \
  --policy-source-arn your-role-arn \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::your-bucket-name/async-inference-output/*
```

### Performance Tuning

#### Endpoint Configuration

- **Concurrent Invocations**: Increase `MaxConcurrentInvocations` for higher throughput
- **Instance Type**: Use larger instances for complex protein sequences
- **Auto Scaling**: Adjust thresholds based on usage patterns

#### Lambda Optimization

- **Memory**: Increase Lambda memory for faster JSON processing
- **Timeout**: Adjust timeout based on expected inference duration
- **Environment Variables**: Optimize for your specific use case

## Stack Outputs

After deployment, the stack provides comprehensive outputs for integration:

### Key Outputs

- **LambdaFunctionName**: Name of the deployed Lambda function
- **LambdaFunctionArn**: ARN for direct Lambda invocation
- **EndpointName**: SageMaker endpoint name
- **S3BucketName**: S3 bucket for input/output data
- **ExecutionRoleArn**: IAM role ARN for the SageMaker endpoint

### Accessing Outputs

```bash
# View all outputs
uv run cdk deploy VEPEndpointStack --outputs-file outputs.json

# Get specific output
aws cloudformation describe-stacks \
  --stack-name VEPEndpointStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text
```

## Cleanup

### Stack Deletion

```bash
# Delete the stack (preserves S3 data by default)
uv run cdk destroy VEPEndpointStack

# Force deletion (use with caution)
uv run cdk destroy VEPEndpointStack --force
```

### Manual S3 Cleanup

If needed, manually clean up S3 resources:

```bash
# Empty and delete S3 bucket
aws s3 rm s3://your-bucket-name --recursive
aws s3 rb s3://your-bucket-name
```

### Resource Preservation

By default, the stack preserves:

- **S3 Bucket and Data**: Retained for data safety
- **CloudWatch Logs**: Retained based on configuration
- **SSM Parameters**: Cleaned up automatically

## Development and Testing

### Local Testing

```bash
# Run unit tests
uv run pytest vep_endpoint/tests/unit/ -v

# Run integration tests (requires AWS credentials)
uv run pytest vep_endpoint/tests/integration/ -v

# Test Lambda function locally
uv run python vep_endpoint/examples/invoke_lambda.py your-function-name --sequence "MKTVRQERLK"
```

### CI/CD Integration

The stack is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Deploy VEP Endpoint Stack
  run: |
    uv run cdk deploy VEPEndpointStack \
      --parameters InstanceType=ml.g6.2xlarge \
      --parameters MinCapacity=0 \
      --require-approval never
```

## Support and Contributing

### Documentation

- **Lambda Function**: See `vep_endpoint/lambda_function/README.md`
- **Testing**: See `vep_endpoint/tests/README.md`
- **Examples**: See example scripts in `vep_endpoint/examples/`

### Version History

- **v1.0.0**: Initial implementation with basic async inference
- **v1.1.0**: Added Lambda integration and MCP compatibility
- **v1.2.0**: Enhanced auto scaling and monitoring
- **v1.3.0**: Improved security and cost optimization features

For issues, feature requests, or contributions, please refer to the project's contribution guidelines.
