# CE Requirements Agent — Project Plan

## Overview

An agentic tool that reads a provider license spreadsheet, researches current Continuing Education (CE) requirements per state and license type, and outputs ready-to-send email drafts for each provider ahead of their renewal deadlines.

---

## The Problem

- CE requirements are scattered across 51 state licensing board websites
- Requirements change without notice
- Providers (MDs and NPs) may be licensed in multiple states
- NPs add complexity: some states require both RN + NP CE, compact vs. non-compact rules vary
- Manual lookup is time-consuming and error-prone

---

## Goals

- **Demo goal:** Working prototype with fake provider data, no real credentials or API keys required for approval
- **Production goal:** Drop in real spreadsheet, get accurate per-provider email drafts with current CE requirements

---

## Agent Behavior (What Makes This an Agent, Not a Script)

The system should *reason*, not just execute. Specifically:

- Decides which state board pages to search and follows links when requirements are buried
- Detects ambiguous or changed requirements and flags them rather than guessing
- Applies NP compact logic dynamically based on provider data
- Notices tight timelines (e.g. renewal in 5 weeks, 40 CE hours required) and escalates tone accordingly
- Surfaces discrepancies if a requirement appears to have changed since last run

---

## Data Source — Spreadsheet Schema

Mirrors existing license tracking spreadsheet format. One row per license.

| Column | Description | Example |
|---|---|---|
| `initials` | Provider identifier | JS |
| `state` | Two-letter state code | OH |
| `license_type` | MD, NP, or RN | NP |
| `expiration_date` | License renewal date | 2026-08-15 |

**Second sheet (lookup table):**

| Column | Description |
|---|---|
| `initials` | Matches license sheet |
| `full_name` | For email salutation |
| `credential` | e.g. Dr., NP-C |
| `email` | For output addressing |
| `np_compact` | Yes/No (NP only) |

> NPs requiring both RN + NP CE are identified by having two rows for the same state (one RN, one NP).

---

## Architecture

### Inputs
- CSV/Excel spreadsheet (provider license data)
- Optional: target date range (e.g. "renewals in next 30 days")

### Agent Tools
- **Spreadsheet reader** — parses provider/license data
- **Web search** — queries state licensing board sites for current CE requirements
- **CE requirement scraper** — extracts structured data (total hours, topic requirements, deadlines) from board pages
- **NP logic handler** — applies compact/non-compact rules, flags RN+NP dual requirements
- **Timeline evaluator** — flags tight renewal windows with appropriate urgency
- **Email formatter** — produces clean, personalized email draft per provider

### Outputs
- One formatted email draft per provider
- Covers all states with upcoming renewals in the target window
- Flags any states where requirements were ambiguous or could not be confirmed
- Optional: summary report of all upcoming renewals sorted by date

---

## NP Complexity Handling

NPs require special handling due to:

1. **Compact states** — NPs in compact states may satisfy CE under a single license
2. **Dual license states** — some states require separate RN *and* NP CE hours
3. **Varying hour requirements** — NP CE hours and RN CE hours may differ per state
4. **Specialty requirements** — some states have pharmacology, opioid, or DEA-specific mandates

The agent should look up and apply these rules dynamically rather than relying on a hardcoded table that goes stale.

---

## Email Output Format (Per Provider)

```
Subject: CE Requirements — [State] [License Type] Renewal — Due [Date]

Hi [Full Name],

Your [license type] license in [State] is due for renewal on [Date].
Below are the current CE requirements per the [State Board Name]:

• Total CE hours required: XX
• Required topics: [e.g., 2 hrs opioid prescribing, 1 hr ethics]
• Accepted formats: [live, online, etc.]
• Source: [State board URL]

[If NP with RN requirement:]
Note: [State] also requires RN CE for NP renewal:
• RN CE hours required: XX
• [Additional details]

⚠️ [If tight timeline:]
Your renewal is in X weeks. Please confirm CE completion is on track.

Please reach out with any questions.
```

---

## Build Phases

### Phase 1 — Demo (No Production Data)
- [ ] Generate fake provider dataset (20 providers, mix of MD/NP, multiple states)
- [ ] Build agent loop: read spreadsheet → search CE requirements → format output
- [ ] Test with 3–5 providers across varied states and license types
- [ ] Validate NP dual-license logic with edge case providers
- [ ] Polish email output format

### Phase 2 — Internal Approval
- [ ] Present demo to manager
- [ ] Confirm approved AI/API tools at org
- [ ] Assess PHI/PII compliance requirements for provider data
- [ ] Determine if email sending is in scope or output-only

### Phase 3 — Production
- [ ] Swap in real spreadsheet
- [ ] Connect approved API/AI infrastructure
- [ ] Add scheduling (on-demand trigger vs. automated 30-day lookahead)
- [ ] Add logging / run history so changes in requirements are trackable over time

---

## Key Technical Decisions (TBD at Phase 2)

| Decision | Options |
|---|---|
| AI platform | Anthropic API, Azure OpenAI, approved internal tool |
| Runtime | Python script, Claude Code, scheduled job |
| Trigger | On-demand (manual run) vs. automated schedule |
| Email sending | Manual copy-paste (v1) → direct send via approved email API (v2) |
| Data storage | Local CSV/Excel → shared drive or internal DB |

---

## Risks & Open Questions

- **State board websites change** — agent must handle broken pages gracefully and flag failures
- **PHI/PII compliance** — provider names + license data may require approved data handling
- **Compact rules change** — NP compact membership evolves; source of truth needs to stay current
- **Email permissions** — direct sending likely requires IT approval; copy-paste output is v1 workaround

---

## Demo Success Criteria

When presenting to colleagues, the demo should show:

1. Agent reads a spreadsheet of fake providers
2. Live web searches against real state board sites
3. Reasoning visible — agent explains what it found, flags anything ambiguous
4. Clean, personalized email draft output per provider
5. At least one NP with dual RN+NP requirement handled correctly
6. At least one provider flagged for a tight renewal timeline

---

*Last updated: June 2026*
