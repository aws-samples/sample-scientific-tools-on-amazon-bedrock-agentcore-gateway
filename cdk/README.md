# Protein Engineering Gateway - CDK TypeScript Implementation

CDK TypeScript implementation of the Amazon Bedrock AgentCore Gateway stack for protein engineering predictions.

## Overview

This CDK stack deploys the Gateway infrastructure with:
- IAM Role for AgentCore Gateway with Lambda invoke permissions
- AgentCore Gateway with JWT authorization (Cognito integration)
- Gateway Target connecting to Lambda function for protein prediction
- MCP tool schema defining invoke_endpoint and get_results operations

## Prerequisites

1. **VEP Endpoint Stack** must be deployed first (provides Lambda ARN in SSM)
2. **Cognito Stack** must be deployed second (provides auth config in SSM)
3. Node.js 18+ and npm installed
4. AWS CLI configured with appropriate credentials

## Installation

```bash
cd cdk
npm install
```

## Configuration

Set environment variables or use defaults:

```bash
export AWS_REGION=us-east-1
export PROJECT_NAME=protein-engineering
export GATEWAY_NAME=agentcore-gateway
```

## Deployment

```bash
# Build TypeScript
npm run build

# Synthesize CloudFormation template
npm run synth

# Deploy to AWS
npm run deploy
```

## Useful Commands

- `npm run build` - Compile TypeScript to JavaScript
- `npm run watch` - Watch for changes and compile
- `npm run synth` - Synthesize CloudFormation template
- `npm run deploy` - Deploy stack to AWS
- `npm run diff` - Compare deployed stack with current state
- `npm run destroy` - Delete the stack from AWS

## Stack Outputs

After deployment, the stack provides:
- **GatewayUrl**: MCP endpoint URL for agent connections
- **GatewayId**: Gateway resource ID
- **GatewayArn**: Gateway ARN
- **GatewayRoleArn**: IAM role ARN
- **TargetId**: Gateway Target ID

## SSM Parameters

The stack reads from SSM Parameter Store:
- `/protein-agent/lambda-function-arn` - Lambda ARN from VEP stack
- `/protein-agent/cognito/discovery-url` - Cognito OIDC discovery URL
- `/protein-agent/cognito/client-id` - OAuth client ID

The stack creates:
- `/protein-agent/gateway/role-arn` - Gateway IAM role ARN

## Architecture

The Gateway Stack integrates with:
1. **VEP Endpoint Stack**: Lambda function for protein predictions
2. **Cognito Stack**: OAuth2 authentication and JWT validation
3. **MCP Protocol**: AI agent communication protocol

## Comparison with CloudFormation

This CDK implementation provides the same functionality as the CloudFormation template
with additional benefits:
- Type-safe TypeScript code with IDE support
- Reusable constructs and better code organization
- Easier testing with CDK assertions
- Programmatic infrastructure definition
