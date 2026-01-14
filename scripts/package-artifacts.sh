#!/usr/bin/env bash

################################################################################
# Package and Upload Artifacts Script
# 
# This script packages the Lambda function code, SageMaker inference code,
# and agent code, then uploads them to S3 for CloudFormation deployment.
#
# Usage:
#   ./package-artifacts.sh --project-name NAME --region REGION
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

# Print colored message
print_message() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
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

# Print info message
print_info() {
    print_message "$BLUE" "ℹ $1"
}

# Parse command line arguments
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
            --help)
                echo "Usage: $0 --project-name NAME --region REGION"
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1"
                ;;
        esac
    done
}

# Get AWS account ID
get_account_id() {
    aws sts get-caller-identity --query Account --output text --region "$AWS_REGION"
}

# Create S3 bucket if it doesn't exist
create_bucket() {
    local account_id=$(get_account_id)
    ARTIFACTS_BUCKET="${PROJECT_NAME}-artifacts-${account_id}"
    
    print_info "Checking S3 bucket..."
    
    # Create single artifacts bucket for all code
    if aws s3 ls "s3://${ARTIFACTS_BUCKET}" --region "$AWS_REGION" 2>/dev/null; then
        print_info "Artifacts bucket already exists: ${ARTIFACTS_BUCKET}"
    else
        print_info "Creating artifacts bucket: ${ARTIFACTS_BUCKET}"
        if [[ "$AWS_REGION" == "us-east-1" ]]; then
            aws s3 mb "s3://${ARTIFACTS_BUCKET}" --region "$AWS_REGION"
        else
            aws s3api create-bucket --bucket "${ARTIFACTS_BUCKET}" --region "$AWS_REGION" --create-bucket-configuration LocationConstraint="$AWS_REGION"
        fi
        print_success "Artifacts bucket created"
    fi
}

# Package Lambda function code
package_lambda_code() {
    print_info "Packaging Lambda function code..."
    
    local lambda_dir="${PROJECT_ROOT}/vep_endpoint/lambda_function"
    LAMBDA_ZIP=$(mktemp).zip
    
    # Check if Lambda directory exists
    if [[ ! -d "$lambda_dir" ]]; then
        error_exit "Lambda function directory not found: $lambda_dir"
    fi
    
    # Create zip file
    (cd "$lambda_dir" && zip -r "$LAMBDA_ZIP" . -x "*.pyc" -x "__pycache__/*" -x "*.md" -x ".DS_Store" -x "*.log" -x "test_*" -x "*_test.py" -x "tests/*") > /dev/null
    
    print_success "Lambda code packaged: $LAMBDA_ZIP"
}

# Package inference code
package_inference_code() {
    print_info "Packaging inference code..."
    
    local inference_dir="${PROJECT_ROOT}/vep_endpoint/inference_code"
    local temp_dir=$(mktemp -d)
    INFERENCE_TAR="${temp_dir}/inference_code.tar.gz"
    
    # Check if inference directory exists
    if [[ ! -d "$inference_dir" ]]; then
        error_exit "Inference code directory not found: $inference_dir"
    fi
    
    # Create tar.gz file (macOS compatible)
    # Create a temporary directory with the 'code' structure
    local staging_dir="${temp_dir}/staging"
    mkdir -p "${staging_dir}/code"
    cp -r "$inference_dir"/* "${staging_dir}/code/"
    
    (cd "$staging_dir" && tar -czf "$INFERENCE_TAR" code) > /dev/null 2>&1
    
    print_success "Inference code packaged: $INFERENCE_TAR"
}

# Package agent code
package_agent_code() {
    print_info "Packaging agent code..."
    
    local agent_dir="${PROJECT_ROOT}/agent"
    AGENT_ZIP=$(mktemp).zip
    
    # Check if agent directory exists
    if [[ ! -d "$agent_dir" ]]; then
        error_exit "Agent directory not found: $agent_dir"
    fi
    
    # Create zip file
    (cd "$agent_dir" && zip -r "$AGENT_ZIP" . -x "*.pyc" -x "__pycache__/*" -x "*.md" -x ".DS_Store" -x "*.log" -x "test_*" -x "*_test.py" -x "tests/*") > /dev/null
    
    print_success "Agent code packaged: $AGENT_ZIP"
}

# Upload artifacts to S3
upload_artifacts() {
    print_info "Uploading Lambda code to S3..."
    aws s3 cp "$LAMBDA_ZIP" "s3://${ARTIFACTS_BUCKET}/lambda/lambda_function.zip" --region "$AWS_REGION"
    print_success "Lambda code uploaded to s3://${ARTIFACTS_BUCKET}/lambda/lambda_function.zip"
    
    print_info "Uploading agent code to S3..."
    aws s3 cp "$AGENT_ZIP" "s3://${ARTIFACTS_BUCKET}/agent/agent.zip" --region "$AWS_REGION"
    print_success "Agent code uploaded to s3://${ARTIFACTS_BUCKET}/agent/agent.zip"
    
    print_info "Uploading inference code to S3..."
    aws s3 cp "$INFERENCE_TAR" "s3://${ARTIFACTS_BUCKET}/inference-code/inference_code.tar.gz" --region "$AWS_REGION"
    print_success "Inference code uploaded to s3://${ARTIFACTS_BUCKET}/inference-code/inference_code.tar.gz"
}

# Main execution
main() {
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "Package and Upload Artifacts"
    print_message "$BLUE" "=========================================="
    echo ""
    
    parse_arguments "$@"
    
    print_info "Project Name: $PROJECT_NAME"
    print_info "AWS Region: $AWS_REGION"
    echo ""
    
    # Create bucket (sets ARTIFACTS_BUCKET)
    create_bucket
    
    # Package artifacts (sets LAMBDA_ZIP, AGENT_ZIP, and INFERENCE_TAR)
    package_lambda_code
    package_agent_code
    package_inference_code
    
    # Upload to S3
    upload_artifacts
    
    # Cleanup temp files
    rm -f "$LAMBDA_ZIP" "$AGENT_ZIP" "$INFERENCE_TAR"
    
    echo ""
    print_success "All artifacts packaged and uploaded successfully!"
    echo ""
    print_info "Artifacts bucket: s3://${ARTIFACTS_BUCKET}"
    print_info "  - Lambda code: lambda/lambda_function.zip"
    print_info "  - Agent code: agent/agent.zip"
    print_info "  - Inference code: inference/inference_code.tar.gz"
}

main "$@"
