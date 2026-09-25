"""TriageOps deterministic triage pipeline.

This module does evidence gathering only: it parses alerts, correlates log
lines, locates traceback frames in the repository, runs the pytest suite, and
renders a markdown incident report.

It deliberately does NOT invent root-cause analysis or fixes. The reasoning
steps happen in IBM Bob IDE (see prompts/bob_tasks.md); their outputs are
saved under triage/reports/ and triage/fixes/ and are picked up from there.

Importing this module has no side effects.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_ALERT_FIELDS = (
    "alert_id",
    "service",
    "endpoint",
    "severity",
    "timestamp",
    "error_signature",
)

TRACEBACK_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line (\d+), in (\S+)', re.MULTILINE)
PYTEST_SUMMARY_RE = re.compile(
    r"(?:(\d+) failed, )?(\d+) passed(?:, (\d+) failed)?(?:, (\d+) errors?)?"
)


def parse_alert(incident_json):
    """Parse an incident alert payload.

    Accepts a path (str/Path) to a JSON file or an already-loaded dict.
    Returns a dict with the required fields plus optional ones
    (traceback, customer_impact).
    """
    if isinstance(incident_json, (str, Path)):
        with open(incident_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = dict(incident_json)

    missing = [f for f in REQUIRED_ALERT_FIELDS if f not in data]
    if missing:
        raise ValueError("incident is missing required fields: %s" % ", ".join(missing))

    return {
        "alert_id": data["alert_id"],
        "service": data["service"],
        "endpoint": data["endpoint"],
        "severity": data["severity"],
        "timestamp": data["timestamp"],
        "error_signature": data["error_signature"],
        "traceback": data.get("traceback"),
        "customer_impact": data.get("customer_impact", "not specified"),
    }


def correlate_logs(log_path, signature, context=2):
    """Find log lines matching an error signature, with surrounding context.

    Returns a list of dicts: {line_no, line, context_before, context_after}.
    A line matches if it contains the signature, or if it belongs to a
    traceback block that follows a matching line.
    """
    path = Path(log_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    matches = []
    in_traceback = False

    for i, line in enumerate(lines):
        hit = signature in line
        if "Traceback (most recent call last)" in line:
            in_traceback = True
        if hit or (in_traceback and line.strip() != ""):
            matches.append(
                {
                    "line_no": i + 1,
                    "line": line,
                    "context_before": lines[max(0, i - context): i],
                    "context_after": lines[i + 1: i + 1 + context],
                }
            )
        if in_traceback and line.strip() == "":
            in_traceback = False

    return matches


def locate_code(repo_path, traceback_text):
    """Parse Python traceback frames into file:line references.

    Each frame's filename is resolved against repo_path by basename search,
    so tracebacks captured from a deployed path still resolve to the repo.
    Returns a list of dicts: {frame_path, line, function, resolved, exists}.
    """
    repo = Path(repo_path)
    locations = []
    for frame_path, line_no, func in TRACEBACK_FRAME_RE.findall(traceback_text or ""):
        line_no = int(line_no)
        resolved = None
        candidates = list(repo.rglob(Path(frame_path).name))
        if candidates:
            resolved = str(candidates[0])
        locations.append(
            {
                "frame_path": frame_path,
                "line": line_no,
                "function": func,
                "resolved": resolved,
                "exists": resolved is not None,
            }
        )
    return locations


def run_tests(repo_path, timeout=180):
    """Run the repo's pytest suite and return a parsed summary.

    Returns {passed, failed, errors, returncode, summary_line, output_tail}.
    Counts come from pytest's own summary line; nothing is invented.
    """
    repo = Path(repo_path)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    tail_lines = output.splitlines()[-15:]

    passed = failed = errors = 0
    summary_line = "no summary line found"
    for line in reversed(output.splitlines()):
        m = PYTEST_SUMMARY_RE.search(line)
        if m and ("passed" in line or "failed" in line or "error" in line):
            summary_line = line.strip()
            failed = int(m.group(1) or m.group(3) or 0)
            passed = int(m.group(2) or 0)
            errors = int(m.group(4) or 0)
            break

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "returncode": proc.returncode,
        "summary_line": summary_line,
        "output_tail": "\n".join(tail_lines),
    }


def render_report(report_data, reports_dir):
    """Render the incident report markdown and write it to reports_dir.

    Returns (path, markdown). The root-cause and fix sections are filled in
    only if Bob-generated files are supplied in report_data; otherwise the
    report honestly marks them as pending Bob IDE tasks.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    alert = report_data["alert"]
    matches = report_data.get("log_matches", [])
    locations = report_data.get("code_locations", [])
    tests = report_data.get("test_results", {})
    root_cause_md = report_data.get("root_cause_md")
    fix_diff = report_data.get("fix_diff")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    evidence_lines = []
    for m in matches[:12]:
        evidence_lines.append("  L%-4d %s" % (m["line_no"], m["line"].strip()[:160]))
    evidence = "\n".join(evidence_lines) if evidence_lines else "  (no matching log lines)"

    location_lines = []
    for loc in locations:
        status = "FOUND" if loc["exists"] else "NOT IN REPO"
        location_lines.append(
            "  %s:%d in %s  [%s]" % (loc["resolved"] or loc["frame_path"], loc["line"], loc["function"], status)
        )
    locations_txt = "\n".join(location_lines) if location_lines else "  (no traceback frames supplied)"

    root_cause_section = (
        root_cause_md
        if root_cause_md
        else "_Pending — produced in IBM Bob IDE, Task 2 (see prompts/bob_tasks.md)._"
    )
    fix_section = (
        "```diff\n%s\n```" % fix_diff
        if fix_diff
        else "_Pending — proposed in IBM Bob IDE, Task 3 (see prompts/bob_tasks.md)._"
    )

    md = f"""# Incident Report: {alert['alert_id']}

- **Service:** {alert['service']}
- **Endpoint:** {alert['endpoint']}
- **Severity:** {alert['severity']}
- **Detected:** {alert['timestamp']}
- **Error signature:** `{alert['error_signature']}`
- **Customer impact:** {alert['customer_impact']}
- **Report generated:** {generated_at} (TriageOps deterministic pipeline)

## Timeline

1. Alert fired for `{alert['error_signature']}` on `{alert['endpoint']}`.
2. Correlated {len(matches)} matching log line(s) around the incident window.
3. Traceback frames resolved to {sum(1 for l in locations if l['exists'])} file(s) in the repo.
4. Test suite executed: {tests.get('passed', '?')} passed, {tests.get('failed', '?')} failed.

## Evidence

### Alert
```
{json.dumps({k: alert[k] for k in ('alert_id', 'service', 'endpoint', 'severity', 'error_signature')}, indent=2)}
```

### Correlated log lines
```
{evidence}
```

### Code locations (from traceback)
```
{locations_txt}
```

## Suspected root cause

{root_cause_section}

## Fix applied

{fix_section}

## Verification

- Pytest summary: `{tests.get('summary_line', 'not run')}`
- Result: {tests.get('passed', '?')} passed / {tests.get('failed', '?')} failed / {tests.get('errors', '?')} errors (returncode {tests.get('returncode', '?')})

## Prevention suggestions

- Add a regression test that pins the fixed behaviour (the bug-covering tests in `victim-service/tests/` already do this).
- Add alerting on the error signature so the next occurrence pages with this report attached.
- Review neighbouring code paths for the same defect pattern.

---
_Generated by TriageOps. Root-cause reasoning and the fix proposal are produced by IBM Bob in the IDE; this pipeline gathers the evidence deterministically and never invents analysis._
"""

    filename = "incident_%s_report.md" % re.sub(r"[^A-Za-z0-9_-]+", "_", alert["alert_id"])
    path = reports_dir / filename
    path.write_text(md, encoding="utf-8")
    return str(path), md


def run_pipeline(incident_json, logs_txt, repo_path, reports_dir=None):
    """Run the full deterministic triage pipeline for one incident.

    Chains parse_alert -> correlate_logs -> locate_code -> run_tests ->
    render_report and returns a structured result dict. Root-cause analysis
    and the fix are intentionally left to IBM Bob (Tasks 2 and 3); this
    function reports them as pending rather than inventing them.
    """
    if reports_dir is None:
        reports_dir = Path(__file__).resolve().parent / "reports"

    alert = parse_alert(incident_json)
    repo_abs = str(Path(repo_path).resolve())
    log_matches = correlate_logs(logs_txt, alert["error_signature"])
    code_locations = locate_code(repo_abs, alert.get("traceback") or "")
    test_results = run_tests(repo_abs)

    report_data = {
        "alert": alert,
        "log_matches": log_matches,
        "code_locations": code_locations,
        "test_results": test_results,
        "root_cause_md": None,   # produced by IBM Bob, Task 2
        "fix_diff": None,        # produced by IBM Bob, Task 3
    }
    report_path, report_md = render_report(report_data, reports_dir)

    return {
        "alert": alert,
        "log_matches": log_matches,
        "code_locations": code_locations,
        "test_results": test_results,
        "root_cause": None,
        "root_cause_note": (
            "Root-cause analysis is produced in IBM Bob IDE (Task 2, prompts/bob_tasks.md). "
            "Save Bob's output to triage/reports/root_cause_<id>.md to attach it here."
        ),
        "fix": None,
        "fix_note": (
            "The fix diff is proposed in IBM Bob IDE (Task 3, prompts/bob_tasks.md). "
            "Save it to triage/fixes/fix_<id>.diff to attach it here."
        ),
        "report_path": report_path,
        "report_markdown": report_md,
    }
