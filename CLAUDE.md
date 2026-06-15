# CE Requirements Agent

An agentic tool that reads a provider license spreadsheet, researches current Continuing Education (CE) requirements per state and license type, and outputs ready-to-send email drafts for each provider ahead of their renewal deadlines.

## Project Status

Currently in **Phase 1 — Demo** (no production data, fake providers only).

## Architecture

### Inputs
- CSV/Excel spreadsheet with two sheets:
  - **License sheet**: `initials`, `state`, `license_type` (MD/NP/RN), `expiration_date`
  - **Provider lookup sheet**: `initials`, `full_name`, `credential`, `email`, `np_compact`
- **Target month** — required run parameter (e.g., "July 2026"); agent processes all licenses expiring in that month

### Agent Tools (to build)
- `spreadsheet_reader` — parses provider/license data from both sheets
- `web_search` — queries state licensing board sites for current CE requirements
- `ce_scraper` — extracts structured data (total hours, topic breakdowns, deadlines) from board pages
- `np_logic_handler` — applies compact/non-compact rules, flags dual RN+NP requirements
- `email_formatter` — produces clean, personalized email draft per provider

### Outputs
- **One combined output file** containing all email drafts for the target month, providers separated clearly
- **Summary section at the top** listing all flags (unresolved requirements, tight timelines) for triage
- Flags also appear **inline** within each affected email draft
- All output is **pending review** — nothing sends automatically; user reviews and sends manually

## Email Cadence

- Agent is run with a **target month** as input (e.g., "run for July")
- One email per provider covers **all licenses expiring that month**
- Emails are intended to go out on the **1st of the prior month** (July renewals → June 1st send)
- Each email is grouped around the provider's **earliest expiration** in that month
- Providers with licenses in different months receive **separate emails per month** — no cross-month consolidation

## Key Domain Rules

### NP Complexity
- NPs in compact states may satisfy CE under a single license
- Some states require separate RN *and* NP CE hours — identified by two rows with same `initials` and `state` (one `RN`, one `NP`)
- **`np_compact = Yes` always wins** — if a provider has both the compact flag and dual RN+NP rows for the same state, the RN row is ignored; the email notes that compact status was applied
- NP CE hours and RN CE hours often differ per state
- Some states mandate specialty hours (pharmacology, opioid, DEA-specific)
- Always look up rules dynamically — no hardcoded tables

### Board Page Failures
1. Try direct state board page
2. If that fails, retry with a broader web search
3. If that also fails, **hold the affected email in pending review** and flag for manual resolution before sending
4. Never send an email with unconfirmed CE requirements without surfacing the gap to the user

### Flags
- ⚠️ **Tight timeline** — any individual license already within 30 days of expiration when the agent runs
- ❓ **Unresolved requirement** — board page could not be confirmed after retry
- Both flag types appear in the **summary section** at the top of the output file and **inline** in the relevant email draft

### Email Format
- Salutation: first name only — `Hi Jane,`
- Subject line per license section within the email: `CE Requirements — [State] [License Type] Renewal — Due [Date]`
- Source every requirement with a direct state board URL

## Fake Dataset Spec (Phase 1)

20 providers across 8–10 states:
- **8 MDs** — mix of single and multi-state licenses
- **8 NPs** — including 2 compact, 2 with dual RN+NP rows, 1 with specialty hour requirement (e.g., opioid prescribing)
- **4 RNs**
- States should include at least one compact state and one with complex NP rules (e.g., CA, TX, OH)
- At least 2 providers with licenses in multiple states (tests consolidation logic)
- At least 1 provider with a license already inside 30 days (tests tight timeline flag)

## Development Phases

### Phase 1 — Demo (current)
- [ ] Generate fake provider dataset per spec above
- [ ] Build agent loop: read spreadsheet → search CE requirements → format output
- [ ] Test with 3–5 providers across varied states and license types
- [ ] Validate NP compact logic and dual-license edge cases
- [ ] Validate board page failure → pending review flow
- [ ] Polish combined output file format with summary section

### Phase 2 — Internal Approval
- Confirm approved AI/API tools at org
- Assess PHI/PII compliance requirements
- Determine if email sending is in scope

### Phase 3 — Production
- Swap in real spreadsheet
- Connect approved API/AI infrastructure
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
4. Clean combined output file with summary section and per-provider email drafts
5. At least one NP with compact status applied correctly (RN row ignored)
6. At least one NP with dual RN+NP requirement handled correctly
7. At least one provider flagged for a tight renewal timeline
8. At least one pending review case demonstrated (unresolved board page)
