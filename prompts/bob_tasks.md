# IBM Bob IDE task prompts

Run these five tasks in Bob IDE, in order, on the **hackathon-provisioned
account** (not your personal account). Copy each prompt into a new Bob task.
Bobcoins are limited to **40 per person** for the whole hackathon and are not
topped up, so follow the discipline notes at the bottom.

After each task, screenshot the task session consumption summary and save it
to `bob_sessions/` (see `bob_sessions/README.md`).

---

## Task 1 — Incident intake (Ask mode)

Goal: turn the raw alert into a structured timeline and ranked hypotheses.

Expected output: a short analysis in chat (no files).
Screenshot: `triageops_task01_incident_intake_summary.png`

```
You are helping triage a production incident. Here is the alert payload
(incidents/incident_001.json):

<paste the full contents of incidents/incident_001.json>

And the correlated service logs (incidents/incident_001_logs.txt):

<paste the full contents of incidents/incident_001_logs.txt>

The service code lives in victim-service/app.py (FastAPI, ~150 lines).

Produce:
1. A minute-by-minute timeline of the incident from the logs.
2. Three ranked root-cause hypotheses, each with the file:line evidence that
   supports or weakens it.
3. The single most likely root cause, stated in one sentence.

Be specific: cite exact file paths, line numbers, and log line numbers.
Do not propose a fix yet.
```

---

## Task 2 — Root-cause trace (Agent mode)

Goal: trace the exact faulty code path and save the analysis.

Expected output file: `triage/reports/root_cause_001.md` (the Streamlit
dashboard renders this file in Stage 4).
Screenshot: `triageops_task02_root_cause_trace_summary.png`

```
In Agent mode, working in the victim-service/ directory:

Trace the exact code path that produces the KeyError from incident_001
(error signature "KeyError", alert INC-2026-1042). Start at the POST /orders
endpoint (create_order), follow every function call until the exception, and
confirm each step against the traceback frames in
incidents/incident_001.json.

Write your findings to triage/reports/root_cause_001.md with these sections:
- Faulty code path (function call chain with file:line for each step)
- Why the exception happens (what value `region` has and why)
- Blast radius (which requests trigger it, which do not)
- The minimal correct behaviour

Do not change any code in this task. Analysis only.
```

---

## Task 3 — Fix proposal (Agent mode)

Goal: a minimal, safe diff for the root cause.

Expected output file: `triage/fixes/fix_001.diff`
Screenshot: `triageops_task03_fix_proposal_summary.png`

```
In Agent mode, using your root-cause analysis in
triage/reports/root_cause_001.md:

Propose the MINIMAL code change in victim-service/app.py that fixes the
KeyError for missing/unknown regions, without changing behaviour for valid
regions. Requirements:
- The diff must be minimal: touch as few lines as possible.
- Write the unified diff to triage/fixes/fix_001.diff (do not apply it yet).
- Below the diff, add a short safety rationale: what could regress, and which
  existing tests cover the changed lines.

Do not run the test suite in this task; verification is the next task.
```

---

## Task 4 — Verify: apply fix, run tests to green (Agent mode)

Goal: apply the fix and iterate until the suite is green.

Expected output: applied fix in `victim-service/app.py`; test report in chat.
Screenshot: `triageops_task04_verify_tests_summary.png`

```
In Agent mode:

1. Apply the diff from triage/fixes/fix_001.diff to victim-service/app.py.
2. Run: python -m pytest victim-service/tests/ -v
3. If any test still fails, diagnose and iterate on the fix until the full
   suite passes. Keep every change minimal and explain each one.
4. Report: the before/after test counts (how many failed before the fix,
   how many pass now) and the final list of changed lines.

Do not change test expectations to make them pass: fix the application code.
```

---

## Task 5 — Incident report (Agent mode)

Goal: the final incident report markdown.

Expected output file: `triage/reports/incident_INC-2026-1042_report.md`
Screenshot: `triageops_task05_incident_report_summary.png`

```
In Agent mode:

Generate the final incident report for INC-2026-1042 and write it to
triage/reports/incident_INC-2026-1042_report.md. Base it strictly on:
- incidents/incident_001.json and incidents/incident_001_logs.txt (evidence)
- triage/reports/root_cause_001.md (root cause)
- triage/fixes/fix_001.diff (fix applied)
- the pytest results from Task 4 (verification)

Sections: Summary, Timeline, Evidence, Root cause, Fix applied,
Verification (with exact test counts), Prevention suggestions.
Keep it factual and under one page. Do not invent data that is not in the
sources above; mark anything uncertain as uncertain.
```

---

## Bobcoins discipline (read before starting)

- **One task per goal.** Do not bundle intake, tracing, fixing, and reporting
  into a single mega-task; separate tasks give you separate, clean session
  summaries for `bob_sessions/`, which the judges require.
- **Paste, don't re-derive.** Paste the incident JSON and logs into Task 1
  once; in later tasks, point Bob at the files instead of re-pasting them.
- **Reuse context.** Run Tasks 2-5 in the same workspace so Bob keeps the
  repository context warm instead of re-reading the repo each time.
- **Agent mode for multi-step work** (Tasks 2-5), **Ask mode** for analysis
  (Task 1). Agent mode with auto-approve for file writes only, scoped to the
  repo directory.
- If Bobcoins run low, Tasks 1-3 are the priority: they produce the analysis,
  the diff, and the evidence the demo and the report depend on.
