# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import requests
import json


def get_auth_info(
    client_id_param_name: str = "/cognito/client-id",
    client_secret_id: str = "cognito-client-secret",
    domain_param_name: str = "/cognito/domain",
    resource_server_id: str = "agentcore-gateway",
) -> str:
    """Get access token using client credentials flow with values from AWS."""

    # Initialize AWS clients
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    # Get configuration from AWS
    client_id = ssm.get_parameter(Name=client_id_param_name)["Parameter"]["Value"]
    domain = ssm.get_parameter(Name=domain_param_name)["Parameter"]["Value"]

    # Get client secret (now stored as JSON)
    secret_response = secrets.get_secret_value(SecretId=client_secret_id)
    secret_data = json.loads(secret_response["SecretString"])
    client_secret = secret_data["client_secret"]

    # Build scopes (adjust based on your resource server identifier)
    scopes = f"{resource_server_id}/gateway:read {resource_server_id}/gateway:write"

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
    token = get_auth_info()
    print(f"Discovery URL: {token[0]}")
    print(f"Bearer token: {token[1]}")