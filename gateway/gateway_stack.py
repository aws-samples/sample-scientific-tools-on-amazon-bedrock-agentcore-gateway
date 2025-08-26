"""
CDK Stack for AgentCore Gateway IAM Role
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct


class AgentCoreGatewayStack(Stack):
    """CDK Stack that creates the IAM role for AgentCore Gateway."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the IAM role for AgentCore Gateway
        self.gateway_role = self._create_gateway_role()

        # Store the role ARN in SSM Parameter Store
        self._store_role_arn()

        # Output the role ARN
        cdk.CfnOutput(
            self,
            "GatewayRoleArn",
            value=self.gateway_role.role_arn,
            description="ARN of the AgentCore Gateway IAM role",
            export_name=f"AgentCoreGatewayRoleArn",
        )

    def _create_gateway_role(self) -> iam.Role:
        """Create the IAM role for AgentCore Gateway."""

        # Retrieve the Lambda function ARN from SSM Parameter Store
        lambda_function_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/sagemaker-async/lambda-function-arn"
        )

        # Create the role with basic service principal first
        role = iam.Role(
            self,
            "AgentCoreGatewayRole",
            role_name=f"agentcore-gateway-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=f"IAM role for AgentCore Gateway",
        )

        # Add the conditions to the assume role policy
        role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                sid="AssumeRolePolicyWithConditions",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")],
                actions=["sts:AssumeRole"],
                conditions={
                    "StringEquals": {"aws:SourceAccount": cdk.Aws.ACCOUNT_ID},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:*"
                    },
                },
            )
        )

        # Add permissions policy with specific Lambda function ARN
        role.add_to_policy(
            iam.PolicyStatement(
                sid="LambdaInvokePermissions",
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                ],
                resources=[lambda_function_arn],
            )
        )

        # # Add Bedrock AgentCore permissions
        # role.add_to_policy(
        #     iam.PolicyStatement(
        #         sid="BedrockAgentCorePermissions",
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "bedrock-agentcore:*",
        #             "bedrock:*",
        #             "agent-credential-provider:*",
        #             "iam:PassRole",
        #             "secretsmanager:GetSecretValue",
        #         ],
        #         resources=["*"]
        #     )
        # )

        # # Add CloudWatch Logs permissions
        # role.add_to_policy(
        #     iam.PolicyStatement(
        #         sid="CloudWatchLogsPermissions",
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "logs:CreateLogGroup",
        #             "logs:CreateLogStream",
        #             "logs:PutLogEvents",
        #             "logs:DescribeLogGroups",
        #             "logs:DescribeLogStreams",
        #         ],
        #         resources=[
        #             f"arn:aws:logs:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/gateways/*"
        #         ]
        #     )
        # )

        # # Add CloudWatch Metrics permissions
        # role.add_to_policy(
        #     iam.PolicyStatement(
        #         sid="CloudWatchMetricsPermissions",
        #         effect=iam.Effect.ALLOW,
        #         actions=["cloudwatch:PutMetricData"],
        #         resources=["*"],
        #         conditions={
        #             "StringEquals": {
        #                 "cloudwatch:namespace": "bedrock-agentcore"
        #             }
        #         }
        #     )
        # )

        # Add tags
        cdk.Tags.of(role).add("Service", "bedrock-agentcore")
        cdk.Tags.of(role).add("Component", "gateway")

        return role

    def _store_role_arn(self) -> None:
        """Store the role ARN in SSM Parameter Store."""
        ssm.StringParameter(
            self,
            "GatewayRoleArnParameter",
            parameter_name=f"/agentcore-gateway/role-arn",
            string_value=self.gateway_role.role_arn,
            #
            description=f"ARN of the AgentCore Gateway IAM role",
            tier=ssm.ParameterTier.STANDARD,
        )
