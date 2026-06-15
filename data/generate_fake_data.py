"""Generate fake_providers.xlsx with two sheets: licenses and providers."""
import openpyxl
from pathlib import Path

# fmt: off
LICENSES = [
    # initials, state, license_type, expiration_date
    # MDs
    ("JS", "OH", "MD", "2026-07-15"),
    ("RB", "CA", "MD", "2026-07-08"),   # tight (30 days from 2026-06-12 = 2026-07-12)
    ("MK", "TX", "MD", "2026-07-22"),
    ("MK", "FL", "MD", "2026-07-30"),
    ("DL", "NY", "MD", "2026-07-03"),   # tight
    ("SP", "IL", "MD", "2026-07-18"),
    ("TC", "PA", "MD", "2026-07-25"),
    ("AG", "OH", "MD", "2026-07-10"),   # tight (OH row)
    ("AG", "NY", "MD", "2026-07-28"),
    ("WJ", "WA", "MD", "2026-07-20"),
    # NPs
    ("LR", "TX", "NP", "2026-07-16"),   # compact
    ("KM", "WA", "NP", "2026-07-09"),   # compact, tight
    ("BT", "OH", "NP", "2026-07-14"),   # dual NP+RN
    ("BT", "OH", "RN", "2026-07-14"),
    ("ET", "CA", "NP", "2026-07-07"),   # dual NP+RN, tight
    ("ET", "CA", "RN", "2026-07-07"),
    ("JW", "FL", "NP", "2026-07-21"),   # specialty opioid hours
    ("NB", "IL", "NP", "2026-07-19"),
    ("AH", "PA", "NP", "2026-07-17"),   # multi-state compact
    ("AH", "TX", "NP", "2026-07-17"),
    ("CM", "NY", "NP", "2026-07-06"),   # dual NP+RN, tight
    ("CM", "NY", "RN", "2026-07-06"),
    # RNs
    ("PJ", "OH", "RN", "2026-07-23"),
    ("MN", "CA", "RN", "2026-07-11"),   # tight
    ("SR", "TX", "RN", "2026-07-26"),
    ("KA", "FL", "RN", "2026-07-29"),
]

PROVIDERS = [
    # initials, full_name, credential, email, np_compact
    ("JS", "James Sullivan",    "Dr.",   "jsullivan@fakeclinic.com",   "No"),
    ("RB", "Rachel Brooks",     "Dr.",   "rbrooks@fakeclinic.com",     "No"),
    ("MK", "Michael Kim",       "Dr.",   "mkim@fakeclinic.com",        "No"),
    ("DL", "Diana Lee",         "Dr.",   "dlee@fakeclinic.com",        "No"),
    ("SP", "Samuel Patel",      "Dr.",   "spatel@fakeclinic.com",      "No"),
    ("TC", "Theresa Chen",      "Dr.",   "tchen@fakeclinic.com",       "No"),
    ("AG", "Aaron Green",       "Dr.",   "agreen@fakeclinic.com",      "No"),
    ("WJ", "William James",     "Dr.",   "wjames@fakeclinic.com",      "No"),
    ("LR", "Laura Rivera",      "NP-C",  "lrivera@fakeclinic.com",     "Yes"),
    ("KM", "Karen Mitchell",    "NP-BC", "kmitchell@fakeclinic.com",   "Yes"),
    ("BT", "Brian Torres",      "NP-C",  "btorres@fakeclinic.com",     "No"),
    ("ET", "Emily Thompson",    "NP-BC", "ethompson@fakeclinic.com",   "No"),
    ("JW", "Jennifer Wu",       "NP-C",  "jwu@fakeclinic.com",         "No"),
    ("NB", "Nathan Bell",       "NP-BC", "nbell@fakeclinic.com",       "No"),
    ("AH", "Angela Harris",     "NP-C",  "aharris@fakeclinic.com",     "Yes"),
    ("CM", "Christine Morris",  "NP-BC", "cmorris@fakeclinic.com",     "No"),
    ("PJ", "Patricia Jones",    "RN",    "pjones@fakeclinic.com",      "No"),
    ("MN", "Marcus Nelson",     "RN",    "mnelson@fakeclinic.com",     "No"),
    ("SR", "Sandra Robinson",   "RN",    "srobinson@fakeclinic.com",   "No"),
    ("KA", "Kevin Adams",       "RN",    "kadams@fakeclinic.com",      "No"),
]
# fmt: on


def generate():
    wb = openpyxl.Workbook()

    # Sheet 1: licenses
    ws_lic = wb.active
    ws_lic.title = "licenses"
    ws_lic.append(["initials", "state", "license_type", "expiration_date"])
    for row in LICENSES:
        ws_lic.append(list(row))

    # Sheet 2: providers
    ws_prov = wb.create_sheet("providers")
    ws_prov.append(["initials", "full_name", "credential", "email", "np_compact"])
    for row in PROVIDERS:
        ws_prov.append(list(row))

    out = Path(__file__).parent / "fake_providers.xlsx"
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    generate()
