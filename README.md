# AI Action Auditor

A small, local-first prototype that checks file-change claims in an AI session against file-change records supplied with that session or collected from a selected local Git project.

## What it does

- Finds supported assistant statements such as “updated `src/app.py`”.
- Matches the claimed path and action to supplied evidence records.
- Marks a claim **Unverified** when matching evidence is missing or the recorded action differs.
- Shows the matching records and lets you download the findings as JSON.
- Collects changed file names and statuses from a local Git working tree, including untracked files.

An **Evidence match** means the path and action match a record; it does not prove that the AI made the change. Git status does not identify who made a change. An unverified claim is not proof that the AI did not perform the action.

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

The prototype expects a JSON object with `messages` and `evidence` lists:

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

Supported file actions include created, added, modified, updated, edited, changed, deleted, and removed. Other kinds of AI actions and unsupported message formats are outside this first version.

## Privacy and limitations

The app processes the uploaded JSON and selected Git status locally and does not contact an AI service. It does not verify that evidence records are authentic or support exported ChatGPT/Codex history formats yet. Claim detection uses simple text patterns, so it can miss claims or interpret wording incorrectly. Treat results as review hints, not proof.
