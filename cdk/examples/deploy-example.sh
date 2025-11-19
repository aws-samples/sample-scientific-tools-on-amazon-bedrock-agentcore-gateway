#!/bin/bash

# Example deployment script for Gateway Stack
# This demonstrates how to deploy the CDK stack with custom configuration

set -e

# Configuration
export AWS_REGION="${AWS_REGION:-us-east-1}"
export PROJECT_NAME="${PROJECT_NAME:-protein-engineering}"
export GATEWAY_NAME="${GATEWAY_NAME:-agentcore-gateway}"
export ENVIRONMENT="${ENVIRONMENT:-development}"

echo "=========================================="
echo "Gateway Stack Deployment"
echo "=========================================="
echo "Region: $AWS_REGION"
echo "Project: $PROJECT_NAME"
echo "Gateway: $GATEWAY_NAME"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

# Verify prerequisites
echo "Checking prerequisites..."

# Check if Lambda ARN exists in SSM
if ! aws ssm get-parameter --name "/protein-agent/lambda-function-arn" --region "$AWS_REGION" &>/dev/null; then
    echo "ERROR: Lambda ARN not found in SSM. Deploy VEP Endpoint Stack first."
    exit 1
fi

# Check if Cognito discovery URL exists
if ! aws ssm get-parameter --name "/protein-agent/cognito/discovery-url" --region "$AWS_REGION" &>/dev/null; then
    echo "ERROR: Cognito discovery URL not found in SSM. Deploy Cognito Stack first."
    exit 1
fi

echo "Prerequisites verified!"

# Install dependencies
echo "Installing dependencies..."
npm install

# Build TypeScript
echo "Building TypeScript..."
npm run build

# Synthesize CloudFormation template
echo "Synthesizing CloudFormation template..."
npm run synth

# Deploy stack
echo "Deploying Gateway Stack..."
npm run deploy -- --require-approval never

echo "=========================================="
echo "Deployment complete!"
echo "=========================================="

# Display outputs
echo "Retrieving stack outputs..."
aws cloudformation describe-stacks \
  --stack-name "${PROJECT_NAME}-gateway" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs' \
  --output table
