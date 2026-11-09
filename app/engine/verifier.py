import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.core.config import settings
from app.core.vector_db import vector_store
from app.etl.indexer import vector_indexer
from app.models.schemas import VerifiedClaim, MeddicSection, TextChunk
from app.engine.prompts import VERIFICATION_SYSTEM_PROMPT, VERIFICATION_PROMPT

logger = logging.getLogger(__name__)


class VerificationAgent:
    """Implements self-correction and citation grounding (Section 6.5 of architecture)."""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if settings.OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.debug(f"OpenAI client init notice in verifier: {e}")

    def verify_section(self, section: MeddicSection, evidence_chunks: List[TextChunk]) -> MeddicSection:
        """Grounds claims in the section against source text chunks via LLM or heuristic search."""
        if not section.key_findings:
            return section

        # 1. Tier 1: Try LLM Verification Gate if OpenAI client is active
        if self.client:
            try:
                verified = self._verify_via_llm(section.key_findings, evidence_chunks)
                if verified:
                    section.claims = verified
                    return section
            except Exception as e:
                logger.debug(f"LLM verification failed ({e}). Falling back to vector heuristic grounding.")

        # 2. Tier 2: Heuristic Vector & Entity Grounding
        section.claims = self._verify_heuristic(section.key_findings, evidence_chunks)
        return section

    def _verify_via_llm(self, statements: List[str], evidence_chunks: List[TextChunk]) -> Optional[List[VerifiedClaim]]:
        evidence_str = "\n\n".join([
            f"[{c.source_type} #{c.source_id}] (Author: {c.speaker_or_author or 'HubSpot'} | Date: {c.timestamp or 'N/A'}):\n{c.content}"
            for c in evidence_chunks
        ])

        claims_json = json.dumps([{"claim_text": s} for s in statements])
        prompt = VERIFICATION_PROMPT.format(
            retrieved_evidence=evidence_str[:6000],
            claims_json=claims_json
        )

        response = self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        items = parsed.get("verified_claims", [])

        if not items:
            return None

        result = []
        for it in items:
            result.append(VerifiedClaim(
                claim_text=it.get("claim_text", ""),
                source_citation=it.get("source_citation"),
                status=it.get("status", "GROUNDED"),
                confidence_score=float(it.get("confidence_score", 0.9))
            ))
        return result

    def _verify_heuristic(self, statements: List[str], evidence_chunks: List[TextChunk]) -> List[VerifiedClaim]:
        verified_claims = []

        # Build quick lookup of chunk text
        chunk_map = {c.id: c for c in evidence_chunks}

        for statement in statements:
            # Check for unverified / missing markers
            lower_stmt = statement.lower()
            if any(marker in lower_stmt for marker in ["missing signal", "unknown", "not yet", "unspecified", "tbd", "to be validated"]):
                verified_claims.append(VerifiedClaim(
                    claim_text=statement,
                    source_citation=None,
                    status="UNSUPPORTED",
                    confidence_score=0.30
                ))
                continue

            matched_sources = []
            best_score = 0.0

            # 1. Vector similarity search
            try:
                emb = vector_indexer.embed_query(statement)
                deal_id = evidence_chunks[0].deal_id if evidence_chunks else None
                sim_results = vector_store.search_similar(emb, deal_id=deal_id, limit=3)

                for match in sim_results:
                    score = match.get("score", 0.0)
                    payload = match.get("payload", {})
                    if score > 0.55:
                        src_type = payload.get("source_type", "CRM")
                        author = payload.get("speaker_or_author") or "CRM"
                        ts = (payload.get("timestamp") or "")[:10]
                        cite = f"{src_type} ({author})" + (f" on {ts}" if ts else "")
                        if cite not in matched_sources:
                            matched_sources.append(cite)
                        if score > best_score:
                            best_score = score
            except Exception as e:
                logger.debug(f"Vector search in verifier error: {e}")

            # 2. Key entity / lexical matching fallback
            keywords = [w for w in re_words(statement) if len(w) >= 4 and w not in STOPWORDS]
            # Extract distinctive tokens: currency, numbers, acronyms, known entities
            import re
            special_tokens = [t.lower() for t in re.findall(r"\$?\b\d+[\d,kKmM%]*\b|[A-Z]{2,}|Datadog|Splunk|Snowflake|Acme|Chen|Vance|Reyes|Kim|Kubernetes", statement)]

            for chunk in evidence_chunks:
                chunk_lower = chunk.content.lower()
                matched_words = [kw for kw in keywords if kw in chunk_lower]
                matched_specials = [st for st in special_tokens if st in chunk_lower]

                # If significant keyword overlap or specific entity/special token match
                if len(matched_words) >= 2 or (matched_specials and len(matched_words) >= 1) or len(matched_specials) >= 2:
                    src_type = chunk.source_type
                    author = chunk.speaker_or_author or "HubSpot"
                    ts = (chunk.timestamp or "")[:10]
                    cite = f"{src_type} ({author})" + (f" on {ts}" if ts else "")
                    if cite not in matched_sources:
                        matched_sources.append(cite)
                    best_score = max(best_score, 0.90)

            if matched_sources:
                verified_claims.append(VerifiedClaim(
                    claim_text=statement,
                    source_citation=f"Source: {', '.join(matched_sources[:2])}",
                    status="GROUNDED",
                    confidence_score=round(max(0.85, best_score), 2)
                ))
            else:
                verified_claims.append(VerifiedClaim(
                    claim_text=statement,
                    source_citation=None,
                    status="UNSUPPORTED",
                    confidence_score=0.40
                ))

        return verified_claims


def re_words(text: str) -> List[str]:
    import re
    return [w.lower() for w in re.findall(r"\b[A-Za-z0-9\$\%]+\b", text)]


STOPWORDS = {
    "their", "there", "about", "would", "could", "should", "which", "where",
    "these", "those", "other", "after", "before", "during", "while", "prospect",
    "solution", "platform", "process", "review", "target"
}

verifier = VerificationAgent()
