"""Local Streamlit interface for the AI Action Auditor MVP."""

import json

import streamlit as st

from auditor import audit_session, collect_git_evidence


st.set_page_config(page_title="AI Action Auditor", page_icon="🔎", layout="wide")
st.title("AI Action Auditor")
st.caption("Check whether file-change claims in an AI session have matching evidence.")

st.info(
    "This first version checks file changes only. It compares assistant claims with "
    "records in the uploaded JSON and optional Git status evidence from a folder you select. "
    "Missing evidence means **unverified**, not false. It does not read file contents or contact an AI service."
)

st.subheader("Collect evidence from a local Git project")
st.caption(
    "Reads changed file names and Git status only. It does not read file contents or identify who made a change."
)
repo_path = st.text_input("Local project folder", placeholder=r"C:\path\to\your\git-project")
if st.button("Collect Git evidence"):
    if not repo_path.strip():
        st.error("Enter the folder path of a Git project first.")
    else:
        try:
            st.session_state["git_evidence"] = collect_git_evidence(repo_path.strip())
            st.success(f"Collected {len(st.session_state['git_evidence'])} changed-file record(s).")
        except ValueError as exc:
            st.error(str(exc))

git_evidence = st.session_state.get("git_evidence", [])
if git_evidence:
    with st.expander("Review collected Git evidence"):
        st.json(git_evidence)

EXAMPLE = {
    "messages": [
        {"role": "assistant", "content": "I updated `src/app.py` and created `README.md`."},
        {"role": "assistant", "content": "I also edited `src/missing.py`."},
    ],
    "evidence": [
        {
            "type": "file_change",
            "path": "src/app.py",
            "operation": "modified",
            "source": "example git diff record",
        },
        {
            "type": "file_change",
            "path": "README.md",
            "operation": "created",
            "source": "example git diff record",
        },
    ],
}

with st.expander("See the expected JSON format"):
    st.code(json.dumps(EXAMPLE, indent=2), language="json")

uploaded = st.file_uploader("Choose a session JSON file", type=["json"])
if uploaded is None:
    st.write("Upload a session JSON file to review its file-change claims. Collected Git evidence will be added to that session.")
    st.stop()

try:
    session_data = json.load(uploaded)
    if not isinstance(session_data, dict):
        raise ValueError("The file must contain a JSON object at its top level.")
    supplied_evidence = session_data.get("evidence", [])
    if not isinstance(supplied_evidence, list):
        raise ValueError("'evidence' must be a JSON list.")
    session_data["evidence"] = supplied_evidence + git_evidence
    findings = audit_session(session_data)
except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
    st.error(f"Could not read this session: {exc}")
    st.stop()

matched = sum(item["status"] == "Evidence match" for item in findings)
unverified = len(findings) - matched
left, right = st.columns(2)
left.metric("Claims matched to evidence", matched)
right.metric("Unverified claims", unverified)

if not findings:
    st.warning("No supported file-change claims were found in assistant messages.")
else:
    st.subheader("Review findings")
    for finding in findings:
        title = f"{finding['status']} · {finding['path']}"
        with st.expander(title, expanded=finding["status"] == "Unverified"):
            st.write(f"**Assistant claim:** {finding['claim']}")
            st.write(finding["explanation"])
            if finding["evidence"]:
                st.write("**Supplied evidence records:**")
                for record in finding["evidence"]:
                    st.json(record)

    report = json.dumps(findings, indent=2, ensure_ascii=False)
    st.download_button(
        "Download review as JSON",
        data=report,
        file_name="ai_action_audit.json",
        mime="application/json",
    )
