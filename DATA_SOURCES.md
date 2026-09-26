# Data sources

How every dataset, log file, vendored file, and traceback in this repository
was produced — and what is synthetic versus real.

## What is in this repo

| Path | Contents | Origin |
|---|---|---|
| `incidents/incident_001.json` + `incident_001_logs.txt` | Synthetic alert payload and service logs for the crash bug | Hand-written for this project; the traceback was captured by running the seeded `victim-service` code locally |
| `incidents/incident_002.json` + `incident_002_logs.txt` | Synthetic finance-reconciliation alert and logs for the silent discount bug | Hand-written for this project |
| `incidents/incident_003.json` + `incident_003_logs.txt` | Synthetic deploy/payment alert and logs for the config bug | Hand-written for this project |
| `incidents/incident_004.json` + `incident_004_logs.txt` | Alert payload and service logs built around a REAL third-party bug | Constructed for this project around the genuine humanize issue #57 (see below); the billing-worker scenario, log lines, and job counts are illustrative, not production data |
| `victim-service/` | Sample FastAPI application with three intentionally seeded bugs | Written for this project |
| `triage/realworld/humanize/` | humanize 4.3.0, vendored verbatim from the official PyPI release (MIT licensed) | Real open-source code — pristine at intake; Bob's fix was applied to this copy in Task 15 |
| `triage/realworld/repro_metric_zero.py` | Minimal reproducer for the humanize bug | Written for this project |
| `triage/reports/`, `triage/fixes/` | Root-cause reports, fix diffs, incident reports | Produced by the deterministic pipeline and by IBM Bob in the IDE |

## Honesty boundary for incident 004

The bug itself is real: `humanize.metric(0)` crashes on humanize 4.3.0
(upstream issue python-humanize/humanize#57, fixed by PR #47 in 4.4.0), and the
vendored copy is byte-for-byte the PyPI release. What is constructed for the
hackathon: the billing-worker alert, the 30 log lines, and the "41 failed
invoice jobs" scenario — they dramatize a plausible production impact but are
not evidence from a real outage.

## Compliance statement

- No client data is used.
- No personal information (PI) is used. Names, IPs, and order ids in the logs are fictional.
- No social media data is used.
- No company-confidential data or assets are used.
- No public-website data was scraped; therefore no source list is required.
- The `PAYMENTS_MODE` payment gateway is fully simulated in code; no real payment provider is contacted.
- Vendored third-party code (`triage/realworld/humanize/`, MIT licensed) is used under its license; its provenance is documented in `triage/realworld/README.md`.

## Reproducibility

Anyone can regenerate the incident_001 traceback from the seeded code:

```bash
cd victim-service
python -c "
import traceback
from app import apply_tax
try:
 apply_tax(20.0, None)
except Exception:
 print(traceback.format_exc())
"
```

Anyone can reproduce the incident_004 crash from the vendored library (before
Bob's fix is applied — see `git log` for the pre-fix state):

```bash
python triage/realworld/repro_metric_zero.py
```
