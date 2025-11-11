#!/usr/bin/env bash

################################################################################
# CloudFormation Deployment Orchestration Script
# 
# This script orchestrates the deployment of all CloudFormation stacks for the
# Protein Engineering Agent infrastructure in the correct order:
# 1. VEP Endpoint Stack (SageMaker + Lambda)
# 2. Cognito Stack (Authentication)
# 3. Gateway Stack (AgentCore Gateway)
#
# Usage:
#   ./deploy.sh [OPTIONS]
#
# Options:
#   --project-name NAME      Project name for resource naming (default: protein-engineering)
#   --region REGION          AWS region for deployment (default: us-east-1)
#   --instance-type TYPE     SageMaker instance type (default: ml.g6.2xlarge)
#   --min-capacity NUM       Minimum auto-scaling capacity (default: 1)
#   --max-capacity NUM       Maximum auto-scaling capacity (default: 2)
#   --enable-autoscaling     Enable auto-scaling (default: true)
#   --help                   Display this help message
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUDFORMATION_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="${CLOUDFORMATION_DIR}/templates"
PARAMETERS_DIR="${CLOUDFORMATION_DIR}/parameters"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
PROJECT_NAME="protein-engineering"
AWS_REGION="us-east-1"
INSTANCE_TYPE="ml.g6.2xlarge"
MIN_CAPACITY=1
MAX_CAPACITY=2
ENABLE_AUTOSCALING="true"

# Stack names
VEP_STACK_NAME="${PROJECT_NAME}-vep-endpoint"
COGNITO_STACK_NAME="${PROJECT_NAME}-cognito"
GATEWAY_STACK_NAME="${PROJECT_NAME}-gateway"

# Template paths
VEP_TEMPLATE="${TEMPLATES_DIR}/vep-endpoint.yaml"
COGNITO_TEMPLATE="${TEMPLATES_DIR}/cognito.yaml"
GATEWAY_TEMPLATE="${TEMPLATES_DIR}/gateway.yaml"

################################################################################
# Helper Functions
################################################################################

# Print colored message
print_message() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

# Print section header
print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

# Print error and exit
error_exit() {
    print_message "$RED" "ERROR: $1"
    exit 1
}

# Print success message
print_success() {
    print_message "$GREEN" "✓ $1"
}

# Print warning message
print_warning() {
    print_message "$YELLOW" "⚠ $1"
}

# Print info message
print_info() {
    print_message "$BLUE" "ℹ $1"
}

# Display usage information
usage() {
    cat << EOF
CloudFormation Deployment Orchestration Script

Usage: $0 [OPTIONS]

Options:
  --project-name NAME      Project name for resource naming (default: protein-engineering)
  --region REGION          AWS region for deployment (default: us-east-1)
  --instance-type TYPE     SageMaker instance type (default: ml.g6.2xlarge)
  --min-capacity NUM       Minimum auto-scaling capacity (default: 1)
  --max-capacity NUM       Maximum auto-scaling capacity (default: 2)
  --enable-autoscaling     Enable auto-scaling (default: true)
  --disable-autoscaling    Disable auto-scaling
  --help                   Display this help message

Examples:
  # Deploy with defaults
  $0

  # Deploy to specific region with custom instance type
  $0 --region us-west-2 --instance-type ml.g5.2xlarge

  # Deploy with auto-scaling disabled
  $0 --disable-autoscaling --min-capacity 0

EOF
    exit 0
}

################################################################################
# Parse Command Line Arguments
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project-name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            --region)
                AWS_REGION="$2"
                shift 2
                ;;
            --instance-type)
                INSTANCE_TYPE="$2"
                shift 2
                ;;
            --min-capacity)
                MIN_CAPACITY="$2"
                shift 2
                ;;
            --max-capacity)
                MAX_CAPACITY="$2"
                shift 2
                ;;
            --enable-autoscaling)
                ENABLE_AUTOSCALING="true"
                shift
                ;;
            --disable-autoscaling)
                ENABLE_AUTOSCALING="false"
                shift
                ;;
            --help)
                usage
                ;;
            *)
                error_exit "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    # Update stack names with project name
    VEP_STACK_NAME="${PROJECT_NAME}-vep-endpoint"
    COGNITO_STACK_NAME="${PROJECT_NAME}-cognito"
    GATEWAY_STACK_NAME="${PROJECT_NAME}-gateway"
}

################################################################################
# Validation Functions
################################################################################

# Check if AWS CLI is installed and configured
check_aws_cli() {
    print_info "Checking AWS CLI installation..."
    
    if ! command -v aws &> /dev/null; then
        error_exit "AWS CLI is not installed. Please install it from https://aws.amazon.com/cli/"
    fi
    
    print_success "AWS CLI is installed"
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        error_exit "AWS credentials are not configured or invalid. Run 'aws configure' to set up credentials."
    fi
    
    local account_id=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
    local user_arn=$(aws sts get-caller-identity --query Arn --output text --region "$AWS_REGION")
    
    print_success "AWS credentials are valid"
    print_info "Account ID: $account_id"
    print_info "User/Role: $user_arn"
}

# Validate CloudFormation template
validate_template() {
    local template_path=$1
    local template_name=$(basename "$template_path")
    
    print_info "Validating template: $template_name"
    
    if [[ ! -f "$template_path" ]]; then
        error_exit "Template file not found: $template_path"
    fi
    
    local validation_output
    if validation_output=$(aws cloudformation validate-template \
        --template-body "file://$template_path" \
        --region "$AWS_REGION" 2>&1); then
        print_success "Template validation passed: $template_name"
        return 0
    else
        print_message "$RED" "Template validation failed: $template_name"
        echo "$validation_output"
        return 1
    fi
}

# Validate all templates
validate_all_templates() {
    print_header "Validating CloudFormation Templates"
    
    local validation_failed=0
    
    validate_template "$VEP_TEMPLATE" || validation_failed=1
    validate_template "$COGNITO_TEMPLATE" || validation_failed=1
    validate_template "$GATEWAY_TEMPLATE" || validation_failed=1
    
    if [[ $validation_failed -eq 1 ]]; then
        error_exit "Template validation failed. Please fix the errors and try again."
    fi
    
    print_success "All templates validated successfully"
}

################################################################################
# Stack Deployment Functions
################################################################################

# Check if stack exists
stack_exists() {
    local stack_name=$1
    
    if aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Get stack status
get_stack_status() {
    local stack_name=$1
    
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].StackStatus' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "DOES_NOT_EXIST"
}

# Wait for stack operation to complete
wait_for_stack() {
    local stack_name=$1
    local operation=$2  # create or update
    
    print_info "Waiting for stack $operation to complete: $stack_name"
    print_info "This may take several minutes..."
    
    local wait_command="stack-${operation}-complete"
    
    if aws cloudformation wait "$wait_command" \
        --stack-name "$stack_name" \
        --region "$AWS_REGION"; then
        print_success "Stack $operation completed: $stack_name"
        return 0
    else
        print_message "$RED" "Stack $operation failed: $stack_name"
        print_message "$RED" "Checking stack events for errors..."
        
        # Display recent stack events
        aws cloudformation describe-stack-events \
            --stack-name "$stack_name" \
            --region "$AWS_REGION" \
            --max-items 10 \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[Timestamp,ResourceType,LogicalResourceId,ResourceStatusReason]' \
            --output table
        
        return 1
    fi
}

# Create S3 bucket and upload artifacts
prepare_artifacts() {
    print_header "Preparing Artifacts"
    
    local account_id=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
    ARTIFACTS_BUCKET="${PROJECT_NAME}-artifacts-${account_id}"
    
    print_info "Artifacts bucket: $ARTIFACTS_BUCKET"
    
    # Create single artifacts bucket
    if aws s3 ls "s3://${ARTIFACTS_BUCKET}" --region "$AWS_REGION" 2>/dev/null; then
        print_info "Artifacts bucket already exists"
    else
        print_info "Creating artifacts bucket..."
        if [[ "$AWS_REGION" == "us-east-1" ]]; then
            aws s3 mb "s3://${ARTIFACTS_BUCKET}" --region "$AWS_REGION"
        else
            aws s3api create-bucket --bucket "${ARTIFACTS_BUCKET}" --region "$AWS_REGION" --create-bucket-configuration LocationConstraint="$AWS_REGION"
        fi
        print_success "Artifacts bucket created"
    fi
    
    # Package and upload artifacts
    print_info "Packaging and uploading artifacts..."
    "${SCRIPT_DIR}/package-artifacts.sh" --project-name "$PROJECT_NAME" --region "$AWS_REGION" || error_exit "Failed to package artifacts"
}

# Deploy VEP Endpoint Stack
deploy_vep_stack() {
    print_header "Deploying VEP Endpoint Stack"
    
    print_info "Stack Name: $VEP_STACK_NAME"
    print_info "Template: $VEP_TEMPLATE"
    print_info "Region: $AWS_REGION"
    print_info "Instance Type: $INSTANCE_TYPE"
    print_info "Auto-scaling: $ENABLE_AUTOSCALING (Min: $MIN_CAPACITY, Max: $MAX_CAPACITY)"
    print_info "Using artifacts bucket: $ARTIFACTS_BUCKET"
    
    local stack_status=$(get_stack_status "$VEP_STACK_NAME")
    
    if [[ "$stack_status" == "DOES_NOT_EXIST" ]]; then
        print_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$VEP_STACK_NAME" \
            --template-body "file://$VEP_TEMPLATE" \
            --parameters \
                ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
                ParameterKey=InstanceType,ParameterValue="$INSTANCE_TYPE" \
                ParameterKey=MinCapacity,ParameterValue="$MIN_CAPACITY" \
                ParameterKey=MaxCapacity,ParameterValue="$MAX_CAPACITY" \
                ParameterKey=EnableAutoScaling,ParameterValue="$ENABLE_AUTOSCALING" \
                ParameterKey=AsyncInferenceBucketName,ParameterValue="$ARTIFACTS_BUCKET" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$AWS_REGION" \
            --tags \
                Key=Project,Value="$PROJECT_NAME" \
                Key=ManagedBy,Value=CloudFormation \
                Key=Component,Value=VEPEndpoint
        
        wait_for_stack "$VEP_STACK_NAME" "create" || error_exit "VEP stack creation failed"
    else
        print_warning "Stack already exists with status: $stack_status"
        print_info "Skipping VEP stack deployment"
    fi
    
    # Verify Lambda ARN in SSM
    print_info "Verifying Lambda ARN in SSM Parameter Store..."
    local lambda_arn
    if lambda_arn=$(aws ssm get-parameter \
        --name "/protein-agent/lambda-function-arn" \
        --query 'Parameter.Value' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null); then
        print_success "Lambda ARN verified: $lambda_arn"
    else
        error_exit "Lambda ARN not found in SSM Parameter Store"
    fi
}

# Deploy Cognito Stack
deploy_cognito_stack() {
    print_header "Deploying Cognito Stack"
    
    print_info "Stack Name: $COGNITO_STACK_NAME"
    print_info "Template: $COGNITO_TEMPLATE"
    print_info "Region: $AWS_REGION"
    
    local stack_status=$(get_stack_status "$COGNITO_STACK_NAME")
    
    if [[ "$stack_status" == "DOES_NOT_EXIST" ]]; then
        print_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$COGNITO_STACK_NAME" \
            --template-body "file://$COGNITO_TEMPLATE" \
            --parameters \
                ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$AWS_REGION" \
            --tags \
                Key=Project,Value="$PROJECT_NAME" \
                Key=ManagedBy,Value=CloudFormation \
                Key=Component,Value=Cognito
        
        wait_for_stack "$COGNITO_STACK_NAME" "create" || error_exit "Cognito stack creation failed"
    else
        print_warning "Stack already exists with status: $stack_status"
        print_info "Skipping Cognito stack deployment"
    fi
    
    # Verify Cognito parameters in SSM
    print_info "Verifying Cognito parameters in SSM Parameter Store..."
    
    local params=(
        "/protein-agent/cognito/discovery-url"
        "/protein-agent/cognito/client-id"
        "/protein-agent/cognito/user-pool-id"
    )
    
    for param in "${params[@]}"; do
        if aws ssm get-parameter --name "$param" --region "$AWS_REGION" &> /dev/null; then
            print_success "Parameter verified: $param"
        else
            error_exit "Parameter not found: $param"
        fi
    done
}

# Deploy Gateway Stack
deploy_gateway_stack() {
    print_header "Deploying Gateway Stack"
    
    print_info "Stack Name: $GATEWAY_STACK_NAME"
    print_info "Template: $GATEWAY_TEMPLATE"
    print_info "Region: $AWS_REGION"
    
    local stack_status=$(get_stack_status "$GATEWAY_STACK_NAME")
    
    if [[ "$stack_status" == "DOES_NOT_EXIST" ]]; then
        print_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$GATEWAY_STACK_NAME" \
            --template-body "file://$GATEWAY_TEMPLATE" \
            --parameters \
                ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$AWS_REGION" \
            --tags \
                Key=Project,Value="$PROJECT_NAME" \
                Key=ManagedBy,Value=CloudFormation \
                Key=Component,Value=Gateway
        
        wait_for_stack "$GATEWAY_STACK_NAME" "create" || error_exit "Gateway stack creation failed"
    else
        print_warning "Stack already exists with status: $stack_status"
        print_info "Skipping Gateway stack deployment"
    fi
    
    # Retrieve and display Gateway URL
    print_info "Retrieving Gateway URL..."
    local gateway_url
    if gateway_url=$(aws cloudformation describe-stacks \
        --stack-name "$GATEWAY_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null); then
        print_success "Gateway URL: $gateway_url"
    else
        print_warning "Could not retrieve Gateway URL from stack outputs"
    fi
}

################################################################################
# Output Display Functions
################################################################################

# Display all stack outputs
display_stack_outputs() {
    print_header "Deployment Summary"
    
    print_info "Retrieving stack outputs..."
    echo ""
    
    # VEP Stack Outputs
    print_message "$GREEN" "VEP Endpoint Stack ($VEP_STACK_NAME):"
    aws cloudformation describe-stacks \
        --stack-name "$VEP_STACK_NAME" \
        --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
        --output table \
        --region "$AWS_REGION" 2>/dev/null || print_warning "Could not retrieve VEP stack outputs"
    
    echo ""
    
    # Cognito Stack Outputs
    print_message "$GREEN" "Cognito Stack ($COGNITO_STACK_NAME):"
    aws cloudformation describe-stacks \
        --stack-name "$COGNITO_STACK_NAME" \
        --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
        --output table \
        --region "$AWS_REGION" 2>/dev/null || print_warning "Could not retrieve Cognito stack outputs"
    
    echo ""
    
    # Gateway Stack Outputs
    print_message "$GREEN" "Gateway Stack ($GATEWAY_STACK_NAME):"
    aws cloudformation describe-stacks \
        --stack-name "$GATEWAY_STACK_NAME" \
        --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
        --output table \
        --region "$AWS_REGION" 2>/dev/null || print_warning "Could not retrieve Gateway stack outputs"
    
    echo ""
}

# Display connection information
display_connection_info() {
    print_header "Connection Information"
    
    # Get Gateway URL
    local gateway_url
    gateway_url=$(aws cloudformation describe-stacks \
        --stack-name "$GATEWAY_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null)
    
    # Get Token Endpoint
    local token_endpoint
    token_endpoint=$(aws cloudformation describe-stacks \
        --stack-name "$COGNITO_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`TokenEndpoint`].OutputValue' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null)
    
    # Get Client ID
    local client_id
    client_id=$(aws ssm get-parameter \
        --name "/protein-agent/cognito/client-id" \
        --query 'Parameter.Value' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null)
    
    print_message "$BLUE" "Gateway URL:"
    echo "  $gateway_url"
    echo ""
    
    print_message "$BLUE" "OAuth Token Endpoint:"
    echo "  $token_endpoint"
    echo ""
    
    print_message "$BLUE" "Client ID:"
    echo "  $client_id"
    echo ""
    
    print_message "$BLUE" "Client Secret Location:"
    echo "  AWS Secrets Manager: ${PROJECT_NAME}/cognito/client-secret"
    echo ""
}

# Display next steps
display_next_steps() {
    print_header "Next Steps"
    
    cat << EOF
1. Retrieve OAuth credentials:
   aws secretsmanager get-secret-value \\
     --secret-id ${PROJECT_NAME}/cognito/client-secret \\
     --region $AWS_REGION \\
     --query SecretString \\
     --output text | jq .

2. Obtain access token:
   Use the get_token.py script or make a direct OAuth request to the token endpoint

3. Test the Gateway:
   curl -X POST <gateway-url> \\
     -H "Authorization: Bearer <access-token>" \\
     -H "Content-Type: application/json" \\
     -d '{"tool_name": "invoke_endpoint", "sequence": "MKTVRQERLK"}'

4. Monitor deployment:
   - CloudFormation Console: https://console.aws.amazon.com/cloudformation
   - SageMaker Console: https://console.aws.amazon.com/sagemaker
   - CloudWatch Logs: https://console.aws.amazon.com/cloudwatch

5. View documentation:
   See cloudformation/README.md for detailed usage instructions

EOF
}

################################################################################
# Error Handling Functions
################################################################################

# Handle deployment errors
handle_deployment_error() {
    local stack_name=$1
    local error_message=$2
    
    print_header "Deployment Error"
    
    print_message "$RED" "Error deploying stack: $stack_name"
    print_message "$RED" "Error: $error_message"
    echo ""
    
    print_message "$YELLOW" "Troubleshooting Steps:"
    echo "1. Check CloudFormation events:"
    echo "   aws cloudformation describe-stack-events --stack-name $stack_name --region $AWS_REGION"
    echo ""
    echo "2. Check CloudWatch Logs for Lambda errors (if applicable)"
    echo ""
    echo "3. Verify IAM permissions for CloudFormation and service roles"
    echo ""
    
    print_message "$YELLOW" "Rollback Instructions:"
    echo "To delete the failed stack:"
    echo "   aws cloudformation delete-stack --stack-name $stack_name --region $AWS_REGION"
    echo ""
    echo "To delete all stacks:"
    echo "   ./cleanup.sh --region $AWS_REGION"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "CloudFormation Deployment Orchestration"
    
    # Parse command line arguments
    parse_arguments "$@"
    
    print_info "Project Name: $PROJECT_NAME"
    print_info "AWS Region: $AWS_REGION"
    print_info "Instance Type: $INSTANCE_TYPE"
    echo ""
    
    # Check prerequisites
    check_aws_cli
    
    # Validate templates
    validate_all_templates
    
    # Prepare artifacts (create buckets and upload code)
    prepare_artifacts
    
    # Deploy stacks in order
    deploy_vep_stack
    deploy_cognito_stack
    deploy_gateway_stack
    
    # Display outputs
    display_stack_outputs
    display_connection_info
    display_next_steps
    
    print_header "Deployment Complete"
    print_success "All stacks deployed successfully!"
}

# Run main function with all arguments
main "$@"
