import sys
import os
import warnings

# Suppress harmless OpenSSL LibreSSL version notice on macOS
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import print as rprint

from app.core.config import settings
from app.core.cache import cache
from app.core.graph_db import graph_client
from app.core.vector_db import vector_store
from app.connectors.hubspot import hubspot_connector
from app.etl.chunker import smart_chunker
from app.etl.graph_loader import graph_loader
from app.etl.indexer import vector_indexer
from app.engine.orchestrator import master_orchestrator
from app.services.html_builder import html_builder

cli = typer.Typer(help="AriGentic — Intelligent Deal Preparation Platform CLI")
console = Console()


@cli.command()
def test_connection():
    """Test HubSpot API Token, Neo4j, Qdrant, Redis, and LLM connectivity."""
    console.print(Panel.fit("[bold cyan]AriGentic — System Connectivity Diagnostic[/bold cyan]"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="dim", width=22)
    table.add_column("Status", width=15)
    table.add_column("Details")

    # 1. HubSpot Test
    if not settings.HUBSPOT_ACCESS_TOKEN:
        table.add_row(
            "HubSpot CRM",
            "[bold yellow]OFFLINE / DEMO[/bold yellow]",
            "HUBSPOT_ACCESS_TOKEN empty. Using built-in demo deal & raw lake fallback."
        )
    else:
        try:
            res = hubspot_connector.test_connection()
            deal_count = len(res.get("results", []))
            table.add_row("HubSpot CRM", "[bold green]CONNECTED[/bold green]", f"Token valid. Found {deal_count}+ accessible deals.")
        except Exception as e:
            table.add_row("HubSpot CRM", "[bold red]ERROR[/bold red]", str(e))

    # 2. Neo4j Graph DB Test
    if graph_client.connect():
        table.add_row("Neo4j Graph DB", "[bold green]CONNECTED[/bold green]", f"Connected to {settings.NEO4J_URI}")
    else:
        table.add_row("Neo4j Graph DB", "[bold yellow]OFFLINE[/bold yellow]", "Docker container not running. Start with 'docker compose up -d neo4j'")

    # 3. Qdrant Vector DB Test
    if vector_store.connect():
        if vector_store.is_in_memory:
            table.add_row("Qdrant Vector DB", "[bold yellow]IN-MEMORY[/bold yellow]", "Using local in-memory fallback until container starts.")
        else:
            table.add_row("Qdrant Vector DB", "[bold green]CONNECTED[/bold green]", f"Ready on {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    else:
        table.add_row("Qdrant Vector DB", "[bold red]ERROR[/bold red]", "Failed to initialize vector database.")

    # 4. Redis Working Memory Test
    if cache.is_connected:
        table.add_row("Redis Working Memory", "[bold green]CONNECTED[/bold green]", f"Ready on {settings.REDIS_URL}")
    else:
        table.add_row("Redis Working Memory", "[bold yellow]IN-MEMORY[/bold yellow]", "Using local in-memory dict fallback.")

    # 5. LLM Engine Test
    if settings.OPENAI_API_KEY:
        table.add_row("LLM Engine", "[bold green]CONFIGURED[/bold green]", f"Model: {settings.LLM_MODEL}")
    else:
        table.add_row("LLM Engine", "[bold yellow]NOT SET[/bold yellow]", "OPENAI_API_KEY empty. Running in heuristic/local fallback mode.")

    console.print(table)


@cli.command()
def sync_all(limit: int = typer.Option(10, help="Max deals to sync")):
    """Ingest all deals, companies, contacts, and notes from HubSpot into the Raw Lake and Graph."""
    console.print(Panel.fit(f"[bold cyan]AriGentic — Ingesting Deals into Raw Lake & Knowledge Graph (Limit: {limit})[/bold cyan]"))

    deals = hubspot_connector.get_deals(limit=limit)
    if not deals:
        console.print("[yellow]No deals found in HubSpot portal or raw lake.[/yellow]")
        return

    table = Table(title="Ingestion Summary", show_header=True, header_style="bold green")
    table.add_column("Deal ID", style="cyan", width=16)
    table.add_column("Deal Name", width=30)
    table.add_column("Company", width=22)
    table.add_column("Contacts", justify="right", width=10)
    table.add_column("Notes/Calls", justify="right", width=12)
    table.add_column("Graph Sync", width=12)

    for d in deals:
        deal_id = d["id"]
        deal_name = d.get("properties", {}).get("dealname") or f"Deal #{deal_id}"
        console.print(f"  [cyan]➔ Ingesting Deal #{deal_id}:[/cyan] {deal_name}...")
        deal_detail = hubspot_connector.get_deal_detail(deal_id)
        chunks = smart_chunker.chunk_deal(deal_detail)
        vector_indexer.index_deal_chunks(chunks)
        graph_synced = graph_loader.load_deal_graph(deal_detail)

        table.add_row(
            deal_detail.id,
            deal_detail.name[:28] + ("..." if len(deal_detail.name) > 28 else ""),
            (deal_detail.company.name if deal_detail.company else "N/A")[:20],
            str(len(deal_detail.contacts)),
            str(len(deal_detail.engagements)),
            "[green]Synced[/green]" if graph_synced else "[yellow]Skipped[/yellow]"
        )

    console.print("\n")
    console.print(table)
    console.print(f"\n[bold green][SUCCESS] Ingestion Complete![/bold green] Raw immutable JSON saved to [cyan]{settings.raw_lake_dir.resolve()}[/cyan]\n")


@cli.command()
def inspect_deal(deal_id: str = typer.Argument("sample-deal", help="HubSpot Deal ID to inspect (defaults to 'sample-deal')")):
    """Inspect ingested deal data, buying committee, and raw files without generating a report."""
    console.print(Panel.fit(f"[bold cyan]Inspecting Ingested Deal #{deal_id}[/bold cyan]"))

    deal = hubspot_connector.get_deal_detail(deal_id)
    chunks = smart_chunker.chunk_deal(deal)

    # 1. Overview Table
    ov_table = Table(show_header=False, box=None)
    ov_table.add_column("Field", style="bold cyan", width=18)
    ov_table.add_column("Value")
    ov_table.add_row("Deal Name:", deal.name)
    ov_table.add_row("Amount:", f"${deal.amount:,.2f}" if deal.amount is not None else "Unspecified")
    ov_table.add_row("Stage:", deal.stage or "N/A")
    ov_table.add_row("Pipeline:", deal.pipeline or "N/A")
    ov_table.add_row("Close Date:", deal.close_date or "N/A")
    ov_table.add_row("Company:", f"{deal.company.name} ({deal.company.domain or 'No domain'})" if deal.company else "None")
    console.print(ov_table)

    # 2. Contacts / Buying Committee
    if deal.contacts:
        c_table = Table(title=f"Buying Committee ({len(deal.contacts)} Contacts)", show_header=True, header_style="bold magenta")
        c_table.add_column("Name", width=22)
        c_table.add_column("Job Title", width=32)
        c_table.add_column("Email", width=28)
        for c in deal.contacts:
            c_table.add_row(f"{c.first_name or ''} {c.last_name or ''}".strip() or "Unnamed", c.job_title or "N/A", c.email or "N/A")
        console.print(c_table)
    else:
        console.print("\n[dim yellow]No contacts associated with this deal in HubSpot.[/dim yellow]")

    # 3. Engagements & Notes
    if deal.engagements:
        e_table = Table(title=f"Engagements & Notes ({len(deal.engagements)} total)", show_header=True, header_style="bold blue")
        e_table.add_column("Type", width=12)
        e_table.add_column("Date", width=14)
        e_table.add_column("Content Snippet")
        for e in deal.engagements:
            snippet = e.body[:120].replace("\n", " ") + ("..." if len(e.body) > 120 else "")
            e_table.add_row(e.type, (e.created_at or "")[:10], snippet)
        console.print(e_table)
    else:
        console.print("\n[dim yellow]No notes, calls, or emails logged for this deal.[/dim yellow]")

    console.print(f"\n[dim]Smart Chunks Created:[/dim] [bold cyan]{len(chunks)} text chunks[/bold cyan]")


@cli.command()
def inspect_graph():
    """Inspect Neo4j Knowledge Graph contents and node counts."""
    if not graph_client.connect():
        console.print("[bold yellow]Neo4j is currently offline. Start with 'docker compose up -d neo4j'[/bold yellow]")
        return

    stats = graph_client.get_graph_stats()

    table = Table(title="Neo4j Knowledge Graph Entities", show_header=True, header_style="bold green")
    table.add_column("Entity Node Label", style="cyan", width=22)
    table.add_column("Count in Graph", justify="right", width=16)
    table.add_row("(:Deal)", str(stats.get("deals", 0)))
    table.add_row("(:Company)", str(stats.get("companies", 0)))
    table.add_row("(:Contact)", str(stats.get("contacts", 0)))
    table.add_row("(:Engagement)", str(stats.get("engagements", 0)))
    console.print(table)
    console.print("\n[dim]Explore visually in your browser at:[/dim] [bold cyan]http://localhost:7474[/bold cyan]\n")


@cli.command()
def generate(deal_id: str = typer.Argument("sample-deal", help="HubSpot Deal ID (defaults to 'sample-deal')")):
    """Run the complete pipeline: Ingestion -> ETL -> Vector DB -> Neo4j -> Verified MEDDIC Playbook."""
    console.print(Panel.fit(f"[bold cyan]AriGentic — Generating Playbook for Deal #{deal_id}[/bold cyan]"))

    with console.status("[bold green]1. Ingesting Deal & Associations...[/bold green]"):
        deal = hubspot_connector.get_deal_detail(deal_id)

    with console.status("[bold green]2. Performing Smart Chunking & Vector Indexing...[/bold green]"):
        chunks = smart_chunker.chunk_deal(deal)
        vector_indexer.index_deal_chunks(chunks)

    with console.status("[bold green]3. Syncing Entities to Neo4j Knowledge Graph...[/bold green]"):
        graph_loader.load_deal_graph(deal)

    with console.status("[bold green]4. Running Multi-Agent Deal Engine & Verification Gate...[/bold green]"):
        playbook = master_orchestrator.generate_playbook(deal)

    # 5. Build and Export Polished HTML Playbook
    html_path = html_builder.build_and_save(deal, playbook)

    # Render Beautiful Playbook to Console
    _render_playbook(playbook)
    console.print(Panel.fit(
        f"[bold green]✨ Interactive HTML Playbook successfully generated:[/bold green]\n[cyan]{html_path.resolve()}[/cyan]",
        title="HTML Export Complete"
    ))


@cli.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload on code change")
):
    """Launch AriGentic REST API Server via Uvicorn."""
    import uvicorn
    console.print(Panel.fit(
        f"[bold green]🚀 AriGentic API Server starting at http://{host}:{port}[/bold green]\n"
        f"API Documentation: [cyan]http://{host}:{port}/docs[/cyan]",
        title="API Server"
    ))
    uvicorn.run("app.api:app", host=host, port=port, reload=reload)


@cli.command()
def seed_demo():
    """Seed sample enterprise deal data into Raw Lake and generate demo playbook."""
    console.print(Panel.fit("[bold cyan]AriGentic — Seeding Demo Enterprise Dataset[/bold cyan]"))
    deal = hubspot_connector.seed_sample_deal()
    console.print(f"[bold green]✓ Seeded Deal:[/bold green] {deal.name} ({deal.company.name if deal.company else 'N/A'})")
    console.print(f"[bold green]✓ Ingested Contacts:[/bold green] {len(deal.contacts)}")
    console.print(f"[bold green]✓ Ingested Engagements:[/bold green] {len(deal.engagements)}")
    
    chunks = smart_chunker.chunk_deal(deal)
    vector_indexer.index_deal_chunks(chunks)
    console.print(f"[bold green]✓ Indexed Chunks:[/bold green] {len(chunks)} into vector store")

    playbook = master_orchestrator.generate_playbook(deal)
    html_path = html_builder.build_and_save(deal, playbook)
    console.print(f"[bold green]✓ Compiled HTML Playbook:[/bold green] [cyan]{html_path.resolve()}[/cyan]\n")
    console.print("[dim]Run 'python main.py generate sample-deal' to view full terminal output![/dim]")


def _render_playbook(pb):
    header = f"""
# 🎯 DEAL PLAYBOOK: {pb.deal_name}
**Generated:** {pb.generated_at} | **Methodology:** {pb.methodology} | **Confidence Score:** {pb.confidence_score} / 5.0

---
### 📌 Deal Summary
{pb.deal_summary}
"""
    console.print(Markdown(header))

    def print_section(sec):
        console.print(f"\n[bold yellow]{sec.title}[/bold yellow]")
        for item in sec.key_findings:
            console.print(f"  • {item}")
        
        # Print Grounded Citations
        if sec.claims:
            for c in sec.claims:
                if c.status == "GROUNDED" and c.source_citation:
                    console.print(f"    [dim green]↳ [{c.source_citation}][/dim green]")
                elif c.status == "UNSUPPORTED":
                    console.print(f"    [dim red]↳ ⚠️ [UNVERIFIED: No CRM source evidence found][/dim red]")

        if sec.strategy_recommendation:
            console.print(f"  [bold cyan]💡 Strategy Angle:[/bold cyan] {sec.strategy_recommendation}")

    print_section(pb.metrics)
    print_section(pb.economic_buyer)
    print_section(pb.decision_criteria)
    print_section(pb.decision_process)
    print_section(pb.identify_pain)
    print_section(pb.champion)
    print_section(pb.competitive_landscape)

    if pb.recommended_talk_tracks:
        console.print("\n[bold green]🗣️ RECOMMENDED TALK TRACKS FOR NEXT CALL[/bold green]")
        for track in pb.recommended_talk_tracks:
            console.print(f"  {track}")

    if pb.unverified_alerts:
        console.print("\n[bold red]⚠️ UNVERIFIED SIGNAL ALERTS (Needs Discovery Validation)[/bold red]")
        for alert in pb.unverified_alerts:
            console.print(f"  • {alert}")

    console.print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    cli()
