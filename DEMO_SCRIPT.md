# Demo script — 3-minute video plan

Total: 3:00 max. At least 0:90 must show the solution live on screen.
Narration cues are in italics; on-screen actions are in plain text.

## 0:00–0:30 — The problem (30s)

*On screen: a terminal tailing victim-service logs with 500 errors scrolling.*

- *"Every on-call engineer knows this moment. It's 2am, the alert fires, and the clock starts."*
- *"Mean time to resolution is dominated by triage: reading the alert, grepping logs, tracing the code, guessing the fix, then proving it. For these three bug classes — a crash, a silent logic bug, a bad config — that manual loop is 20 to 40 minutes of expert work."*
- *"TriageOps compresses that loop: deterministic evidence gathering plus IBM Bob reasoning in the IDE."*

## 0:30–2:00 — Live demo (90s)

*On screen: `streamlit run triage/app.py`, incident_001 selected.*

1. **Stages 1–3 (25s)** — Click "Run triage".
   - *"The alert is parsed: service, endpoint, error signature, severity. Log lines are correlated around the incident window. The traceback frames resolve to exact file-and-line locations in the repo."*
2. **Stage 4 (15s)** — Scroll to the root-cause panel.
   - *"The root-cause analysis was produced by IBM Bob in Agent mode — Task 2. Bob traced the call chain from the endpoint to the faulty line."*
3. **Stage 5 (10s)** — Show the diff.
   - *"Task 3: Bob proposed this minimal diff, with a safety rationale."*
4. **Stage 6 (25s)** — Click "Run test suite now". Show the red run first if pre-fix, then the green run.
   - *"Task 4: Bob applied the fix and iterated until the suite went green. Four failing tests before, all passing after. Nothing was faked — this is the real pytest run."*
5. **Stage 7 (15s)** — Show the rendered incident report; click Download.
   - *"And the pipeline renders the incident report: timeline, evidence, root cause, verification."*

## 2:00–2:45 — Bob evidence (45s)

*On screen: Bob IDE with the task list open; then the `bob_sessions/` folder.*

- *"Every reasoning step ran in IBM Bob IDE on the hackathon account. Five tasks: intake in Ask mode, then root-cause trace, fix proposal, verification, and the incident report in Agent mode."*
- Open one task session summary; show the consumption summary.
- *"The session summaries are committed in `bob_sessions/` — that is our evidence of Bob usage."*

## 2:45–3:00 — Impact and close (15s)

*On screen: the repo README architecture diagram or the closing slide.*

- *"TriageOps turns a 30-minute manual triage loop into a guided, evidence-backed workflow measured in minutes — on real, seeded incidents, with the fix verified by the test suite."*
- *"Incident triage is the debugging workflow every team dreads. We built the assistant we wish we had on call."*
- End card: project title, repo URL, team.

## Recording tips

- Record at 1080p, terminal and browser zoomed to 125%+.
- Do the pytest run once before recording so you know the timing.
- Keep narration tight: rehearse the 90-second demo block twice.
- If anything is slow live, it is fine to cut between the stages — judges care that the solution is real, not that it is one unbroken take.
