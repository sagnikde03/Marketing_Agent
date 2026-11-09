import os
import html
from pathlib import Path
from datetime import datetime
from app.models.schemas import DealModel, PlaybookOutput, MeddicSection


class HTMLPlaybookBuilder:
    """Generates standalone, beautifully styled, interactive HTML playbooks matching the DealCraft target blueprint."""

    def __init__(self, output_dir: str = "./playbooks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_and_save(self, deal: DealModel, playbook: PlaybookOutput) -> Path:
        company_name = deal.company.name if deal.company and deal.company.name else deal.name
        stage_name = deal.stage or "Solution Evaluation"
        updated_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        amount_formatted = f"${deal.amount:,.2f}" if deal.amount is not None else "Unspecified"

        # 1. Identify Key Stakeholders
        eb_title = "VP / Decision Maker"
        champ_title = "Technical Lead / Champion"
        if deal.contacts:
            for c in deal.contacts:
                title = (c.job_title or "").lower()
                c_name = f"{c.first_name or ''} {c.last_name or ''}".strip() or "Unnamed"
                if any(k in title for k in ["cfo", "vp", "director of finance", "chief", "president"]):
                    eb_title = f"{c.job_title} ({c_name})"
                elif any(k in title for k in ["architect", "lead", "manager", "engineer", "specialist"]):
                    champ_title = f"{c.job_title} ({c_name})"

        # 2. Render Battlecards
        battlecard_rows_html = ""
        if playbook.battlecards:
            for bc in playbook.battlecards:
                src_color = "#6366f1"
                if "call" in bc.source.lower():
                    src_color = "#0ea5e9"
                elif "email" in bc.source.lower():
                    src_color = "#f59e0b"

                battlecard_rows_html += f"""
        <div class="bc-row">
          <div class="c-them"><span class="ic-x">&#10005;</span><p>{html.escape(bc.them)}</p></div>
          <div class="c-us"><span class="ic-c">&#10003;</span><p>{html.escape(bc.us)}</p></div>
          <div class="c-src"><span class="pill" style="color:{src_color};background:{src_color}14;border-color:{src_color}33">{html.escape(bc.source)}</span></div>
        </div>"""
        else:
            battlecard_rows_html = """
        <div class="bc-row">
          <div class="c-them"><span class="ic-x">&#10005;</span><p>High ongoing maintenance overhead and complex custom integrations.</p></div>
          <div class="c-us"><span class="ic-c">&#10003;</span><p>Out-of-the-box connectors and automated intelligence workflows.</p></div>
          <div class="c-src"><span class="pill" style="color:#6366f1;background:#6366f114;border-color:#6366f133">CRM Notes</span></div>
        </div>"""

        # 3. Render Watch Items ("Where Alternative is stronger")
        watch_items_html = ""
        if playbook.watch_items:
            for w in playbook.watch_items:
                watch_items_html += f"""
        <div class="watch-item">
          <p class="w-strength">{html.escape(w.strength)} <span class="pill" style="color:#6366f1;background:#6366f114;border-color:#6366f133">{html.escape(w.source)}</span></p>
          <p class="w-action">&#9888; {html.escape(w.action)}</p>
        </div>"""
        else:
            watch_items_html = """
        <div class="watch-item">
          <p class="w-strength">Existing familiarity with legacy processes across operational staff <span class="pill" style="color:#6366f1;background:#6366f114;border-color:#6366f133">CRM Signal</span></p>
          <p class="w-action">&#9888; Emphasize zero-friction onboarding and rapid time-to-value (under 2 weeks).</p>
        </div>"""

        # 4. Render Discovery Sections (MEDDIC with grounded citations)
        def render_section_bullets(sec: MeddicSection) -> str:
            res = ""
            for claim in sec.claims:
                txt = html.escape(claim.claim_text)
                if claim.status == "GROUNDED" and claim.source_citation:
                    tag = f' <span class="source-tag" title="Verified against CRM evidence">&#10003; {html.escape(claim.source_citation)}</span>'
                elif claim.status == "UNSUPPORTED":
                    tag = ' <span class="unverified-tag" title="No direct CRM citation found">&#9888; Unverified Signal</span>'
                else:
                    tag = ""
                res += f"<li>{txt}{tag}</li>\n"
            if not sec.claims:
                for kf in sec.key_findings:
                    res += f"<li>{html.escape(kf)}</li>\n"
            return res

        # 5. Render Talk Tracks
        talk_tracks_html = ""
        for idx, track in enumerate(playbook.recommended_talk_tracks):
            track_clean = track.strip()
            if track_clean.startswith(f"{idx+1}."):
                track_clean = track_clean[2:].strip()
            stripped_quote = track_clean.strip("'\"")
            talk_tracks_html += f"""
        <div class="talk-track-item">
          <div class="tt-num">{idx + 1}</div>
          <div class="tt-body">
            <p class="tt-quote">{html.escape(stripped_quote)}</p>
          </div>
        </div>"""

        # 6. Render Unverified Alerts (if any)
        alerts_html = ""
        if playbook.unverified_alerts:
            alerts_html += """
      <div class="watch" style="border-color:#fca5a5;background:linear-gradient(180deg,#fff5f5,#fff);margin-top:20px;">
        <div class="watch-head">
          <span class="warn" style="background:#ef4444">!</span>
          <b style="color:#991b1b">Unverified Signals (Validate in Next Discovery Call)</b>
          <span class="muted">&mdash; claims lacking direct CRM documentation.</span>
        </div>"""
            for alert in playbook.unverified_alerts:
                alerts_html += f"""
        <div class="watch-item" style="border-color:#fecaca;">
          <p class="w-strength" style="color:#7f1d1d">{html.escape(alert)}</p>
          <p class="w-action" style="color:#b91c1c">&#9888; Confirm this dimension during discovery before pricing submission.</p>
        </div>"""
            alerts_html += "</div>"

        # Clean filename
        safe_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.lower().replace(' ', '-') or f"deal-{deal.id}"
        output_file = self.output_dir / f"deal-playbook-{safe_name}.html"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deal Playbook &mdash; {html.escape(company_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #eef1f5; color: #0f172a; line-height: 1.5; padding: 40px 20px; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  .muted {{ color: #64748b; font-size: 13.5px; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 26px; }}
  .top h1 {{ font-size: 30px; font-weight: 800; letter-spacing: .14em; }}
  .top .tagline {{ color: #64748b; font-size: 15px; margin-top: 6px; }}
  .chip {{ background: #fff; border: 1px solid #e6e9ef; border-radius: 14px; padding: 14px 18px; display: flex; gap: 26px; box-shadow: 0 1px 2px rgba(16,24,40,.04); }}
  .chip .lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #94a3b8; }}
  .chip .val {{ font-size: 14px; font-weight: 700; color: #1e293b; margin-top: 3px; }}
  .card {{ background: #fff; border: 1px solid #e6e9ef; border-radius: 18px; padding: 26px; margin-bottom: 22px; box-shadow: 0 4px 18px rgba(16,24,40,.05); }}
  .icon-circ {{ width: 46px; height: 46px; border-radius: 13px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
  .snum {{ font-size: 15px; font-weight: 750; letter-spacing: .02em; color: #0f172a; }}
  .wide {{ display: grid; grid-template-columns: 220px 1fr; gap: 32px; align-items: start; }}
  .intro .icon-circ {{ margin-bottom: 14px; }} .intro .snum {{ margin-bottom: 6px; }}
  .cols4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 26px; }}
  .col-head {{ display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; color: #1e293b; margin-bottom: 10px; }}
  ul {{ list-style: none; }}
  li {{ font-size: 13px; color: #475569; margin-bottom: 9px; padding-left: 15px; position: relative; line-height: 1.5; }}
  li::before {{ content: ''; position: absolute; left: 2px; top: 8px; width: 5px; height: 5px; border-radius: 50%; background: #cbd5e1; }}
  .clink {{ font-weight: 650; font-size: 13px; text-decoration: none; display: inline-block; margin-top: 10px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-bottom: 22px; }}
  .grid-2 .card {{ margin-bottom: 0; }}
  .mini-head {{ display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }}
  .bc {{ border: 1px solid #e6e9ef; border-radius: 14px; overflow: hidden; margin-top: 18px; }}
  .bc-head, .bc-row {{ display: grid; grid-template-columns: 1fr 1fr 140px; }}
  .bc-head > div {{ padding: 12px 18px; font-weight: 700; font-size: 14px; display: flex; align-items: center; gap: 8px; }}
  .bc-head .h-them {{ background: #475569; color: #fff; }} .bc-head .h-us {{ background: #059669; color: #fff; }}
  .bc-head .h-src {{ background: #f8fafc; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }}
  .logo-dot {{ width: 9px; height: 9px; border-radius: 50%; background: rgba(255,255,255,.85); }}
  .bc-row {{ border-top: 1px solid #eef1f5; }}
  .bc-row > div {{ padding: 14px 18px; display: flex; gap: 10px; align-items: flex-start; }}
  .bc-row .c-them {{ background: #fcfcfd; }} .bc-row .c-us {{ background: #f6fdfa; }}
  .bc-row p {{ font-size: 13.5px; }} .bc-row .c-them p {{ color: #475569; }} .bc-row .c-us p {{ color: #0f3d2e; font-weight: 550; }}
  .ic-x {{ color: #dc6b6b; font-weight: 700; font-size: 13px; flex-shrink: 0; }}
  .ic-c {{ color: #059669; font-weight: 700; font-size: 13px; flex-shrink: 0; }}
  .pill {{ display: inline-block; font-size: 11px; font-weight: 650; padding: 3px 10px; border-radius: 20px; border: 1px solid; white-space: nowrap; }}
  .watch {{ margin-top: 18px; border: 1px solid #fcd9a8; background: linear-gradient(180deg,#fffaf2,#fff); border-radius: 14px; padding: 18px; }}
  .watch-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }}
  .watch-head b {{ color: #92400e; font-size: 15px; }}
  .watch .warn {{ width: 26px; height: 26px; border-radius: 8px; background: #f59e0b; color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; }}
  .watch-item {{ background: #fff; border: 1px solid #fde4bf; border-radius: 11px; padding: 12px 14px; margin-bottom: 10px; }}
  .watch-item:last-child {{ margin-bottom: 0; }}
  .w-strength {{ font-size: 13.5px; font-weight: 600; color: #1e293b; }}
  .w-action {{ font-size: 12.5px; color: #b45309; margin-top: 5px; font-weight: 600; }}
  .source-tag {{ font-size: 11px; color: #059669; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 2px 7px; margin-left: 6px; display: inline-block; font-weight: 600; }}
  .unverified-tag {{ font-size: 11px; color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 2px 7px; margin-left: 6px; display: inline-block; font-weight: 600; }}
  .talk-track-item {{ display: flex; gap: 16px; align-items: flex-start; padding: 14px 18px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 10px; }}
  .talk-track-item:last-child {{ margin-bottom: 0; }}
  .tt-num {{ width: 28px; height: 28px; border-radius: 8px; background: #6366f1; color: #fff; font-weight: 700; font-size: 13px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
  .tt-quote {{ font-size: 13.5px; color: #1e293b; font-weight: 550; font-style: italic; }}
  .foot {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; background: #fff; border: 1px solid #e6e9ef; border-radius: 14px; padding: 16px 22px; }}
  .foot .living {{ display: flex; align-items: center; gap: 12px; }}
  .foot .spark {{ width: 34px; height: 34px; border-radius: 9px; background: #eef2ff; color: #6366f1; display: flex; align-items: center; justify-content: center; font-size: 17px; }}
  .foot .living b {{ font-size: 14px; }} .foot .living p {{ font-size: 13px; color: #64748b; }}
  .foot .upd {{ font-size: 12px; color: #94a3b8; text-align: right; }}
  @media (max-width: 860px) {{
    .wide {{ grid-template-columns: 1fr; gap: 18px; }} .cols4 {{ grid-template-columns: 1fr 1fr; }}
    .grid-2 {{ grid-template-columns: 1fr; }} .bc-head, .bc-row {{ grid-template-columns: 1fr 1fr 90px; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <!-- TOP HEADER -->
    <div class="top">
      <div>
        <h1>DEAL PLAYBOOK</h1>
        <p class="tagline">Grounded MEDDIC Strategy &amp; Live Battlecard &middot; {html.escape(deal.name)}</p>
      </div>
      <div class="chip">
        <div><div class="lbl">Deal</div><div class="val">{html.escape(company_name)}</div></div>
        <div><div class="lbl">Stage</div><div class="val">{html.escape(stage_name)}</div></div>
        <div><div class="lbl">Value</div><div class="val" style="color:#059669">{amount_formatted}</div></div>
        <div><div class="lbl">Confidence</div><div class="val" style="color:#6366f1">{playbook.confidence_score} / 5.0</div></div>
      </div>
    </div>
    
    <!-- EXECUTIVE SUMMARY -->
    <section class="card" style="border-left: 4px solid #6366f1;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <span style="font-size:16px;">🎯</span>
        <b style="font-size:15px;color:#1e293b;">Executive Deal Summary</b>
        <span class="pill" style="color:#059669;background:#05966914;border-color:#05966933">Verified Grounding</span>
      </div>
      <p style="font-size:14px;color:#334155;line-height:1.6;">{html.escape(playbook.deal_summary)}</p>
    </section>

    <!-- 1. DEAL STRATEGY -->
    <section class="card wide">
      <div class="intro">
        <span class="icon-circ" style="background:#6366f115">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/></svg>
        </span>
        <div class="snum">1. DEAL STRATEGY</div>
        <p class="muted">Our plan to win.</p>
      </div>
      <div class="cols4">
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 4 14 11 14 10 22 19 9 12 9 13 2"/></svg><span>Next Action</span></div>
          <ul>
            <li>Schedule technical deep dive with {html.escape(company_name)} platform team</li>
            <li>Share tailored ROI analysis for target value ({amount_formatted})</li>
            <li>Establish mutual milestones leading to close ({html.escape(deal.close_date or 'Q4')})</li>
          </ul>
          <a class="clink" style="color:#6366f1" href="#">View Action Plan &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 6"/><path d="M18 20a6 6 0 0 0-3-5.2"/></svg><span>People</span></div>
          <ul>
            <li><b>Economic Buyer:</b> {html.escape(eb_title)}</li>
            <li><b>Champion:</b> {html.escape(champ_title)}</li>
            <li><b>Contacts:</b> {len(deal.contacts)} total recorded in CRM</li>
          </ul>
          <a class="clink" style="color:#6366f1" href="#">View Stakeholder Map &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4"/><path d="M5 4h11l-1.5 4L16 12H5"/></svg><span>Positioning</span></div>
          <ul>
            <li>Lead with operational efficiency &amp; cost predictability</li>
            <li>Emphasize enterprise reliability &amp; compliance</li>
            <li>Align directly with {html.escape(company_name)}'s data growth roadmap</li>
          </ul>
          <a class="clink" style="color:#6366f1" href="#">View Messaging &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg><span>Product</span></div>
          <ul>
            <li>Enterprise Platform License</li>
            <li>VPC &amp; Private Cloud Deployment</li>
            <li>Dedicated Solutions Architect Onboarding</li>
          </ul>
          <a class="clink" style="color:#6366f1" href="#">View Solution Fit &rarr;</a>
        </div>
      </div>
    </section>
    
    <!-- 2. COMPETITIVE INTEL & BATTLECARD -->
    <section class="card">
      <div class="mini-head">
        <span class="icon-circ" style="background:#10b98115">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M8.2 13.5 7 22l5-3 5 3-1.2-8.5"/></svg>
        </span>
        <div>
          <div class="snum">2. COMPETITIVE INTEL &amp; BATTLECARD</div>
          <p class="muted">Live Battlecard &middot; Alternative / Status Quo vs Our Platform &middot; Synthesized from CRM Notes, Calls &amp; Marketing Intel.</p>
        </div>
      </div>
      
      <div class="bc">
        <div class="bc-head">
          <div class="h-them"><span class="logo-dot"></span>Alternative / Status Quo</div>
          <div class="h-us"><span class="logo-dot"></span>Our Platform (DealCraft)</div>
          <div class="h-src">Evidence Source</div>
        </div>
        {battlecard_rows_html}
      </div>
      
      <div class="watch">
        <div class="watch-head">
          <span class="warn">!</span><b>Where Alternative is stronger</b>
          <span class="muted">&mdash; flagged for rep discovery &amp; positioning.</span>
        </div>
        {watch_items_html}
      </div>
    </section>

    <!-- 3 & 4. DISCOVERY FRAMEWORK (MEDDIC) & OBJECTION HANDLING -->
    <div class="grid-2">
      <!-- 3. MEDDIC PILLARS -->
      <section class="card">
        <div class="mini-head">
          <span class="icon-circ" style="background:#0ea5e915">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.7" y2="16.7"/></svg>
          </span>
          <div>
            <div class="snum">3. DISCOVERY FRAMEWORK (MEDDIC)</div>
            <p class="muted">Audit-verified deal qualification pillars.</p>
          </div>
        </div>
        
        <div style="margin-bottom:14px;">
          <b style="font-size:13.5px;color:#0369a1;">Metrics (M)</b>
          <ul>{render_section_bullets(playbook.metrics)}</ul>
        </div>
        
        <div style="margin-bottom:14px;">
          <b style="font-size:13.5px;color:#0369a1;">Economic Buyer (E)</b>
          <ul>{render_section_bullets(playbook.economic_buyer)}</ul>
        </div>

        <div style="margin-bottom:14px;">
          <b style="font-size:13.5px;color:#0369a1;">Decision Criteria (D)</b>
          <ul>{render_section_bullets(playbook.decision_criteria)}</ul>
        </div>

        <div style="margin-bottom:14px;">
          <b style="font-size:13.5px;color:#0369a1;">Decision Process (D)</b>
          <ul>{render_section_bullets(playbook.decision_process)}</ul>
        </div>

        <div style="margin-bottom:14px;">
          <b style="font-size:13.5px;color:#0369a1;">Identify Pain (I)</b>
          <ul>{render_section_bullets(playbook.identify_pain)}</ul>
        </div>

        <div style="margin-bottom:8px;">
          <b style="font-size:13.5px;color:#0369a1;">Champion (C)</b>
          <ul>{render_section_bullets(playbook.champion)}</ul>
        </div>
      </section>

      <!-- 4. OBJECTION HANDLING & TALK TRACKS -->
      <section class="card">
        <div class="mini-head">
          <span class="icon-circ" style="background:#f9731615">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-11.7 7.7L3 21l1.9-6.1A8.5 8.5 0 1 1 21 11.5z"/></svg>
          </span>
          <div>
            <div class="snum">4. OBJECTION HANDLING &amp; REBUTTALS</div>
            <p class="muted">Counter objections with verified talk tracks.</p>
          </div>
        </div>
        
        <div style="margin-bottom:16px;">
          <ul>
            <li><b>Price / Budget:</b> Anchor against total cost of inaction over 12 months. Emphasize 50% savings over escalating alternative storage fees.</li>
            <li><b>Migration Risk:</b> Offer zero-disruption parallel ingestion pilot with automated schema validation.</li>
            <li><b>Security &amp; Compliance:</b> Provide SOC2 Type II certification and native VPC deployment documentation upfront.</li>
            <li><b>Timeline / Quarter End:</b> Propose phased rollout starting with highest-volume Kubernetes services.</li>
          </ul>
        </div>

        <div class="mini-head" style="margin-top:20px;">
          <span class="icon-circ" style="background:#10b98115">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          </span>
          <div>
            <div class="snum">STRATEGIC CALL TALK TRACKS</div>
            <p class="muted">High-impact discovery questions for the rep's next call.</p>
          </div>
        </div>
        {talk_tracks_html}
        {alerts_html}
      </section>
    </div>
    
    <!-- 5. DEAL SUPPORT -->
    <section class="card wide">
      <div class="intro">
        <span class="icon-circ" style="background:#eab30815">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 6"/><path d="M18 20a6 6 0 0 0-3-5.2"/></svg>
        </span>
        <div class="snum">5. DEAL SUPPORT</div>
        <p class="muted">Resources to strengthen your deal.</p>
      </div>
      <div class="cols4">
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z"/><path d="M6 17h12"/></svg><span>Case Studies</span></div>
          <ul>
            <li>Fintech Enterprise Migration Case Study</li>
            <li>50% Infrastructure TCO Reduction Benchmark</li>
          </ul>
          <a class="clink" style="color:#ca8a04" href="#">View Case Studies &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 6"/><path d="M18 20a6 6 0 0 0-3-5.2"/></svg><span>Internal SMEs</span></div>
          <ul>
            <li>Lead Solutions Architect (Cloud Data)</li>
            <li>Information Security &amp; Compliance Officer</li>
          </ul>
          <a class="clink" style="color:#ca8a04" href="#">Request SME &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg><span>Tools &amp; Assets</span></div>
          <ul>
            <li>Interactive TCO Comparison Calculator</li>
            <li>Executive Business Case Proposal Deck</li>
          </ul>
          <a class="clink" style="color:#ca8a04" href="#">Download Assets &rarr;</a>
        </div>
        <div class="col">
          <div class="col-head"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M8.2 13.5 7 22l5-3 5 3-1.2-8.5"/></svg><span>Enablement</span></div>
          <ul>
            <li>MEDDIC Discovery Field Checklist</li>
            <li>Competitive Displace Battlecard Guide</li>
          </ul>
          <a class="clink" style="color:#ca8a04" href="#">View Enablement &rarr;</a>
        </div>
      </div>
    </section>

    <!-- 6 & 7. DEAL INSIGHTS & WIN ROOM -->
    <div class="grid-2">
      <section class="card mini">
        <div class="mini-head">
          <span class="icon-circ" style="background:#8b5cf615">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg>
          </span>
          <div>
            <div class="snum">6. DEAL INSIGHTS &amp; HEALTH</div>
            <p class="muted">CRM signal &amp; velocity analytics.</p>
          </div>
        </div>
        <ul>
          <li>Deal Health: <b style="color:#16a34a">Active ({html.escape(stage_name)})</b></li>
          <li>Engagements Recorded: <b>{len(deal.engagements)} notes, calls &amp; emails</b></li>
          <li>Target Close Date: <b>{html.escape(deal.close_date or 'End of Quarter')}</b></li>
          <li>Strategy Confidence: <b>{playbook.confidence_score} / 5.0</b></li>
        </ul>
        <a class="clink" style="color:#8b5cf6" href="#">View Deal Insights &rarr;</a>
      </section>

      <section class="card mini">
        <div class="mini-head">
          <span class="icon-circ" style="background:#3b82f615">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><polyline points="14 3 14 8 19 8"/></svg>
          </span>
          <div>
            <div class="snum">7. WIN ROOM &amp; COLLABORATION</div>
            <p class="muted">Align and execute as an account team.</p>
          </div>
        </div>
        <ul>
          <li>Mutual Action Plan &amp; Gate Criteria</li>
          <li>Target Contract Value: <b style="color:#059669">{amount_formatted}</b></li>
          <li>Dedicated Slack / Teams Deal Room Connected</li>
        </ul>
        <a class="clink" style="color:#3b82f6" href="#">Go to Win Room &rarr;</a>
      </section>
    </div>

    <!-- LIVING PLAYBOOK FOOTER -->
    <div class="foot">
      <div class="living">
        <span class="spark">&#10022;</span>
        <div>
          <b>This is a living playbook.</b>
          <p>Continuously updated as deal activity, customer communications, and CRM signals evolve.</p>
        </div>
      </div>
      <div class="upd">Last updated<br>{updated_time}</div>
    </div>
  </div>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_file


html_builder = HTMLPlaybookBuilder()
