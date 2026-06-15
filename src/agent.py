"""
CE Requirements Agent — main entry point.

Usage:
    python src/agent.py data/fake_providers.xlsx "July 2026"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Windows consoles default to cp1252 and can't encode the box-drawing / arrow
# glyphs used in progress output. Force UTF-8 where the stream supports it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Add repo root to path so imports work regardless of CWD
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tools.ce_scraper import fetch_page, web_search
from src.tools.email_formatter import format_output_file
from src.tools.np_logic import prepare_license_context
from src.tools.spreadsheet_reader import load_spreadsheet

load_dotenv(ROOT / ".env")

MODEL = "claude-sonnet-4-6"  # default; override with --model (e.g. claude-opus-4-8)
MAX_ITERATIONS = 15  # safety cap on the per-provider tool loop

# Client-side tools — Claude calls them, we execute them. Used in both modes.
_FLAG_TOOL = {
    "name": "flag_for_review",
    "description": (
        "Flag this provider's draft for manual review before sending. Use this when: "
        "(1) CE requirements could not be confirmed from the state board website, "
        "(2) the page was unavailable or ambiguous, "
        "(3) requirements appear to have changed or are contradictory, "
        "(4) NP compact/dual rules are unclear for this provider."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Specific reason the draft needs review",
            }
        },
        "required": ["reason"],
    },
}

# Final-answer tool: the agent submits its draft through this strict schema
# instead of returning JSON as free text (which is brittle to parse).
_SUBMIT_TOOL = {
    "name": "submit_draft",
    "description": (
        "Submit the finished email draft for this provider. Call this exactly once, "
        "as your final action, after researching all licenses. Do NOT return the draft "
        "as plain text — always submit it through this tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Email subject line"},
            "body": {
                "type": "string",
                "description": "Full email body, beginning with 'Hi <FirstName>,'",
            },
            "flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Review flags (unconfirmed requirements, conflicts). Empty list if none.",
            },
            "pending_review": {
                "type": "boolean",
                "description": "True if this draft needs human review before it can be sent.",
            },
        },
        "required": ["subject", "body", "flags", "pending_review"],
    },
}

# Default: Anthropic server-side tools. Search + fetch run on Anthropic's
# infrastructure (no DDG rate limits, no scraping, citations included).
SERVER_TOOLS: list[dict] = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8},
    {
        "type": "web_fetch_20250910",
        "name": "web_fetch",
        "max_uses": 8,
        "citations": {"enabled": True},
    },
    _FLAG_TOOL,
    _SUBMIT_TOOL,
]

# Legacy fallback: our own DuckDuckGo + requests tools, executed client-side.
# Kept behind --legacy-search for offline/no-server-tools situations.
LEGACY_TOOLS: list[dict] = [
    {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo. Use this to find state licensing board "
            "websites and current CE requirements."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page",
        "description": (
            "Fetch the full text of a web page. Use this to read CE requirement details "
            "from a state board page after finding it via web_search. Content is truncated "
            "to ~16000 characters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch"}
            },
            "required": ["url"],
        },
    },
    _FLAG_TOOL,
    _SUBMIT_TOOL,
]

SYSTEM_PROMPT = """You are a CE Requirements Agent. Your job is to research current Continuing Education (CE) requirements for healthcare provider license renewals and produce personalized email drafts.

## Research each license
For each license, use web_search to find the official state licensing board's current CE / renewal requirements, then use web_fetch to read the specific page (or PDF) and extract exact figures. Strongly prefer official state board (.gov) sources.
- Capture for each license: total CE hours required, mandatory topic hours (e.g. ethics, opioid / controlled-substance prescribing, implicit bias), accepted formats, and the renewal cycle.
- Cite the exact source URL for every requirement you state.
- PDFs from the board often contain the exact hour breakdown — fetch them when search points to one.
- If, after searching and reading official sources, you cannot confirm a specific CE hour figure, call flag_for_review with a precise reason, and still write the best draft you can with [NEEDS VERIFICATION] inline next to anything unconfirmed.

## NP rules
- np_compact=true: use compact CE rules only; RN CE is handled via compact enrollment. Note this in the email.
- dual_rn_states non-empty and np_compact=false: include BOTH NP CE and RN CE requirements.
- Always look up requirements dynamically — never hardcode.

## Email format
Subject: CE Requirements — [State] [License Type] Renewal — Due [Date]

Hi [First Name],

[One paragraph per license: CE hours required, mandatory topics, accepted formats, source URL]

[If tight_timeline: urgent paragraph with renewal link]

Please reach out with any questions.

## Output format
When you have finished researching all licenses, call the `submit_draft` tool with your
final subject, body, flags, and pending_review. This is your final action — submit the
draft through the tool, never as plain text.

## Rules
- tight_timeline within 30 days: add urgent language in the body AND add a flag string.
- Only call flag_for_review when you truly cannot find CE requirements from an official source.
- Quote a source URL for every CE requirement you state.
- Keep emails professional and concise."""


def _execute_tool(name: str, tool_input: dict, flags: list[str]) -> str:
    if name == "web_search":
        results = web_search(tool_input["query"])
        return json.dumps(results)
    elif name == "fetch_page":
        result = fetch_page(tool_input["url"])
        return json.dumps(result)
    elif name == "flag_for_review":
        flags.append(tool_input["reason"])
        return json.dumps({"flagged": True, "reason": tool_input["reason"]})
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent_for_provider(
    client: anthropic.Anthropic,
    provider_ctx: dict,
    target_month: str,
    model: str = MODEL,
    use_server_tools: bool = True,
) -> dict:
    """Run the agent loop for a single provider and return draft dict."""
    flags: list[str] = []
    tools = SERVER_TOOLS if use_server_tools else LEGACY_TOOLS

    user_message = _build_user_message(provider_ctx, target_month)
    messages = [{"role": "user", "content": user_message}]

    print(f"\n{'─'*60}")
    print(f"Processing: {provider_ctx['initials']} — {provider_ctx['full_name']}")
    print(f"Licenses  : {len(provider_ctx['licenses'])} expiring in {target_month}")

    response = None
    submitted_draft: dict | None = None
    nudge_count = 0
    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            thinking={"type": "adaptive"},
        )

        # Log any server-tool activity for visibility
        for block in response.content:
            btype = getattr(block, "type", "")
            if btype == "server_tool_use":
                print(f"  → {block.name}({json.dumps(block.input)[:100]})")

        # Append assistant response to message history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            if submitted_draft is not None:
                break
            # Model finished but answered as text instead of calling submit_draft.
            # Nudge it to emit the actual tool call (a few times, then give up).
            if nudge_count < 2:
                nudge_count += 1
                print("  → (no draft submitted; nudging to call submit_draft)")
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You ended your turn without calling submit_draft. Call the "
                            "submit_draft tool now with your final subject, body, flags, and "
                            "pending_review. Respond with the tool call only, not text."
                        ),
                    }
                )
                continue
            break  # give up; fallback extraction handles it

        # Server tools (web_search/web_fetch) ran inline but the turn is long;
        # pass the content back and let Claude continue. No tool_result needed.
        if response.stop_reason == "pause_turn":
            continue

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if getattr(block, "type", "") != "tool_use":
                    continue
                if block.name == "submit_draft":
                    print("  → submit_draft (final)")
                    submitted_draft = dict(block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Draft received.",
                        }
                    )
                else:
                    print(f"  → tool: {block.name}({json.dumps(block.input)[:120]})")
                    result = _execute_tool(block.name, block.input, flags)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            # Final answer received — we're done with this provider.
            if submitted_draft is not None:
                break
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason (e.g. max_tokens) — stop looping
        break
    else:
        flags.append(
            f"Agent loop hit the {MAX_ITERATIONS}-iteration cap without finishing — "
            "draft may be incomplete."
        )

    # Prefer the structured submit_draft payload; fall back to regex extraction
    # only if the model never called the tool.
    if submitted_draft is not None:
        draft = submitted_draft
        draft.setdefault("flags", [])
        draft.setdefault("pending_review", False)
    else:
        draft = _extract_draft(response.content)

    if flags:
        draft["flags"] = flags + draft.get("flags", [])
        draft["pending_review"] = True

    # Inherit tight timeline from context
    tight_licenses = [l for l in provider_ctx["licenses"] if l["tight_timeline"]]
    if tight_licenses:
        draft["tight_timeline"] = True
        earliest = min(tight_licenses, key=lambda l: l["expiration_date"])
        draft["tight_reason"] = (
            f"{earliest['state']} {earliest['license_type']} expires "
            f"{earliest['expiration_date_str']} "
            f"({earliest['days_until_expiration']} days)"
        )

    draft["initials"] = provider_ctx["initials"]
    draft["email"] = provider_ctx["email"]
    return draft


def _build_user_message(provider_ctx: dict, target_month: str) -> str:
    np_flags = provider_ctx["np_flags"]
    license_lines = []
    for lic in provider_ctx["licenses"]:
        tight = " ⚠ TIGHT TIMELINE" if lic["tight_timeline"] else ""
        license_lines.append(
            f"  - {lic['state']} {lic['license_type']}: expires {lic['expiration_date_str']}"
            f" ({lic['days_until_expiration']} days from today){tight}"
        )

    msg = (
        f"Provider: {provider_ctx['full_name']} ({provider_ctx['credential']})\n"
        f"Email: {provider_ctx['email']}\n"
        f"Initials: {provider_ctx['initials']}\n"
        f"First name: {provider_ctx['first_name']}\n"
        f"Target month: {target_month}\n\n"
        f"Licenses expiring this month:\n" + "\n".join(license_lines)
    )

    if np_flags.get("is_np"):
        msg += f"\n\nNP flags:"
        msg += f"\n  np_compact: {np_flags['np_compact']}"
        if np_flags.get("compact_note"):
            msg += f"\n  {np_flags['compact_note']}"
        if np_flags.get("dual_rn_note"):
            msg += f"\n  {np_flags['dual_rn_note']}"

    return msg


def _extract_draft(content: list) -> dict:
    """Pull JSON draft from assistant response content blocks."""
    full_text = ""
    for block in content:
        if hasattr(block, "text"):
            full_text += block.text

    # Look for ```json ... ``` block
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", full_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: look for bare JSON object
    match = re.search(r"\{[^{}]*\"subject\"[^{}]*\}", full_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Last resort: return raw text as body
    return {
        "subject": "CE Requirements — See Details",
        "body": full_text.strip() or "[Agent produced no output]",
        "flags": ["Could not parse structured draft from agent response"],
        "pending_review": True,
    }


def _check_api_key() -> None:
    """Fail early with an actionable message if the API key is missing."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Create a .env file in the PROJECT ROOT (not src/) containing:")
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        print(f"Expected location: {ROOT / '.env'}")
        sys.exit(1)


def _dry_run_draft(provider_ctx: dict) -> dict:
    """Build a placeholder draft without calling the API (for --dry-run)."""
    lic_lines = "\n".join(
        f"- {l['state']} {l['license_type']} expires {l['expiration_date_str']}"
        f" ({l['days_until_expiration']} days)"
        for l in provider_ctx["licenses"]
    )
    draft = {
        "subject": f"[DRY RUN] CE Requirements — {provider_ctx['initials']} Renewal",
        "body": (
            f"Hi {provider_ctx['first_name']},\n\n"
            f"[DRY RUN — no research performed]\n{lic_lines}\n\n"
            "Please reach out with any questions."
        ),
        "flags": ["DRY RUN — placeholder draft, no CE requirements researched"],
        "pending_review": True,
        "initials": provider_ctx["initials"],
        "email": provider_ctx["email"],
    }
    tight = [l for l in provider_ctx["licenses"] if l["tight_timeline"]]
    if tight:
        earliest = min(tight, key=lambda l: l["expiration_date"])
        draft["tight_timeline"] = True
        draft["tight_reason"] = (
            f"{earliest['state']} {earliest['license_type']} expires "
            f"{earliest['expiration_date_str']} ({earliest['days_until_expiration']} days)"
        )
    return draft


def _filter_contexts(
    contexts: list[dict],
    only: list[str] | None,
    limit: int | None,
) -> list[dict]:
    """Apply --only (by initials, case-insensitive) then --limit."""
    if only:
        wanted = {i.strip().upper() for i in only}
        contexts = [c for c in contexts if c["initials"].upper() in wanted]
    if limit is not None:
        contexts = contexts[:limit]
    return contexts


def main(
    spreadsheet_path: str,
    target_month: str,
    only: list[str] | None = None,
    limit: int | None = None,
    as_of: date | None = None,
    model: str = MODEL,
    dry_run: bool = False,
    legacy_search: bool = False,
) -> None:
    today = as_of or date.today()
    path = Path(spreadsheet_path)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    print(f"CE Requirements Agent")
    print(f"Spreadsheet : {path}")
    print(f"Target month: {target_month}")
    print(f"Run date    : {today.isoformat()}" + ("  (--as-of override)" if as_of else ""))
    print(f"Model       : {model}")
    print(f"Search      : {'legacy DuckDuckGo' if legacy_search else 'server-side web_search/web_fetch'}")
    if dry_run:
        print("Mode        : DRY RUN (no API calls)")

    licenses, providers = load_spreadsheet(path, target_month)
    if not licenses:
        print(f"No licenses found expiring in {target_month}.")
        sys.exit(0)

    provider_contexts = prepare_license_context(licenses, providers, today)
    provider_contexts = _filter_contexts(provider_contexts, only, limit)
    if not provider_contexts:
        print("No providers matched the --only/--limit filters.")
        sys.exit(0)
    print(f"\nProcessing {len(provider_contexts)} provider(s).")

    client = None
    if not dry_run:
        _check_api_key()
        client = anthropic.Anthropic()

    drafts = []
    for ctx in provider_contexts:
        if dry_run:
            drafts.append(_dry_run_draft(ctx))
        else:
            draft = run_agent_for_provider(
                client, ctx, target_month, model=model,
                use_server_tools=not legacy_search,
            )
            drafts.append(draft)

    # Build output path: output/ce_drafts_<month_slug>_<date>_<HHMMSS>.txt
    month_slug = target_month.replace(" ", "_").lower()
    stamp = datetime.now().strftime("%H%M%S")
    out_file = ROOT / "output" / f"ce_drafts_{month_slug}_{today.isoformat()}_{stamp}.txt"
    format_output_file(drafts, target_month, today, out_file)

    # Console summary
    tight_count = sum(1 for d in drafts if d.get("tight_timeline"))
    review_count = sum(1 for d in drafts if d.get("pending_review"))
    print(f"\n{'='*60}")
    print(f"Done. {len(drafts)} drafts written.")
    print(f"  Tight timelines : {tight_count}")
    print(f"  Pending review  : {review_count}")
    print(f"  Output file     : {out_file}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent.py",
        description="CE Requirements Agent — research CE requirements and draft renewal emails.",
    )
    parser.add_argument("spreadsheet", help="Path to the provider .xlsx file")
    parser.add_argument("target_month", help="Target month, e.g. 'July 2026'")
    parser.add_argument(
        "--only",
        help="Comma-separated provider initials to process (e.g. JS,RB,LR)",
    )
    parser.add_argument(
        "--limit", type=int, help="Process only the first N providers (by earliest expiration)"
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        help="Pin 'today' to this YYYY-MM-DD (reproducible tight-timeline math)",
    )
    parser.add_argument("--model", default=MODEL, help=f"Model id (default: {MODEL})")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip all API calls; emit placeholder drafts to test formatting",
    )
    parser.add_argument(
        "--legacy-search",
        action="store_true",
        help="Use the client-side DuckDuckGo scraper instead of server-side web tools",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])

    as_of_date = None
    if args.as_of:
        try:
            as_of_date = datetime.strptime(args.as_of, "%Y-%m-%d").date()
        except ValueError:
            print(f"ERROR: --as-of must be YYYY-MM-DD, got {args.as_of!r}")
            sys.exit(1)

    only_list = [s for s in args.only.split(",")] if args.only else None

    main(
        spreadsheet_path=args.spreadsheet,
        target_month=args.target_month,
        only=only_list,
        limit=args.limit,
        as_of=as_of_date,
        model=args.model,
        dry_run=args.dry_run,
        legacy_search=args.legacy_search,
    )
