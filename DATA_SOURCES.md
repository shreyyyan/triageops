# Data sources

Every dataset, log file, and traceback in this repository is **synthetic** and
was generated specifically for this hackathon submission.

## What is in this repo

| Path | Contents | Origin |
|---|---|---|
| `incidents/incident_001.json` + `incident_001_logs.txt` | Synthetic alert payload and service logs for the crash bug | Hand-written for this project; the traceback was captured by running the seeded `victim-service` code locally |
| `incidents/incident_002.json` + `incident_002_logs.txt` | Synthetic finance-reconciliation alert and logs for the silent discount bug | Hand-written for this project |
| `incidents/incident_003.json` + `incident_003_logs.txt` | Synthetic deploy/payment alert and logs for the config bug | Hand-written for this project |
| `victim-service/` | Sample FastAPI application with three intentionally seeded bugs | Written for this project |
| `triage/reports/`, `triage/fixes/` | Generated during the Bob IDE workflow | Produced by the pipeline and by IBM Bob |

## Compliance statement

- No client data is used.
- No personal information (PI) is used. Names, IPs, and order ids in the logs are fictional.
- No social media data is used.
- No company-confidential data or assets are used.
- No public-website data was scraped; therefore no source list is required.
- The `PAYMENTS_MODE` payment gateway is fully simulated in code; no real payment provider is contacted.

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
