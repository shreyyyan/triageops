# TriageOps — incident triage assistant

Built for the **IBM Bob 2.0 hackathon** (lablab.ai, 48-hour build, Sept 25–27 2026).
Theme: *improve a developer workflow* — here, **debugging / incident response**.

## The problem

When an alert fires, an on-call engineer burns tens of minutes on mechanical
triage: reading the alert, grepping logs, reconstructing a timeline, tracing
the fault through code, guessing a fix, and proving it works. For three of the
most common bug classes — **crashes** (stack traces), **silent logic bugs**
(no crash, wrong numbers), and **config mistakes** (only visible after a
deploy) — that loop is slow, error-prone, and miserable at 2am.

## What TriageOps does

Feed it an incident alert + service logs. It:

1. Parses the alert (service, endpoint, error signature, severity, timestamp).
2. Correlates matching log lines with surrounding context.
3. Resolves traceback frames to exact `file:line` locations in the repo.
4. Runs the project's test suite to establish the failing baseline.
5. Hands the evidence to **IBM Bob in the IDE**, which traces the root cause,
   proposes a minimal fix, applies it, and iterates until the incident's
   tests pass.
6. Renders a downloadable incident report: timeline, evidence, root cause,
   fix, verification.

The pipeline is deterministic and never invents analysis; the reasoning is
Bob's, with session screenshots committed under `bob_sessions/`.

## Architecture

```
                    +----------------------+
                    |  incidents/*.json    |
                    |  incidents/*_logs.txt|  synthetic alerts + logs
                    +----------+-----------+
                               |
                    +----------v-----------+
                    | triage/triage_core.py|  deterministic pipeline
                    |  parse_alert         |  (no invented analysis)
                    |  correlate_logs      |
                    |  locate_code         |
                    |  run_tests (pytest)  |
                    |  render_report       |
                    +----------+-----------+
                               |
              +----------------+----------------+
              |                                 |
   +----------v-----------+          +----------v-----------+
   | triage/app.py         |          | IBM Bob IDE          |
   | (Streamlit dashboard)|          |  Task 1: intake      |
   | 7-stage demo UI      |<-------->|  Task 2: root cause  |
   +----------------------+  files   |  Task 3: fix diff    |
                                     |  Task 4: verify      |
   +--------------------------------+  Task 5: report      |
   | victim-service/  (FastAPI app with 3 seeded bugs)      |
   +--------------------------------------------------------+
```

## Quickstart

```bash
# 1. Install dependencies
pip install -r victim-service/requirements.txt
pip install -r triage/requirements.txt   # streamlit for the dashboard

# 2. Run the victim service (the "production" app)
cd victim-service && uvicorn app:app --port 8000

# 3. Run the test suite (2 tests fail on the remaining seeded bugs —
#    incidents 002/003; incident 001's tests were fixed via Bob in Task 4)
python -m pytest victim-service/tests/ -v

# 4. Run the deterministic pipeline headlessly
cd triage && python -c "
from triage_core import run_pipeline
r = run_pipeline('../incidents/incident_001.json',
                 '../incidents/incident_001_logs.txt',
                 '../victim-service')
print(r['test_results']['summary_line'])
print('report:', r['report_path'])
"

# 5. Launch the demo dashboard
streamlit run triage/app.py
```

## The 5-step Bob workflow

In Bob IDE, on the **hackathon-provisioned account**, run the prompts in
`prompts/bob_tasks.md` in order:

1. **Incident intake** (Ask mode) — timeline + ranked hypotheses from the alert and logs.
2. **Root-cause trace** (Agent mode) — exact faulty code path, saved to `triage/reports/root_cause_001.md`.
3. **Fix proposal** (Agent mode) — minimal diff + safety rationale, saved to `triage/fixes/fix_001.diff`.
4. **Verify** (Agent mode) — apply the fix, run pytest, iterate until the incident's tests pass.
5. **Incident report** (Agent mode) — final one-page markdown report.

Screenshot each task's session consumption summary into `bob_sessions/`
(see `bob_sessions/README.md`).

## How to demo

Follow `DEMO_SCRIPT.md` (3-minute video plan). The short version:

1. `streamlit run triage/app.py`, select incident 001, click **Run triage**.
2. Walk stages 1–3 (alert, logs, code locations).
3. Show Bob's root-cause analysis and fix diff (stages 4–5).
4. Click **Run test suite now** — live pytest run (stage 6).
5. Download the incident report (stage 7), then show the `bob_sessions/` evidence.

## Impact framing

Manual triage of these three bug classes is a 20–40 minute loop of reading,
grepping, tracing, and guessing, even for engineers who know the codebase.
TriageOps reduces it to a guided workflow measured in minutes: the pipeline
gathers all evidence in seconds, Bob's trace-fix-verify loop runs against the
real repo and the real test suite, and the report it produces is the artefact
an on-call engineer would otherwise write by hand. Stated honestly: the
"minutes, not tens of minutes" claim is measured on the seeded incidents in
this repo, not on production outages.

## Repo map

- `victim-service/` — the sample FastAPI app with 3 seeded bugs + pytest suite
- `triage/` — `triage_core.py` (deterministic pipeline), `app.py` (Streamlit demo UI)
- `incidents/` — 3 synthetic incident payloads (alert JSON + logs each)
- `prompts/bob_tasks.md` — the 5 Bob IDE task prompts
- `bob_sessions/` — Bob task session screenshots (required deliverable)
- `DEMO_SCRIPT.md` — 3-minute video plan
- `STATEMENTS.md` — submission statements: problem/solution and IBM Bob usage
- `DATA_SOURCES.md` — dataset compliance statement

## How IBM Bob was used

Bob is the reasoning engine: intake analysis (Ask mode), root-cause tracing,
fix proposal, and fix verification (Agent mode), plus the final incident
report — all against the real repository, all evidenced by the session
summaries in `bob_sessions/`. See `STATEMENTS.md` for the full usage statement.
