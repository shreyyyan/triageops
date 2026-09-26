# TriageOps — Demo Video Plan

Total: 3:00 max (aim 2:30–2:45). At least 90 seconds must show the working solution live on screen, with narration throughout. Bob must be visibly central.

## 0:00–0:15 — The problem

On screen: the TriageOps dashboard open in the browser.

"Every developer knows this moment. It's 2 AM, an alert fires, the checkout service is crashing. Normally that's 30 minutes of reading logs and guessing. TriageOps turns it into a guided workflow. Let me show you."

## 0:15–0:50 — Dashboard: the pipeline (incident 001)

On screen: `streamlit run triage/app.py`.

- Sidebar: select incident 001, click **Run triage**.
- Stage 1 — Alert parsed. Stage 2 — 48 log lines correlated. Stage 3 — traceback resolves to `victim-service/app.py:60`.
- Stage 6 — click **Run test suite now**: 7 passed, 2 failed (the 2 failures are separate seeded incidents, intentionally untouched).
- Stage 7 — download the incident report.
- Move briskly: 2–3 seconds per stage. This is the setup.

## 0:50–2:10 — The real-world proof: incident 004 (the centerpiece — never cut)

On screen: dashboard, then Bob IDE, then terminal.

- Sidebar: select incident 004 (real `humanize` 4.3.0 bug: `metric(0)` → `ValueError` at `number.py:511`), click **Run triage**. 30 log lines correlated.
- Stage 4 — Bob's root-cause report (exact code path, step by step). Stage 5 — the fix Bob proposed **blind** (never saw the upstream patch). Scroll past Stage 6 without clicking (it covers the seeded service's suite, not this incident). Stage 7 — the "Bob vs Upstream" comparison section.
- Bob IDE: Tasks panel (12–16) → `triage/reports/root_cause_004.md` → `triage/fixes/fix_004.diff` (the two-line guard).
- Live terminal: `python triage/realworld/repro_metric_zero.py` → prints `0.00`. (Before the fix, this exact command crashed.)
- `triage/reports/incident_INC-2026-1045_report.md` — Task 16's comparison: Bob's fix vs the real upstream patch (PR #47), honestly judging the maintainer's one-liner cleaner.

## 2:10–2:30 — The paper trail

On screen: Bob IDE tasks panel (all 16 tasks), then `github.com/shreyyyan/triageops` → `bob_sessions/` (16 screenshots).

"Sixteen Bob tasks — the first eleven closed three incidents on our seeded service. Every session screenshotted and committed. The pipeline gathers evidence it can't hallucinate; Bob does the reasoning."

## 2:30–2:45 — Close

On screen: repo README.

"TriageOps turns a 30-minute panic into a guided workflow — proven on seeded bugs, and proven on a real one. Everything is open source. Link below. Thank you."

## Recording notes

- 1080p, browser and terminal zoomed to 125%+.
- Narrate each action before doing it; pause half a second, then click.
- Full word-for-word narration: `triageops-demo-narration.md` (in the submission package).
- Do 3–4 takes; trim dead air at the start and end.
- If a take runs long, trim the 001 walkthrough first — never the 004 section.
