"""Prepare NP/RN license context for the agent prompt."""
from __future__ import annotations

from datetime import date


def prepare_license_context(
    licenses: list[dict],
    providers: dict[str, dict],
    today: date,
) -> list[dict]:
    """
    Group licenses by provider and annotate with NP logic flags.

    Returns a list of provider context dicts, one per initials, each containing:
      - initials, first_name, full_name, credential, email
      - licenses: list of license dicts annotated with tight_timeline bool
      - np_flags: dict describing compact/dual-RN situation per state
    """
    TIGHT_DAYS = 30

    # Group licenses by initials
    by_provider: dict[str, list[dict]] = {}
    for lic in licenses:
        by_provider.setdefault(lic["initials"], []).append(lic)

    contexts = []
    for initials, lic_list in by_provider.items():
        prov = providers.get(initials, {})
        full_name = prov.get("full_name", initials)
        first_name = full_name.split()[0] if full_name else initials

        annotated = []
        for lic in lic_list:
            days_until = (lic["expiration_date"] - today).days
            annotated.append(
                {
                    **lic,
                    "expiration_date_str": lic["expiration_date"].isoformat(),
                    "days_until_expiration": days_until,
                    "tight_timeline": days_until <= TIGHT_DAYS,
                }
            )

        np_flags = _compute_np_flags(initials, annotated, prov)

        contexts.append(
            {
                "initials": initials,
                "first_name": first_name,
                "full_name": full_name,
                "credential": prov.get("credential", ""),
                "email": prov.get("email", ""),
                "licenses": annotated,
                "np_flags": np_flags,
            }
        )

    # Sort by earliest expiration across all licenses for each provider
    contexts.sort(key=lambda c: min(l["expiration_date"] for l in c["licenses"]))
    return contexts


def _compute_np_flags(
    initials: str,
    licenses: list[dict],
    prov: dict,
) -> dict:
    """
    Analyse NP/RN rows for this provider and return flag dict.

    np_compact=True overrides all dual-RN requirements for compact-enrolled states.
    Dual-RN states are states where both an NP and RN row exist with the same state.
    """
    np_compact = prov.get("np_compact", False)

    # Find states where this provider has both NP and RN rows
    np_states = {l["state"] for l in licenses if l["license_type"] == "NP"}
    rn_states = {l["state"] for l in licenses if l["license_type"] == "RN"}
    dual_states = np_states & rn_states

    flags: dict = {
        "is_np": bool(np_states),
        "np_compact": np_compact,
        "dual_rn_states": sorted(dual_states),
        "compact_note": "",
        "dual_rn_note": "",
    }

    if np_compact and dual_states:
        flags["compact_note"] = (
            f"Provider is NP Compact enrolled. "
            f"Compact CE rules apply — separate RN CE rows for "
            f"{', '.join(sorted(dual_states))} are superseded by compact requirements."
        )
    elif dual_states:
        flags["dual_rn_note"] = (
            f"Provider has both NP and RN licenses in: "
            f"{', '.join(sorted(dual_states))}. "
            f"Both NP CE and RN CE requirements must be included in the email."
        )

    return flags
