# CloudFormation vs CDK Comparison

## Gateway Stack Implementation Comparison

This document compares the CloudFormation YAML template with the CDK TypeScript implementation.

### Resource Mapping

| CloudFormation Resource | CDK Equivalent | Notes |
|------------------------|----------------|-------|
| `AWS::IAM::Role` (GatewayRole) | `iam.Role` | Same trust policy and permissions |
| `AWS::SSM::Parameter` (GatewayRoleArnParameter) | `ssm.StringParameter` | Stores Gateway role ARN |
| `AWS::BedrockAgentCore::Gateway` | `bedrockagentcore.CfnGateway` | Main gateway resource |
| `AWS::BedrockAgentCore::GatewayTarget` | `bedrockagentcore.CfnGatewayTarget` | Lambda target with MCP schema |

### SSM Parameter References

**CloudFormation** uses dynamic references:
```yaml
Resource: '{{resolve:ssm:/protein-agent/lambda-function-arn}}'
```

**CDK** uses `StringParameter.valueFromLookup()`:
```typescript
const lambdaFunctionArn = ssm.StringParameter.valueFromLookup(
  this, '/protein-agent/lambda-function-arn'
);
```

### Configuration Properties

Both implementations support the same configuration:
- `projectName`: Resource naming prefix
- `gatewayName`: Gateway name
- `gatewayDescription`: Gateway description

### Key Differences

1. **Type Safety**: CDK provides compile-time type checking
2. **Code Organization**: CDK allows better separation of concerns
3. **Reusability**: CDK constructs can be easily reused
4. **Testing**: CDK supports unit testing with assertions
5. **IDE Support**: TypeScript provides autocomplete and inline docs
