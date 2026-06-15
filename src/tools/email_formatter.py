"""Build the combined output file from agent-produced drafts."""
from __future__ import annotations

from datetime import date
from pathlib import Path


def format_output_file(
    drafts: list[dict],
    target_month: str,
    run_date: date,
    output_path: Path,
) -> None:
    """
    Write combined output file.

    drafts: list of {initials, email, subject, body, flags: list[str], pending_review: bool}
    """
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        "=" * 72,
        f"CE REQUIREMENTS AGENT — OUTPUT",
        f"Target month : {target_month}",
        f"Run date     : {run_date.isoformat()}",
        f"Providers    : {len(drafts)}",
        "=" * 72,
        "",
    ]

    # ── Summary flags section ────────────────────────────────────────────────
    all_flags = [
        (d["initials"], d.get("email", ""), flag)
        for d in drafts
        for flag in d.get("flags", [])
    ]
    tight = [d for d in drafts if d.get("tight_timeline")]
    review_needed = [d for d in drafts if d.get("pending_review")]

    lines += ["SUMMARY FLAGS", "-" * 40]
    if not all_flags and not tight:
        lines.append("No flags.")
    else:
        if tight:
            lines.append(f"⚠  TIGHT TIMELINE ({len(tight)} provider(s)):")
            for d in tight:
                lines.append(f"   • {d['initials']} — {d.get('tight_reason', '')}")
        if review_needed:
            lines.append(f"")
            lines.append(f"🔍 PENDING REVIEW ({len(review_needed)} provider(s)):")
            for d in review_needed:
                lines.append(f"   • {d['initials']}")
                for flag in d.get("flags", []):
                    lines.append(f"     - {flag}")
    lines += ["", ""]

    # ── Per-provider drafts ──────────────────────────────────────────────────
    for d in drafts:
        lines += [
            "=" * 72,
            f"PROVIDER : {d['initials']}  ({d.get('email', 'no email')})",
        ]
        if d.get("pending_review"):
            lines.append("STATUS   : ⚠ PENDING REVIEW — do not send until reviewed")
        else:
            lines.append("STATUS   : Ready for review")
        if d.get("flags"):
            lines.append("FLAGS    :")
            for flag in d["flags"]:
                lines.append(f"  • {flag}")
        lines += [
            "-" * 72,
            f"To      : {d.get('email', '')}",
            f"Subject : {d.get('subject', '')}",
            "",
            d.get("body", "[No draft produced]"),
            "",
        ]

    lines.append("=" * 72)
    lines.append("END OF OUTPUT")
    lines.append("=" * 72)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Output written to: {output_path}")
