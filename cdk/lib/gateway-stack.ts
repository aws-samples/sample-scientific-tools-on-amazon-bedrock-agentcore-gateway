import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import { Construct } from 'constructs';

export interface GatewayStackProps extends cdk.StackProps {
  /**
   * Project name used for resource naming and tagging
   * @default 'protein-engineering'
   */
  readonly projectName?: string;

  /**
   * Name for the AgentCore Gateway
   * @default 'agentcore-gateway'
   */
  readonly gatewayName?: string;

  /**
   * Description for the AgentCore Gateway
   * @default 'AgentCore Gateway for protein engineering agent with MCP integration'
   */
  readonly gatewayDescription?: string;
}
export class GatewayStack extends cdk.Stack {
  public readonly gateway: bedrockagentcore.CfnGateway;
  public readonly gatewayTarget: bedrockagentcore.CfnGatewayTarget;
  public readonly gatewayRole: iam.Role;

  constructor(scope: Construct, id: string, props?: GatewayStackProps) {
    super(scope, id, props);

    // Extract configuration with defaults
    const projectName = props?.projectName ?? 'protein-engineering';
    const gatewayName = props?.gatewayName ?? 'agentcore-gateway';
    const gatewayDescription = props?.gatewayDescription ?? 
      'AgentCore Gateway for protein engineering agent with MCP integration';

    this.gatewayRole = new iam.Role(this, 'GatewayRole', {
      roleName: `${projectName}-agentcore-gateway-role`,
      description: 'Execution role for Amazon Bedrock AgentCore Gateway to invoke Lambda functions',
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com', {
        conditions: {
          StringEquals: {
            'aws:SourceAccount': this.account,
          },
          ArnLike: {
            'aws:SourceArn': `arn:${this.partition}:bedrock-agentcore:${this.region}:${this.account}:*`,
          },
        },
      }),
    });

    this.gatewayRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [lambdaFunctionArn],
      })
    );

    this.gateway = new bedrockagentcore.CfnGateway(this, 'AgentCoreGateway', {
      name: gatewayName,
      description: gatewayDescription,
      roleArn: this.gatewayRole.roleArn,
      protocolType: 'MCP',
      authorizerType: 'CUSTOM_JWT',
      authorizerConfiguration: {
        customJwtAuthorizer: {
          discoveryUrl: cognitoDiscoveryUrl,
          allowedClients: [cognitoClientId],
        },
      },
      protocolConfiguration: {
        mcp: {
          searchType: 'SEMANTIC',
        },
      },
      tags: {
        Project: projectName,
        Component: 'Gateway',
        ManagedBy: 'CDK',
      },
    });

    this.gatewayTarget = new bedrockagentcore.CfnGatewayTarget(this, 'GatewayTarget', {
      name: 'protein-engineering-lambda',
      description: 'Lambda target for protein variant effect prediction',
      gatewayIdentifier: this.gateway.ref,
      targetConfiguration: {
        mcp: {
          lambda: {
            lambdaArn: lambdaFunctionArn,
            toolSchema: {
              inlinePayload: [
                {
                  name: 'invoke_endpoint',
                  description: 'Submit a job to predict the variant effects for an amino acid sequence',
                  inputSchema: {
                    type: 'object',
                    properties: {
                      sequence: {
                        type: 'string',
                        description: 'Amino acid sequence',
                      },
                    },
                    required: ['sequence'],
                  },
                },
                {
                  name: 'get_results',
                  description: 'Check if a variant effect prediction job has completed and retrieve results',
                  inputSchema: {
                    type: 'object',
                    properties: {
                      output_id: {
                        type: 'string',
                        description: 'output_id returned by invoke_endpoint',
                      },
                    },
                    required: ['output_id'],
                  },
                },
              ],
            },
          },
        },
      },
      credentialProviderConfigurations: [
        {
          credentialProviderType: 'GATEWAY_IAM_ROLE',
        },
      ],
    });
