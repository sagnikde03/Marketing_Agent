from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, List, Dict, Any

from app.core.config import settings
from app.core.cache import cache
from app.core.graph_db import graph_client
from app.core.vector_db import vector_store
from app.connectors.hubspot import hubspot_connector
from app.etl.chunker import smart_chunker
from app.etl.indexer import vector_indexer
from app.etl.graph_loader import graph_loader
from app.engine.orchestrator import master_orchestrator
from app.services.html_builder import html_builder
from app.models.schemas import PlaybookOutput, DealModel

app = FastAPI(
    title="AriGentic API",
    description="Intelligent Deal Preparation & MEDDIC Strategy Platform REST API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "platform": "AriGentic",
        "description": "Intelligent Deal Preparation & MEDDIC Strategy Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health_check():
    neo4j_online = graph_client.connect()
    vector_online = vector_store.connect()
    redis_online = cache.is_connected
    llm_configured = bool(settings.OPENAI_API_KEY)
    
    hubspot_status = "NOT_CONFIGURED"
    if settings.HUBSPOT_ACCESS_TOKEN:
        try:
            hubspot_connector.test_connection()
            hubspot_status = "CONNECTED"
        except Exception as e:
            hubspot_status = f"ERROR: {e}"

    return {
        "status": "ok",
        "components": {
            "hubspot": hubspot_status,
            "neo4j": "CONNECTED" if neo4j_online else "OFFLINE",
            "qdrant": "IN-MEMORY" if vector_store.is_in_memory else ("CONNECTED" if vector_online else "OFFLINE"),
            "redis": "CONNECTED" if redis_online else "IN-MEMORY_FALLBACK",
            "llm": f"CONFIGURED ({settings.LLM_MODEL})" if llm_configured else "HEURISTIC_OFFLINE_MODE"
        }
    }


@app.get("/deals")
def list_deals(limit: int = Query(10, ge=1, le=100)):
    try:
        deals = hubspot_connector.get_deals(limit=limit)
        return {"count": len(deals), "results": deals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/deals/{deal_id}", response_model=DealModel)
def get_deal(deal_id: str):
    try:
        deal = hubspot_connector.get_deal_detail(deal_id)
        return deal
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Deal not found or failed to fetch: {e}")


@app.post("/deals/{deal_id}/playbook", response_model=PlaybookOutput)
def generate_playbook(deal_id: str):
    try:
        # Check cache first
        cached_pb = cache.get_json(f"playbook:{deal_id}")
        if cached_pb:
            return PlaybookOutput(**cached_pb)

        deal = hubspot_connector.get_deal_detail(deal_id)
        chunks = smart_chunker.chunk_deal(deal)
        vector_indexer.index_deal_chunks(chunks)
        graph_loader.load_deal_graph(deal)

        playbook = master_orchestrator.generate_playbook(deal)
        html_builder.build_and_save(deal, playbook)
        return playbook
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate playbook: {e}")


@app.get("/deals/{deal_id}/playbook/html", response_class=HTMLResponse)
def get_playbook_html(deal_id: str):
    try:
        deal = hubspot_connector.get_deal_detail(deal_id)
        playbook = master_orchestrator.generate_playbook(deal)
        path = html_builder.build_and_save(deal, playbook)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render HTML playbook: {e}")


@app.get("/graph/stats")
def graph_stats():
    return graph_client.get_graph_stats()

