"""TriageOps demo dashboard.

Run with:  streamlit run triage/app.py   (from the repo root)

The dashboard walks through the incident-triage pipeline stage by stage.
Deterministic evidence gathering runs here; root-cause reasoning and the fix
are produced in IBM Bob IDE (see prompts/bob_tasks.md) and are picked up
from triage/reports/ and triage/fixes/ when present.

Two modes:
  * Bundled incident — one of the four bundled incidents shipped with the repo (three synthetic, one real-world).
  * Custom alert — paste any alert JSON (plus optional log lines) and the
    pipeline runs live on your input. If the alert matches a known incident
    signature, Bob's IDE-generated diagnosis for it is shown; otherwise the
    dashboard honestly reports the deterministic evidence only.
"""

import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INCIDENTS = ROOT / "incidents"
VICTIM = ROOT / "victim-service"
REPORTS = HERE / "reports"
FIXES = HERE / "fixes"

sys.path.insert(0, str(HERE))
from triage_core import correlate_logs, locate_code, parse_alert, run_tests  # noqa: E402

st.set_page_config(page_title="TriageOps", layout="wide")

_css = ROOT / ".streamlit" / "style.css"
if _css.exists():
    st.markdown(f"<style>{_css.read_text()}</style>", unsafe_allow_html=True)


INCIDENT_META = {
    "001": ("INC-2026-1042", "Crash: KeyError in apply_tax on POST /orders"),
    "002": ("INC-2026-1043", "Silent revenue leak: bulk discount applied twice"),
    "003": ("INC-2026-1044", "Config: PAYMENTS_MODE=sandbox declines all orders"),
    "004": ("INC-2026-1045", "Real-world: humanize.metric(0) crashes (upstream issue #57)"),
}

# Prefill for the custom-alert box: guaranteed-valid example JSON.
CUSTOM_TEMPLATE = json.dumps(
    json.loads((INCIDENTS / "incident_001.json").read_text(encoding="utf-8")),
    indent=2,
)


def match_known_incident(alert):
    """Match a custom alert to a bundled incident by error signature.

    Returns "001"/"002"/"003"/"004" or None. Only used to surface Bob's
    IDE-generated artifacts for a matching known incident — never to
    invent a diagnosis.
    """
    sig = (alert.get("error_signature") or "").lower()
    tb = (alert.get("traceback") or "").lower()
    if "keyerror" in sig or "apply_tax" in tb:
        return "001"
    if "discount" in sig:
        return "002"
    if "payment" in sig:
        return "003"
    if "math domain error" in tb:
        return "004"
    return None


def stage_header(n, title):
    st.markdown(
        f'<div class="stage-head"><span class="stage-num">{n}</span>'
        f'<span class="stage-title">{title}</span></div>',
        unsafe_allow_html=True,
    )


st.markdown(
    '<div class="hero"><div class="hero-kicker">IBM Bob 2.0 hackathon</div>'
    '<div class="hero-title">TriageOps</div>'
    '<div class="hero-sub">Incident triage assistant &mdash; deterministic evidence '
    'pipeline + IBM Bob reasoning in the IDE.</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- sidebar ---
st.sidebar.header("Incident")
mode = st.sidebar.radio(
    "Mode",
    ["Bundled incident", "Custom alert"],
    index=0,
    help="Bundled: one of the four bundled incidents. Custom: paste your "
    "own alert JSON and the pipeline runs live on it.",
)

custom_alert_text = ""
custom_logs_text = ""
if mode == "Bundled incident":
    choice = st.sidebar.selectbox(
        "Select a bundled incident",
        options=["001", "002", "003", "004"],
        format_func=lambda k: f"{k} — {INCIDENT_META[k][1]}",
    )
    alert_id, short_title = INCIDENT_META[choice]
    incident_json = INCIDENTS / f"incident_{choice}.json"
    incident_logs = INCIDENTS / f"incident_{choice}_logs.txt"
else:
    choice = None
    st.sidebar.markdown("Paste an alert JSON with the same fields as the bundled incidents.")
    custom_alert_text = st.sidebar.text_area(
        "Alert JSON", value=CUSTOM_TEMPLATE, height=220
    )
    custom_logs_text = st.sidebar.text_area(
        "Log lines (optional)",
        value="",
        height=120,
        help="Paste raw log lines; they get correlated against the alert's error signature.",
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Bob evidence:** every reasoning step for this demo is produced in "
    "IBM Bob IDE. Session screenshots live in `bob_sessions/`; the sixteen task "
    "prompts are in `prompts/bob_tasks.md`."
)

if "triage_run" not in st.session_state:
    st.session_state.triage_run = False

run = st.sidebar.button("Run triage", type="primary", use_container_width=True)
if run:
    st.session_state.triage_run = True

if st.session_state.triage_run:
    # ------------------------------------------------- resolve inputs ----
    matched = None
    logs_path = None
    if mode == "Bundled incident":
        evidence_key = choice
        try:
            alert = parse_alert(incident_json)
        except (ValueError, OSError) as exc:
            st.error(f"Could not parse the bundled incident: {exc}")
            st.stop()
        logs_path = incident_logs
    else:
        evidence_key = None
        try:
            payload = json.loads(custom_alert_text)
        except json.JSONDecodeError as exc:
            st.error(f"That JSON doesn't parse ({exc}). Fix it and press Run triage again.")
            st.stop()
        try:
            alert = parse_alert(payload)
        except ValueError as exc:
            st.error(f"Alert problem: {exc}")
            st.stop()
        alert_id = alert["alert_id"]
        if custom_logs_text.strip():
            logs_path = Path(tempfile.gettempdir()) / "triageops_custom_logs.txt"
            logs_path.write_text(custom_logs_text, encoding="utf-8")
        matched = match_known_incident(alert)
        evidence_key = matched

    # ------------------------------------------------- Stage 1: alert ----
    stage_header(1, "Alert parsed")
    c1, c2, c3 = st.columns(3)
    c1.metric("Alert", alert["alert_id"])
    c2.metric("Severity", alert["severity"])
    c3.metric("Endpoint", alert["endpoint"])
    st.code(
        f"service:  {alert['service']}\n"
        f"detected: {alert['timestamp']}\n"
        f"signature: {alert['error_signature']}\n"
        f"impact:   {alert['customer_impact']}",
        language="text",
    )

    # ------------------------------------------------- Stage 2: logs -----
    stage_header(2, "Log evidence")
    if logs_path is None:
        st.info(
            "No log lines supplied. Paste some into the sidebar's **Log lines** "
            "box and re-run to correlate them against the error signature."
        )
        matches = []
    else:
        matches = correlate_logs(logs_path, alert["error_signature"], alert=alert)
        st.write(f"**{len(matches)} matching log line(s)** around the incident window.")
        with st.expander("Show correlated log lines", expanded=True):
            for m in matches[:10]:
                st.code(f"L{m['line_no']:>4}  {m['line'][:200]}", language="text")

    # ------------------------------------------------- Stage 3: code ----
    stage_header(3, "Code locations (from traceback)")
    locations = locate_code(VICTIM, alert.get("traceback") or "")
    if locations:
        for loc in locations:
            target = loc["resolved"] or loc["frame_path"]
            icon = "FOUND" if loc["exists"] else "MISSING"
            st.write(f"`{target}:{loc['line']}` in `{loc['function']}()` — **{icon}**")
    else:
        st.info(
            "No traceback frames in this alert. "
            "Bob traces the faulty code path in the root-cause task instead."
        )

    # Which Bob IDE task produced each stage's artifact (keeps captions honest per incident)
    RC_TASKS = {"001": 2, "002": 6, "003": 9, "004": 13}
    FIX_TASKS = {"001": 3, "002": 7, "003": 10, "004": 14}

    # --------------------------------------- Stage 4: root cause (Bob) ---
    stage_header(4, "Root-cause analysis")
    if evidence_key:
        rc_path = REPORTS / f"root_cause_{evidence_key}.md"
        if rc_path.exists():
            st.markdown(rc_path.read_text(encoding="utf-8"))
            if mode == "Custom alert":
                st.caption(
                    f"Bob's Task {RC_TASKS.get(evidence_key, 2)} output for the matching known incident — "
                    "generated in IBM Bob IDE, not invented for this alert."
                )
            else:
                st.caption(f"Generated in IBM Bob IDE — Task {RC_TASKS.get(evidence_key, 2)}.")
        else:
            st.warning(
                "Not generated yet. In IBM Bob IDE, run **Task 2** from "
                "`prompts/bob_tasks.md` and save Bob's output to "
                f"`triage/reports/root_cause_{evidence_key}.md`, then re-run this dashboard."
            )
    else:
        st.info(
            "No Bob investigation matches this alert's signature yet. In the real "
            "workflow this is where you'd run Bob IDE Tasks 1–5 "
            "(`prompts/bob_tasks.md`) on the evidence above — the deterministic "
            "pipeline output is exactly what Bob would start from."
        )

    # ------------------------------------------ Stage 5: fix (Bob) ------
    stage_header(5, "Proposed fix")
    if evidence_key:
        fix_path = FIXES / f"fix_{evidence_key}.diff"
        if fix_path.exists():
            st.code(fix_path.read_text(encoding="utf-8"), language="diff")
            if mode == "Custom alert":
                st.caption(
                    f"Bob's Task {FIX_TASKS.get(evidence_key, 3)} proposal for the matching known incident — "
                    "generated in IBM Bob IDE."
                )
            else:
                st.caption(f"Proposed in IBM Bob IDE — Task {FIX_TASKS.get(evidence_key, 3)}.")
        else:
            st.warning(
                "Not generated yet. In IBM Bob IDE, run **Task 3** from "
                "`prompts/bob_tasks.md` and save the diff to "
                f"`triage/fixes/fix_{evidence_key}.diff`, then re-run this dashboard."
            )
    else:
        st.info(
            "No fix proposal exists for an unmatched alert. Run Bob IDE Task 3 "
            "on this evidence to produce one."
        )

    # -------------------------------------- Stage 6: verification -------
    stage_header(6, "Test verification")
    st.write(
        "Runs the victim-service pytest suite live. Before the fix, the "
        "bug-covering tests fail; after applying Bob's fix, they go green."
    )
    if st.button("Run test suite now", key="run_tests"):
        with st.spinner("Running pytest on victim-service..."):
            st.session_state["test_results"] = run_tests(VICTIM)
    results = st.session_state.get("test_results")
    if results:
        a, b, c = st.columns(3)
        a.metric("Passed", results["passed"])
        b.metric("Failed", results["failed"])
        c.metric("Errors", results["errors"])
        st.code(results["summary_line"], language="text")
        with st.expander("Full pytest output (tail)"):
            st.code(results["output_tail"], language="text")

    # -------------------------------------- Stage 7: incident report ----
    stage_header(7, "Incident report")
    if mode == "Bundled incident":
        report_path = REPORTS / f"incident_{alert_id}_report.md"
        if report_path.exists():
            md = report_path.read_text(encoding="utf-8")
        else:
            md = (
                "## Incident report\n\n"
                "Run the headless pipeline once to generate it:\n\n"
                "```bash\n"
                "cd triage && python -c \"from triage_core import run_pipeline; "
                f"run_pipeline('../incidents/incident_{choice}.json', "
                f"'../incidents/incident_{choice}_logs.txt', '../victim-service')\"\n"
                "```\n"
            )
        report_name = f"incident_{alert_id}_report.md"
    else:
        tr = st.session_state.get("test_results")
        verif = (
            f"- pytest: **{tr['passed']} passed, {tr['failed']} failed** "
            f"(`{tr['summary_line']}`)"
            if tr
            else "- pytest: not run yet (see Stage 6)"
        )
        evidence_lines = "".join(
            f"- `{loc['resolved'] or loc['frame_path']}:{loc['line']}` "
            f"in `{loc['function']}()`\n"
            for loc in locations
        ) or "- none (no traceback frames)\n"
        md = (
            "## Incident report (draft)\n\n"
            f"**Alert:** {alert['alert_id']} — {alert['service']} {alert['endpoint']}\n\n"
            f"**Severity:** {alert['severity']} | **Detected:** {alert['timestamp']}\n\n"
            f"**Signature:** `{alert['error_signature']}`\n\n"
            f"**Impact:** {alert['customer_impact']}\n\n"
            "### Evidence (deterministic pipeline)\n\n"
            f"- Log lines matched: **{len(matches)}**\n"
            f"{evidence_lines}\n"
            "### Verification\n\n"
            f"{verif}\n\n"
            "> Draft generated by the deterministic pipeline, not by Bob. "
            "Root-cause reasoning and the fix proposal for this alert have not "
            "been produced in Bob IDE yet.\n"
        )
        report_name = f"incident_{alert['alert_id']}_report_draft.md"
    st.markdown(md)
    st.download_button(
        "Download incident report",
        data=md,
        file_name=report_name,
        mime="text/markdown",
    )

# ------------------------------------------------------- Bob evidence ------
with st.expander("Bob evidence — how IBM Bob was used"):
    st.markdown(
        """
IBM Bob (IDE, hackathon-provisioned account) is the reasoning engine of this
workflow. The sixteen Bob tasks in `prompts/bob_tasks.md`:

1. **Incident intake** (Ask mode) — structured timeline + ranked hypotheses.
2. **Root-cause trace** (Agent mode) — exact faulty code path, saved to `triage/reports/`.
3. **Fix proposal** (Agent mode) — minimal diff + safety rationale, saved to `triage/fixes/`.
4. **Verify** (Agent mode) — apply fix, run pytest, iterate until the incident's tests pass.
5. **Incident report** (Agent mode) — final markdown report.

Tasks 1-5 cover incident 001 end to end; tasks 6-11 repeat the
trace-propose-report loop for incidents 002 and 003, with fixes proposed
only (never applied). Tasks 12-16 take the full loop to a real-world case:
humanize issue #57 (vendored 4.3.0) — the fix is applied to the vendored copy,
verified with the reproducer, then compared against the actual upstream fix.

Per-task session summary screenshots are stored in `bob_sessions/` and are a
required submission deliverable.
"""
    )
    st.page_link("https://bob.ibm.com/docs", label="Bob IDE docs (external)")

st.markdown("---")
st.caption("TriageOps — built for the IBM Bob 2.0 hackathon. Incidents 001–003 are synthetic; 004 is a real-world case study (humanize #57).")
