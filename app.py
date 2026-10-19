"""Local Streamlit interface for the AI Action Auditor MVP."""

import json

import streamlit as st

from auditor import audit_session


st.set_page_config(page_title="AI Action Auditor", page_icon="🔎", layout="wide")
st.title("AI Action Auditor")
st.caption("Check whether file-change claims in an AI session have matching evidence.")

st.info(
    "This first version checks file changes only. It compares assistant claims with "
    "file-change records included in the uploaded JSON. Missing evidence means "
    "**unverified**, not false. It does not inspect your computer or contact an AI service."
)

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
    st.write("Upload a JSON file to review its file-change claims.")
    st.stop()

try:
    session_data = json.load(uploaded)
    if not isinstance(session_data, dict):
        raise ValueError("The file must contain a JSON object at its top level.")
    findings = audit_session(session_data)
except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
    st.error(f"Could not read this session: {exc}")
    st.stop()

confirmed = sum(item["status"].startswith("Confirmed") for item in findings)
unverified = len(findings) - confirmed
left, right = st.columns(2)
left.metric("Claims with matching records", confirmed)
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
