"""Local Streamlit interface for the AI Action Auditor MVP."""

import json

import streamlit as st

from auditor import (
    audit_session,
    collect_git_evidence,
    detect_risky_commands,
    normalize_chat_export,
)


st.set_page_config(page_title="AI Action Auditor", page_icon="🔎", layout="wide")
st.title("AI Action Auditor")
st.caption("Check whether file-change claims in an AI session have matching evidence.")

st.info(
    "This prototype reviews supported ChatGPT export JSON or the app's simple JSON format. It checks file-change claims "
    "and flags selected potentially destructive command patterns. A command mentioned in chat is not proof that it ran. "
    "Optional Git status evidence comes from a folder you select. It does not read repository file contents or contact an AI service."
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
    st.write("Upload a JSON session or extracted ChatGPT conversations.json. Choose one conversation to review; collected Git evidence will be added to it.")
    st.stop()

try:
    imported_data = normalize_chat_export(json.load(uploaded))
    if "conversations" in imported_data:
        conversations = imported_data["conversations"]
        counts: dict[str, int] = {}
        labels = []
        for conversation in conversations:
            title = conversation["title"]
            counts[title] = counts.get(title, 0) + 1
            labels.append(title)
        seen_labels: dict[str, int] = {}
        display_labels = []
        for label in labels:
            seen_labels[label] = seen_labels.get(label, 0) + 1
            display_labels.append(
                f"{label} ({seen_labels[label]})" if counts[label] > 1 else label
            )
        selected_index = st.selectbox(
            "Choose a conversation to review",
            options=range(len(conversations)),
            format_func=lambda index: display_labels[index],
        )
        selected_conversation = conversations[selected_index]
        session_data = {
            "messages": selected_conversation["messages"],
            "evidence": selected_conversation.get("evidence", []),
        }
        st.caption(
            f"Reviewing {len(session_data['messages'])} text messages from “{selected_conversation['title']}”."
        )
    else:
        session_data = imported_data
    supplied_evidence = session_data.get("evidence", [])
    if not isinstance(supplied_evidence, list):
        raise ValueError("'evidence' must be a JSON list.")
    session_data["evidence"] = supplied_evidence + git_evidence
    risky_commands = detect_risky_commands(session_data)
    findings = audit_session(session_data)
except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
    st.error(f"Could not read this session: {exc}")
    st.stop()

matched = sum(item["status"] == "Evidence match" for item in findings)
unverified = len(findings) - matched
left, middle, right = st.columns(3)
left.metric("Claims matched to evidence", matched)
middle.metric("Unverified claims", unverified)
right.metric("Potentially risky commands", len(risky_commands))

if risky_commands:
    st.subheader("Potentially risky commands mentioned")
    st.warning(
        "These command patterns appeared in assistant messages. This does not show that a command was run."
    )
    for item in risky_commands:
        with st.expander(f"{item['severity']} · {item['category']}", expanded=True):
            st.code(item["command_text"], language="powershell")
            st.write(item["explanation"])
            st.caption(f"Assistant message #{item['message_index'] + 1} · {item['status']}")

if findings:
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

if not findings and not risky_commands:
    st.warning("No supported file-change claims or flagged command patterns were found in assistant messages.")

report = json.dumps(
    {"file_change_claims": findings, "potentially_risky_commands": risky_commands},
    indent=2,
    ensure_ascii=False,
)
st.download_button(
    "Download review as JSON",
    data=report,
    file_name="ai_action_audit.json",
    mime="application/json",
)
