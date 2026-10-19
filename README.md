# AI Action Auditor

A small, local-first prototype that checks file-change claims in an AI session against file-change records supplied with that session or collected from a selected local Git project.

## What it does

- Finds supported assistant statements such as “updated `src/app.py`”.
- Matches the claimed path and action to supplied evidence records.
- Marks a claim **Unverified** when matching evidence is missing or the recorded action differs.
- Shows the matching records and lets you download the findings as JSON.
- Collects changed file names and statuses from a local Git working tree, including untracked files.
- Flags selected potentially destructive command patterns in assistant messages.

An **Evidence match** means the path and action match a record; it does not prove that the AI made the change. Git status does not identify who made a change. An unverified claim is not proof that the AI did not perform the action.

Risk warnings currently cover a small set of patterns, including recursive deletion, hard Git reset, forced Git cleanup or push, SQL table/database deletion, and Terraform destroy. A warning means the text appeared in an assistant message; it does not mean the command was run.

## Run locally

From this project directory, in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local address printed by Streamlit, then upload `sample_session.json` to try the example.

To include current Git evidence, enter the path to a local Git project folder in the app and choose **Collect Git evidence** before uploading the session JSON. Git must be installed and available on `PATH`. The collector reads Git status and changed file names; it does not read file contents.

## Input format

The prototype expects a JSON object with `messages` and `evidence` lists. The `evidence` list can be empty if you are only reviewing command warnings:

```json
{
  "messages": [
    {"role": "assistant", "content": "I updated `src/app.py`."}
  ],
  "evidence": [
    {
      "type": "file_change",
      "path": "src/app.py",
      "operation": "modified",
      "source": "example git diff record"
    }
  ]
}
```

Supported file actions include created, added, modified, updated, edited, changed, deleted, and removed. Other kinds of AI actions and unsupported message formats are outside this first version. Command scanning is rule-based and can miss risky commands or flag harmless examples; review warnings in context.

## Privacy and limitations

The app processes the uploaded JSON and selected Git status locally and does not contact an AI service. ChatGPT export support handles text messages from the common `mapping`/`current_node` JSON layout; export formats can change, so this adapter should be checked against real exports. Non-text content is skipped. The tool does not verify that evidence records are authentic or support Codex history exports. Claim and command detection use simple patterns, so they can miss claims or flag harmless examples. Treat results as review hints, not proof. Chat exports can contain sensitive information; keep the file secure.

## Use a ChatGPT data export

Request an export in ChatGPT under **Settings → Data controls → Export data**, download the ZIP when it is ready, and extract it. Upload `conversations.json` in the app, then select one conversation by title. If a large export contains numbered conversation JSON files instead, upload one of those files. The export may contain sensitive account and conversation data, so only use it on a computer you trust.
