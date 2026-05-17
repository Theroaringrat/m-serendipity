# M-Serendipity

An AI-powered research lab matchmaker for UMich students. Given a research interest, it recommends the most relevant faculty and explains why — covering fit, openness to undergraduates, and current recruiting status.

## The Problem

Finding a research mentor at a large university is a cold-start problem: students don't know which labs are a good fit, and faculty pages are unstructured and hard to compare. M-Serendipity automates the discovery process by indexing 35+ UMich Robotics faculty and letting an LLM agent reason over the data.

## Architecture

```
Faculty pages (35+ labs)
        │
        ▼
  Crawl4AI (ETL)          ← two-tier scraper: lab homepage + subpages
        │
        ▼
  ChromaDB (vector DB)    ← chunked by page type: research / join / people
        │
        ▼
  ReAct Agent (LangGraph) ← dynamically routes between two tools:
    ├─ search_by_direction(query)      → semantic vector search
    └─ get_professor_details(name)     → full structured lookup
        │
        ▼
  Streamlit frontend      ← interactive recommendations
```

## Tech Stack

| Layer | Tools |
|---|---|
| Agent | LangGraph, LangChain, Gemini |
| Vector DB | ChromaDB, Gemini Embedding |
| ETL / Scraping | Crawl4AI (Playwright) |
| Frontend | Streamlit |
| Language | Python |

## Setup

1. Clone the repo and install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

2. Set your API key:
```bash
export GOOGLE_API_KEY=your_key_here
```

3. Run the ETL pipeline to build the vector DB:
```bash
python ingest.py
```

4. Launch the app:
```bash
streamlit run app.py
```
