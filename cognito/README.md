# Cognito CDK Stack

This CDK stack provides a complete AWS Cognito User Pool setup for AgentCore Gateway authentication, including:

- **User Pool** with configurable security policies
- **User Pool Domain** with auto-generated prefix for OAuth endpoints
- **Resource Server** with custom scopes (gateway:read, gateway:write)
- **Machine-to-Machine Client** with client credentials flow
- **SSM Parameters** for configuration values
- **Secrets Manager** integration for client secret via custom Lambda resource

## Features

### Security Configuration

- Configurable password policies (length, character requirements)
- Optional MFA support (SMS and TOTP)
- Email-based account recovery
- Auto-verified email attributes
- Optional deletion protection for production environments
- Threat protection capabilities

### OAuth 2.0 Support

- Client credentials flow for machine-to-machine authentication
- Custom resource server with configurable scopes
- OpenID Connect discovery endpoint
- Configurable token validity periods

### Integration Ready

- SSM Parameters for easy configuration retrieval
- Secrets Manager for secure client secret storage via custom Lambda
- CloudFormation outputs for cross-stack references
- Auto-generated domain prefixes to avoid conflicts

## Quick Start

### 1. Deploy the Stack

The stack is deployed as part of the main application in `app.py`:

```bash
# From project root
uv run cdk deploy CognitoStack
```

The stack automatically:

- Creates all Cognito resources with default configuration
- Retrieves the client secret from Cognito via custom Lambda resource
- Stores it securely in AWS Secrets Manager
- Sets up all SSM parameters for easy access

### 2. Basic Usage in Code

```python
import aws_cdk as cdk
from cognito.cognito_stack import CognitoStack

app = cdk.App()

# Deploy with default configuration
cognito_stack = CognitoStack(app, "CognitoStack")

app.synth()
```

### 3. Custom Configuration

```python
from cognito.cognito_config import CognitoConfig, CognitoResourceScope, CognitoOutputConfig

# Create custom configuration
config = CognitoConfig(
    user_pool_name="my-gateway-pool",
    resource_server_identifier="my-gateway-api-id",
    resource_server_name="My Gateway API",
    client_name="my-gateway-client",
    scopes=[
        CognitoResourceScope("api:read", "Read access to API"),
        CognitoResourceScope("api:write", "Write access to API"),
        CognitoResourceScope("api:admin", "Admin access to API")
    ],
    min_password_length=12,
    require_symbols=True,
    deletion_protection=True
)

# Custom output configuration
output_config = CognitoOutputConfig(
    discovery_url_parameter_name="/my-app/cognito/discovery-url",
    client_id_parameter_name="/my-app/cognito/client-id",
    client_secret_name="my-app-cognito-secret"
)

cognito_stack = CognitoStack(
    app, 
    "CognitoStack", 
    config=config,
    output_config=output_config
)
```

### 4. Environment-Specific Deployment

```python
environment = app.node.try_get_context("environment") or "dev"

config = CognitoConfig(
    user_pool_name=f"gateway-pool-{environment}",
    deletion_protection=(environment == "prod"),
    enable_threat_protection=(environment == "prod")
)

cognito_stack = CognitoStack(
    app, 
    f"CognitoStack-{environment}",
    config=config
)
```

## Deployment

### Prerequisites

- AWS CDK CLI installed: `npm install -g aws-cdk`
- Python dependencies: `uv sync`
- AWS credentials configured

### Deploy the Stack

```bash
# From project root - deploy all stacks including Cognito
uv run cdk deploy --all

# Or deploy just the Cognito stack
uv run cdk deploy CognitoStack
```

### Retrieve Configuration Values

After deployment, retrieve the configuration values using the default parameter names:

```bash
# Get discovery URL
aws ssm get-parameter --name "/cognito/discovery-url" --query "Parameter.Value" --output text

# Get client ID
aws ssm get-parameter --name "/cognito/client-id" --query "Parameter.Value" --output text

# Get user pool ID
aws ssm get-parameter --name "/cognito/user-pool-id" --query "Parameter.Value" --output text

# Get domain URL
aws ssm get-parameter --name "/cognito/domain" --query "Parameter.Value" --output text

# Get client secret (returns JSON with client_secret, client_id, discovery_url, etc.)
aws secretsmanager get-secret-value --secret-id "cognito-client-secret" --query "SecretString" --output text
```

## Configuration Options

### CognitoConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_pool_name` | str | "agentcore-gateway-pool" | Name of the Cognito User Pool |
| `resource_server_identifier` | str | "agentcore-gateway-id" | Unique identifier for the resource server |
| `resource_server_name` | str | "agentcore-gateway-name" | Display name for the resource server |
| `client_name` | str | "agentcore-gateway-client" | Name of the User Pool Client |
| `scopes` | List[CognitoResourceScope] | gateway:read, gateway:write | OAuth scopes for the resource server |
| `generate_secret` | bool | True | Whether to generate a client secret |
| `domain_prefix` | Optional[str] | None (auto-generated) | Custom domain prefix for Cognito domain |
| `min_password_length` | int | 8 | Minimum password length (6-128) |
| `require_lowercase` | bool | True | Require lowercase characters |
| `require_uppercase` | bool | True | Require uppercase characters |
| `require_digits` | bool | True | Require numeric digits |
| `require_symbols` | bool | False | Require special symbols |
| `enable_threat_protection` | bool | True | Enable advanced threat protection |
| `mfa` | cognito.Mfa | OPTIONAL | MFA configuration (OFF, OPTIONAL, REQUIRED) |
| `mfa_second_factor` | Dict[str, bool] | {"sms": True, "otp": True} | MFA second factor options |
| `account_recovery` | cognito.AccountRecovery | EMAIL_ONLY | Account recovery method |
| `auto_verify` | Dict[str, bool] | {"email": True, "phone": False} | Auto-verified attributes |
| `deletion_protection` | bool | False | Enable deletion protection |

### CognitoOutputConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `discovery_url_parameter_name` | str | "/cognito/discovery-url" | SSM parameter name for discovery URL |
| `client_id_parameter_name` | str | "/cognito/client-id" | SSM parameter name for client ID |
| `user_pool_id_parameter_name` | str | "/cognito/user-pool-id" | SSM parameter name for user pool ID |
| `user_pool_arn_parameter_name` | str | "/cognito/user-pool-arn" | SSM parameter name for user pool ARN |
| `domain_parameter_name` | str | "/cognito/domain" | SSM parameter name for domain URL |
| `client_secret_name` | str | "cognito-client-secret" | Secrets Manager secret name |
| `discovery_url_output_name` | str | "CognitoDiscoveryUrl" | CloudFormation output name for discovery URL |
| `client_id_output_name` | str | "CognitoClientId" | CloudFormation output name for client ID |
| `user_pool_id_output_name` | str | "CognitoUserPoolId" | CloudFormation output name for user pool ID |
| `user_pool_arn_output_name` | str | "CognitoUserPoolArn" | CloudFormation output name for user pool ARN |
| `domain_output_name` | str | "CognitoDomain" | CloudFormation output name for domain URL |
| `client_secret_arn_output_name` | str | "CognitoClientSecretArn" | CloudFormation output name for secret ARN |

## Usage Examples

### Getting Access Token (Python)

```python
import boto3
import requests
import json

def get_access_token(client_id: str, client_secret: str, domain_url: str, scopes: str) -> str:
    """Get access token using client credentials flow."""
    
    url = f"{domain_url}/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scopes
    }
    
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    
    return response.json()["access_token"]

# Usage with default configuration
ssm = boto3.client('ssm')
secrets = boto3.client('secretsmanager')

# Get configuration from SSM and Secrets Manager
client_id = ssm.get_parameter(Name='/cognito/client-id')['Parameter']['Value']
domain = ssm.get_parameter(Name='/cognito/domain')['Parameter']['Value']

# Get client secret from Secrets Manager (stored as JSON)
secret_response = secrets.get_secret_value(SecretId='cognito-client-secret')
secret_data = json.loads(secret_response['SecretString'])
client_secret = secret_data['client_secret']

# Get access token with default scopes
token = get_access_token(
    client_id=client_id,
    client_secret=client_secret,
    domain_url=domain,
    scopes="agentcore-gateway-id/gateway:read agentcore-gateway-id/gateway:write"
)
```

### Using the Provided Token Script

The project includes a utility script for getting tokens:

```python
# Use the provided get_token.py script
from cognito.get_token import get_token

token = get_token()
print(f"Access token: {token}")
```

### Using with API Gateway

```python
import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway

# Reference the Cognito User Pool from another stack
user_pool = cognito.UserPool.from_user_pool_id(
    self, "ImportedUserPool", 
    user_pool_id=ssm.StringParameter.value_from_lookup(
        self, "/cognito/user-pool-id"
    )
)

# Create JWT authorizer
authorizer = apigateway.CognitoUserPoolsAuthorizer(
    self, "CognitoAuthorizer",
    cognito_user_pools=[user_pool]
)

# Use in API Gateway method
api.add_method(
    "GET", 
    integration,
    authorizer=authorizer,
    authorization_type=apigateway.AuthorizationType.COGNITO
)
```

## Security Considerations

### Production Deployment

For production environments, ensure:

1. **Enable deletion protection**: Set `deletion_protection=True`
2. **Use strong password policies**: Increase `min_password_length` and enable `require_symbols=True`
3. **Enable threat protection**: Set `enable_threat_protection=True` (default)
4. **Configure MFA**: Set `mfa=cognito.Mfa.REQUIRED` for enhanced security
5. **Monitor access**: Enable CloudTrail logging for Cognito events
6. **Use custom domain prefix**: Set `domain_prefix` to avoid auto-generated names

Example production configuration:

```python
prod_config = CognitoConfig(
    user_pool_name="gateway-pool-prod",
    min_password_length=12,
    require_symbols=True,
    deletion_protection=True,
    enable_threat_protection=True,
    mfa=cognito.Mfa.REQUIRED,
    domain_prefix="my-company-gateway-prod"
)
```

### Client Secret Management

- Client secrets are automatically retrieved from Cognito and stored in AWS Secrets Manager via a custom Lambda resource
- The secret is stored as JSON containing `client_secret`, `client_id`, `user_pool_id`, `discovery_url`, and metadata
- Use IAM policies to restrict access to the secret
- The custom resource preserves secrets during stack deletion (commented out deletion code)
- Never log or expose client secrets in application code

### Custom Resource Implementation

The stack uses a custom Lambda resource to:

1. Retrieve the client secret from Cognito after client creation
2. Store it securely in Secrets Manager with additional metadata
3. Handle updates when the client configuration changes
4. Preserve the secret during stack deletion for data safety

### Network Security

- Use VPC endpoints for Secrets Manager and SSM access when possible
- Implement proper security groups and NACLs
- Consider using AWS PrivateLink for enhanced security

## Troubleshooting

### Common Issues

1. **Domain already exists**: Cognito domains must be globally unique
   - Solution: Customize `domain_prefix` in configuration or let the stack auto-generate one

2. **Client secret not accessible**: Custom Lambda resource may still be running
   - Solution: Wait for stack deployment to complete fully, check CloudFormation events

3. **OAuth scope errors**: Ensure scopes match between resource server and client
   - Solution: Verify scope names in configuration match the format `{resource_server_identifier}/{scope_name}`

4. **Custom resource timeout**: Lambda function may timeout during secret creation
   - Solution: Check CloudWatch logs for the ClientSecretLambda function

5. **IAM permission errors**: Custom resource Lambda may lack required permissions
   - Solution: Verify the Lambda has permissions for `cognito-idp:DescribeUserPoolClient` and Secrets Manager actions

### Debugging

```bash
# Check stack events
aws cloudformation describe-stack-events --stack-name CognitoStack

# Verify User Pool configuration
USER_POOL_ID=$(aws ssm get-parameter --name "/cognito/user-pool-id" --query "Parameter.Value" --output text)
aws cognito-idp describe-user-pool --user-pool-id $USER_POOL_ID

# Check custom resource Lambda logs
aws logs filter-log-events --log-group-name "/aws/lambda/CognitoStack-ClientSecretLambda*" --start-time $(date -d '1 hour ago' +%s)000

# Test OAuth endpoint
DOMAIN=$(aws ssm get-parameter --name "/cognito/domain" --query "Parameter.Value" --output text)
CLIENT_ID=$(aws ssm get-parameter --name "/cognito/client-id" --query "Parameter.Value" --output text)
CLIENT_SECRET=$(aws secretsmanager get-secret-value --secret-id "cognito-client-secret" --query "SecretString" --output text | jq -r '.client_secret')

curl -X POST $DOMAIN/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET&scope=agentcore-gateway-id/gateway:read"
```

## Cost Optimization

- Cognito User Pool pricing is based on monthly active users (MAUs)
- No charges for inactive users
- Advanced security features may incur additional costs
- Monitor usage through CloudWatch metrics

## Monitoring

The stack automatically creates CloudWatch metrics for:

- Authentication attempts
- Failed sign-ins
- Token generation
- Advanced security events

Set up CloudWatch alarms for:

- High failure rates
- Suspicious activity
- Token generation spikes

## Testing

The Cognito stack includes comprehensive tests:

```bash
# Run all Cognito tests
uv run pytest cognito/tests/ -v

# Run with coverage
uv run pytest cognito/tests/ --cov=cognito --cov-report=html

# Run specific test categories
uv run pytest cognito/tests/unit/test_stack_basic.py -v
uv run pytest cognito/tests/unit/test_config_validation.py -v
```

Test coverage includes:

- Configuration validation and edge cases
- CDK stack synthesis and resource creation
- Different configuration scenarios
- Custom resource Lambda functionality

## Contributing

When contributing to this stack:

1. Follow the coding standards in the project root
2. Add comprehensive tests for new features (see `cognito/tests/`)
3. Update documentation for configuration changes
4. Ensure security best practices are maintained
5. Test with different configuration combinations
