# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import requests
import json


def get_access_token_from_aws(project_name: str = "protein-engineering") -> str:
    """Get access token using client credentials flow with values from AWS."""

    # Initialize AWS clients
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    # Get configuration from AWS (using CloudFormation parameter paths)
    client_id = ssm.get_parameter(Name=f"/protein-agent/cognito/client-id")["Parameter"]["Value"]
    domain = ssm.get_parameter(Name=f"/protein-agent/cognito/domain")["Parameter"]["Value"]

    # Get client secret (stored as JSON in Secrets Manager)
    secret_response = secrets.get_secret_value(SecretId=f"{project_name}/cognito/client-secret")
    secret_data = json.loads(secret_response["SecretString"])
    client_secret = secret_data["client_secret"]

    # Build scopes (using the resource server identifier from CloudFormation)
    resource_server_id = "agentcore-gateway"
    scopes = f"{resource_server_id}/read {resource_server_id}/write {resource_server_id}/admin"

    # Get token
    url = f"{domain}/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scopes,
    }

    response = requests.post(url, headers=headers, data=data, timeout=5)
    response.raise_for_status()

    return response.json()["access_token"]


# Usage
if __name__ == "__main__":
    token = get_access_token_from_aws()
    print()
    print(token)
    print()