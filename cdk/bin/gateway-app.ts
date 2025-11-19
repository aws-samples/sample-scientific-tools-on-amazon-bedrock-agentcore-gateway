#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { GatewayStack } from '../lib/gateway-stack';

/**
 * CDK Application for Protein Engineering Gateway Stack
 * 
 * This application deploys the Amazon Bedrock AgentCore Gateway
 * with MCP integration for protein engineering predictions.
 * 
 * Prerequisites:
 * - VEP Endpoint Stack must be deployed (provides Lambda ARN)
 * - Cognito Stack must be deployed (provides auth configuration)
 * 
 * Configuration:
 * - Set AWS_REGION environment variable or use default (us-east-1)
 * - Set PROJECT_NAME environment variable or use default (protein-engineering)
 * - Set GATEWAY_NAME environment variable or use default (agentcore-gateway)
 * 
 * Deployment:
 * ```bash
 * npm install
 * npm run build
 * cdk synth
 * cdk deploy
 * ```
 * 
 * Custom Configuration:
 * ```bash
 * export AWS_REGION=us-west-2
 * export PROJECT_NAME=my-protein-project
 * export GATEWAY_NAME=my-gateway
 * cdk deploy
 * ```
 */

const app = new cdk.App();

// Get configuration from environment or use defaults
const projectName = process.env.PROJECT_NAME || 'protein-engineering';
const gatewayName = process.env.GATEWAY_NAME || 'agentcore-gateway';
const region = process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || 'us-east-1';
const account = process.env.CDK_DEFAULT_ACCOUNT;

// Create the Gateway Stack
new GatewayStack(app, 'ProteinEngineeringGatewayStack', {
  stackName: `${projectName}-gateway`,
  description: 'Gateway Stack - Amazon Bedrock AgentCore Gateway infrastructure for MCP integration',
  
  // Stack configuration
  projectName: projectName,
  gatewayName: gatewayName,
  gatewayDescription: 'AgentCore Gateway for protein engineering agent with MCP integration',
  
  // Environment configuration
  env: {
    account: account,
    region: region,
  },
  
  // Stack tags
  tags: {
    Project: projectName,
    Component: 'Gateway',
    ManagedBy: 'CDK',
    Environment: process.env.ENVIRONMENT || 'development',
  },
});

// Synthesize the CloudFormation template
app.synth();
