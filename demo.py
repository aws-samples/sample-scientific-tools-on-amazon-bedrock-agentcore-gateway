# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import asyncio
import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

# Configure logging
logging.getLogger("strands").setLevel(
    logging.INFO
)  # Set to DEBUG for more detailed logs

GATEWAY_URL = os.environ["GATEWAY_URL"]
BEARER_TOKEN = os.environ["BEARER_TOKEN"]

# Create an MCP Client pointing to the Gateway
gateway_client = MCPClient(
    lambda: streamablehttp_client(
        GATEWAY_URL, headers={"Authorization": f"Bearer {BEARER_TOKEN}"}
    )
)

if __name__ == "__main__":
    print("\n👨‍🍳 Protein Agent: Ask me about proteins! Type 'exit' to quit.\n")

    # Run the agent in a loop for interactive conversation
    with gateway_client:
        tools = gateway_client.list_tools_sync()
        agent = Agent(
            model="global.anthropic.claude-sonnet-4-20250514-v1:0",
            tools=tools,
            system_prompt="You are a helpful assistant designed to answer question about proteins and submit analysis jobs using the tools available",
            callback_handler=None,
        )

        while True:
            user_input = input("\nYou > ")

            async def process_streaming_response():
                """
                Invoke the agent with a payload
                """

                agent_stream = agent.stream_async(user_input)
                async for event in agent_stream:
                    # Track event loop lifecycle
                    if event.get("init_event_loop", False):
                        print("🔄 Event loop initialized")
                    elif event.get("start_event_loop", False):
                        print("▶️ Event loop cycle starting")
                    elif event.get("start", False):
                        print("📝 New cycle started")
                    elif "message" in event:
                        print(f"📬 New message created: {event['message']['role']}")
                    elif event.get("force_stop", False):
                        print(
                            f"🛑 Event loop force-stopped: {event.get('force_stop_reason', 'unknown reason')}"
                        )

                    if "current_tool_use" in event and event["current_tool_use"].get(
                        "name"
                    ):
                        tool_name = event["current_tool_use"]["name"]
                        print(f"🔧 Using tool: {tool_name}")

                    if "data" in event:
                        print(event["data"], end="")

            asyncio.run(process_streaming_response())
