from app.core.graph_db import graph_client
from app.models.schemas import DealModel
import logging

logger = logging.getLogger(__name__)


class Neo4jGraphLoader:
    """Loads deal entities, buying committee, companies, and notes into Neo4j Knowledge Graph."""

    def load_deal_graph(self, deal: DealModel) -> bool:
        if not graph_client.is_connected:
            logger.info("Neo4j not connected. Skipping graph sync.")
            return False

        try:
            # 1. Upsert Deal node
            deal_query = """
            MERGE (d:Deal {id: $deal_id})
            SET d.name = $name,
                d.amount = $amount,
                d.stage = $stage,
                d.pipeline = $pipeline,
                d.close_date = $close_date,
                d.updated_at = datetime()
            """
            graph_client.execute_write(deal_query, {
                "deal_id": deal.id,
                "name": deal.name,
                "amount": deal.amount or 0.0,
                "stage": deal.stage or "Unknown",
                "pipeline": deal.pipeline or "default",
                "close_date": deal.close_date or ""
            })

            # 2. Upsert Company node and relationship
            if deal.company:
                comp_query = """
                MERGE (c:Company {id: $company_id})
                SET c.name = $name,
                    c.domain = $domain,
                    c.industry = $industry,
                    c.number_of_employees = $employees,
                    c.annual_revenue = $revenue
                WITH c
                MATCH (d:Deal {id: $deal_id})
                MERGE (d)-[:FOR_COMPANY]->(c)
                """
                graph_client.execute_write(comp_query, {
                    "company_id": deal.company.id,
                    "name": deal.company.name or "Unknown Company",
                    "domain": deal.company.domain or "",
                    "industry": deal.company.industry or "",
                    "employees": str(deal.company.number_of_employees or ""),
                    "revenue": str(deal.company.annual_revenue or ""),
                    "deal_id": deal.id
                })

            # 3. Upsert Contact nodes and relationships
            for contact in deal.contacts:
                contact_query = """
                MERGE (p:Contact {id: $contact_id})
                SET p.first_name = $first_name,
                    p.last_name = $last_name,
                    p.email = $email,
                    p.job_title = $job_title
                WITH p
                MATCH (d:Deal {id: $deal_id})
                MERGE (p)-[:INVOLVED_IN]->(d)
                """
                graph_client.execute_write(contact_query, {
                    "contact_id": contact.id,
                    "first_name": contact.first_name or "",
                    "last_name": contact.last_name or "",
                    "email": contact.email or "",
                    "job_title": contact.job_title or "",
                    "deal_id": deal.id
                })

                # If company exists, link contact to company
                if deal.company:
                    link_query = """
                    MATCH (p:Contact {id: $contact_id}), (c:Company {id: $company_id})
                    MERGE (p)-[:WORKS_AT]->(c)
                    """
                    graph_client.execute_write(link_query, {
                        "contact_id": contact.id,
                        "company_id": deal.company.id
                    })

            # 4. Upsert Engagements
            for eng in deal.engagements:
                eng_query = """
                MERGE (e:Engagement {id: $eng_id})
                SET e.type = $type,
                    e.created_at = $created_at,
                    e.snippet = $snippet
                WITH e
                MATCH (d:Deal {id: $deal_id})
                MERGE (d)-[:HAS_ENGAGEMENT]->(e)
                """
                graph_client.execute_write(eng_query, {
                    "eng_id": eng.id,
                    "type": eng.type,
                    "created_at": eng.created_at or "",
                    "snippet": (eng.body[:250] if eng.body else "").replace("\n", " "),
                    "deal_id": deal.id
                })

            logger.info(f"Successfully loaded Deal #{deal.id} into Neo4j graph.")
            return True
        except Exception as e:
            logger.error(f"Error loading deal {deal.id} into Neo4j: {e}")
            return False


graph_loader = Neo4jGraphLoader()
