# Submission statements — FINAL

> Each statement is 500 words or less, per the submission requirements.
> Paste into the lablab.ai submission form as-is, or lightly adapt to your voice.

---

## 1. Problem & Solution Statement (326 words)

Incident triage dominates on-call toil. When an alert fires, an engineer must
read the alert, grep through logs, reconstruct a timeline, trace the fault
through unfamiliar code, propose a fix, and then prove the fix works — usually
against the clock, at night, under pressure. For three of the most common bug
classes — crashes with stack traces, silent logic errors that never raise, and
configuration mistakes that only surface after a deploy — that manual loop
takes tens of minutes even for experienced engineers, and far longer for
anyone new to the codebase. Every minute of it extends customer impact.

TriageOps compresses that loop into a guided, evidence-backed workflow. Given
an incident alert and the service logs, a deterministic Python pipeline parses
the alert, correlates the matching log lines with surrounding context, resolves
traceback frames to exact file-and-line locations in the repository, and runs
the project's test suite to establish a failing baseline. That evidence feeds a
Streamlit dashboard that walks the responder through seven stages: alert,
evidence, code locations, root-cause analysis, proposed fix, live test
verification, and a downloadable incident report.

The reasoning steps — the root-cause trace, the minimal fix proposal, and the
fix-verify iteration — run in IBM Bob IDE in Agent mode, with the session
summaries committed as evidence. Bob works on the real repository, cites real
file-and-line references, and iterates against the real pytest suite until it
goes green.

On our three seeded incidents, the workflow moves from alert to a verified fix
in minutes instead of tens of minutes, and the incident report it produces is
the same artefact an on-call engineer would otherwise write by hand at 3am.
TriageOps does not replace the responder's judgment; it removes the mechanical
triage work so judgment can be applied faster. The next step is pointing the
same pipeline at real services, where the only change is the incident feed.

---

## 2. IBM Bob Usage Statement (356 words)

IBM Bob IDE is the reasoning engine of TriageOps; the deterministic pipeline
only gathers evidence and never invents analysis. All five Bob tasks ran on the
hackathon-provisioned Bob account, and every task's session consumption summary
is committed under `bob_sessions/`.

Task 1 used Ask mode for incident intake: we pasted the alert JSON and the
service logs and asked Bob for a minute-by-minute timeline plus three ranked
root-cause hypotheses, each backed by file-and-line evidence. This replaced
the manual first stretch of triage — reading logs and forming hypotheses.

Tasks 2 through 5 used Agent mode against the real repository. In Task 2, Bob
traced the exact faulty call chain from the POST /orders endpoint to the
raising line, confirming each step against the traceback frames, and wrote the
analysis to `triage/reports/root_cause_001.md` — exercising document
understanding across the alert, the logs, and the codebase. In Task 3, Bob
proposed a minimal unified diff with a safety rationale, saved to
`triage/fixes/fix_001.diff` without applying it. In Task 4, Bob applied the
diff, ran the pytest suite, and iterated on the fix until all tests passed,
reporting exact before/after counts: four failing tests on the seeded code,
the full suite green after the fix.

Task 5 had Bob compose the final incident report from the evidence, the
root-cause analysis, the diff, and the verified test results — a one-page
artefact with timeline, evidence, root cause, fix, and verification.

We managed the 40-Bobcoin budget with strict discipline: one task per goal so
each session summary is clean submission evidence, pasting the incident data
once and referencing files afterwards, and reusing the same workspace so
repository context stayed warm. Agent mode handled the multi-step
trace-fix-verify loop; Ask mode handled the analytical intake. The subagent
pattern maps directly onto our staged pipeline: each stage has one job, and
Bob's reasoning stages plug into the dashboard where the deterministic stages
leave off. Without Bob, TriageOps is an evidence viewer; with Bob, it is a
working triage assistant.
