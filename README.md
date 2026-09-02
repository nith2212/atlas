# Atlas — Global Health Intelligence

Ask a question in plain English. Atlas autonomously picks the right analytical tool, computes the
answer against live WHO data cached in PostgreSQL, and streams back a structured, evidence-backed
result — no dashboards to configure, no SQL to write.

**Live demo:** [your-render-or-vercel-url-here](#)

```
Backend (Render):   https://your-app.onrender.com
Frontend (Vercel):  https://your-app.vercel.app
```

---

## Table of Contents

- [Why Atlas](#why-atlas)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [What makes this different](#what-makes-this-different)
- [The MCP server, explained](#the-mcp-server-explained)
- [MCP Tools Reference](#mcp-tools-reference)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Deploying](#deploying)
- [Connect Your Own Client to the MCP Server](#connect-your-own-client-to-the-mcp-server)
- [Example Queries](#example-queries)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

---

## Why Atlas

Global health data from the WHO Global Health Observatory is public, but genuinely using it is
not: it's scattered across thousands of indicators, inconsistent units, missing years, and country
codes that mean nothing to a casual user. Answering something as simple as *"is France's
life expectancy actually good compared to the rest of the world?"* normally means writing a script.

Atlas removes that friction. Type the question. Get a percentile-adjusted, direction-aware,
narrated answer with the evidence table right next to it.

---

## How it works

1. You ask a question in the query bar (or pick an indicator from the category browser).
2. The question goes to an LLM (Llama via Groq) that has been handed a live list of
   MCP tools — it never sees a database schema, only tool names and descriptions.
3. The LLM decides which tool(s) to call and with what arguments. Plain-English indicator names
   like `"air pollution"` are resolved internally to WHO codes — the model never needs to know them.
4. Each tool call runs real computation: percentile calculation, direction-aware trend
   classification, year-fallback logic, distribution stats — not just a `SELECT *`.
5. Results stream back over Server-Sent Events as they happen: tool call → live progress stages →
   typed result → narrated answer, token by token.
6. The frontend renders each result type with a dedicated component — profile rings, comparison
   tables, trend charts, categorical badges — driven entirely by a `type` field in the JSON, never
   by parsing markdown.

---

## Architecture

```
WHO GHO API
    │
    ▼
Metadata + cache ETL  (backend/etl/)
    │
    ▼
Neon PostgreSQL          ← indicators_metadata (catalog) + indicator_cache (values)
    │
    ▼
MCP Tools Server (server.py)     ← stdio transport, all analytical computation lives here
    │
    ▼
FastAPI + SSE Gateway (api.py)   ← spawns the MCP server, bridges Groq ⇄ MCP, streams events
    │
    ▼
React Frontend (Vite)           ← category browser, query bar, typed evidence renderer
```

**The LLM writes prose. The tools compute findings. React renders typed evidence. Nobody swaps
jobs.** This separation is what keeps the answers factually grounded — the model can't
hallucinate a percentile because it never computes one; it only reads back what the tool returned.

---

## What makes this different

**Direction-aware analytics, not raw numbers.** A lower PM2.5 (air pollution) reading is a
*better* health outcome, but a lower life expectancy is worse. Every percentile, ranking, and
trend classification in Atlas is aware of each indicator's `higher_is_better` direction, so
"strongest indicator" always means *healthiest*, never just *numerically highest*.

**Real computation, not a chatbot with search.** The four core tools compute health-adjusted
percentiles, year-over-year deltas, trend classification with noise tolerance, and full
distribution statistics (mean/median/stdev) server-side. The LLM only narrates results that
already exist as typed JSON.

**Lazy, self-healing cache.** Nothing is bulk-downloaded up front. The first time an indicator is
requested, Atlas fetches it from the WHO API, tries the recent window first (2015+), and falls
back to full historical range only if that comes back empty — so a demo doesn't need to warm
3,000+ indicators to be useful, and one-off historical indicators aren't silently marked "no data."

**Handles categorical data, not just numbers.** Many WHO indicators are Yes/No/status fields
(e.g. "has a national nutrition awareness program"), not numeric values. Atlas detects this and
routes them to a dedicated categorical lookup instead of forcing a percentile calculation onto a
non-numeric answer.

**No markdown-parsing, no guessing UI.** Every tool response carries a `type` field
(`"profile"`, `"comparison"`, `"trend"`, `"ranking"`, `"categorical_result"`, …). The frontend
switches on that type and renders a purpose-built component. There is no regex-scraping an LLM's
prose to find numbers to chart.

**A transparent MCP server that any client can reuse.** The analytical layer is a standard MCP
server over stdio — it doesn't know about Groq, FastAPI, or React. Anything that speaks MCP
(Claude Desktop, your own agent, another LLM provider) can attach to it. See
[Connect Your Own Client](#connect-your-own-client-to-the-mcp-server) below.

---

## The MCP server, explained

[Model Context Protocol](https://modelcontextprotocol.io) (MCP) is an open standard for exposing
tools to an LLM in a way that's provider-agnostic. Instead of hardcoding "if the user asks X, call
function Y" inside your prompt, you describe each tool's name, description, and JSON parameter
schema — and let the model decide when and how to call it.

In Atlas, [`server.py`](backend/server.py) is a standalone MCP server built with `fastmcp`. It:

- Exposes six tools (profile, comparison, trend, ranking, categorical value, search/browse).
- Talks to Neon PostgreSQL directly for cached data and to the WHO API on cache misses.
- Has **zero knowledge of Groq or React.** It communicates purely over stdio using the MCP
  protocol.

[`api.py`](backend/api.py) is the *only* piece of Atlas that knows about both sides: it spawns
`server.py` as a subprocess on startup, discovers its tools via `session.list_tools()`, converts
their schemas into the OpenAI/Groq function-calling format, and relays each `tool_call` /
`tool_result` back to the browser as a Server-Sent Event.

This separation is deliberate. It means:

- You can swap Groq for OpenAI, Anthropic, or a local model by changing `api.py` alone —
  `server.py` never changes.
- You can run `server.py` completely independently — from a terminal client, from Claude Desktop,
  from your own script — without touching any web code.
- Debugging is trivial: if a result is wrong, you can call the tool directly in Python and see
  exactly what it returns, with no LLM in the loop at all.

---

## MCP Tools Reference

Each tool performs non-trivial computation — the LLM receives findings it could not produce from
raw rows alone.

### `get_country_health_profile(country_code, year, indicators)`
Full health profile for one country in a given year.
- Health-adjusted global percentile for each indicator
- Strongest and weakest indicator by percentile (missing data excluded)
- Missing data flags per indicator

### `compare_countries(country_a, country_b, year, indicators)`
Side-by-side comparison across specified indicators in one call.
- Health-adjusted percentile for both countries per indicator
- Absolute difference and which country leads (by health outcome, not raw value)
- Indicator with the largest gap between the two countries
- Missing data flags

### `get_health_trend(country_code, indicator, start_year, end_year)`
Time-series analysis for one country/indicator over a year range.
- Overall % change and year-over-year deltas for every step
- Best and worst outcome years (direction-aware — lowest pollution = best year for PM2.5)
- Trend classification: `improving` / `declining` / `volatile` / `stable` / `insufficient_data`
  - Requires ≥ 4 data points to classify; 1% tolerance band filters out noise

### `rank_countries_by_indicator(indicator, year, limit=10)`
Top N countries by best health outcome for an indicator/year.
- Sort direction driven by `higher_is_better` — rankings always mean best health outcome
- Health-adjusted percentile per ranked country
- Global distribution stats: mean, median, min, max, stdev, n

### `get_indicator_value(indicator, country_code, year)`
Looks up a categorical/status value (e.g. `Yes`, `No`, `Don't know`) for one country and year —
used for indicators that aren't numeric.

### `search_indicators(query, category=None)` / `browse_categories()`
Explore the WHO catalog by name or by category bucket, used when a user wants to discover what's
available rather than get a specific value.

---

## Tech Stack

**Backend**
- Python, FastAPI, Server-Sent Events (SSE)
- [MCP](https://modelcontextprotocol.io) via `fastmcp` — stdio transport
- Groq API — Llama-family model, function/tool calling
- PostgreSQL-compatible database (Neon)

**Frontend**
- React + Vite
- `html2pdf.js` for client-side PDF export
- No UI framework — custom CSS only

---

## Getting Started

### 1. Clone and set up the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=your_neon_postgres_connection_string
GROQ_MODEL=openai/gpt-oss-20b
```

Get a free Groq key at [console.groq.com](https://console.groq.com). Get a free Postgres instance
at [neon.tech](https://neon.tech).

### 3. Populate the metadata catalog

Fetches the WHO indicator catalog and populates PostgreSQL metadata (~2–3 minutes, one-time):

```bash
python -m etl.metadata_pipeline
```

Indicator *values* are fetched lazily — the first time a query needs an indicator, it's pulled
from the WHO API and cached. To pre-warm a curated set of demo indicators, run:

```bash
python -m etl.preload_pipeline
```

### 4. Start the backend

```bash
uvicorn api:app --reload
```

Runs at `http://localhost:8000`. Visit `/health` to confirm the MCP tools loaded.

### 5. Start the frontend

```bash
cd ../frontend-app
npm install
```

Create `frontend-app/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
```

Open `http://localhost:5173`.

---

## Deploying

**Backend → Render**

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Environment variables: `GROQ_API_KEY`, `DATABASE_URL`, `GROQ_MODEL`
- Run `python -m etl.metadata_pipeline` once (locally, or via a Render one-off job) pointed at
  your production `DATABASE_URL` before relying on the category browser.

**Frontend → Vercel**

- Root directory: `frontend-app`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_URL=https://your-backend.onrender.com`

Never commit `.env` or `.env.local` — secrets belong in your host's environment variable settings,
not in git.

---

## Connect Your Own Client to the MCP Server

Because [`server.py`](backend/server.py) is a self-contained MCP server, you can attach *any* MCP
client to it — you are not locked into this repo's FastAPI/React frontend.

### Option A — Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "atlas": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/absolute/path/to/backend",
      "env": {
        "DATABASE_URL": "your_neon_connection_string"
      }
    }
  }
}
```

Restart Claude Desktop — Atlas's six tools now appear alongside its other tools.

### Option B — Your own Python client

This is exactly what [`client.py`](backend/client.py) does; use it as a template:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="python", args=["server.py"])

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()          # discover what's available
        result = await session.call_tool(
            "compare_countries",
            {"country_a": "FRA", "country_b": "JPN", "year": 2019,
             "indicators": ["life expectancy"]},
        )
```

### Option C — A different LLM provider

Swap Groq for OpenAI/Anthropic/a local model by only touching `api.py`:

1. Keep `server.py` untouched — it has no idea which LLM is calling it.
2. In `api.py`, replace the Groq client with your provider's SDK.
3. Convert `session.list_tools()` output into that provider's function/tool-calling schema
   (the same `patch_schema()` pattern already used for Groq will need adjusting per-provider).
4. Everything downstream — SSE streaming, evidence rendering — is unchanged.

---

## Example Queries

- `Compare the full health profiles of France and Japan in 2019`
- `Which country had the lowest NCD mortality in 2020?`
- `How has life expectancy changed in Nigeria between 2015 and 2020?`
- `Rank the top 10 countries by hospital bed density in 2018`
- `Compare air pollution between China and India in 2020`
- `Does Benin have a national nutrition awareness program?`

---

## Project Structure

```
etl-mcp-health/
├── backend/
│   ├── api.py            # FastAPI SSE gateway — bridges Groq ⇄ MCP, streams events
│   ├── server.py          # MCP tools server — all analytical computation lives here
│   ├── client.py          # Standalone terminal MCP client (reference implementation)
│   ├── config.py          # Infrastructure settings and curated indicator aliases
│   ├── etl/               # Metadata catalog, cache migration, and preload jobs
│   ├── services/          # Metadata, cache, health-percentile, and LLM helpers
│   ├── database/          # PostgreSQL schema initialization
│   ├── tests/             # Backend unit tests
│   └── requirements.txt
└── frontend-app/
    └── src/
        ├── components/     # Query bar, category browser, indicator modal, evidence views
        ├── utils/          # Frontend display helpers
        ├── App.jsx
        └── App.css
```

---

## Roadmap

- [x] Neon PostgreSQL metadata + cache schema
- [x] Lazy cache-aside fetching with historical fallback
- [x] Category browser + indicator detail modal
- [x] Categorical (non-numeric) indicator support
- [x] PDF / plain-text export
- [ ] Charts for trend and ranking evidence
- [ ] Richer dashboard view beyond the query bar
