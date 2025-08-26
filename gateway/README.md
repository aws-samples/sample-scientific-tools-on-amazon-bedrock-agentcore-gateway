# AgentCore Gateway Infrastructure

This directory contains the CDK infrastructure for deploying Amazon Bedrock AgentCore Gateway components.

## Components

- **IAM Role Stack**: Creates the IAM role required for AgentCore Gateway operations
- **Deployment Script**: Python script to deploy the actual gateway using the CDK-created role

## Quick Start

### 1. Deploy the IAM Role

```bash
# Install dependencies
pip install -r requirements.txt

# Deploy the role stack
cdk deploy AgentCoreGatewayRole-dev --context environment=dev

# For production
cdk deploy AgentCoreGatewayRole-prod --context environment=prod
```

### 2. Deploy the Gateway

```bash
# Deploy gateway using the CDK-created role
python deploy_agentcore_gateway.py --environment dev

# For production
python deploy_agentcore_gateway.py --environment prod
```

## Architecture

The IAM role created by the CDK stack includes permissions for:
- Bedrock AgentCore operations
- Lambda function invocation
- Secrets Manager access
- CloudWatch logging and metrics
- IAM role passing

The role ARN is stored in SSM Parameter Store at:
`/agentcore-gateway/{environment}/role-arn`

## Environment Variables

- `environment`: Deployment environment (dev, staging, prod)

## Outputs

- **GatewayRoleArn**: The ARN of the created IAM role
- **SSM Parameter**: Role ARN stored in Parameter Store for easy retrieval