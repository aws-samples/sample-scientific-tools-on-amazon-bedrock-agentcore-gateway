# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from dataclasses import dataclass
from typing import Optional
import time
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnParameter,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    aws_applicationautoscaling as applicationautoscaling,
    aws_cloudwatch as cloudwatch,
    aws_s3_assets as s3_assets,
    aws_lambda as _lambda,
    aws_ssm as ssm,
)
from constructs import Construct
import logging


@dataclass
class VEPEndpointConfig:
    """Configuration class for Protein Enginering Stack parameters."""

    instance_type: str = "ml.g6.2xlarge"
    model_id: str = "chandar-lab/AMPLIFY_350M"
    s3_bucket_name: Optional[str] = None
    min_capacity: int = 1
    max_capacity: int = 2
    max_concurrent_invocations: int = 4
    enable_autoscaling: bool = True
    # Resource cleanup configuration
    logs_removal_policy: RemovalPolicy = RemovalPolicy.DESTROY

    def __post_init__(self):
        """Validate configuration parameters after initialization."""
        # Validate instance type
        valid_instance_types = {
            "ml.g6.2xlarge",
            "ml.g6.4xlarge",
            "ml.g6.8xlarge",
            "ml.g6.12xlarge",
            "ml.g6e.2xlarge",
            "ml.g6e.4xlarge",
            "ml.g6e.8xlarge",
            "ml.g6e.12xlarge",
            "ml.g5.2xlarge",
            "ml.g5.4xlarge",
            "ml.g5.8xlarge",
            "ml.g5.12xlarge",
            "ml.p4d.24xlarge",
            "ml.p3.2xlarge",
            "ml.p3.8xlarge",
            "ml.p3.16xlarge",
        }
        if self.instance_type not in valid_instance_types:
            raise ValueError(
                f"Instance type must be GPU-enabled. Got: {self.instance_type}"
            )

        # Validate capacity settings
        if self.min_capacity < 0:
            raise ValueError(
                f"Minimum capacity cannot be negative. Got: {self.min_capacity}"
            )
        if self.max_capacity < 1:
            raise ValueError(
                f"Maximum capacity must be at least 1. Got: {self.max_capacity}"
            )
        if self.min_capacity > self.max_capacity:
            raise ValueError(
                f"Minimum capacity ({self.min_capacity}) cannot exceed maximum capacity ({self.max_capacity})"
            )

        # Validate concurrent invocations
        if self.max_concurrent_invocations < 1:
            raise ValueError(
                f"Maximum concurrent invocations must be at least 1. Got: {self.max_concurrent_invocations}"
            )
        if self.max_concurrent_invocations > 1000:
            raise ValueError(
                f"Maximum concurrent invocations cannot exceed 1000. Got: {self.max_concurrent_invocations}"
            )

        # Validate model ID
        if not self.model_id or not self.model_id.strip():
            raise ValueError("Model ID cannot be empty")

        # Validate S3 bucket name if provided
        if self.s3_bucket_name:
            import re

            bucket_name = self.s3_bucket_name.strip()
            if len(bucket_name) < 3 or len(bucket_name) > 63:
                raise ValueError(
                    f"S3 bucket name must be between 3 and 63 characters. Got: {len(bucket_name)}"
                )
            if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", bucket_name):
                raise ValueError(f"Invalid S3 bucket name format: {bucket_name}")
            if "--" in bucket_name:
                raise ValueError(
                    f"S3 bucket name cannot contain consecutive hyphens: {bucket_name}"
                )
            if bucket_name != bucket_name.lower():
                raise ValueError(f"S3 bucket name must be lowercase: {bucket_name}")


class VEPEndpointStack(Stack):
    """
    CDK Stack for deploying VEP endpoint stack.

    This stack creates all necessary resources for a SageMaker async inference endpoint
    including the model, endpoint configuration, endpoint, IAM roles, S3 bucket,
    auto scaling policies, and CloudWatch monitoring. It also includes a lambda function
    for invokation and some example code for MCP integration.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Optional[VEPEndpointConfig] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Set up logging
        self.logger = logging.getLogger(__name__)

        # Use provided config or create default
        self.config = config or VEPEndpointConfig()

        # Define CDK parameters for runtime configuration
        self._define_parameters()

        # Load context-specific configuration
        self._load_context_configuration()

        # Initialize configuration values from parameters and context
        self._initialize_configuration()

    def _define_parameters(self) -> None:
        """Define CDK parameters for stack configuration."""
        self.instance_type_param = CfnParameter(
            self,
            "InstanceType",
            type="String",
            default=self.config.instance_type,
            description="EC2 instance type for SageMaker endpoint",
            allowed_values=[
                "ml.g6.2xlarge",
                "ml.g6.4xlarge",
                "ml.g6.8xlarge",
                "ml.g6.12xlarge",
                "ml.g6e.2xlarge",
                "ml.g6e.4xlarge",
                "ml.g6e.8xlarge",
                "ml.g6e.12xlarge",
                "ml.g5.2xlarge",
                "ml.g5.4xlarge",
                "ml.g5.8xlarge",
                "ml.g5.12xlarge",
                "ml.p4d.24xlarge",
                "ml.p3.2xlarge",
                "ml.p3.8xlarge",
                "ml.p3.16xlarge",
            ],
        )

        self.model_id_param = CfnParameter(
            self,
            "ModelId",
            type="String",
            default=self.config.model_id,
            description="HuggingFace model identifier for AMPLIFY model",
            min_length=1,
            max_length=256,
        )

        self.s3_bucket_name_param = CfnParameter(
            self,
            "S3BucketNameParam",
            type="String",
            default=self.config.s3_bucket_name or "",
            description="S3 bucket name for async inference (leave empty for auto-generated)",
            max_length=63,
        )

        self.min_capacity_param = CfnParameter(
            self,
            "MinCapacity",
            type="Number",
            default=self.config.min_capacity,
            description="Minimum number of instances for auto scaling",
            min_value=0,
            max_value=10,
        )

        self.max_capacity_param = CfnParameter(
            self,
            "MaxCapacity",
            type="Number",
            default=self.config.max_capacity,
            description="Maximum number of instances for auto scaling",
            min_value=1,
            max_value=20,
        )

        self.max_concurrent_invocations_param = CfnParameter(
            self,
            "MaxConcurrentInvocations",
            type="Number",
            default=self.config.max_concurrent_invocations,
            description="Maximum concurrent invocations per instance",
            min_value=1,
            max_value=1000,
        )

    def _load_context_configuration(self) -> None:
        """Load environment-specific configuration from CDK context."""
        # Load context values for environment-specific deployments
        self.project_name = self.node.try_get_context("project_name") or "protein-agent"

    def _initialize_configuration(self) -> None:
        """Initialize final configuration values from parameters and context."""
        # Use parameter values if provided, otherwise use config defaults
        self.final_instance_type = self.instance_type_param.value_as_string
        self.final_model_id = self.model_id_param.value_as_string
        self.final_s3_bucket_name = self.s3_bucket_name_param.value_as_string
        self.final_min_capacity = self.min_capacity_param.value_as_number
        self.final_max_capacity = self.max_capacity_param.value_as_number
        self.final_max_concurrent_invocations = (
            self.max_concurrent_invocations_param.value_as_number
        )

        # Create resource naming convention with stable functionality prefix
        self.resource_prefix = f"{self.project_name}-{int(time.time())}"

        self.model_name = "amplify-vep-model"
        self.endpoint_config_name = "amplify-vep-config"
        self.endpoint_name = "amplify-vep-endpoint"

        # Create IAM roles and permissions
        self._create_iam_roles()

        # Create S3 bucket and storage configuration
        self._create_s3_bucket_and_storage()

        # Create SageMaker model with inference code
        self._create_sagemaker_model()

        # Create endpoint configuration with async inference settings
        self._create_endpoint_configuration()

        # Deploy SageMaker endpoint
        self._create_sagemaker_endpoint()

        # Create Lambda function for async endpoint integration
        self._create_lambda_function()

        # Implement auto scaling configuration (if enabled)
        if self.config.enable_autoscaling:
            self._create_auto_scaling_configuration()

        # Configure resource cleanup and removal policies
        self._configure_resource_cleanup_policies()

        # Create comprehensive stack outputs for all important resource references
        self._create_stack_summary_outputs()

    def _create_iam_roles(self) -> None:
        """Create IAM roles and permissions for SageMaker resources."""
        # Create SageMaker execution role with proper trust relationship
        self.sagemaker_execution_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            role_name=f"{self.resource_prefix}-sagemaker-execution-role",
            description="Execution role for SageMaker async inference endpoint",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            # Use scoped-down inline policies instead of AmazonSageMakerFullAccess
            inline_policies={
                "SageMakerModelPermissions": iam.PolicyDocument(
                    statements=[
                        # Core SageMaker permissions for model operations
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sagemaker:CreateModel",
                                "sagemaker:DescribeModel",
                                "sagemaker:DeleteModel",
                                "sagemaker:CreateEndpointConfig",
                                "sagemaker:DescribeEndpointConfig",
                                "sagemaker:DeleteEndpointConfig",
                                "sagemaker:CreateEndpoint",
                                "sagemaker:DescribeEndpoint",
                                "sagemaker:DeleteEndpoint",
                                "sagemaker:InvokeEndpoint",
                                "sagemaker:InvokeEndpointAsync",
                            ],
                            resources=[
                                f"arn:aws:sagemaker:{self.region}:{self.account}:model/{self.model_name}",
                                f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint-config/{self.endpoint_config_name}",
                                f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{self.endpoint_name}",
                            ],
                        )
                    ]
                )
            },
        )

        # S3 policy will be created after bucket creation with actual bucket ARN

        # Create inline policy for ECR access (for PyTorch inference container)
        ecr_policy = iam.PolicyDocument(
            statements=[
                # Allow pulling PyTorch inference container images
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        # "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                    ],
                    resources=[
                        f"arn:aws:ecr:{self.region}:763104351884:repository/pytorch-inference"
                    ],
                ),
                # Allow ECR authorization token retrieval (no resource restriction)
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ecr:GetAuthorizationToken"],
                    resources=["*"],
                ),
            ]
        )

        # Create inline policy for CloudWatch logging
        cloudwatch_policy = iam.PolicyDocument(
            statements=[
                # Allow creating and writing to CloudWatch log groups and streams for endpoint
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                    ],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/Endpoints/{self.resource_prefix}-*",
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/Endpoints/{self.resource_prefix}-*:*",
                    ],
                ),
                # Allow publishing CloudWatch metrics. Policy condition limits * resource
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["cloudwatch:PutMetricData"],
                    resources=["*"],
                    conditions={
                        "StringEquals": {"cloudwatch:namespace": "AWS/SageMaker"}
                    },
                ),
            ]
        )

        # S3 policy will be created after bucket creation

        # Attach ECR and CloudWatch policies immediately
        self.sagemaker_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "ECRAccessPolicy",
                policy_name="ECRContainerAccess",
                document=ecr_policy,
            )
        )

        self.sagemaker_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "CloudWatchLogsPolicy",
                policy_name="CloudWatchLogsAccess",
                document=cloudwatch_policy,
            )
        )

        # Add CDK asset bucket access immediately so SageMaker model can access inference code
        self.cdk_asset_policy = iam.Policy(
            self,
            "CDKAssetBucketAccessPolicy",
            policy_name="CDKAssetBucketAccess",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["s3:GetObject", "s3:ListBucket"],
                        resources=[
                            f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}",
                            f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}/*",
                        ],
                    ),
                ]
            ),
        )
        self.sagemaker_execution_role.attach_inline_policy(self.cdk_asset_policy)

    def _create_s3_bucket_and_storage(self) -> None:
        """Create S3 bucket and storage configuration for async inference."""
        # Create S3 bucket (auto-generated name)
        self.async_inference_bucket = self._create_new_bucket()
        self.bucket_created = True

        # Set up input and output prefixes for async inference
        self.input_prefix = "async-inference-input/"
        self.output_prefix = "async-inference-output/"
        self.model_artifacts_prefix = "model-artifacts/"
        self.inference_code_prefix = "inference-code/"

        # Update IAM policies with actual bucket ARN
        self._update_iam_policies_with_bucket_info()

        # Create stack outputs for S3 bucket information
        self._create_s3_outputs()

        self.logger.info("S3 bucket and storage configuration completed successfully")

    def _create_new_bucket(self) -> s3.Bucket:
        """
        Create a new S3 bucket with proper security settings and reliable deletion.

        This method addresses common S3 bucket deletion issues by:
        1. Properly configuring auto_delete_objects only when removal_policy is DESTROY
        2. Disabling versioning to prevent deletion conflicts
        3. Avoiding server access logging when auto-delete is enabled
        4. Adding proper metadata for CDK's auto-delete process
        """
        # Use the safer default: always preserve data
        # This avoids the CloudFormation S3 deletion issues entirely
        self.logger.info("S3 bucket configured with RETAIN policy (safe mode)")
        self.logger.info("Bucket and data will be preserved when stack is deleted")
        self.logger.info(
            "To enable auto-delete for development, manually empty and delete the bucket after stack deletion"
        )

        # Use custom bucket name if provided, otherwise let CDK auto-generate
        bucket_name = self.final_s3_bucket_name if self.final_s3_bucket_name else None

        # Create bucket with safe configuration - always preserve data
        bucket = s3.Bucket(
            self,
            "AsyncInferenceBucket",
            bucket_name=bucket_name,
            # Disable versioning to prevent conflicts
            versioned=False,
            # Use S3 managed encryption for security
            encryption=s3.BucketEncryption.S3_MANAGED,
            # Block all public access for security
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            # Always use RETAIN to avoid CloudFormation deletion issues
            removal_policy=RemovalPolicy.RETAIN,
            # Never enable auto-delete to avoid the CloudFormation bug
            auto_delete_objects=False,
            # Enable server access logging for audit trail
            server_access_logs_prefix="access-logs/",
            # Enforce SSL for all requests (CDK Nag AwsSolutions-S10)
            enforce_ssl=True,
        )

        return bucket

    def _update_iam_policies_with_bucket_info(self) -> None:
        """Update IAM policies with actual S3 bucket information."""
        # Create updated S3 policy with actual bucket ARN
        updated_s3_policy = iam.PolicyDocument(
            statements=[
                # Allow listing buckets (required for SageMaker)
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:ListBucket"],
                    resources=[self.async_inference_bucket.bucket_arn],
                ),
                # Allow read/write access to async inference input/output paths
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.input_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/{self.output_prefix}*",
                    ],
                ),
                # Allow access to model artifacts and inference code
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.model_artifacts_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/{self.inference_code_prefix}*",
                    ],
                ),
            ]
        )

        # Replace the existing S3 policy with updated one
        self.s3_access_policy = iam.Policy(
            self,
            "S3AsyncInferenceAccessPolicy",
            policy_name="S3AsyncInferenceAccess",
            document=updated_s3_policy,
        )
        self.sagemaker_execution_role.attach_inline_policy(self.s3_access_policy)

    def get_storage_configuration(self) -> dict:
        """Return storage configuration details for async inference."""
        return {
            "bucket_name": self.async_inference_bucket.bucket_name,
            "bucket_arn": self.async_inference_bucket.bucket_arn,
            "input_prefix": self.input_prefix,
            "output_prefix": self.output_prefix,
            "model_artifacts_prefix": self.model_artifacts_prefix,
            "inference_code_prefix": self.inference_code_prefix,
            "input_path": f"s3://{self.async_inference_bucket.bucket_name}/{self.input_prefix}",
            "output_path": f"s3://{self.async_inference_bucket.bucket_name}/{self.output_prefix}",
            "bucket_created": self.bucket_created,
        }

    def _create_s3_outputs(self) -> None:
        """Create CDK outputs for S3 bucket information."""
        CfnOutput(
            self,
            "S3BucketName",
            value=self.async_inference_bucket.bucket_name,
            description="S3 bucket name for async inference I/O",
            export_name=f"{self.resource_prefix}-s3-bucket-name",
        )

        CfnOutput(
            self,
            "S3BucketArn",
            value=self.async_inference_bucket.bucket_arn,
            description="S3 bucket ARN for async inference I/O",
            export_name=f"{self.resource_prefix}-s3-bucket-arn",
        )

        CfnOutput(
            self,
            "AsyncInferenceBucketName",
            value=self.async_inference_bucket.bucket_name,
            description="S3 bucket name for async inference I/O",
            export_name=f"{self.resource_prefix}-async-inference-bucket-name",
        )

        CfnOutput(
            self,
            "AsyncInferenceBucketArn",
            value=self.async_inference_bucket.bucket_arn,
            description="S3 bucket ARN for async inference I/O",
            export_name=f"{self.resource_prefix}-async-inference-bucket-arn",
        )

        CfnOutput(
            self,
            "AsyncInferenceInputPath",
            value=f"s3://{self.async_inference_bucket.bucket_name}/{self.input_prefix}",
            description="S3 path for async inference input files",
            export_name=f"{self.resource_prefix}-async-inference-input-path",
        )

        CfnOutput(
            self,
            "AsyncInferenceOutputPath",
            value=f"s3://{self.async_inference_bucket.bucket_name}/{self.output_prefix}",
            description="S3 path for async inference output files",
            export_name=f"{self.resource_prefix}-async-inference-output-path",
        )

        CfnOutput(
            self,
            "BucketCreatedByStack",
            value="true" if self.bucket_created else "false",
            description="Whether the S3 bucket was created by this stack",
            export_name=f"{self.resource_prefix}-bucket-created-by-stack",
        )

    def _create_sagemaker_model(self) -> None:
        """Create SageMaker model using PyTorch inference container with custom inference code."""
        # Create tar.gz asset from inference code directory
        self._prepare_inference_code_tarball()

        # Upload inference code as S3 asset (now as tar.gz)
        self.inference_code_asset = s3_assets.Asset(
            self,
            "InferenceCodeAsset",
            path="vep_endpoint/inference_code.tar.gz",
        )

        # Use PyTorch inference container (same as your working deploy_async.py)
        pytorch_inference_image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker"

        # Create SageMaker model with PyTorch container and custom inference code
        self.sagemaker_model = sagemaker.CfnModel(
            self,
            "AmplifyModel",
            model_name=self.model_name,
            execution_role_arn=self.sagemaker_execution_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                # Use PyTorch inference container
                image=pytorch_inference_image_uri,
                # Point to the tar.gz asset containing inference code
                model_data_url=self.inference_code_asset.s3_object_url,
                # Configure environment variables for AMPLIFY model (same as your deploy_async.py)
                environment={
                    # Set the AMPLIFY model ID from parameters
                    "AMPLIFY_MODEL_ID": self.final_model_id,
                    # Configure SageMaker inference settings
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/code",
                    # Set timeout values for long-running inference
                    "TS_DEFAULT_RESPONSE_TIMEOUT": "900",
                    "MODEL_SERVER_TIMEOUT_ENV": "900",
                    # Optimize for single-threaded inference
                    "OMP_NUM_THREADS": "1",
                    # Enable unbuffered Python output for better logging
                    "PYTHONUNBUFFERED": "1",
                    # Set model cache directory
                    "TRANSFORMERS_CACHE": "/tmp/transformers_cache",
                    # Configure PyTorch settings for GPU inference
                    "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:512",
                },
            ),
            # Add tags for resource management
            tags=[
                cdk.CfnTag(key="Project", value=self.project_name),
                # cdk.CfnTag(key="Environment", value=self.deployment_environment),
                cdk.CfnTag(key="ModelType", value="AMPLIFY"),
                cdk.CfnTag(key="InferenceType", value="Async"),
            ],
        )

        # Ensure model creation depends on IAM role and policies
        self.sagemaker_model.add_dependency(
            self.sagemaker_execution_role.node.default_child
        )
        self.sagemaker_model.add_dependency(self.cdk_asset_policy.node.default_child)

        # Create stack outputs for model information
        self._create_model_outputs()

    def _create_model_outputs(self) -> None:
        """Create CDK outputs for SageMaker model information."""

        CfnOutput(
            self,
            "ModelName",
            value=self.model_name,
            description="Name of the created SageMaker model",
            export_name=f"{self.resource_prefix}-model-name",
        )

        CfnOutput(
            self,
            "SageMakerModelName",
            value=self.model_name,
            description="Name of the created SageMaker model",
            export_name=f"{self.resource_prefix}-sagemaker-model-name",
        )

        CfnOutput(
            self,
            "SageMakerModelArn",
            value=f"arn:aws:sagemaker:{self.region}:{self.account}:model/{self.model_name}",
            description="ARN of the created SageMaker model",
            export_name=f"{self.resource_prefix}-sagemaker-model-arn",
        )

        CfnOutput(
            self,
            "InferenceCodeS3Location",
            value=self.inference_code_asset.s3_object_url,
            description="S3 location of the uploaded inference code tar.gz archive",
            export_name=f"{self.resource_prefix}-inference-code-s3-location",
        )

        CfnOutput(
            self,
            "AmplifyModelId",
            value=self.final_model_id,
            description="AMPLIFY model ID used for inference",
            export_name=f"{self.resource_prefix}-amplify-model-id",
        )

    def _prepare_inference_code_tarball(self) -> None:
        """Create tar.gz file from inference code directory before CDK asset creation."""
        import tarfile
        import os

        # Create tar.gz file in the same directory as the inference code
        tar_path = "vep_endpoint/inference_code.tar.gz"

        # Remove existing tar.gz if it exists
        if os.path.exists(tar_path):
            os.remove(tar_path)

        # Create tar.gz archive with inference code (following your deploy_async.py pattern)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add("vep_endpoint/inference_code", arcname="code")

        self.logger.info(f"Created inference code tar.gz: {tar_path}")

    def _create_endpoint_configuration(self) -> None:
        """Create endpoint configuration with async inference settings."""

        # Create endpoint configuration with async inference support
        self.endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "AsyncEndpointConfig",
            endpoint_config_name=self.endpoint_config_name,
            # Configure production variants with instance type and scaling parameters
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    variant_name="primary",
                    model_name=self.model_name,
                    # Start with 1 instance, auto scaling will manage capacity
                    initial_instance_count=1,
                    instance_type=self.final_instance_type,
                    # Set initial variant weight for traffic distribution
                    initial_variant_weight=1.0,
                    # Configure container startup health check timeout
                    container_startup_health_check_timeout_in_seconds=600,
                    # Set model data download timeout for large models
                    model_data_download_timeout_in_seconds=900,
                )
            ],
            # Configure async inference settings
            async_inference_config=sagemaker.CfnEndpointConfig.AsyncInferenceConfigProperty(
                # Configure S3 output path for async inference results
                output_config=sagemaker.CfnEndpointConfig.AsyncInferenceOutputConfigProperty(
                    s3_output_path=f"s3://{self.async_inference_bucket.bucket_name}/{self.output_prefix}",
                    # Configure notification settings (optional)
                    # notification_config can be added here for SNS notifications
                    s3_failure_path=f"s3://{self.async_inference_bucket.bucket_name}/async-inference-failures/",
                ),
                # Configure client settings for concurrent invocations
                client_config=sagemaker.CfnEndpointConfig.AsyncInferenceClientConfigProperty(
                    max_concurrent_invocations_per_instance=int(
                        self.final_max_concurrent_invocations
                    )
                ),
            ),
            # Note: DataCaptureConfig is not supported with AsyncInferenceConfig
            # For async inference monitoring, use CloudWatch metrics and logs instead
            # Add tags for resource management
            tags=[
                cdk.CfnTag(key="Project", value=self.project_name),
                cdk.CfnTag(key="ModelType", value="AMPLIFY"),
                cdk.CfnTag(key="InferenceType", value="Async"),
                cdk.CfnTag(key="ConfigType", value="AsyncEndpointConfig"),
            ],
        )

        # Ensure endpoint config creation depends on model
        self.endpoint_config.add_dependency(self.sagemaker_model)

        # Create stack outputs for endpoint configuration information
        self._create_endpoint_config_outputs()

    def _create_endpoint_config_outputs(self) -> None:
        """Create CDK outputs for endpoint configuration information."""

        CfnOutput(
            self,
            "EndpointConfigName",
            value=self.endpoint_config_name,
            description="Name of the created SageMaker endpoint configuration",
            export_name=f"{self.resource_prefix}-endpoint-config-name",
        )

        CfnOutput(
            self,
            "EndpointConfigArn",
            value=f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint-config/{self.endpoint_config_name}",
            description="ARN of the created SageMaker endpoint configuration",
            export_name=f"{self.resource_prefix}-endpoint-config-arn",
        )

        CfnOutput(
            self,
            "AsyncInferenceConfigOutputPath",
            value=f"s3://{self.async_inference_bucket.bucket_name}/{self.output_prefix}",
            description="S3 path where async inference results will be stored (from endpoint config)",
            export_name=f"{self.resource_prefix}-async-config-output-path",
        )

        CfnOutput(
            self,
            "AsyncInferenceFailurePath",
            value=f"s3://{self.async_inference_bucket.bucket_name}/async-inference-failures/",
            description="S3 path where async inference failures will be stored",
            export_name=f"{self.resource_prefix}-async-failure-path",
        )

        # Note: Data capture is not supported with async inference
        # Monitoring is handled through CloudWatch metrics and logs instead

        CfnOutput(
            self,
            "MaxConcurrentInvocationsOutput",
            value=str(int(self.final_max_concurrent_invocations)),
            description="Maximum concurrent invocations per instance configured",
            export_name=f"{self.resource_prefix}-max-concurrent-invocations",
        )

    def _create_sagemaker_endpoint(self) -> None:
        """Create SageMaker endpoint using CfnEndpoint construct."""
        # Create SageMaker endpoint with reference to endpoint configuration
        self.sagemaker_endpoint = sagemaker.CfnEndpoint(
            self,
            "AsyncEndpoint",
            endpoint_name=self.endpoint_name,
            endpoint_config_name=self.endpoint_config_name,
            # Add tags for resource management
            tags=[
                cdk.CfnTag(key="Project", value=self.project_name),
                cdk.CfnTag(key="ModelType", value="AMPLIFY"),
                cdk.CfnTag(key="InferenceType", value="Async"),
                cdk.CfnTag(key="ResourceType", value="Endpoint"),
            ],
        )

        # Implement proper dependency management between model, config, and endpoint
        # Endpoint depends on endpoint configuration
        self.sagemaker_endpoint.add_dependency(self.endpoint_config)

        # Endpoint configuration already depends on model (set in _create_endpoint_configuration)
        # This creates the proper dependency chain: Model -> EndpointConfig -> Endpoint

        # Create stack outputs for endpoint information
        self._create_endpoint_outputs()

    def _create_endpoint_outputs(self) -> None:
        """Create CDK outputs for SageMaker endpoint information."""

        CfnOutput(
            self,
            "EndpointName",
            value=self.endpoint_name,
            description="Name of the created SageMaker async inference endpoint",
            export_name=f"{self.resource_prefix}-sagemaker-endpoint-name",
        )

        CfnOutput(
            self,
            "EndpointArn",
            value=f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{self.endpoint_name}",
            description="ARN of the created SageMaker async inference endpoint",
            export_name=f"{self.resource_prefix}-sagemaker-endpoint-arn",
        )

        CfnOutput(
            self,
            "SageMakerEndpointName",
            value=self.endpoint_name,
            description="Name of the created SageMaker async inference endpoint",
            export_name=f"{self.resource_prefix}-sagemaker-endpoint-name-alt",
        )

        CfnOutput(
            self,
            "SageMakerEndpointArn",
            value=f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{self.endpoint_name}",
            description="ARN of the created SageMaker async inference endpoint",
            export_name=f"{self.resource_prefix}-sagemaker-endpoint-arn-alt",
        )

    def _create_lambda_function(self) -> None:
        """Create Lambda function for async endpoint integration."""
        # Create Lambda execution role with basic execution permissions
        # This role provides the Lambda function with permissions to:
        # 1. Write logs to CloudWatch (via AWSLambdaBasicExecutionRole)
        # 2. Invoke SageMaker async endpoint (via custom policy)
        # 3. Access S3 bucket for input/output/failure prefixes (via custom policy)
        self.lambda_execution_role = iam.Role(
            self,
            "AsyncEndpointLambdaRole",
            role_name=f"{self.resource_prefix}-lambda-execution-role",
            description="Execution role for Lambda function that integrates with SageMaker async endpoint",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                # Provides basic Lambda execution permissions including CloudWatch Logs
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add SageMaker permissions to Lambda role
        # Grant permission to invoke the specific SageMaker async endpoint
        sagemaker_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sagemaker:InvokeEndpointAsync",  # Required to submit async inference requests
                        "sagemaker:DescribeEndpoint",  # Required to check endpoint status
                    ],
                    resources=[
                        #
                        f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/amplify-vep-endpoint"
                    ],
                ),
            ]
        )

        # Add S3 permissions to Lambda role with least privilege principle
        s3_policy = iam.PolicyDocument(
            statements=[
                # Allow listing the bucket to check for object existence
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:ListBucket"],
                    resources=[self.async_inference_bucket.bucket_arn],
                ),
                # Allow putting objects in input prefix (for Lambda to upload input data if needed)
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:PutObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.input_prefix}*",
                    ],
                ),
                # Allow getting objects from output and failure prefixes
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.output_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/async-inference-failures/*",
                    ],
                ),
            ]
        )

        # Add CloudWatch permissions to Lambda role for custom metrics and log group management
        cloudwatch_policy = iam.PolicyDocument(
            statements=[
                # Allow Lambda to create and manage CloudWatch log groups
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:DescribeLogGroups",
                        "logs:CreateLogGroup",
                        "logs:DescribeLogStreams",
                        "logs:CreateLogStream",
                    ],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/protein-agent-*-async-endpoint-lambda"
                    ],
                ),
                # Allow Lambda to put custom metrics to CloudWatch
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudwatch:PutMetricData",
                    ],
                    resources=[
                        "*"
                    ],  # CloudWatch metrics don't support resource-level permissions
                    conditions={
                        "StringEquals": {
                            "cloudwatch:namespace": [
                                "SageMaker/AsyncEndpoint/Lambda",
                                "AWS/Lambda",
                            ]
                        }
                    },
                ),
            ]
        )

        # Attach policies to Lambda role
        self.lambda_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "LambdaSageMakerPolicy",
                policy_name="SageMakerAsyncAccess",
                document=sagemaker_policy,
            )
        )

        self.lambda_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "LambdaS3Policy",
                policy_name="S3AsyncInferenceAccess",
                document=s3_policy,
            )
        )

        self.lambda_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "LambdaCloudWatchPolicy",
                policy_name="CloudWatchMetricsAccess",
                document=cloudwatch_policy,
            )
        )

        # Create CDK asset for Lambda function code
        # This packages the Lambda function code and dependencies into a deployment package
        # The asset will be uploaded to the CDK bootstrap S3 bucket and referenced by the Lambda function
        lambda_code_asset = s3_assets.Asset(
            self,
            "LambdaCodeAsset",
            path="vep_endpoint/lambda_function",
            # Exclude unnecessary files from the deployment package to reduce size
            exclude=[
                "*.pyc",
                "__pycache__",
                "*.md",
                ".DS_Store",
                "*.log",
                "test_*",
                "*_test.py",
                "*.pytest_cache",
            ],
        )

        # Store asset reference for potential use in outputs or other resources
        self.lambda_code_asset = lambda_code_asset

        # Create Lambda function with proper deployment package configuration
        self.lambda_function = _lambda.Function(
            self,
            "AsyncEndpointLambda",
            function_name=f"{self.resource_prefix}-async-endpoint-lambda",
            description="Lambda function for SageMaker async endpoint integration with Bedrock Agent Core compatibility",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            # Use the CDK asset for code deployment
            code=_lambda.Code.from_asset(
                "vep_endpoint/lambda_function",
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    "*.md",
                    ".DS_Store",
                    "*.log",
                    "test_*",
                    "*_test.py",
                    "test",
                ],
            ),
            role=self.lambda_execution_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            architecture=_lambda.Architecture.X86_64,
            environment={
                #
                "SAGEMAKER_ENDPOINT_NAME": self.endpoint_name,
                "S3_BUCKET_NAME": self.async_inference_bucket.bucket_name,
                "S3_INPUT_PREFIX": self.input_prefix,
                "S3_OUTPUT_PREFIX": self.output_prefix,
                "S3_FAILURE_PREFIX": "async-inference-failures/",
                "LOG_LEVEL": "INFO",
            },
        )

        # Add tags to Lambda function using CDK Tags
        cdk.Tags.of(self.lambda_function).add("Project", self.project_name)
        cdk.Tags.of(self.lambda_function).add("ResourceType", "Lambda")
        cdk.Tags.of(self.lambda_function).add("Integration", "SageMakerAsync")

        # Ensure proper IAM policy attachment and dependency management
        # Lambda function must be created after SageMaker endpoint and S3 bucket
        # to ensure the IAM policies reference valid resources and environment variables are correct
        self.lambda_function.node.add_dependency(self.sagemaker_endpoint)
        self.lambda_function.node.add_dependency(self.async_inference_bucket)
        self.lambda_function.node.add_dependency(self.lambda_execution_role)

        # Create Lambda function outputs
        self._create_lambda_outputs()

        # Store Lambda function ARN in Systems Manager Parameter Store
        self._store_lambda_arn_in_ssm()

    def _create_lambda_outputs(self) -> None:
        """Create CDK outputs for Lambda function information."""
        CfnOutput(
            self,
            "LambdaFunctionArn",
            value=self.lambda_function.function_arn,
            description="ARN of the Lambda function for async endpoint integration",
            export_name=f"{self.resource_prefix}-lambda-function-arn",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Name of the Lambda function for async endpoint integration",
            export_name=f"{self.resource_prefix}-lambda-function-name",
        )

        CfnOutput(
            self,
            "LambdaExecutionRoleArn",
            value=self.lambda_execution_role.role_arn,
            description="ARN of the Lambda execution role",
            export_name=f"{self.resource_prefix}-lambda-execution-role-arn",
        )

        CfnOutput(
            self,
            "LambdaCodeAssetS3Bucket",
            value=self.lambda_code_asset.s3_bucket_name,
            description="S3 bucket containing the Lambda deployment package",
            export_name=f"{self.resource_prefix}-lambda-code-bucket",
        )

        CfnOutput(
            self,
            "LambdaCodeAssetS3Key",
            value=self.lambda_code_asset.s3_object_key,
            description="S3 object key for the Lambda deployment package",
            export_name=f"{self.resource_prefix}-lambda-code-key",
        )

        CfnOutput(
            self,
            "LambdaInvokeUrl",
            value=f"https://lambda.{self.region}.amazonaws.com/2015-03-31/functions/{self.lambda_function.function_name}/invocations",
            description="URL for invoking the Lambda function directly via AWS API",
            export_name=f"{self.resource_prefix}-lambda-invoke-url",
        )

        CfnOutput(
            self,
            "EndpointInvokeUrl",
            #
            value=f"https://runtime.sagemaker.{self.region}.amazonaws.com/endpoints/amplify-vep-endpoint/async-invocations",
            description="URL for invoking the async inference endpoint",
            export_name=f"{self.resource_prefix}-endpoint-invoke-url",
        )

    def _store_lambda_arn_in_ssm(self) -> None:
        """Store Lambda function ARN in Systems Manager Parameter Store for AgentCore Gateway."""
        # Create SSM parameter for Lambda function ARN
        self.lambda_arn_parameter = ssm.StringParameter(
            self,
            "LambdaFunctionArnParameter",
            #
            parameter_name=f"/sagemaker-async/lambda-function-arn",
            string_value=self.lambda_function.function_arn,
            description=f"Lambda function ARN for SageMaker async endpoint integration",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Ensure parameter creation depends on Lambda function
        self.lambda_arn_parameter.node.add_dependency(self.lambda_function)

        # Create additional parameter for easier discovery by gateway deployment
        self.lambda_arn_parameter_alt = ssm.StringParameter(
            self,
            "LambdaFunctionArnParameterAlt",
            #
            parameter_name=f"/protein-agent/lambda-function-arn",
            string_value=self.lambda_function.function_arn,
            description=f"Lambda function ARN for protein engineering agent",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Ensure parameter creation depends on Lambda function
        self.lambda_arn_parameter_alt.node.add_dependency(self.lambda_function)

        # Create output for the SSM parameter name
        CfnOutput(
            self,
            "LambdaArnParameterName",
            value=self.lambda_arn_parameter.parameter_name,
            description="SSM Parameter Store name containing the Lambda function ARN",
            export_name=f"{self.resource_prefix}-lambda-arn-parameter-name",
        )

        CfnOutput(
            self,
            "LambdaArnParameterNameAlt",
            value=self.lambda_arn_parameter_alt.parameter_name,
            description="Alternative SSM Parameter Store name containing the Lambda function ARN",
            export_name=f"{self.resource_prefix}-lambda-arn-parameter-name-alt",
        )

    def _create_auto_scaling_configuration(self) -> None:
        """Create Application Auto Scaling configuration for the SageMaker endpoint."""
        # Create Application Auto Scaling scalable target for the endpoint
        self.scalable_target = applicationautoscaling.CfnScalableTarget(
            self,
            "EndpointScalableTarget",
            service_namespace="sagemaker",
            resource_id=f"endpoint/{self.endpoint_name}/variant/primary",
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            min_capacity=int(self.final_min_capacity),
            max_capacity=int(self.final_max_capacity),
            # Use service-linked role for Application Auto Scaling
            role_arn=f"arn:aws:iam::{self.account}:role/aws-service-role/sagemaker.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_SageMakerEndpoint",
        )

        # Ensure scalable target creation depends on endpoint
        self.scalable_target.add_dependency(self.sagemaker_endpoint)

        # Configure scaling policies with step scaling for HasBacklogWithoutCapacity metric
        self.scaling_policy = applicationautoscaling.CfnScalingPolicy(
            self,
            "ScalingPolicy",
            policy_name=f"{self.resource_prefix}-HasBacklogWithoutCapacity-ScalingPolicy",
            service_namespace="sagemaker",
            resource_id=self.scalable_target.resource_id,
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            policy_type="StepScaling",
            step_scaling_policy_configuration=applicationautoscaling.CfnScalingPolicy.StepScalingPolicyConfigurationProperty(
                adjustment_type="ChangeInCapacity",
                metric_aggregation_type="Average",
                cooldown=300,  # 5 minutes cooldown period
                step_adjustments=[
                    # Scale up by 1 instance when HasBacklogWithoutCapacity >= 1
                    applicationautoscaling.CfnScalingPolicy.StepAdjustmentProperty(
                        metric_interval_lower_bound=0, scaling_adjustment=1
                    )
                ],
            ),
        )

        # Ensure scaling policy creation depends on scalable target
        self.scaling_policy.add_dependency(self.scalable_target)

        # Create CloudWatch alarm for HasBacklogWithoutCapacity metric
        self.scaling_alarm = cloudwatch.CfnAlarm(
            self,
            "HasBacklogWithoutCapacityAlarm",
            alarm_name=f"{self.resource_prefix}-HasBacklogWithoutCapacity-Alarm",
            alarm_description="Alarm to trigger auto scaling when there is backlog without capacity",
            metric_name="HasBacklogWithoutCapacity",
            namespace="AWS/SageMaker",
            statistic="Average",
            evaluation_periods=2,
            datapoints_to_alarm=2,
            threshold=1,
            comparison_operator="GreaterThanOrEqualToThreshold",
            treat_missing_data="notBreaching",
            dimensions=[
                cloudwatch.CfnAlarm.DimensionProperty(
                    name="EndpointName", value=self.endpoint_name
                )
            ],
            period=60,  # 1 minute period
            alarm_actions=[self.scaling_policy.ref],
        )

        # Ensure alarm creation depends on scaling policy
        self.scaling_alarm.add_dependency(self.scaling_policy)

        # Create scale-down policy for when there's no backlog
        self.scale_down_policy = applicationautoscaling.CfnScalingPolicy(
            self,
            "ScaleDownPolicy",
            policy_name=f"{self.resource_prefix}-NoBacklog-ScaleDownPolicy",
            service_namespace="sagemaker",
            resource_id=self.scalable_target.resource_id,
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            policy_type="StepScaling",
            step_scaling_policy_configuration=applicationautoscaling.CfnScalingPolicy.StepScalingPolicyConfigurationProperty(
                adjustment_type="ChangeInCapacity",
                metric_aggregation_type="Average",
                cooldown=600,  # 10 minutes cooldown for scale down
                step_adjustments=[
                    # Scale down by 1 instance when HasBacklogWithoutCapacity < 1
                    applicationautoscaling.CfnScalingPolicy.StepAdjustmentProperty(
                        metric_interval_upper_bound=0, scaling_adjustment=-1
                    )
                ],
            ),
        )

        # Ensure scale-down policy creation depends on scalable target
        self.scale_down_policy.add_dependency(self.scalable_target)

        # Create CloudWatch alarm for scale down when no backlog
        self.scale_down_alarm = cloudwatch.CfnAlarm(
            self,
            "NoBacklogAlarm",
            alarm_name=f"{self.resource_prefix}-NoBacklog-Alarm",
            alarm_description="Alarm to trigger scale down when there is no backlog",
            metric_name="HasBacklogWithoutCapacity",
            namespace="AWS/SageMaker",
            statistic="Average",
            evaluation_periods=5,  # Longer evaluation period for scale down
            datapoints_to_alarm=5,
            threshold=1,
            comparison_operator="LessThanThreshold",
            treat_missing_data="breaching",  # Treat missing data as no backlog
            dimensions=[
                cloudwatch.CfnAlarm.DimensionProperty(
                    name="EndpointName", value=self.endpoint_name
                )
            ],
            period=60,  # 1 minute period
            alarm_actions=[self.scale_down_policy.ref],
        )

        # Ensure scale-down alarm creation depends on scale-down policy
        self.scale_down_alarm.add_dependency(self.scale_down_policy)

        # Create stack outputs for auto scaling information
        self._create_auto_scaling_outputs()

    def _create_auto_scaling_outputs(self) -> None:
        """Create CDK outputs for auto scaling configuration information."""
        CfnOutput(
            self,
            "ScalableTargetResourceId",
            value=self.scalable_target.resource_id,
            description="Resource ID of the Application Auto Scaling scalable target",
            export_name=f"{self.resource_prefix}-scalable-target-resource-id",
        )

        CfnOutput(
            self,
            "ScalingPolicyArn",
            value=self.scaling_policy.ref,
            description="ARN of the scaling policy for HasBacklogWithoutCapacity",
            export_name=f"{self.resource_prefix}-scaling-policy-arn",
        )

        CfnOutput(
            self,
            "ScaleDownPolicyArn",
            value=self.scale_down_policy.ref,
            description="ARN of the scale down policy for no backlog",
            export_name=f"{self.resource_prefix}-scale-down-policy-arn",
        )

        CfnOutput(
            self,
            "HasBacklogAlarmName",
            value=self.scaling_alarm.alarm_name,
            description="Name of the CloudWatch alarm for HasBacklogWithoutCapacity",
            export_name=f"{self.resource_prefix}-has-backlog-alarm-name",
        )

        CfnOutput(
            self,
            "NoBacklogAlarmName",
            value=self.scale_down_alarm.alarm_name,
            description="Name of the CloudWatch alarm for no backlog scale down",
            export_name=f"{self.resource_prefix}-no-backlog-alarm-name",
        )

        CfnOutput(
            self,
            "AutoScalingMinCapacity",
            value=str(int(self.final_min_capacity)),
            description="Minimum capacity configured for auto scaling",
            export_name=f"{self.resource_prefix}-autoscaling-min-capacity",
        )

        CfnOutput(
            self,
            "AutoScalingMaxCapacity",
            value=str(int(self.final_max_capacity)),
            description="Maximum capacity configured for auto scaling",
            export_name=f"{self.resource_prefix}-autoscaling-max-capacity",
        )

    def _create_stack_summary_outputs(self) -> None:
        """Create comprehensive CDK outputs for all important resource references."""
        # IAM Role outputs for reference
        CfnOutput(
            self,
            "ExecutionRoleName",
            value=self.sagemaker_execution_role.role_name,
            description="Name of the SageMaker execution role",
            export_name=f"{self.resource_prefix}-execution-role-name",
        )

        CfnOutput(
            self,
            "ExecutionRoleArn",
            value=self.sagemaker_execution_role.role_arn,
            description="ARN of the SageMaker execution role",
            export_name=f"{self.resource_prefix}-execution-role-arn",
        )

        CfnOutput(
            self,
            "SageMakerExecutionRoleName",
            value=self.sagemaker_execution_role.role_name,
            description="Name of the SageMaker execution role",
            export_name=f"{self.resource_prefix}-sagemaker-execution-role-name",
        )

        CfnOutput(
            self,
            "SageMakerExecutionRoleArn",
            value=self.sagemaker_execution_role.role_arn,
            description="ARN of the SageMaker execution role",
            export_name=f"{self.resource_prefix}-sagemaker-execution-role-arn",
        )

        CfnOutput(
            self,
            "ProjectName",
            value=self.project_name,
            description="Project name used for resource naming",
            export_name=f"{self.resource_prefix}-project-name",
        )

        CfnOutput(
            self,
            "ResourcePrefix",
            value=self.resource_prefix,
            description="Resource prefix used for naming all resources in this stack",
            export_name=f"{self.resource_prefix}-resource-prefix",
        )

        CfnOutput(
            self,
            "InstanceTypeOutput",
            value=self.final_instance_type,
            description="EC2 instance type used for the SageMaker endpoint",
            export_name=f"{self.resource_prefix}-instance-type",
        )

        # Stack feature flags
        CfnOutput(
            self,
            "AutoScalingEnabled",
            value="true" if self.config.enable_autoscaling else "false",
            description="Whether auto scaling is enabled for this endpoint",
            export_name=f"{self.resource_prefix}-autoscaling-enabled",
        )

        # Quick reference summary for developers
        CfnOutput(
            self,
            "StackSummary",
            #
            value=f"AMPLIFY VEP Async Endpoint: {f"{self.resource_prefix}-endpoint"} | S3 Bucket: {self.async_inference_bucket.bucket_name}",
            description="Quick summary of the deployed stack resources",
            export_name=f"{self.resource_prefix}-stack-summary",
        )

    def _configure_resource_cleanup_policies(self) -> None:
        """Configure resource cleanup and removal policies for proper deletion order."""
        # Set removal policies for SageMaker resources
        # SageMaker resources should be destroyed when stack is deleted
        self.sagemaker_endpoint.apply_removal_policy(RemovalPolicy.DESTROY)
        self.endpoint_config.apply_removal_policy(RemovalPolicy.DESTROY)
        self.sagemaker_model.apply_removal_policy(RemovalPolicy.DESTROY)

        # Configure IAM role removal policy
        # IAM roles should be destroyed when stack is deleted
        self.sagemaker_execution_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Configure auto scaling resources removal policies (if enabled)
        if self.config.enable_autoscaling:
            # Auto scaling resources should be destroyed when stack is deleted
            self.scalable_target.apply_removal_policy(RemovalPolicy.DESTROY)
            self.scaling_policy.apply_removal_policy(RemovalPolicy.DESTROY)
            self.scale_down_policy.apply_removal_policy(RemovalPolicy.DESTROY)
            self.scaling_alarm.apply_removal_policy(RemovalPolicy.DESTROY)
            self.scale_down_alarm.apply_removal_policy(RemovalPolicy.DESTROY)

        # Ensure proper deletion order through explicit dependencies
        self._configure_deletion_dependencies()

        # Add cleanup outputs for user reference
        self._create_cleanup_outputs()

    def _configure_deletion_dependencies(self) -> None:
        """Configure explicit resource dependencies for proper deletion order."""
        # Auto scaling resources must be deleted before endpoint
        if self.config.enable_autoscaling:
            # Alarms depend on scaling policies
            self.scaling_alarm.add_dependency(self.scaling_policy)
            self.scale_down_alarm.add_dependency(self.scale_down_policy)

            # Scaling policies depend on scalable target
            self.scaling_policy.add_dependency(self.scalable_target)
            self.scale_down_policy.add_dependency(self.scalable_target)

            # Scalable target depends on endpoint
            self.scalable_target.add_dependency(self.sagemaker_endpoint)

    def _create_cleanup_outputs(self) -> None:
        """Create CDK outputs for cleanup configuration information."""
        CfnOutput(
            self,
            "S3DataPreservationPolicy",
            value="RETAIN",
            description="S3 bucket removal policy - whether data is preserved on stack deletion",
            export_name=f"{self.resource_prefix}-s3-data-preservation-policy",
        )

        CfnOutput(
            self,
            "LogsRemovalPolicy",
            value=self.config.logs_removal_policy.name,
            description="CloudWatch logs removal policy configured for this stack",
            export_name=f"{self.resource_prefix}-logs-removal-policy",
        )

        # Add manual cleanup commands as a separate output
        CfnOutput(
            self,
            "ManualS3CleanupCommand",
            value=f"aws s3 rm s3://{self.async_inference_bucket.bucket_name} --recursive && aws s3 rb s3://{self.async_inference_bucket.bucket_name}",
            description="Manual S3 cleanup command if cdk destroy fails",
            export_name=f"{self.resource_prefix}-manual-s3-cleanup-command",
        )

    def _update_iam_policies_with_bucket_info(self) -> None:
        """Update IAM policies with actual bucket information."""
        # Create S3 access policy for async inference bucket only
        # CDK asset access is already handled in IAM role creation
        s3_access_policy = iam.PolicyDocument(
            statements=[
                # Allow listing the bucket
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:ListBucket"],
                    resources=[self.async_inference_bucket.bucket_arn],
                ),
                # Allow full access to async inference input/output paths
                # SageMaker needs this for async inference operations
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.input_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/{self.output_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/async-inference-failures/*",
                    ],
                ),
                # Allow read access to model artifacts and inference code stored in our bucket
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject"],
                    resources=[
                        f"{self.async_inference_bucket.bucket_arn}/{self.inference_code_prefix}*",
                        f"{self.async_inference_bucket.bucket_arn}/{self.model_artifacts_prefix}*",
                    ],
                ),
            ]
        )

        # Attach the S3 policy to the SageMaker execution role
        self.sagemaker_execution_role.attach_inline_policy(
            iam.Policy(
                self,
                "S3AsyncInferenceAccessPolicy",
                policy_name="S3AsyncInferenceAccess",
                document=s3_access_policy,
            )
        )
