"""TriageOps demo dashboard.

Run with:  streamlit run triage/app.py   (from the repo root)

The dashboard walks through the incident-triage pipeline stage by stage.
Deterministic evidence gathering runs here; root-cause reasoning and the fix
are produced in IBM Bob IDE (see prompts/bob_tasks.md) and are picked up
from triage/reports/ and triage/fixes/ when present.
"""

import sys
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
}


def stage_header(n, title):
    st.markdown(f"## Stage {n}: {title}")


st.title("TriageOps — incident triage assistant")
st.caption("Deterministic evidence pipeline + IBM Bob reasoning in the IDE.")

# ---------------------------------------------------------------- sidebar ---
st.sidebar.header("Incident")
choice = st.sidebar.selectbox(
    "Select a bundled incident",
    options=["001", "002", "003"],
    format_func=lambda k: f"{k} — {INCIDENT_META[k][1]}",
)
alert_id, short_title = INCIDENT_META[choice]
incident_json = INCIDENTS / f"incident_{choice}.json"
incident_logs = INCIDENTS / f"incident_{choice}_logs.txt"

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Bob evidence:** every reasoning step for this demo is produced in "
    "IBM Bob IDE. Session screenshots live in `bob_sessions/`; the five task "
    "prompts are in `prompts/bob_tasks.md`."
)

run = st.sidebar.button("Run triage", type="primary", use_container_width=True)

if run:
    alert = parse_alert(incident_json)

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
    matches = correlate_logs(incident_logs, alert["error_signature"])
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
            "No traceback frames in this alert (silent logic bug). "
            "Bob traces the faulty code path in Task 2 instead."
        )

    # --------------------------------------- Stage 4: root cause (Bob) ---
    stage_header(4, "Root-cause analysis")
    rc_path = REPORTS / f"root_cause_{choice}.md"
    if rc_path.exists():
        st.markdown(rc_path.read_text(encoding="utf-8"))
        st.caption("Generated in IBM Bob IDE — Task 2.")
    else:
        st.warning(
            "Not generated yet. In IBM Bob IDE, run **Task 2** from "
            "`prompts/bob_tasks.md` and save Bob's output to "
            f"`triage/reports/root_cause_{choice}.md`, then re-run this dashboard."
        )

    # ------------------------------------------ Stage 5: fix (Bob) ------
    stage_header(5, "Proposed fix")
    fix_path = FIXES / f"fix_{choice}.diff"
    if fix_path.exists():
        st.code(fix_path.read_text(encoding="utf-8"), language="diff")
        st.caption("Proposed in IBM Bob IDE — Task 3.")
    else:
        st.warning(
            "Not generated yet. In IBM Bob IDE, run **Task 3** from "
            "`prompts/bob_tasks.md` and save the diff to "
            f"`triage/fixes/fix_{choice}.diff`, then re-run this dashboard."
        )

    # -------------------------------------- Stage 6: verification -------
    stage_header(6, "Test verification")
    st.write(
        "Runs the victim-service pytest suite live. Before the fix, the "
        "bug-covering tests fail; after applying Bob's fix, they go green."
    )
    if st.button("Run test suite now", key="run_tests"):
        with st.spinner("Running pytest on victim-service..."):
            results = run_tests(VICTIM)
        a, b, c = st.columns(3)
        a.metric("Passed", results["passed"])
        b.metric("Failed", results["failed"])
        c.metric("Errors", results["errors"])
        st.code(results["summary_line"], language="text")
        with st.expander("Full pytest output (tail)"):
            st.code(results["output_tail"], language="text")

    # -------------------------------------- Stage 7: incident report ----
    stage_header(7, "Incident report")
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
    st.markdown(md)
    st.download_button(
        "Download incident report",
        data=md,
        file_name=f"incident_{alert_id}_report.md",
        mime="text/markdown",
    )

# ------------------------------------------------------- Bob evidence ------
with st.expander("Bob evidence — how IBM Bob was used"):
    st.markdown(
        """
IBM Bob (IDE, hackathon-provisioned account) is the reasoning engine of this
workflow. The five Bob tasks in `prompts/bob_tasks.md`:

1. **Incident intake** (Ask mode) — structured timeline + ranked hypotheses.
2. **Root-cause trace** (Agent mode) — exact faulty code path, saved to `triage/reports/`.
3. **Fix proposal** (Agent mode) — minimal diff + safety rationale, saved to `triage/fixes/`.
4. **Verify** (Agent mode) — apply fix, run pytest, iterate to green.
5. **Incident report** (Agent mode) — final markdown report.

Per-task session summary screenshots are stored in `bob_sessions/` and are a
required submission deliverable.
"""
    )
    st.page_link("https://bob.ibm.com/docs", label="Bob IDE docs (external)")

st.markdown("---")
st.caption("TriageOps — built for the IBM Bob 2.0 hackathon. All incident data is synthetic.")
