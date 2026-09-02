"""
FastAPI SSE backend — initialises the MCP session once on startup and streams
agent activity and answer tokens to the frontend via POST /query.
"""

import os
import json
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
from config import GROQ_MODEL
from services.metadata_service import get_indicator_details, list_categories, search_indicators
from services.cache_service import get_coverage, get_indicator_data_type, get_or_fetch

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are an expert epidemiological assistant with access to the full WHO Global Health Observatory. "
        "All tools accept plain English indicator names like 'obesity', 'life expectancy', 'air pollution' — never look up WHO codes. "
        "Country codes must be ISO 3-letter codes (e.g. FRA, MEX, IND, CHN, USA, JPN). "
        "The tool results are already displayed to the user as formatted evidence tables. "
        "Write 2-3 sentences of narrative interpretation: reference the key numbers naturally (e.g. 'At 36%, the US obesity rate is nearly 5x Japan\'s 7%'), explain what is notable or surprising, and what it means for the populations involved. "
        "Never use bullet points or lists. Never say 'the data shows' or 'according to the results' — just interpret directly. If data is missing or incomplete, say so plainly. "
        "Only call search_indicators when the user explicitly asks what indicators exist or wants to browse/discover options. "
        "For categorical yes/no or status indicators, use get_indicator_value with the requested country and year. "
        "For any question asking for actual data (a value, comparison, ranking, or trend), call the relevant data tool directly on the first attempt — do not call search_indicators first to double-check."
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

    def patch_schema(schema: dict) -> dict:
        """Deep copy schema and ensure all array properties have items type."""
        import copy
        schema = copy.deepcopy(dict(schema))
        for prop in schema.get("properties", {}).values():
            if prop.get("type") == "array" and "items" not in prop:
                prop["items"] = {"type": "string"}
        return schema

    groq_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": patch_schema(dict(tool.inputSchema)),
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


def tool_stage_sequence(tool_name: str):
    sequence = {
        "get_country_health_profile": [
            "Resolving indicators",
            "Fetching country data",
            "Computing percentiles",
            "Finalizing profile",
        ],
        "compare_countries": [
            "Resolving indicators",
            "Fetching country data",
            "Computing percentiles",
            "Final comparison output",
        ],
        "get_health_trend": [
            "Resolving indicators",
            "Fetching country data",
            "Computing trend",
            "Final trend output",
        ],
        "rank_countries_by_indicator": [
            "Resolving indicators",
            "Fetching country data",
            "Computing percentiles",
            "Final ranking output",
        ],
        "search_indicators": [
            "Checking the indicator catalog",
            "Final search output",
        ],
        "browse_categories": [
            "Checking category buckets",
            "Final category output",
        ],
        "get_indicator_value": [
            "Resolving indicator",
            "Checking country and year",
            "Final indicator value",
        ],
    }
    return sequence.get(tool_name, [tool_name])


async def run_agent_stream(query: str):
    session = mcp_state["session"]
    groq_tools = mcp_state["groq_tools"]
    messages = [SYSTEM_MESSAGE, {"role": "user", "content": query}]

    while True:
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=groq_tools,
                tool_choice="auto",
                stream=False,
            )
        except Exception as e:
            yield sse_event("error", {"message": f"LLM request failed: {e}"})
            yield sse_event("done", {})
            return

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            for word in msg.content.split(" "):
                yield sse_event("answer_token", {"token": word + " "})
            yield sse_event("done", {})
            break

        for tc in msg.tool_calls:
            # gpt-oss models occasionally leak "<|channel|>..." fragments into the tool name
            tool_name = tc.function.name.split("<|")[0]
            func_args = json.loads(tc.function.arguments)
            yield sse_event("tool_call", {"name": tool_name, "args": func_args})

            stages = tool_stage_sequence(tool_name)
            yield sse_event("stage_plan", {"names": stages})
            for stage_name in stages:
                yield sse_event("stage", {"name": stage_name})

            try:
                mcp_result = await session.call_tool(tool_name, func_args)
                result_text = next(
                    (c.text for c in mcp_result.content if isinstance(c, TextContent)),
                    "(no result)",
                )
            except Exception as e:
                result_text = json.dumps({"type": "error", "message": f"Tool '{tool_name}' failed: {e}"})

            try:
                result_data = json.loads(result_text)
            except (json.JSONDecodeError, TypeError):
                result_data = {"type": "raw", "text": result_text}

            yield sse_event("tool_result", {"name": tool_name, "result": result_data})

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


@app.get("/categories")
async def categories_endpoint():
    return {"categories": list_categories()}


@app.get("/categories/{category}/indicators")
async def category_indicators_endpoint(category: str, limit: int = 10):
    bounded_limit = max(1, min(limit, 50))
    return {
        "category": category,
        "indicators": search_indicators("", limit=bounded_limit, category=category),
    }


@app.get("/indicators/{code}")
async def indicator_details_endpoint(code: str):
    details = get_indicator_details(code)
    if not details:
        return {"error": "Indicator not found"}

    await get_or_fetch(code)
    details.update(get_indicator_data_type(code))
    details["coverage"] = get_coverage(code) or {
        "min_year": None,
        "max_year": None,
        "country_count": 0,
        "countries": [],
    }
    return details


@app.get("/health")
async def health():
    return {"status": "ok", "tools_loaded": len(mcp_state["groq_tools"])}
