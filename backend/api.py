"""
FastAPI SSE backend — initialises the MCP session once on startup and streams
agent activity and answer tokens to the frontend via POST /query.
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"
SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are an expert epidemiological assistant. Use your available tools to fetch exact health indicators before answering. "
        "Never guess numbers. The only valid indicator_name values are: NCD_MORTALITY_PROB, AIR_POLLUTION_PM25, HOSPITAL_BED_DENSITY, LIFE_EXPECTANCY. "
        "Always use these exact strings when calling tools. Country codes must be ISO 3-letter codes (e.g. FRA for France, MEX for Mexico, IND for India)."
    ),
}

mcp_state = {"session": None, "groq_tools": [], "stdio_cm": None, "session_cm": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_params = StdioServerParameters(command="python", args=["server.py"])
    stdio_cm = stdio_client(server_params)
    read, write = await stdio_cm.__aenter__()
    session_cm = ClientSession(read, write)
    session = await session_cm.__aenter__()
    await session.initialize()

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

    mcp_state["session"] = session
    mcp_state["groq_tools"] = groq_tools
    mcp_state["stdio_cm"] = stdio_cm
    mcp_state["session_cm"] = session_cm

    print(f"[API] MCP session ready. Loaded {len(groq_tools)} tools.")
    yield

    await session_cm.__aexit__(None, None, None)
    await stdio_cm.__aexit__(None, None, None)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


def sse_event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


async def run_agent_stream(query: str):
    session = mcp_state["session"]
    groq_tools = mcp_state["groq_tools"]
    messages = [SYSTEM_MESSAGE, {"role": "user", "content": query}]

    while True:
        response = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
            stream=False,
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            for word in msg.content.split(" "):
                yield sse_event("answer_token", {"token": word + " "})
                await asyncio.sleep(0.03)
            yield sse_event("done", {})
            break

        for tc in msg.tool_calls:
            func_args = json.loads(tc.function.arguments)
            yield sse_event("tool_call", {"name": tc.function.name, "args": func_args})

            mcp_result = await session.call_tool(tc.function.name, func_args)
            result_text = next(
                (c.text for c in mcp_result.content if isinstance(c, TextContent)),
                "(no result)",
            )

            try:
                result_data = json.loads(result_text)
            except (json.JSONDecodeError, TypeError):
                result_data = {"type": "raw", "text": result_text}

            yield sse_event("tool_result", {"name": tc.function.name, "result": result_data})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })


@app.post("/query")
async def query_endpoint(request: QueryRequest):
    async def event_generator():
        async for event in run_agent_stream(request.query):
            yield event

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    return {"status": "ok", "tools_loaded": len(mcp_state["groq_tools"])}
