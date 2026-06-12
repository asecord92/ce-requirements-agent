# CE Requirements Agent

An agentic tool that reads a provider license spreadsheet, researches current Continuing Education (CE) requirements per state and license type, and outputs ready-to-send email drafts for each provider ahead of their renewal deadlines.

## Project Status

Currently in **Phase 1 — Demo** (no production data, fake providers only).

## Architecture

### Inputs
- CSV/Excel spreadsheet with two sheets:
  - **License sheet**: `initials`, `state`, `license_type` (MD/NP/RN), `expiration_date`
  - **Provider lookup sheet**: `initials`, `full_name`, `credential`, `email`, `np_compact`
- Optional: target date range filter (e.g., "renewals in next 30 days")

### Agent Tools (to build)
- `spreadsheet_reader` — parses provider/license data from both sheets
- `web_search` — queries state licensing board sites for current CE requirements
- `ce_scraper` — extracts structured data (total hours, topic breakdowns, deadlines) from board pages
- `np_logic_handler` — applies compact/non-compact rules, flags dual RN+NP requirements
- `timeline_evaluator` — flags tight renewal windows and adjusts email urgency
- `email_formatter` — produces clean, personalized email draft per provider

### Outputs
- One formatted email draft per provider covering all upcoming renewals in the target window
- Flags for states where requirements were ambiguous or could not be confirmed
- Optional summary report sorted by renewal date

## Key Domain Rules

### NP Complexity
- NPs in compact states may satisfy CE under a single license
- Some states require separate RN *and* NP CE hours — identified by two rows with same `initials` and `state` (one `RN`, one `NP`)
- NP CE hours and RN CE hours often differ per state
- Some states mandate specialty hours (pharmacology, opioid, DEA-specific)
- Always look up rules dynamically — no hardcoded tables

### Email Urgency
- Tight timeline = renewal within ~5 weeks; escalate tone with ⚠️ warning
- Source every requirement with a direct state board URL

### Email Subject Format
```
Subject: CE Requirements — [State] [License Type] Renewal — Due [Date]
```

## Development Phases

### Phase 1 — Demo (current)
- [ ] Generate fake provider dataset (20 providers, mix of MD/NP, multiple states)
- [ ] Build agent loop: read spreadsheet → search CE requirements → format output
- [ ] Test with 3–5 providers across varied states and license types
- [ ] Validate NP dual-license logic with edge case providers
- [ ] Polish email output format

### Phase 2 — Internal Approval
- Confirm approved AI/API tools at org
- Assess PHI/PII compliance requirements
- Determine if email sending is in scope

### Phase 3 — Production
- Swap in real spreadsheet
- Add scheduling and run history/logging

## Technical Decisions (Pending Phase 2)
- **AI platform**: Anthropic API, Azure OpenAI, or approved internal tool — TBD
- **Runtime**: Python script (likely), possibly scheduled job
- **Email sending**: Manual copy-paste for v1; approved email API for v2
- **Data storage**: Local CSV/Excel for demo → shared drive or internal DB in production

## Risks
- State board websites change structure — agent must handle broken pages and flag failures
- PHI/PII compliance applies to provider names + license data in production
- NP compact membership evolves; source of truth for compact rules must stay current
- Direct email sending likely requires IT approval

## Demo Success Criteria
1. Agent reads a spreadsheet of fake providers
2. Live web searches against real state board sites
3. Reasoning is visible — agent explains what it found and flags ambiguities
4. Clean personalized email draft output per provider
5. At least one NP with dual RN+NP requirement handled correctly
6. At least one provider flagged for a tight renewal timeline
