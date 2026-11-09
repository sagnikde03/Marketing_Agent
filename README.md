# DealCraft 🎯
### Autonomous Marketing & Sales Agent

DealCraft is an enterprise deal intelligence engine that automatically ingests CRM data, communications, and transcripts, models buying committees in a knowledge graph, indexes engagement evidence in a vector store, and synthesizes grounded, audit-verified **MEDDIC playbooks** and battlecards for enterprise sales teams.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Project Directory Structure](#-project-directory-structure)
- [Tech Stack & Dependencies](#-tech-stack--dependencies)
- [Prerequisites](#-prerequisites)
- [Quickstart Guide](#-quickstart-guide)
  - [1. Clone & Set Up Environment](#1-clone--set-up-environment)
  - [2. Configure Environment Variables](#2-configure-environment-variables)
  - [3. Start Database Infrastructure (Docker)](#3-start-database-infrastructure-docker)
- [CLI Reference & Usage](#-cli-reference--usage)
  - [Diagnostic Check](#1-system-diagnostic)
  - [Sync Deals from HubSpot](#2-sync-crm-deals)
  - [Inspect Deal & Buying Committee](#3-inspect-deal-details)
  - [Inspect Knowledge Graph](#4-inspect-knowledge-graph)
  - [Generate Deal Playbook](#5-generate-meddic-playbook)
- [Core Components & Deep Dive](#-core-components--deep-dive)
  - [HubSpot Connector & Raw Lake](#hubspot-connector--raw-lake)
  - [Smart Chunking Engine](#smart-chunking-engine)
  - [Neo4j Knowledge Graph](#neo4j-knowledge-graph)
  - [Qdrant Vector Database](#qdrant-vector-database)
  - [Multi-Agent Synthesis & Verification Gate](#multi-agent-synthesis--verification-gate)
  - [Interactive HTML Playbook Generator](#interactive-html-playbook-generator)
- [Configuration Reference](#-configuration-reference)
- [Fallback & Offline Resilience](#-fallback--offline-resilience)
- [License](#-license)

---

## 🌟 Overview

Enterprise sales reps spend hours manually reviewing CRM notes, call transcripts, and past emails before discovery and negotiation calls. Existing generic AI summaries often hallucinate facts or give boilerplate advice that costs deals.

**DealCraft solves this by combining:**
1. **Deterministic Data Grounding:** Every claim in the playbook is verified against timestamped source citations (notes, call snippets, emails).
2. **Graph-Backed Buying Committee Intelligence:** Direct visual and relational mapping of Economic Buyers, Champions, Blockers, and Influencers across organizations.
3. **MEDDIC Framework Alignment:** Structured analysis directly tailored to Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, and Champion.
4. **Dual Output Modalities:** Instant interactive terminal visualization via Rich CLI and self-contained, publication-grade HTML playbooks.

---

## ✨ Key Features

- **HubSpot CRM Integration:** Automated extraction of Deals, Companies, associated Contacts, and full engagement histories (Notes, Calls, Meetings, Emails).
- **Immutable Raw Lake:** Archival storage of raw JSON records (`data/raw/`) preserving audit trails and source state.
- **Smart Chunking:** Speaker-turn segmentation for call transcripts, HTML sanitization, and structured deal/company summary chunking.
- **Dual Vector & Graph Memory:**
  - **Qdrant Vector Store:** Semantic search with local embeddings (`BAAI/bge-small-en-v1.5` via FastEmbed) or OpenAI embeddings with automatic in-memory fallback.
  - **Neo4j Knowledge Graph:** Relational mapping of `Deal`, `Company`, `Contact`, and `Engagement` nodes with constraint enforcement.
- **Self-Correcting Verification Gate:** Two-stage AI pipeline where a **Verification Agent** cross-references the **Strategy Agent's** draft against text chunks, tagging claims as `GROUNDED` or `UNSUPPORTED`.
- **Offline / Heuristic Mode:** Built-in rule-based heuristic synthesis that works even when offline or without an OpenAI API key.
- **Interactive HTML Playbooks:** Beautifully styled, standalone HTML deal briefs saved to `./playbooks/` with status badges, stakeholder mapping, talk tracks, and risk alerts.

---

## 🏛️ Architecture

```
                                  ┌────────────────────────┐
                                  │      HubSpot CRM       │
                                  │ (Deals/Contacts/Notes) │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                 [app/connectors/hubspot.py]
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
          ┌─────────────────────┐                          ┌─────────────────────┐
          │    Raw Data Lake    │                          │    Smart Chunker    │
          │     (data/raw/)     │                          │ (app/etl/chunker.py)│
          └─────────────────────┘                          └──────────┬──────────┘
                                                                      │
                                     ┌────────────────────────────────┴────────────────────────────────┐
                                     ▼                                                                 ▼
                          ┌─────────────────────┐                                           ┌─────────────────────┐
                          │   Neo4j Graph DB    │                                           │  Qdrant Vector DB   │
                          │(app/etl/graph_loader│                                           │ (app/etl/indexer.py)│
                          │   & core/graph_db)  │                                           │ & core/vector_db)   │
                          └──────────┬──────────┘                                           └──────────┬──────────┘
                                     │                                                                 │
                                     └────────────────────────────────┬────────────────────────────────┘
                                                                      │
                                                                      ▼
                                                      ┌───────────────────────────────┐
                                                      │    Master Deal Orchestrator   │
                                                      │  (app/engine/orchestrator.py) │
                                                      └───────────────┬───────────────┘
                                                                      │
                                                                      ▼
                                                      ┌───────────────────────────────┐
                                                      │   Strategy Agent Synthesis    │
                                                      │    (MEDDIC Strategy Model)    │
                                                      └───────────────┬───────────────┘
                                                                      │
                                                                      ▼
                                                      ┌───────────────────────────────┐
                                                      │   Verification Agent Gate     │
                                                      │   (app/engine/verifier.py)    │
                                                      │   [GROUNDED vs UNSUPPORTED]   │
                                                      └───────────────┬───────────────┘
                                                                      │
                                             ┌────────────────────────┴────────────────────────┐
                                             ▼                                                 ▼
                                  ┌─────────────────────┐                           ┌─────────────────────┐
                                  │   Rich Console UI   │                           │ Interactive HTML PB │
                                  │  (Terminal Output)  │                           │(app/services/html..)│
                                  └─────────────────────┘                           └─────────────────────┘
```

---

## 📂 Project Directory Structure

```
Marketing_Agent/
├── app/
│   ├── connectors/
│   │   └── hubspot.py          # HubSpot REST API connector & raw lake sync
│   ├── core/
│   │   ├── config.py           # Pydantic Settings & environment variables
│   │   ├── graph_db.py         # Neo4j client, schema init, & cypher query execution
│   │   └── vector_db.py        # Qdrant client, collection mgmt, & in-memory fallback
│   ├── engine/
│   │   ├── orchestrator.py     # Master Deal Orchestrator & heuristic engine
│   │   ├── prompts.py          # MEDDIC system, strategy, & verification prompts
│   │   └── verifier.py         # Verification agent for citation grounding
│   ├── etl/
│   │   ├── chunker.py          # Smart chunker for transcripts, notes, and CRM records
│   │   ├── graph_loader.py     # Neo4j graph loader for deals, contacts, & companies
│   │   └── indexer.py          # Vector embedding generator & Qdrant indexer
│   ├── models/
│   │   └── schemas.py          # Pydantic data models (Deal, Contact, Playbook, etc.)
│   └── services/
│       └── html_builder.py     # Generator for modern standalone HTML deal playbooks
├── data/
│   ├── raw/                    # Immutable data lake storage (deals, companies, contacts, notes)
│   └── sample_playbook.html    # Reference compiled playbook artifact
├── playbooks/                  # Output directory for generated HTML playbooks
├── docker-compose.yml          # Container definitions: Neo4j 5.26, Qdrant v1.12, Redis 7
├── main.py                     # CLI entrypoint (Typer + Rich)
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration template
└── README.md                   # Project documentation
```

---

## 🛠️ Tech Stack & Dependencies

- **Language & Runtime:** Python 3.10+
- **CLI & Formatting:** [Typer](https://typer.tiangolo.com/), [Rich](https://github.com/Textualize/rich)
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/), [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Knowledge Graph:** [Neo4j 5.26](https://neo4j.com/) with APOC library (`neo4j-python-driver`)
- **Vector Database:** [Qdrant v1.12](https://qdrant.tech/) (`qdrant-client`)
- **Working Memory / Cache:** [Redis 7](https://redis.io/)
- **Embeddings & LLM:** [OpenAI](https://github.com/openai/openai-python) (`gpt-4o-mini`, `text-embedding-3-small`), [FastEmbed](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`)
- **HTTP Client:** [HTTPX](https://www.python-httpx.org/), [Requests](https://requests.readthedocs.io/)
- **API Server Ready:** [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)

---

## ⚡ Quickstart Guide

### 1. Clone & Set Up Environment

```bash
cd Marketing_Agent

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# HubSpot Private App Access Token (scopes: crm.objects.deals.read, crm.objects.contacts.read, crm.objects.companies.read)
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# LLM Provider (Leave empty to use built-in heuristic/offline mode)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Neo4j Graph DB
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# Qdrant Vector DB
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=dealcraft_deal_intel

# Redis Working Memory
REDIS_URL=redis://localhost:6379/0

# Raw Data Lake Path
RAW_DATA_LAKE_PATH=./data/raw
```

### 3. Start Database Infrastructure (Docker)

Start Neo4j, Qdrant, and Redis using Docker Compose:

```bash
docker compose up -d
```

Verify running containers:
- **Neo4j Web Browser:** [http://localhost:7474](http://localhost:7474) (Auth: `neo4j` / `password123`)
- **Qdrant REST Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Redis Server:** `localhost:6379`

> *Note:* If you don't have Docker running, DealCraft gracefully falls back to in-memory vector storage and local heuristic processing!

---

## 💻 CLI Reference & Usage

The application provides a comprehensive CLI powered by **Typer** and **Rich**.

### 1. System Diagnostic

Verify connectivity to HubSpot, Neo4j, Qdrant, and OpenAI:

```bash
python main.py test-connection
```

*Example Output:*
```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component          ┃ Status       ┃ Details                                     ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ HubSpot CRM        │ CONNECTED    │ Token valid. Found 10+ accessible deals.    │
│ Neo4j Graph DB     │ CONNECTED    │ Connected to bolt://localhost:7687          │
│ Qdrant Vector DB   │ CONNECTED    │ Ready on localhost:6333                     │
│ LLM Engine         │ CONFIGURED   │ Model: gpt-4o-mini                          │
└────────────────────┴──────────────┴─────────────────────────────────────────────┘
```

### 2. Sync CRM Deals

Ingest recent deals, companies, contacts, and note/call histories into the Raw Data Lake, Vector Store, and Neo4j Graph:

```bash
# Sync up to 10 deals (default)
python main.py sync-all

# Sync up to 25 deals
python main.py sync-all --limit 25
```

### 3. Inspect Deal Details

Inspect a deal's metadata, company info, buying committee (contacts), and engagement timeline without running the AI playbook generation:

```bash
python main.py inspect-deal <DEAL_ID>
```

Displays:
- Deal Name, Amount, Pipeline Stage, Target Close Date
- Associated Company & Domain
- Buying Committee members with Job Titles & Emails
- Engagements (Calls, Emails, Notes) snippet overview
- Number of smart chunks created

### 4. Inspect Knowledge Graph

Query the Neo4j graph for current entity counts and health:

```bash
python main.py inspect-graph
```

Displays node counts for `(:Deal)`, `(:Company)`, `(:Contact)`, and `(:Engagement)`.

### 5. Generate MEDDIC Playbook

Run the complete pipeline for a deal: Fetch -> Smart Chunk -> Vector Index -> Neo4j Graph Sync -> AI Synthesis -> Verification Gate -> Terminal Report + HTML Export:

```bash
python main.py generate <DEAL_ID>
```

This will:
1. Fetch the deal record and all associated records from HubSpot.
2. Ingest immutable raw JSON into `data/raw/`.
3. Generate structured and speaker-turn chunks via `smart_chunker`.
4. Index embeddings into Qdrant.
5. Upsert entities and relationships into Neo4j.
6. Execute `master_orchestrator` to generate the 6-pillar MEDDIC strategy.
7. Run `verifier` to ground every claim against timestamped citations.
8. Render a colored, formatted terminal summary.
9. Export a standalone interactive HTML Playbook to `playbooks/deal-playbook-<company>.html`.

---

## 🔍 Core Components & Deep Dive

### HubSpot Connector & Raw Lake
- **Location:** [app/connectors/hubspot.py](app/connectors/hubspot.py)
- Uses HubSpot CRM v3 REST API.
- Implements resilient batch extraction of deals and cross-object associations (`/crm/v3/objects/deals/{id}/associations/{companies,contacts,engagements}`).
- Automatically stores raw JSON into `data/raw/{deals, companies, contacts, notes}/{id}.json` to ensure auditable, immutable data lake persistence.

### Smart Chunking Engine
- **Location:** [app/etl/chunker.py](app/etl/chunker.py)
- Handles heterogenous CRM records:
  - **Overview Chunks:** Summarizes deal economics, pipeline stage, and buying committee.
  - **Call Transcripts:** Parses speaker turns (`Speaker 1: ...`, `Rep: ...`, `Prospect: ...`) to preserve contextual conversational dialogue.
  - **Notes & Emails:** Strips HTML formatting and chunks with author/date metadata.

### Neo4j Knowledge Graph
- **Location:** [app/core/graph_db.py](app/core/graph_db.py), [app/etl/graph_loader.py](app/etl/graph_loader.py)
- Creates a structured entity-relationship graph:
  ```cypher
  (:Deal)-[:FOR_COMPANY]->(:Company)
  (:Contact)-[:INVOLVED_IN]->(:Deal)
  (:Contact)-[:WORKS_AT]->(:Company)
  (:Deal)-[:HAS_ENGAGEMENT]->(:Engagement)
  ```
- Enforces uniqueness constraints on entity IDs.

### Qdrant Vector Database
- **Location:** [app/core/vector_db.py](app/core/vector_db.py), [app/etl/indexer.py](app/etl/indexer.py)
- Generates 384-dimensional dense vectors using FastEmbed (`BAAI/bge-small-en-v1.5`) or OpenAI embeddings.
- Automatic in-memory fallback (`QdrantClient(":memory:")`) if the Qdrant container is not reachable.

### Multi-Agent Synthesis & Verification Gate
- **Location:** [app/engine/orchestrator.py](app/engine/orchestrator.py), [app/engine/verifier.py](app/engine/verifier.py), [app/engine/prompts.py](app/engine/prompts.py)
- **Strategy Agent:** Generates MEDDIC pillars:
  - **M — Metrics:** Quantifiable target outcomes (ROI, cost reduction, cycle time).
  - **E — Economic Buyer:** Identifies budget sign-off authority and executive sponsors.
  - **D — Decision Criteria:** Technical, financial, and compliance requirements.
  - **D — Decision Process:** Procurement stages, legal approval, and milestones.
  - **I — Identify Pain:** Cost of inaction and operational bottlenecks.
  - **C — Champion:** Internal advocate mapping and relationship strength.
- **Verification Agent (Grounding):** Cross-references each strategic claim against indexed text chunks. Unsupported claims are flagged with `⚠️ [UNVERIFIED: No CRM source evidence found]` and moved to the **Unverified Alerts** section for discovery validation.

### Interactive HTML Playbook Generator
- **Location:** [app/services/html_builder.py](app/services/html_builder.py)
- Compiles a self-contained, beautifully styled HTML document including:
  - Header with Deal Value, Confidence Rating, and Pipeline Stage
  - Executive Deal Summary
  - Full MEDDIC breakdown cards with color-coded badges
  - Grounded source evidence tags (`[Source: Call note ...]`)
  - Strategic Call Talk Tracks
  - Unverified Signal Alerts for next discovery calls

---

## ⚙️ Configuration Reference

All settings can be configured via environment variables or a `.env` file:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot Private App Access Token | `""` |
| `OPENAI_API_KEY` | OpenAI API Key for Strategy & Verification LLMs | `""` |
| `LLM_MODEL` | OpenAI Model Name | `gpt-4o-mini` |
| `EMBEDDING_MODEL` | OpenAI Embedding Model | `text-embedding-3-small` |
| `NEO4J_URI` | Neo4j Bolt Connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j Username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j Password | `password123` |
| `QDRANT_HOST` | Qdrant Server Hostname | `localhost` |
| `QDRANT_PORT` | Qdrant Server REST Port | `6333` |
| `QDRANT_COLLECTION` | Qdrant Collection Name | `dealcraft_deal_intel` |
| `REDIS_URL` | Redis Connection URL | `redis://localhost:6379/0` |
| `RAW_DATA_LAKE_PATH` | Local Directory Path for Raw Lake Storage | `./data/raw` |

---

## 🛡️ Fallback & Offline Resilience

DealCraft is built to be resilient in disconnected, air-gapped, or rate-limited environments:

1. **No Docker / Database Offline:**
   - If **Neo4j** is offline, the CLI skips graph loading and warns gracefully.
   - If **Qdrant** is offline, it automatically instantiates an in-memory vector database.
2. **No OpenAI API Key / Offline LLM:**
   - If `OPENAI_API_KEY` is not provided or fails, DealCraft switches to the deterministic **Heuristic Strategy Engine**, parsing contact titles (CFO, VP, Director) and keyword triggers in engagement notes to generate a verified MEDDIC playbook.
3. **No Embeddings Provider:**
   - Uses local FastEmbed models or deterministic feature-hash pseudo-embeddings to ensure zero crashing during indexing.

---

## 📄 License

This project is proprietary and intended for internal use with the DealCraft Deal Preparation Platform. All rights reserved.
