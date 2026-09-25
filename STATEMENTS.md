# TriageOps — Submission Statements

## Problem & Solution

At 2 a.m., a PagerDuty alert fires: POST /orders is returning 500s. The on-call engineer opens the alert, greps through thousands of log lines, reconstructs a timeline by hand, traces the fault through unfamiliar code, guesses at a fix, and then has to prove the fix works — a 20-to-40-minute loop of mechanical, error-prone work. Three of the most common bug classes make it worse: crashes with stack traces, silent logic bugs that produce wrong numbers without crashing, and config mistakes visible only after deploy. Multiply that loop by every incident, every team, every week.

TriageOps compresses that loop into a guided workflow measured in minutes. Feed it an incident alert (JSON) and the service's logs. A deterministic Python pipeline — deliberately not an LLM, so it never invents evidence — parses the alert, correlates the matching log lines with surrounding context, resolves every traceback frame to an exact file:line in the repository, and runs the project's pytest suite to establish the failing baseline. Then IBM Bob takes over inside the IDE as the reasoning engine: it triages the alert into a timeline with ranked hypotheses, traces the exact faulty code path, proposes a minimal fix as a reviewable diff, applies it, and iterates against the real test suite until the incident's tests go green. The pipeline then renders a one-page incident report — timeline, evidence, root cause, fix, verification — the artifact an on-call engineer would otherwise write by hand.

We proved it on a seeded FastAPI service carrying three real bug classes. On incident INC-2026-1042, a KeyError crash on POST /orders, Bob traced the fault to a single dictionary lookup at victim-service/app.py:60, proposed a one-line fix (TAX_RATES.get(region, 0.0)), applied it, and moved the suite from 5 passed / 4 failed to 7 passed / 2 failed — the two remaining failures belonging to two other seeded incidents, deliberately kept separate. The business value is straightforward: faster mean time to recovery, fixes verified by tests instead of hope, and a paper trail (every Bob session screenshotted and committed) that turns tribal debugging knowledge into a repeatable process. Stated honestly, the "minutes, not tens of minutes" claim is measured on our seeded incidents, not production outages — but the workflow is exactly the one production teams run, minus the toil.

## IBM Bob Usage

IBM Bob is the reasoning core of TriageOps — not a code-completion accessory, but the agent that performs the incident-triage loop no deterministic pipeline can: hypothesize, trace, fix, verify, report. All work ran on the hackathon-provisioned account (team ibm-hackathon-lablab), and every task's session consumption summary is screenshotted under bob_sessions/.

Task 1 (Ask mode) — incident intake. We pasted the alert payload and correlated logs for INC-2026-1042; Bob produced a minute-by-minute timeline, three ranked root-cause hypotheses with file:line evidence for each, and a one-sentence most-likely cause. This replaced the manual "read the alert, grep the logs" phase.

Task 2 (Agent mode) — root-cause trace. Working in victim-service/, Bob followed the request path from the POST /orders endpoint through every function call to the exception, confirming each step against the traceback frames, and wrote triage/reports/root_cause_001.md: the faulty call chain, why region arrived as None, the blast radius (which requests crash, which don't), and the minimal correct behavior. Analysis only — no code changed.

Task 3 (Agent mode) — fix proposal. From the root-cause report, Bob proposed the minimal change in victim-service/app.py, wrote the unified diff to triage/fixes/fix_001.diff without applying it, and added a safety rationale: what could regress and which existing tests cover the changed lines.

Task 4 (Agent mode) — apply and verify. Bob applied the diff, ran python -m pytest victim-service/tests/ -v, and reported exact before/after counts: 5 passed / 4 failed → 7 passed / 2 failed, with the two remaining failures correctly attributed to separate seeded incidents (002/003) left untouched per instructions. No test expectations were modified.

Task 5 (Agent mode) — incident report. Bob synthesized the alert, logs, root-cause report, diff, and test results into a one-page factual report at triage/reports/incident_INC-2026-1042_report.md, marking uncertain items as uncertain rather than inventing data.

Total Bobcoin spend stayed well under the 40-coin allocation. The division of labor is deliberate: the deterministic pipeline gathers evidence it cannot hallucinate; Bob does the reasoning, and every claim it makes is anchored to a file, a line, or a test result.
