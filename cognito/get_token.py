import boto3
import requests
import json


def get_access_token_from_aws() -> str:
    """Get access token using client credentials flow with values from AWS."""

    # Initialize AWS clients
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    # Get configuration from AWS
    client_id = ssm.get_parameter(Name=f"/cognito/client-id")[
        "Parameter"
    ]["Value"]
    domain = ssm.get_parameter(Name=f"/cognito/domain")["Parameter"][
        "Value"
    ]

    # Get client secret (now stored as JSON)
    secret_response = secrets.get_secret_value(
        SecretId=f"cognito-client-secret"
    )
    secret_data = json.loads(secret_response["SecretString"])
    client_secret = secret_data["client_secret"]

    # Build scopes (adjust based on your resource server identifier)
    resource_server_id = f"agentcore-gateway"
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

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()

    return response.json()["access_token"]


# Usage
if __name__ == "__main__":
    token = get_access_token_from_aws()
    print(f"Bearer token: {token}")
