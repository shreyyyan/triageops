# TriageOps — Demo Video Plan

Total: 3:00 max. At least 90 seconds must show the working solution live on screen, with narration throughout.

## 0:00–0:20 — The problem

On screen: the TriageOps dashboard open in the browser.

"Every developer knows this moment. It's 2 AM, an alert fires, the checkout service is crashing. Normally that's 30 minutes of reading logs and guessing. TriageOps changes that."

## 0:20–1:10 — Live demo: the dashboard

On screen: `streamlit run triage/app.py`.

- Sidebar: select incident 001, click **Run triage**.
- Stage 1 — Alert parsed: the alert payload, structured.
- Stage 2 — Log evidence: 48 matching log lines around the incident window.
- Stage 3 — Code locations: traceback frames resolved to `victim-service/app.py:60`.
- Stage 6 — Test verification: click **Run test suite now** — 7 passed, 2 failed (the 2 failures are separate seeded incidents, intentionally untouched).
- Stage 7 — Incident report: download the rendered report.

## 1:10–2:20 — Bob IDE: the core

On screen: Bob IDE. This section is the heart of the video — do not shorten it.

- Tasks panel: all 11 tasks.
- Task 1: timeline + 3 ranked hypotheses from the alert and logs.
- `triage/reports/root_cause_001.md`: the traced call chain and blast radius.
- `triage/fixes/fix_001.diff`: the one-line fix — `TAX_RATES[region]` → `TAX_RATES.get(region, 0.0)`.
- Task 4: before/after — 5 passed / 4 failed → 7 passed / 2 failed.
- Live terminal: `python -m pytest victim-service/tests/ -v`.
- `triage/reports/incident_INC-2026-1042_report.md`: the final report.

## 2:20–2:45 — Close

On screen: `github.com/shreyyyan/triageops`, then the `bob_sessions/` folder.

"TriageOps turns a 30-minute panic into a guided workflow. The pipeline gathers the evidence, Bob does the reasoning, the fix is proven by tests. All eleven Bob sessions are saved in the repo."

## Recording notes

- 1080p, browser and terminal zoomed to 125%+.
- Narrate each action before doing it; pause half a second, then click.
- Do 3–4 takes; trim dead air at the start and end.
- If a take runs long, trim the dashboard walkthrough — never the Bob section.
