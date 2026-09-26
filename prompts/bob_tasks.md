# IBM Bob Task Prompts

The sixteen Bob IDE tasks behind TriageOps' incident-triage loop, in order. Run each
as a new Bob task with the repo open in Bob IDE. Session screenshots for every
task are committed under `bob_sessions/`.

Tasks 1-11 run the loop on three synthetic incidents in victim-service/.
Tasks 12-16 run the same loop on a real-world case: a genuine bug in humanize
4.3.0 (vendored under triage/realworld/), reported as upstream issue #57.

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

## Task 6 — Incident 002 root-cause trace (Agent mode)

Trace the exact faulty code path for the silent discount bug. Output:
`triage/reports/root_cause_002.md`.

```
In Agent mode, working in the victim-service/ directory:

Trace the exact code path that applies the bulk discount twice for incident_002
(error signature "BULK_DISCOUNT_ANOMALY", alert INC-2026-1043). This is a
silent logic bug: no exception, no traceback — find where the discount is
applied at both the item level and again at the subtotal level.

Write your findings to triage/reports/root_cause_002.md with these sections:
- Faulty code path (function call chain with file:line for each step)
- Why the discount is applied twice (which two code locations, and why the
  second application is wrong)
- Blast radius (which orders are affected)
- The minimal correct behaviour

Do not change any code in this task. Analysis only. Do NOT apply any fix:
the fix for this incident is proposed only, so the live test suite keeps
failing on it by design.
```

## Task 7 — Incident 002 fix proposal (Agent mode)

Propose a minimal, safe diff for the double-discount bug. Output:
`triage/fixes/fix_002.diff`. Do NOT apply it.

```
In Agent mode, using your root-cause analysis in
triage/reports/root_cause_002.md:

Propose the MINIMAL code change in victim-service/app.py that stops the bulk
discount being applied twice (remove the second, subtotal-level application),
without changing behaviour for orders that legitimately qualify once.
Requirements:
- The diff must be minimal: touch as few lines as possible.
- Write the unified diff to triage/fixes/fix_002.diff (do NOT apply it —
  this fix stays proposed-only so the dashboard keeps showing the honest
  7 passed / 2 failed suite).
- Below the diff, add a short safety rationale: what could regress, and which
  existing tests cover the changed lines.

Do not run the test suite in this task.
```

## Task 8 — Incident 002 incident report (Agent mode)

Write the final incident report. Output:
`triage/reports/incident_INC-2026-1043_report.md`.

```
In Agent mode:

Write the incident report for INC-2026-1043 to
triage/reports/incident_INC-2026-1043_report.md. Base it strictly on:
- incidents/incident_002.json (evidence; no traceback — silent bug)
- triage/reports/root_cause_002.md (root cause)
- triage/fixes/fix_002.diff (fix PROPOSED, not applied)

Sections: Summary, Timeline, Evidence, Root cause, Proposed fix (mark clearly
as NOT applied), Prevention suggestions. Keep it factual and under one page.
Do not invent data that is not in the sources above; mark anything uncertain
as uncertain.
```

## Task 9 — Incident 003 root-cause trace (Agent mode)

Trace the exact faulty code path for the sandbox payments bug. Output:
`triage/reports/root_cause_003.md`.

```
In Agent mode, working in the victim-service/ directory:

Trace the exact code path that makes PAYMENTS_MODE=sandbox decline every
order for incident_003 (error signature "PaymentError", alert INC-2026-1044).
The sandbox branch raises PaymentError instead of simulating the charge;
the correct behaviour is to return a test_-prefixed transaction id without
declining.

Write your findings to triage/reports/root_cause_003.md with these sections:
- Faulty code path (function call chain with file:line for each step)
- Why the sandbox branch raises instead of simulating
- Blast radius (which orders fail)
- The minimal correct behaviour

Do not change any code in this task. Analysis only. Do NOT apply any fix:
the fix for this incident is proposed only, so the live test suite keeps
failing on it by design.
```

## Task 10 — Incident 003 fix proposal (Agent mode)

Propose a minimal, safe diff for the sandbox payments bug. Output:
`triage/fixes/fix_003.diff`. Do NOT apply it.

```
In Agent mode, using your root-cause analysis in
triage/reports/root_cause_003.md:

Propose the MINIMAL code change in victim-service/app.py that makes the
sandbox branch return "test_sandbox_txn" instead of raising PaymentError,
without changing behaviour for other payment modes.
Requirements:
- The diff must be minimal: touch as few lines as possible.
- Write the unified diff to triage/fixes/fix_003.diff (do NOT apply it —
  this fix stays proposed-only so the dashboard keeps showing the honest
  7 passed / 2 failed suite).
- Below the diff, add a short safety rationale: what could regress, and which
  existing tests cover the changed lines.

Do not run the test suite in this task.
```

## Task 11 — Incident 003 incident report (Agent mode)

Write the final incident report. Output:
`triage/reports/incident_INC-2026-1044_report.md`.

```
In Agent mode:

Write the incident report for INC-2026-1044 to
triage/reports/incident_INC-2026-1044_report.md. Base it strictly on:
- incidents/incident_003.json (evidence)
- triage/reports/root_cause_003.md (root cause)
- triage/fixes/fix_003.diff (fix PROPOSED, not applied)

Sections: Summary, Timeline, Evidence, Root cause, Proposed fix (mark clearly
as NOT applied), Prevention suggestions. Keep it factual and under one page.
Do not invent data that is not in the sources above; mark anything uncertain
as uncertain.
```

## Notes

- One task per goal: separate tasks produce separate session summaries, which
  is the evidence of Bob usage.
- Paste the incident JSON and logs once in Task 1; later tasks reference the
  files instead of re-pasting them.
- Tasks 2–5 run in the same workspace so repository context stays warm.
- Tasks 12–16 run as their own workspace session, separate from Tasks 1–11.
- Ask mode for analysis (Task 1); Agent mode for multi-step work (Tasks 2–5).

## Task 12 — Real-world incident intake (Ask mode)

Turn the raw alert into a structured timeline and ranked hypotheses.
Output: a short analysis in chat (no files). This is REAL third-party code,
not a seeded bug — treat it like a production incident on a dependency.

```
You are helping triage a production incident. Here is the alert payload
(incidents/incident_004.json):

<paste the full contents of incidents/incident_004.json>

And the correlated service logs (incidents/incident_004_logs.txt):

<paste the full contents of incidents/incident_004_logs.txt>

Background: our billing-worker formats invoice amounts with the humanize
library. The exact vendored copy of humanize 4.3.0 we run is in
triage/realworld/humanize/ (verbatim from PyPI). A minimal reproducer is
triage/realworld/repro_metric_zero.py. The real upstream issue is
https://github.com/python-humanize/humanize/issues/57 — you may read the
issue for context, but do NOT look at the upstream fix yet.

Produce:
1. A minute-by-minute timeline of the incident from the logs.
2. Three ranked root-cause hypotheses, each with the file:line evidence that
   supports or weakens it.
3. The single most likely root cause, stated in one sentence.

Be specific: cite exact file paths, line numbers, and log line numbers.
Do not propose a fix yet.
```

## Task 13 — Real-world root-cause trace (Agent mode)

Trace the exact faulty code path in the vendored humanize 4.3.0 and save the
analysis. Output: `triage/reports/root_cause_004.md` (rendered by the dashboard
in Stage 4).

```
In Agent mode, working in the triage/realworld/ directory:

1. Run the reproducer: python triage/realworld/repro_metric_zero.py
   (from the repo root). Capture the full traceback.
2. Read the faulty function in triage/realworld/humanize/number.py and trace
   the exact code path from the metric() entry point to the crash.
3. Explain WHY the crash happens: what mathematical operation is undefined
   for this input, and why the function's logic reaches it.

Write triage/reports/root_cause_004.md with:
- The reproduced traceback (exact).
- The faulty code path, step by step, with file:line references.
- The root cause in one paragraph: which line, which operation, which input
  value triggers it.
- Why zero is a legitimate input here (invoice credit/refund line items).

Do not propose a fix yet. Do not look at the upstream fix.
```

## Task 14 — Real-world fix proposal (Agent mode)

Propose a minimal fix for the vendored humanize 4.3.0 WITHOUT looking at the
upstream fix. Output: `triage/fixes/fix_004.diff` (rendered by the dashboard
in Stage 5).

```
In Agent mode, working in the triage/realworld/ directory:

Based on triage/reports/root_cause_004.md, propose the smallest safe fix to
triage/realworld/humanize/number.py that:
1. Stops the crash for the triggering input.
2. Returns a sensible formatted result for it (follow the function's existing
   formatting conventions — check what the function returns for nearby inputs).
3. Changes no behavior for any other input.

Write the fix as a unified diff to triage/fixes/fix_004.diff, and in chat
explain: the one-line change, why this input value is special, and what the
function now returns for it. Then STOP — do not apply it yet, and do not
look at the upstream fix.
```

## Task 15 — Apply fix to vendored copy and verify (Agent mode)

Apply Bob's fix, verify with the reproducer, and run sanity checks.
Output: chat summary of before/after (no new files besides the modified
vendored copy).

```
In Agent mode, working in the triage/realworld/ directory:

1. Apply triage/fixes/fix_004.diff to triage/realworld/humanize/number.py.
2. Re-run the reproducer: python triage/realworld/repro_metric_zero.py
   (from the repo root). Confirm the crash is gone and record the output.
3. Sanity-check neighboring behavior (all must be unchanged and correct):
   - number.metric(1500, "V")      -> '1.50 kV'
   - number.metric(0, "V")         -> sensible zero formatting with unit
   - number.metric(220e-6, "F")    -> '220 μF'
   - number.metric(1e40)           -> scientific fallback '1.00 x 10⁴⁰'
   - number.metric(-5)             -> negative values still work
4. Report the before/after: the exact crash before, the exact output after,
   and the sanity-check results. If anything is off, iterate on the fix and
   update triage/fixes/fix_004.diff to match what was actually applied.
```

## Task 16 — Real-world incident report (Agent mode)

Write the final incident report, including a comparison of Bob's fix against
the actual upstream fix. Output:
`triage/reports/incident_INC-2026-1045_report.md` (rendered by the dashboard
in Stage 7).

```
In Agent mode:

Write the incident report for INC-2026-1045 to
triage/reports/incident_INC-2026-1045_report.md. Base it strictly on:
- incidents/incident_004.json (evidence)
- incidents/incident_004_logs.txt (evidence)
- triage/reports/root_cause_004.md (root cause)
- triage/fixes/fix_004.diff (Bob's fix, applied and verified in Task 15)

Sections: Summary, Timeline, Evidence, Root cause, Fix applied and verified,
Prevention suggestions. Keep it factual and under one page.

Then add a final section, "Bob vs upstream": the actual upstream fix for this
issue is public — humanize PR #47, released in 4.4.0, which changed the
faulty line to:

    exponent = int(math.floor(math.log10(abs(value)))) if value != 0 else 0

Compare Bob's independently proposed fix (Task 14, written BEFORE seeing
this) against the upstream fix: are they equivalent? Which inputs do they
differ on, if any? State the comparison honestly — if upstream's is better,
say so.

Do not invent data that is not in the sources above; mark anything uncertain
as uncertain.
```
