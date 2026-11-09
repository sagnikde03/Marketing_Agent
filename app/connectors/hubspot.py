import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import settings
from app.models.schemas import DealModel, CompanyModel, ContactModel, EngagementModel

logger = logging.getLogger(__name__)


# Built-in reference sample deal for immediate out-of-the-box offline evaluation
DEMO_DEAL = {
    "id": "sample-deal",
    "properties": {
        "dealname": "Acme Corp — Global Enterprise Observability Modernization",
        "amount": "175000.00",
        "dealstage": "solution_evaluation",
        "pipeline": "enterprise_sales",
        "closedate": "2026-11-30",
        "hubspot_owner_id": "rep_alex_morgan",
        "description": "Enterprise cloud observability migration replacing legacy Datadog infrastructure with decoupled high-cardinality data lake."
    },
    "company": {
        "id": "comp-acme-1",
        "properties": {
            "name": "Acme Corporation",
            "domain": "acme.corp",
            "industry": "Fintech & Cloud Infrastructure",
            "numberofemployees": "4500",
            "annualrevenue": "450000000",
            "description": "Leading financial cloud infrastructure provider operating across North America and Europe."
        }
    },
    "contacts": [
        {
            "id": "contact-1",
            "properties": {
                "firstname": "Sarah",
                "lastname": "Chen",
                "email": "sarah.chen@acme.corp",
                "jobtitle": "VP of Infrastructure & Platform Engineering",
                "phone": "+1-415-555-0192"
            }
        },
        {
            "id": "contact-2",
            "properties": {
                "firstname": "Marcus",
                "lastname": "Vance",
                "email": "marcus.vance@acme.corp",
                "jobtitle": "Lead Observability Architect",
                "phone": "+1-415-555-0188"
            }
        },
        {
            "id": "contact-3",
            "properties": {
                "firstname": "Elena",
                "lastname": "Reyes",
                "email": "elena.reyes@acme.corp",
                "jobtitle": "Chief Financial Officer (CFO)",
                "phone": "+1-415-555-0130"
            }
        },
        {
            "id": "contact-4",
            "properties": {
                "firstname": "David",
                "lastname": "Kim",
                "email": "david.kim@acme.corp",
                "jobtitle": "Director of Information Security & Compliance",
                "phone": "+1-415-555-0144"
            }
        }
    ],
    "engagements": [
        {
            "id": "note-101",
            "type": "NOTE",
            "properties": {
                "hs_note_body": "<p>Discovery Call with Sarah Chen (VP Infra) and Marcus Vance (Observability Lead). Current monthly log ingestion is at 25TB/day and growing 40% YoY. Main complaint: Datadog retention costs are escalating uncontrollably ($45k/mo). Target is to cut retention bill by 50% while maintaining 365-day queryability for SOC2 compliance audits.</p>",
                "hs_createdate": "2026-07-15T14:30:00Z",
                "hubspot_owner_id": "rep_alex_morgan"
            }
        },
        {
            "id": "call-102",
            "type": "CALL",
            "properties": {
                "hs_call_body": "Speaker 1 (Alex - Sales Rep): Thanks for joining Sarah and Marcus. Let's touch on your evaluation timeline.\n\nSpeaker 2 (Sarah Chen - VP Infra): Our fiscal year review happens in October. Elena Reyes (CFO) has signed off on an exploratory budget cap of $200k ARR. However, David Kim (Security Director) requires complete SOC2 Type II compliance and VPC peering before any data leaves our AWS accounts.\n\nSpeaker 1 (Alex - Sales Rep): Understood. We support native VPC deployment. Marcus, what technical proof of concept is needed?\n\nSpeaker 3 (Marcus Vance - Architect): If you can ingest our Kubernetes log stream at 100k events/sec and execute high-cardinality customer_id queries in under 2 seconds without dropping historical indices, we will recommend you to Elena as our primary vendor.",
                "hs_createdate": "2026-07-28T16:00:00Z",
                "hubspot_owner_id": "rep_alex_morgan"
            }
        },
        {
            "id": "email-103",
            "type": "EMAIL",
            "properties": {
                "hs_email_text": "Hi Alex, Marcus and I reviewed your architectural proposal. Datadog account rep reached out offering a 15% discount renewal, but their multi-year lock-in and high-cardinality query degradation are still major blockers. Please send over the Mutual Action Plan so we can align with Procurement for an end of quarter close. Best, Sarah Chen.",
                "hs_createdate": "2026-08-04T09:15:00Z",
                "hubspot_owner_id": "rep_alex_morgan"
            }
        }
    ]
}


class HubSpotConnector:
    BASE_URL = "https://api.hubapi.com"

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or settings.HUBSPOT_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.access_token:
            raise ValueError("HubSpot Access Token is not set. Please update your .env file.")
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{self.BASE_URL}{endpoint}", headers=self.headers, params=params)
            if response.status_code == 401:
                raise PermissionError("HubSpot Authentication Failed (401). Check your Private App Token.")
            response.raise_for_status()
            return response.json()

    def test_connection(self) -> Dict[str, Any]:
        """Test API connectivity and basic permissions."""
        if not self.access_token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN is not configured in .env")
        return self._get("/crm/v3/objects/deals", params={"limit": 1})

    def get_deals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch list of deals with core properties from HubSpot, or fallback to lake/demo."""
        if self.access_token:
            try:
                params = {
                    "limit": limit,
                    "properties": "dealname,amount,dealstage,pipeline,closedate,hubspot_owner_id,description"
                }
                res = self._get("/crm/v3/objects/deals", params=params)
                return res.get("results", [])
            except Exception as e:
                logger.warning(f"Failed to fetch live HubSpot deals: {e}. Checking local raw lake.")

        # Offline / Demo fallback
        lake_deals = self._load_lake_deals(limit=limit)
        if lake_deals:
            return lake_deals

        # Default sample deal
        return [{
            "id": DEMO_DEAL["id"],
            "properties": DEMO_DEAL["properties"]
        }]

    def get_deal_detail(self, deal_id: str) -> DealModel:
        """Fetch full deal details, associated companies, contacts, and notes/engagements."""
        # 1. Check if requesting demo deal or no token is provided
        if deal_id in ("sample-deal", "demo-deal", "101") or not self.access_token:
            demo = self._load_demo_or_lake_deal(deal_id)
            if demo:
                return demo

        # 2. Live HubSpot REST API Ingestion
        try:
            deal_raw = self._get(
                f"/crm/v3/objects/deals/{deal_id}",
                params={"properties": "dealname,amount,dealstage,pipeline,closedate,hubspot_owner_id,description"}
            )
            props = deal_raw.get("properties", {})

            # Save to Raw Data Lake
            self._save_to_raw_lake(deal_raw, "deals", deal_id)

            company = self._get_associated_company(deal_id)
            contacts = self._get_associated_contacts(deal_id)
            engagements = self._get_associated_engagements(deal_id)

            amount_val = None
            if props.get("amount"):
                try:
                    amount_val = float(props.get("amount"))
                except ValueError:
                    pass

            return DealModel(
                id=deal_id,
                name=props.get("dealname") or f"Deal #{deal_id}",
                amount=amount_val,
                stage=props.get("dealstage"),
                pipeline=props.get("pipeline"),
                close_date=props.get("closedate"),
                owner_id=props.get("hubspot_owner_id"),
                company=company,
                contacts=contacts,
                engagements=engagements,
                raw_properties=props
            )
        except Exception as e:
            logger.warning(f"Could not fetch deal #{deal_id} from HubSpot API: {e}. Trying raw lake fallback.")
            demo = self._load_demo_or_lake_deal(deal_id)
            if demo:
                return demo
            raise

    def _get_associated_company(self, deal_id: str) -> Optional[CompanyModel]:
        try:
            assoc = self._get(f"/crm/v3/objects/deals/{deal_id}/associations/companies")
            results = assoc.get("results", [])
            if not results:
                return None
            
            company_id = results[0]["id"]
            comp_raw = self._get(
                f"/crm/v3/objects/companies/{company_id}",
                params={"properties": "name,domain,industry,numberofemployees,annualrevenue,description"}
            )
            self._save_to_raw_lake(comp_raw, "companies", company_id)
            c_props = comp_raw.get("properties", {})
            return CompanyModel(
                id=company_id,
                name=c_props.get("name") or "Unknown Company",
                domain=c_props.get("domain"),
                industry=c_props.get("industry"),
                number_of_employees=c_props.get("numberofemployees"),
                annual_revenue=c_props.get("annualrevenue")
            )
        except Exception as e:
            logger.debug(f"No associated company found for deal {deal_id}: {e}")
            return None

    def _get_associated_contacts(self, deal_id: str) -> List[ContactModel]:
        contacts = []
        try:
            assoc = self._get(f"/crm/v3/objects/deals/{deal_id}/associations/contacts")
            for item in assoc.get("results", []):
                contact_id = item["id"]
                c_raw = self._get(
                    f"/crm/v3/objects/contacts/{contact_id}",
                    params={"properties": "firstname,lastname,email,jobtitle,phone"}
                )
                self._save_to_raw_lake(c_raw, "contacts", contact_id)
                props = c_raw.get("properties", {})
                contacts.append(ContactModel(
                    id=contact_id,
                    first_name=props.get("firstname"),
                    last_name=props.get("lastname"),
                    email=props.get("email"),
                    job_title=props.get("jobtitle"),
                    phone=props.get("phone")
                ))
        except Exception as e:
            logger.debug(f"Error fetching contacts for deal {deal_id}: {e}")
        return contacts

    def _get_associated_engagements(self, deal_id: str) -> List[EngagementModel]:
        engagements = []
        object_types = [
            ("notes", "NOTE", "hs_note_body"),
            ("calls", "CALL", "hs_call_body"),
            ("meetings", "MEETING", "hs_meeting_body"),
            ("emails", "EMAIL", "hs_email_text")
        ]

        for obj_type, enum_type, body_field in object_types:
            try:
                assoc = self._get(f"/crm/v3/objects/deals/{deal_id}/associations/{obj_type}")
                for item in assoc.get("results", []):
                    item_id = item["id"]
                    raw_data = self._get(
                        f"/crm/v3/objects/{obj_type}/{item_id}",
                        params={"properties": f"{body_field},hs_createdate,hubspot_owner_id"}
                    )
                    self._save_to_raw_lake(raw_data, obj_type, item_id)
                    props = raw_data.get("properties", {})
                    body_text = props.get(body_field) or ""
                    if body_text.strip():
                        engagements.append(EngagementModel(
                            id=item_id,
                            type=enum_type,
                            body=body_text,
                            created_at=props.get("hs_createdate"),
                            author=props.get("hubspot_owner_id"),
                            metadata=props
                        ))
            except Exception as e:
                logger.debug(f"Could not retrieve {obj_type} for deal {deal_id}: {e}")

        return engagements

    def _save_to_raw_lake(self, payload: Dict[str, Any], entity_type: str, entity_id: str):
        """Saves immutable payload to local Raw Data Lake partition."""
        today = datetime.now().strftime("%Y-%m-%d")
        partition_dir = settings.raw_lake_dir / entity_type / today
        partition_dir.mkdir(parents=True, exist_ok=True)
        file_path = partition_dir / f"{entity_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _load_lake_deals(self, limit: int = 10) -> List[Dict[str, Any]]:
        deals = []
        deals_dir = settings.raw_lake_dir / "deals"
        if deals_dir.exists():
            for p in deals_dir.rglob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "id" in data:
                            deals.append(data)
                        if len(deals) >= limit:
                            break
                except Exception:
                    pass
        return deals

    def _load_demo_or_lake_deal(self, deal_id: str) -> Optional[DealModel]:
        # Build DealModel from built-in demo deal
        comp_data = DEMO_DEAL["company"]
        company = CompanyModel(
            id=comp_data["id"],
            name=comp_data["properties"]["name"],
            domain=comp_data["properties"]["domain"],
            industry=comp_data["properties"]["industry"],
            number_of_employees=comp_data["properties"]["numberofemployees"],
            annual_revenue=comp_data["properties"]["annualrevenue"]
        )

        contacts = [
            ContactModel(
                id=c["id"],
                first_name=c["properties"]["firstname"],
                last_name=c["properties"]["lastname"],
                email=c["properties"]["email"],
                job_title=c["properties"]["jobtitle"],
                phone=c["properties"]["phone"]
            )
            for c in DEMO_DEAL["contacts"]
        ]

        engagements = [
            EngagementModel(
                id=e["id"],
                type=e["type"],
                body=e["properties"].get("hs_note_body") or e["properties"].get("hs_call_body") or e["properties"].get("hs_email_text") or "",
                created_at=e["properties"]["hs_createdate"],
                author=e["properties"]["hubspot_owner_id"],
                metadata=e["properties"]
            )
            for e in DEMO_DEAL["engagements"]
        ]

        # Save demo deal to raw data lake
        self._save_to_raw_lake(DEMO_DEAL, "deals", DEMO_DEAL["id"])
        self._save_to_raw_lake(comp_data, "companies", comp_data["id"])

        return DealModel(
            id=deal_id if deal_id not in ("sample-deal", "demo-deal", "101") else DEMO_DEAL["id"],
            name=DEMO_DEAL["properties"]["dealname"],
            amount=float(DEMO_DEAL["properties"]["amount"]),
            stage=DEMO_DEAL["properties"]["dealstage"],
            pipeline=DEMO_DEAL["properties"]["pipeline"],
            close_date=DEMO_DEAL["properties"]["closedate"],
            owner_id=DEMO_DEAL["properties"]["hubspot_owner_id"],
            company=company,
            contacts=contacts,
            engagements=engagements,
            raw_properties=DEMO_DEAL["properties"]
        )

    def seed_sample_deal(self) -> DealModel:
        """Seeds the sample deal into raw lake and returns it."""
        return self._load_demo_or_lake_deal("sample-deal")


hubspot_connector = HubSpotConnector()
