# CDK to CloudFormation Migration

This document summarizes the migration from AWS CDK to native CloudFormation templates.

## What Was Removed

### CDK Stack Files
- `app.py` - CDK application entry point
- `cdk.json` - CDK configuration file
- `cdk.context.json` - CDK context cache
- `cdk.out/` - CDK synthesis output directory
- `cognito/` - CDK Cognito stack directory
- `gateway/` - CDK Gateway stack directory
- `vep_endpoint/vep_endpoint_stack.py` - CDK VEP stack implementation

### CDK Deployment Scripts
- `deploy_agentcore.py` - Python script for AgentCore Gateway deployment
- `delete_agentcore.py` - Python script for AgentCore Gateway deletion

### CDK Dependencies
Removed from `pyproject.toml`:
- `aws-cdk-lib==2.208.0`
- `cdk-nag>=2.37.9`
- `constructs>=10.0.0,<11.0.0`

## What Was Added

### CloudFormation Templates
- `cloudformation/templates/vep-endpoint.yaml` - SageMaker async inference infrastructure
- `cloudformation/templates/cognito.yaml` - Authentication infrastructure
- `cloudformation/templates/gateway.yaml` - AgentCore Gateway infrastructure

### Deployment Scripts
- `cloudformation/scripts/deploy.sh` - Orchestrated multi-stack deployment
- `cloudformation/scripts/package-artifacts.sh` - Artifact packaging and upload

### Documentation
- `cloudformation/README.md` - CloudFormation deployment guide
- `.kiro/steering/cloudformation-deployment.md` - Comprehensive deployment documentation

## What Was Updated

### Documentation Files
- `README.md` - Updated to use CloudFormation deployment
- `vep_endpoint/README.md` - Removed CDK references, added CloudFormation instructions
- `.kiro/steering/project-overview.md` - Updated architecture and structure
- `.kiro/steering/development-workflow.md` - Updated deployment workflow
- `.kiro/steering/coding-standards.md` - Replaced CDK standards with CloudFormation standards
- `.kiro/steering/aws-best-practices.md` - Updated deployment best practices

### Configuration Files
- `pyproject.toml` - Removed CDK dependencies
- `pytest.ini` - Updated test markers (removed `cdk`, added `lambda`)
- `.gitignore` - Updated to ignore CloudFormation outputs instead of `cdk.out`

## Migration Benefits

### Advantages of CloudFormation
1. **Native AWS Integration** - Direct CloudFormation syntax without abstraction
2. **Better Visibility** - YAML templates are human-readable and easier to debug
3. **No Build Step** - Templates deploy directly without synthesis
4. **Change Sets** - Preview changes before applying
5. **Drift Detection** - Built-in resource drift detection
6. **Console Integration** - Full AWS Console support for stack management

### Deployment Improvements
1. **Orchestrated Deployment** - Single script deploys all stacks in correct order
2. **SSM Parameter Store** - Flexible cross-stack references without tight coupling
3. **Comprehensive Validation** - Template validation before deployment
4. **Better Error Reporting** - Direct CloudFormation events for troubleshooting

## How to Deploy

### Quick Start
```bash
cd cloudformation/scripts
./deploy.sh --region us-east-1
```

### Custom Configuration
```bash
./deploy.sh \
  --project-name my-project \
  --region us-west-2 \
  --instance-type ml.g6.4xlarge \
  --min-capacity 1 \
  --max-capacity 5
```

For detailed deployment instructions, see:
- `cloudformation/README.md`
- `.kiro/steering/cloudformation-deployment.md`

## Rollback Instructions

If you need to revert to CDK (not recommended):
1. Restore deleted files from git history
2. Run `uv sync` to reinstall CDK dependencies
3. Use `cdk deploy` commands instead of CloudFormation scripts

Note: The CloudFormation templates provide the same functionality with better visibility and control.
