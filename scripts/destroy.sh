#!/usr/bin/env bash

################################################################################
# CloudFormation Stack Destruction Script
# 
# This script safely deletes all CloudFormation stacks created by deploy.sh
# in the correct reverse order:
# 1. Gateway Stack (AgentCore Gateway)
# 2. Cognito Stack (Authentication)
# 3. VEP Endpoint Stack (SageMaker + Lambda)
#
# Usage:
#   ./destroy.sh [OPTIONS]
#
# Options:
#   --project-name NAME      Project name for resource naming (default: protein-engineering)
#   --region REGION          AWS region (default: us-east-1)
#   --delete-buckets         Delete S3 buckets (WARNING: destroys all data)
#   --force                  Skip confirmation prompts
#   --help                   Display this help message
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
PROJECT_NAME="protein-engineering"
AWS_REGION="us-east-1"
DELETE_BUCKETS="false"
FORCE="false"

# Stack names
VEP_STACK_NAME="${PROJECT_NAME}-vep-endpoint"
COGNITO_STACK_NAME="${PROJECT_NAME}-cognito"
GATEWAY_STACK_NAME="${PROJECT_NAME}-gateway"

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
CloudFormation Stack Destruction Script

Usage: $0 [OPTIONS]

Options:
  --project-name NAME      Project name for resource naming (default: protein-engineering)
  --region REGION          AWS region (default: us-east-1)
  --delete-buckets         Delete S3 buckets and all data (WARNING: irreversible)
  --force                  Skip confirmation prompts
  --help                   Display this help message

Examples:
  # Delete stacks with confirmation
  $0

  # Delete stacks in specific region
  $0 --region us-west-2

  # Delete stacks and S3 buckets without confirmation
  $0 --delete-buckets --force

  # Delete stacks for custom project
  $0 --project-name my-project --region us-east-1

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
            --delete-buckets)
                DELETE_BUCKETS="true"
                shift
                ;;
            --force)
                FORCE="true"
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

################################################################################
# Stack Management Functions
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

# Wait for stack deletion to complete
wait_for_stack_deletion() {
    local stack_name=$1
    
    print_info "Waiting for stack deletion to complete: $stack_name"
    print_info "This may take several minutes..."
    
    if aws cloudformation wait stack-delete-complete \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" 2>/dev/null; then
        print_success "Stack deleted: $stack_name"
        return 0
    else
        # Check if stack still exists
        if stack_exists "$stack_name"; then
            print_message "$RED" "Stack deletion failed: $stack_name"
            
            # Display recent stack events
            aws cloudformation describe-stack-events \
                --stack-name "$stack_name" \
                --region "$AWS_REGION" \
                --max-items 10 \
                --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`].[Timestamp,ResourceType,LogicalResourceId,ResourceStatusReason]' \
                --output table
            
            return 1
        else
            print_success "Stack deleted: $stack_name"
            return 0
        fi
    fi
}

# Delete a CloudFormation stack
delete_stack() {
    local stack_name=$1
    
    if ! stack_exists "$stack_name"; then
        print_info "Stack does not exist: $stack_name"
        return 0
    fi
    
    local stack_status=$(get_stack_status "$stack_name")
    print_info "Current status: $stack_status"
    
    # Check if stack is in a deletable state
    case "$stack_status" in
        DELETE_IN_PROGRESS)
            print_info "Stack deletion already in progress: $stack_name"
            wait_for_stack_deletion "$stack_name"
            return $?
            ;;
        DELETE_FAILED|ROLLBACK_COMPLETE|CREATE_FAILED)
            print_warning "Stack is in $stack_status state"
            ;;
    esac
    
    print_info "Deleting stack: $stack_name"
    
    if aws cloudformation delete-stack \
        --stack-name "$stack_name" \
        --region "$AWS_REGION"; then
        wait_for_stack_deletion "$stack_name"
        return $?
    else
        print_message "$RED" "Failed to initiate stack deletion: $stack_name"
        return 1
    fi
}

################################################################################
# S3 Bucket Management Functions
################################################################################

# List S3 buckets for the project
list_project_buckets() {
    local account_id=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
    
    # Artifacts bucket
    ARTIFACTS_BUCKET="${PROJECT_NAME}-artifacts-${account_id}"
    
    # Async inference bucket (if created separately)
    ASYNC_BUCKET="${PROJECT_NAME}-async-inference-${account_id}"
    
    echo "$ARTIFACTS_BUCKET $ASYNC_BUCKET"
}

# Check if S3 bucket exists
bucket_exists() {
    local bucket_name=$1
    
    if aws s3 ls "s3://${bucket_name}" --region "$AWS_REGION" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Delete S3 bucket and all contents
delete_bucket() {
    local bucket_name=$1
    
    if ! bucket_exists "$bucket_name"; then
        print_info "Bucket does not exist: $bucket_name"
        return 0
    fi
    
    print_info "Deleting bucket: $bucket_name"
    
    # Get object count
    local object_count=$(aws s3 ls "s3://${bucket_name}" --recursive --region "$AWS_REGION" 2>/dev/null | wc -l | tr -d ' ')
    
    if [[ "$object_count" -gt 0 ]]; then
        print_warning "Bucket contains $object_count objects"
        print_info "Deleting all objects in bucket..."
        
        if aws s3 rm "s3://${bucket_name}" --recursive --region "$AWS_REGION"; then
            print_success "All objects deleted from bucket: $bucket_name"
        else
            print_message "$RED" "Failed to delete objects from bucket: $bucket_name"
            return 1
        fi
    fi
    
    # Delete the bucket
    if aws s3 rb "s3://${bucket_name}" --region "$AWS_REGION"; then
        print_success "Bucket deleted: $bucket_name"
        return 0
    else
        print_message "$RED" "Failed to delete bucket: $bucket_name"
        return 1
    fi
}

# Delete all project S3 buckets
delete_all_buckets() {
    print_header "Deleting S3 Buckets"
    
    local buckets=$(list_project_buckets)
    
    for bucket in $buckets; do
        delete_bucket "$bucket"
    done
}

################################################################################
# Confirmation Functions
################################################################################

# Display resources to be deleted
display_resources() {
    print_header "Resources to be Deleted"
    
    print_message "$YELLOW" "CloudFormation Stacks:"
    
    for stack_name in "$GATEWAY_STACK_NAME" "$COGNITO_STACK_NAME" "$VEP_STACK_NAME"; do
        if stack_exists "$stack_name"; then
            local status=$(get_stack_status "$stack_name")
            echo "  - $stack_name ($status)"
        else
            echo "  - $stack_name (does not exist)"
        fi
    done
    
    echo ""
    
    if [[ "$DELETE_BUCKETS" == "true" ]]; then
        print_message "$YELLOW" "S3 Buckets (and all contents):"
        
        local buckets=$(list_project_buckets)
        for bucket in $buckets; do
            if bucket_exists "$bucket"; then
                local object_count=$(aws s3 ls "s3://${bucket}" --recursive --region "$AWS_REGION" 2>/dev/null | wc -l | tr -d ' ')
                echo "  - $bucket ($object_count objects)"
            else
                echo "  - $bucket (does not exist)"
            fi
        done
        
        echo ""
        print_message "$RED" "WARNING: Deleting S3 buckets will permanently destroy all data!"
    fi
    
    echo ""
}

# Confirm deletion
confirm_deletion() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    
    display_resources
    
    print_message "$YELLOW" "This action will delete the resources listed above."
    
    if [[ "$DELETE_BUCKETS" == "true" ]]; then
        print_message "$RED" "This includes PERMANENT deletion of all S3 bucket data!"
    fi
    
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Deletion cancelled by user"
        exit 0
    fi
    
    if [[ "$DELETE_BUCKETS" == "true" ]]; then
        print_message "$RED" "FINAL WARNING: You are about to permanently delete all S3 bucket data!"
        read -p "Type 'DELETE' to confirm: " -r
        echo ""
        
        if [[ "$REPLY" != "DELETE" ]]; then
            print_info "Deletion cancelled by user"
            exit 0
        fi
    fi
}

################################################################################
# Stack Deletion Functions
################################################################################

# Delete Gateway Stack
delete_gateway_stack() {
    print_header "Deleting Gateway Stack"
    delete_stack "$GATEWAY_STACK_NAME"
}

# Delete Cognito Stack
delete_cognito_stack() {
    print_header "Deleting Cognito Stack"
    delete_stack "$COGNITO_STACK_NAME"
}

# Delete VEP Endpoint Stack
delete_vep_stack() {
    print_header "Deleting VEP Endpoint Stack"
    delete_stack "$VEP_STACK_NAME"
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "CloudFormation Stack Destruction"
    
    # Parse command line arguments
    parse_arguments "$@"
    
    print_info "Project Name: $PROJECT_NAME"
    print_info "AWS Region: $AWS_REGION"
    print_info "Delete Buckets: $DELETE_BUCKETS"
    echo ""
    
    # Check prerequisites
    check_aws_cli
    
    # Confirm deletion
    confirm_deletion
    
    # Delete stacks in reverse order
    delete_gateway_stack
    delete_cognito_stack
    delete_vep_stack
    
    # Delete S3 buckets if requested
    if [[ "$DELETE_BUCKETS" == "true" ]]; then
        delete_all_buckets
    else
        print_header "S3 Buckets Retained"
        print_info "S3 buckets were not deleted. To delete them, run:"
        echo "  $0 --delete-buckets --project-name $PROJECT_NAME --region $AWS_REGION"
        echo ""
        print_info "Or manually delete using AWS CLI:"
        local buckets=$(list_project_buckets)
        for bucket in $buckets; do
            if bucket_exists "$bucket"; then
                echo "  aws s3 rb s3://${bucket} --force --region $AWS_REGION"
            fi
        done
        echo ""
    fi
    
    print_header "Destruction Complete"
    print_success "All requested resources have been deleted!"
}

# Run main function with all arguments
main "$@"
