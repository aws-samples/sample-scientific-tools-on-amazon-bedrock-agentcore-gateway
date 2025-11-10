# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import asyncio
import logging
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

from utils import get_auth_info

# Configure logging
logging.getLogger("strands").setLevel(
    logging.INFO
)  # Set to DEBUG for more detailed logs

app = BedrockAgentCoreApp()

GATEWAY_URL = "https://agentcore-gateway-ghdmx62zxq.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
BEARER_TOKEN = get_auth_info()

# Create an MCP Client pointing to the Gateway
gateway_client = MCPClient(
    lambda: streamablehttp_client(
        GATEWAY_URL, headers={"Authorization": f"Bearer {BEARER_TOKEN}"}
    )
)
with gateway_client:
    tools = gateway_client.list_tools_sync()
    agent = Agent(
        model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        tools=tools,
        system_prompt="You are a helpful assistant designed to answer question about proteins and submit analysis jobs using the tools available",
        callback_handler=None,
    )


@app.entrypoint
async def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    print("User input:", user_input)
    try:
        async for event in agent.stream_async(user_input):

            # Print tool use
            for content in event.get("message", {}).get("content", []):
                if tool_use := content.get("toolUse"):
                    yield "\n"
                    yield f"🔧 Using tool: {tool_use['name']}"
                    for k, v in tool_use["input"].items():
                        yield f"**{k}**: {v}\n"
                    yield "\n"

            # Print event data
            if "data" in event:
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
