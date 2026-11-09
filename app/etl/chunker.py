import re
from typing import List
from app.models.schemas import DealModel, TextChunk


class SmartChunker:
    """Implements Stage 1 Smart Chunking strategy from the AriGentic architecture."""

    def chunk_deal(self, deal: DealModel) -> List[TextChunk]:
        chunks: List[TextChunk] = []

        # 1. Structured Deal & Company Overview Chunk
        company_name = deal.company.name if deal.company and deal.company.name else "Unknown Company"
        company_ind = deal.company.industry if deal.company and deal.company.industry else "Unspecified"
        company_emp = deal.company.number_of_employees if deal.company and deal.company.number_of_employees else "Unspecified"
        company_rev = deal.company.annual_revenue if deal.company and deal.company.annual_revenue else "Unspecified"

        contacts_list = []
        for c in deal.contacts:
            c_name = f"{c.first_name or ''} {c.last_name or ''}".strip() or "Unnamed"
            c_title = c.job_title or "Role Unknown"
            c_email = f" <{c.email}>" if c.email else ""
            contacts_list.append(f"{c_name} ({c_title}){c_email}")
        contacts_str = ", ".join(contacts_list) if contacts_list else "None listed"

        amount_str = f"${deal.amount:,.2f}" if deal.amount is not None else "Unspecified"
        deal_summary = (
            f"Deal Name: {deal.name}\n"
            f"Deal Amount: {amount_str}\n"
            f"Pipeline Stage: {deal.stage or 'Unknown'} (Pipeline: {deal.pipeline or 'default'})\n"
            f"Target Close Date: {deal.close_date or 'Unspecified'}\n"
            f"Company: {company_name} (Industry: {company_ind}, Employees: {company_emp}, Revenue: {company_rev})\n"
            f"Key Contacts: {contacts_str}"
        )

        chunks.append(TextChunk(
            id=f"{deal.id}_overview",
            deal_id=deal.id,
            source_type="CRM_RECORD",
            source_id=deal.id,
            content=deal_summary,
            speaker_or_author="HubSpot CRM",
            metadata={
                "type": "deal_summary",
                "company": company_name,
                "amount": deal.amount,
                "stage": deal.stage
            }
        ))

        # 2. Chunk Engagements (Notes, Calls, Emails, Meetings)
        for eng in deal.engagements:
            raw_text = self._clean_html(eng.body)
            if not raw_text.strip():
                continue

            # If it's a call transcript with speaker turns
            if eng.type == "CALL" and ("Speaker" in raw_text or "Rep:" in raw_text or "Prospect:" in raw_text or "\n" in raw_text):
                sub_chunks = self._chunk_speaker_turns(raw_text)
                for idx, turn in enumerate(sub_chunks):
                    chunks.append(TextChunk(
                        id=f"{eng.id}_turn_{idx}",
                        deal_id=deal.id,
                        source_type="CALL_TRANSCRIPT",
                        source_id=eng.id,
                        content=turn,
                        timestamp=eng.created_at,
                        speaker_or_author=eng.author,
                        metadata={
                            "engagement_type": "CALL",
                            "turn_index": idx,
                            "parent_id": eng.id
                        }
                    ))
            else:
                # Note, Email, or Meeting: clean section chunk
                # If note is very long (> 1200 chars), split into sub-sections
                if len(raw_text) > 1200:
                    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
                    if len(paragraphs) > 1:
                        for p_idx, para in enumerate(paragraphs):
                            chunks.append(TextChunk(
                                id=f"{eng.id}_part_{p_idx}",
                                deal_id=deal.id,
                                source_type=f"{eng.type}_RECORD",
                                source_id=eng.id,
                                content=para,
                                timestamp=eng.created_at,
                                speaker_or_author=eng.author,
                                metadata={"engagement_type": eng.type, "part": p_idx}
                            ))
                        continue

                chunks.append(TextChunk(
                    id=f"{eng.id}_full",
                    deal_id=deal.id,
                    source_type=f"{eng.type}_RECORD",
                    source_id=eng.id,
                    content=raw_text,
                    timestamp=eng.created_at,
                    speaker_or_author=eng.author,
                    metadata={"engagement_type": eng.type}
                ))

        return chunks

    def _clean_html(self, raw_html: str) -> str:
        """Strip HTML tags while preserving line breaks and paragraph structure."""
        if not raw_html:
            return ""
        # Convert break and block tags to newlines
        text = re.sub(r"<(?:br|p|div|li|tr)[^>]*>", "\n", raw_html, flags=re.IGNORECASE)
        # Strip all other HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Normalize non-breaking spaces
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        # Normalize spaces per line
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        # Remove consecutive blank lines
        cleaned_text = "\n".join([line for line in lines if line])
        return cleaned_text.strip()

    def _chunk_speaker_turns(self, text: str) -> List[str]:
        """Split call transcripts preserving speaker turns or paragraphs."""
        # Try splitting by speaker turn headers (e.g., 'Speaker 1:', 'Rep:', 'Prospect:', 'Alex:')
        speaker_pattern = r"(?=(?:Speaker\s+\d+|Rep|Prospect|Customer|Sales|Client|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:)"
        splits = [s.strip() for s in re.split(speaker_pattern, text) if s.strip()]
        if len(splits) > 1:
            return splits

        # Otherwise split by paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]
        return paragraphs


smart_chunker = SmartChunker()
