# IBM Bob Task Prompts

The five Bob IDE tasks behind TriageOps' incident-triage loop, in order. Run each
as a new Bob task with the repo open in Bob IDE. Session screenshots for every
task are committed under `bob_sessions/`.

## Task 1 — Incident intake (Ask mode)

Turn the raw alert into a structured timeline and ranked hypotheses. Output: a
short analysis in chat (no files).

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

## Task 2 — Root-cause trace (Agent mode)

Trace the exact faulty code path and save the analysis. Output:
`triage/reports/root_cause_001.md` (rendered by the dashboard in Stage 4).

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

## Task 3 — Fix proposal (Agent mode)

Propose a minimal, safe diff for the root cause. Output:
`triage/fixes/fix_001.diff`.

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

## Task 4 — Verify: apply fix, run tests (Agent mode)

Apply the fix and iterate until the incident's tests pass. Output: applied fix
in `victim-service/app.py`; test report in chat.

```
In Agent mode:

1. Apply the diff from triage/fixes/fix_001.diff to victim-service/app.py.
2. Run: python -m pytest victim-service/tests/ -v
3. If the two KeyError tests still fail, diagnose and iterate on the fix until
   they pass. Keep every change minimal and explain each one.
4. Report: the before/after test counts and the final list of changed lines.

Do not change test expectations to make them pass: fix the application code.
The remaining failures (bulk discount, sandbox mode) are separate known
issues tracked as incident_002 and incident_003 — do NOT fix them in this task.
```

## Task 5 — Incident report (Agent mode)

Generate the final incident report. Output:
`triage/reports/incident_INC-2026-1042_report.md`.

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

## Notes

- One task per goal: separate tasks produce separate session summaries, which
  is the evidence of Bob usage.
- Paste the incident JSON and logs once in Task 1; later tasks reference the
  files instead of re-pasting them.
- Tasks 2–5 run in the same workspace so repository context stays warm.
- Ask mode for analysis (Task 1); Agent mode for multi-step work (Tasks 2–5).
