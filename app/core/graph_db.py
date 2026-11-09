from neo4j import GraphDatabase, Driver
from typing import Optional, List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self._driver: Optional[Driver] = None

    def connect(self) -> bool:
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=2.0
            )
            self._driver.verify_connectivity()
            self._init_schema()
            logger.info("Connected to Neo4j successfully.")
            return True
        except Exception as e:
            logger.warning(f"Neo4j connection could not be established: {e}")
            self._driver = None
            return False

    @property
    def is_connected(self) -> bool:
        if not self._driver:
            return self.connect()
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return self.connect()

    def _init_schema(self):
        if not self._driver:
            return
        queries = [
            "CREATE CONSTRAINT deal_id_unique IF NOT EXISTS FOR (d:Deal) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT contact_id_unique IF NOT EXISTS FOR (p:Contact) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT engagement_id_unique IF NOT EXISTS FOR (e:Engagement) REQUIRE e.id IS UNIQUE",
        ]
        try:
            with self._driver.session() as session:
                for q in queries:
                    session.run(q)
        except Exception as e:
            logger.debug(f"Neo4j schema init notice: {e}")

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        if not self.is_connected or not self._driver:
            return None
        try:
            with self._driver.session() as session:
                return session.run(query, parameters or {}).consume()
        except Exception as e:
            logger.error(f"Neo4j write error: {e}")
            return None

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.is_connected or not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Neo4j read error: {e}")
            return []

    def get_deal_stakeholders(self, deal_id: str) -> List[Dict[str, Any]]:
        query = """
        MATCH (p:Contact)-[:INVOLVED_IN]->(d:Deal {id: $deal_id})
        OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
        RETURN p.id as id, p.first_name as first_name, p.last_name as last_name,
               p.email as email, p.job_title as job_title, c.name as company_name
        """
        return self.execute_read(query, {"deal_id": deal_id})

    def get_graph_stats(self) -> Dict[str, int]:
        if not self.is_connected:
            return {"deals": 0, "companies": 0, "contacts": 0, "engagements": 0}
        
        def safe_count(label: str) -> int:
            res = self.execute_read(f"MATCH (n:{label}) RETURN count(n) as c")
            return res[0]["c"] if res and "c" in res[0] else 0

        return {
            "deals": safe_count("Deal"),
            "companies": safe_count("Company"),
            "contacts": safe_count("Contact"),
            "engagements": safe_count("Engagement"),
        }

    def close(self):
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None


graph_client = Neo4jClient()
