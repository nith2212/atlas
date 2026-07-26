"""
Phase 3: Agentic MCP Client with LLM Orchestration
Connects to server.py via stdio, hands off tool schemas to Groq,
and executes multi-step data lookups dynamically.
"""

import os
import asyncio
import json
from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"


async def run_agent():
    server_params = StdioServerParameters(command="python", args=["server.py"])

    print("[CLIENT] Connecting to local MCP server via stdio...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Step 1: Discover MCP tools and convert to Groq/OpenAI tool format
            mcp_tools = await session.list_tools()
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in mcp_tools.tools
            ]

            print(f"[AGENT] Loaded {len(mcp_tools.tools)} MCP tools into LLM context window.")
            print("=" * 60)

            system_message = {"role": "system", "content": "You are an expert epidemiological assistant. Use your available tools to fetch exact health indicators before answering. Never guess numbers. The only valid indicator_name values are: NCD_MORTALITY_PROB, AIR_POLLUTION_PM25, HOSPITAL_BED_DENSITY, LIFE_EXPECTANCY. Always use these exact strings when calling tools. Country codes must be ISO 3-letter codes (e.g. FRA for France, MEX for Mexico, IND for India)."}

            while True:
                user_prompt = input("\nEnter your health query (or 'exit' to quit): ").strip()
                if user_prompt.lower() in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                if not user_prompt:
                    continue

                print(f"User Query: {user_prompt}\n")
                messages = [system_message, {"role": "user", "content": user_prompt}]

                # Agentic loop: keep calling tools until Groq returns a final text response
                while True:
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=messages,
                        tools=groq_tools,
                        tool_choice="auto",
                    )
                    msg = response.choices[0].message
                    messages.append(msg)

                    if not msg.tool_calls:
                        break

                    for tc in msg.tool_calls:
                        func_args = json.loads(tc.function.arguments)
                        print(f"[TOOL CALL] LLM requested: {tc.function.name}({func_args})")

                        mcp_result = await session.call_tool(tc.function.name, func_args)
                        result_text = next(
                            (c.text for c in mcp_result.content if isinstance(c, TextContent)),
                            "(no result)"
                        )
                        print(f"[TOOL RESULT] {result_text}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_text,
                        })

                print("\n" + "=" * 60)
                print("FINAL AGENT ANSWER:")
                print("=" * 60)
                print(msg.content)
                print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_agent())
