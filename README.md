# Atlas — Global Health Intelligence

An agentic AI application that lets you explore WHO global health data using natural language.
Ask a question, and Atlas autonomously decides which tools to call, runs real analytical
computation against a local SQLite database, and streams back a structured answer with
evidence tables.

---

## What it does

Type a question like:

> *"Compare life expectancy between Japan and Brazil in 2019"*

Atlas will:
1. Route the query to an LLM (Llama 3.3 70B via Groq)
2. The LLM autonomously selects and calls the right MCP tools
3. Tools run analytical computation — percentiles, trend classification, distribution stats — against a local SQLite database
4. Structured findings stream back to the UI in real time
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
MCP Tools Server (server.py)        ← stdio transport, analytical computation layer
    ↓
FastAPI + SSE Backend (api.py)      ← streams tool_call / tool_result / answer_token events
    ↓
React Frontend (Vite)               ← routes by result type → typed Evidence components
```

**The LLM writes prose. The tools compute findings. React renders visuals. None of them swap jobs.**

---

## Health Indicators

Data sourced from the [WHO Global Health Observatory](https://www.who.int/data/gho) API:

| Key | WHO Code | Description | Direction |
|---|---|---|---|
| `LIFE_EXPECTANCY` | WHOSIS_000001 | Life expectancy at birth (years) | higher is better |
| `HOSPITAL_BED_DENSITY` | WHS4_100 | Hospital beds per 10,000 population | higher is better |
| `NCD_MORTALITY_PROB` | NCDMORT3070 | Premature NCD mortality probability, ages 30–70 (%) | lower is better |
| `AIR_POLLUTION_PM25` | SDGPM25 | Fine particulate matter PM2.5 concentration (µg/m³) | lower is better |

The `higher_is_better` flag in `config.py` drives percentile direction, ranking sort order,
and trend classification across all tools — so analytical results are always in health terms,
not raw value terms.

---

## MCP Tools

Each tool performs non-trivial computation. The LLM receives findings it could not produce
from raw rows alone.

### `get_country_health_profile(country_code, year)`
Full health profile for one country in a given year.
- Health-adjusted global percentile for each indicator
- Strongest and weakest indicator by percentile (missing data excluded)
- Missing data flags per indicator

### `compare_countries(country_a, country_b, year)`
Side-by-side comparison across **all** indicators in one call.
- Health-adjusted percentile for both countries per indicator
- Absolute difference and which country leads (by health outcome, not raw value)
- Indicator with the largest gap between the two countries
- Missing data flags

### `get_health_trend(country_code, indicator_name, start_year, end_year)`
Time-series analysis for one country/indicator over a year range.
- Overall % change
- Year-over-year changes for every step
- Best and worst outcome years (direction-aware — least pollution = best year for PM2.5)
- Trend classification: `improving` / `declining` / `volatile` / `stable` / `insufficient_data`
  - Requires ≥ 4 data points to classify
  - 1% tolerance band filters noise from genuine direction changes
  - Classification accounts for indicator direction — rising PM2.5 = `declining`, not `improving`

### `rank_countries_by_indicator(indicator_name, year, limit=10)`
Top N countries by best health outcome for an indicator/year.
- Sort direction driven by `higher_is_better` — rankings always mean best health outcome
- Health-adjusted percentile per ranked country
- Global distribution stats: mean, median, min, max, stdev, n

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
source .venv/bin/activate    # macOS/Linux
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
- `Which country had the lowest NCD mortality in 2020?`
- `How has life expectancy changed in Nigeria between 2015 and 2020?`
- `Rank the top 10 countries by hospital bed density in 2018`
- `Compare air pollution between China and India in 2020`

---

## Project Structure

```
etl-mcp-health/
├── backend/
│   ├── config.py         # Indicator definitions — code, label, unit, higher_is_better
│   ├── pipeline.py       # ETL — WHO GHO API → SQLite
│   ├── server.py         # MCP tools server (stdio) — analytical computation layer
│   ├── client.py         # Terminal agentic client (development/testing)
│   ├── api.py            # FastAPI SSE backend
│   └── requirements.txt
└── frontend-app/
    └── src/
        ├── components/
        │   ├── QueryBar.jsx       # Search input
        │   ├── EmptyState.jsx     # Landing with example queries
        │   ├── ResultsView.jsx    # Question / Answer / Evidence / Activity
        │   └── EvidenceBlock.jsx  # Routes typed evidence to the right card component
        ├── App.jsx
        └── App.css
```
