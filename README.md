# Atlas — Global Health Intelligence

An agentic AI application that lets you explore WHO global health data using natural language. Ask a question, and Atlas autonomously decides which data tools to call, fetches real numbers from a local SQLite database, and streams back a structured answer with evidence tables.

---

## What it does

Type a question like:

> *"Compare life expectancy between Japan and Brazil in 2019"*

Atlas will:
1. Route the query to an LLM (Llama 3.3 70B via Groq)
2. The LLM autonomously selects and calls the right MCP tools
3. Tools query a local SQLite database populated from the WHO GHO API
4. Structured results stream back to the UI in real time
5. Evidence tables render from typed JSON — no markdown parsing, no guessing

---

## Architecture

```
WHO GHO API
    ↓
ETL Pipeline (pipeline.py)
    ↓
SQLite Database (health_signals.db)
    ↓
MCP Tools Server (server.py)        ← stdio transport
    ↓
FastAPI + SSE Backend (api.py)      ← streams tool_call / tool_result / answer_token events
    ↓
React Frontend (Vite)               ← routes by result type → typed Evidence components
```

**The LLM writes prose. React renders visuals. They never swap jobs.**

---

## Health Indicators

Data sourced from the [WHO Global Health Observatory](https://www.who.int/data/gho) API:

| Indicator | WHO Code | Description |
|---|---|---|
| `NCD_MORTALITY_PROB` | NCDMORT3070 | Premature NCD mortality probability, ages 30–70 (%) |
| `AIR_POLLUTION_PM25` | SDGPM25 | Fine particulate matter PM2.5 concentration (µg/m³) |
| `HOSPITAL_BED_DENSITY` | WHS4_100 | Hospital beds per 10,000 population |
| `LIFE_EXPECTANCY` | WHOSIS_000001 | Life expectancy at birth (years) |

---

## MCP Tools

| Tool | Description |
|---|---|
| `get_country_health_profile` | All indicators for a country in a given year |
| `compare_countries` | Side-by-side value for two countries on one indicator |
| `rank_countries_by_indicator` | Top N countries by indicator and year |
| `get_health_trend` | Time-series with % change for a country/indicator range |

---

## Tech Stack

**Backend**
- Python, FastAPI, Server-Sent Events (SSE)
- [MCP](https://modelcontextprotocol.io) (Model Context Protocol) via `fastmcp`
- Groq API — Llama 3.3 70B Versatile
- SQLite

**Frontend**
- React + Vite
- Cormorant Garamond + Bitcount Grid Double (Google Fonts)
- No UI library — custom CSS only

---

## Getting Started

### 1. Clone and set up the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 2. Add your Groq API key

Create `backend/.env`:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

### 3. Run the ETL pipeline

Fetches data from the WHO API and populates the local database (~2–3 minutes):

```bash
python pipeline.py
```

### 4. Start the backend

```bash
uvicorn api:app --reload
```

API runs at `http://localhost:8000`. Check `http://localhost:8000/health` to confirm 4 tools are loaded.

### 5. Start the frontend

```bash
cd ../frontend-app
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Example Queries

- `Compare the full health profiles of France and Japan in 2019`
- `Which country had the highest NCD mortality in 2020?`
- `How has life expectancy changed in Nigeria between 2015 and 2020?`
- `Rank the top 10 countries by hospital bed density in 2018`
- `Compare air pollution between China and India in 2020`

---

## Project Structure

```
etl-mcp-health/
├── backend/
│   ├── pipeline.py       # Phase 1: ETL — WHO API → SQLite
│   ├── server.py         # Phase 2: MCP tools server (stdio)
│   ├── client.py         # Phase 3: Terminal agentic client
│   ├── api.py            # Phase 4: FastAPI SSE backend
│   ├── config.py         # Indicator codes and DB path
│   └── requirements.txt
└── frontend-app/         # Phase 5: React UI
    └── src/
        ├── components/
        │   ├── QueryBar.jsx       # Search input
        │   ├── EmptyState.jsx     # Landing with suggestions
        │   ├── ResultsView.jsx    # Question / Answer / Evidence / Activity
        │   └── EvidenceBlock.jsx  # Typed evidence renderer (routes by type)
        ├── App.jsx
        └── App.css
```
