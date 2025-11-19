# CDK Deployment Guide

## Prerequisites

### 1. Deploy Prerequisite Stacks

The Gateway Stack depends on two other stacks that must be deployed first:

```bash
# Deploy VEP Endpoint Stack (CloudFormation)
cd cloudformation/scripts
./deploy.sh --region us-east-1

# This creates SSM parameter: /protein-agent/lambda-function-arn
```

The Cognito stack should also be deployed, which creates:
- `/protein-agent/cognito/discovery-url`
- `/protein-agent/cognito/client-id`

### 2. Install Dependencies

```bash
cd cdk
npm install
```

## Deployment Steps

### Step 1: Configure Environment

```bash
export AWS_REGION=us-east-1
export PROJECT_NAME=protein-engineering
export GATEWAY_NAME=agentcore-gateway
```

### Step 2: Build TypeScript

```bash
npm run build
```

### Step 3: Synthesize CloudFormation Template

```bash
npm run synth
```

This generates the CloudFormation template in `cdk.out/` directory.

### Step 4: Review Changes (Optional)

```bash
npm run diff
```

### Step 5: Deploy to AWS

```bash
npm run deploy
```

## Verification

After deployment, verify the stack:

```bash
# Get Gateway URL
aws cloudformation describe-stacks \
  --stack-name protein-engineering-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' \
  --output text
```
