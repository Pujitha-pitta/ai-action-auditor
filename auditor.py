"""Small, evidence-based checks for file-change claims in AI session logs."""

from __future__ import annotations

import re
import subprocess
from pathlib import PurePosixPath
from typing import Any


CLAIM_PATTERN = re.compile(
    r"\b(?P<verb>created|added|modified|updated|edited|changed|deleted|removed)"
    r"\s+(?:(?:the|a)\s+)?(?:file\s+)?[\"'`]*(?P<path>"
    r"(?:[A-Za-z0-9_.-]+[\\/])*[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+)[\"'`]*",
    re.IGNORECASE,
)

RISKY_COMMAND_PATTERNS = [
    (
        "High",
        "Recursive or forced deletion",
        re.compile(r"(?im)^\s*(?:\$\s*)?rm\s+-[a-z]*r[a-z]*f[a-z]*\b[^\r\n]*|^\s*(?:\$\s*)?rm\s+-[a-z]*f[a-z]*r[a-z]*\b[^\r\n]*"),
        "This command can recursively delete files without normal safeguards.",
    ),
    (
        "High",
        "Recursive PowerShell deletion",
        re.compile(r"(?im)^\s*(?:PS>\s*)?Remove-Item\b[^\r\n]*(?:-Recurse|-Force)\b[^\r\n]*"),
        "This PowerShell command can remove files or folders recursively or forcibly.",
    ),
    (
        "High",
        "Hard Git reset",
        re.compile(r"(?im)^\s*(?:\$\s*)?git\s+reset\s+--hard\b[^\r\n]*"),
        "This command discards tracked working-tree changes and resets files to a commit.",
    ),
    (
        "High",
        "Forced Git cleanup",
        re.compile(r"(?im)^\s*(?:\$\s*)?git\s+clean\b[^\r\n]*-[a-z]*f[a-z]*[^\r\n]*"),
        "This command can delete untracked files from the working tree.",
    ),
    (
        "High",
        "Force push",
        re.compile(r"(?im)^\s*(?:\$\s*)?git\s+push\b[^\r\n]*(?:--force\b|\s-f(?:\s|$))[^\r\n]*"),
        "A force push can overwrite commits on the remote branch.",
    ),
    (
        "High",
        "SQL deletion statement",
        re.compile(r"(?im)^\s*(?:DROP\s+(?:DATABASE|TABLE)\b|TRUNCATE\s+TABLE\b)[^\r\n]*"),
        "This SQL statement can remove a database, table, or its rows.",
    ),
    (
        "High",
        "Infrastructure destruction",
        re.compile(r"(?im)^\s*(?:\$\s*)?terraform\s+destroy\b[^\r\n]*"),
        "This command can destroy infrastructure managed by the selected Terraform configuration.",
    ),
]

VERB_TO_OPERATION = {
    "created": {"created", "added"},
    "added": {"created", "added"},
    "modified": {"modified", "updated", "edited", "changed"},
    "updated": {"modified", "updated", "edited", "changed"},
    "edited": {"modified", "updated", "edited", "changed"},
    "changed": {"modified", "updated", "edited", "changed"},
    "deleted": {"deleted", "removed"},
    "removed": {"deleted", "removed"},
}


def normalize_path(value: str) -> str:
    """Normalize separators and harmless ./ prefixes for matching."""
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return str(PurePosixPath(path)).casefold()


def collect_git_evidence(repo_path: str) -> list[dict[str, Any]]:
    """Read changed paths from a local Git working tree without reading file contents."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise ValueError("Git was not found. Install Git and make sure it is on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode(errors="replace").strip()
        raise ValueError(message or "Could not read Git status for that folder.") from exc

    fields = result.stdout.split(b"\0")
    evidence: list[dict[str, Any]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            continue
        status = record[:2].decode("ascii", errors="replace")
        path = record[3:].decode(errors="replace")

        if "R" in status or "C" in status:
            operation = "modified"
            old_path = fields[index].decode(errors="replace") if index < len(fields) else ""
            index += bool(old_path)
        elif "?" in status or "A" in status:
            operation = "created"
            old_path = ""
        elif "D" in status:
            operation = "deleted"
            old_path = ""
        else:
            operation = "modified"
            old_path = ""

        item: dict[str, Any] = {
            "type": "file_change",
            "path": path,
            "operation": operation,
            "source": "local git status (working-tree snapshot)",
            "git_status": status,
        }
        if old_path:
            item["previous_path"] = old_path
        evidence.append(item)

    return evidence


def audit_session(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Find assistant file-change claims and compare them with supplied evidence.

    Expected input format:
      {"messages": [{"role": "assistant", "content": "..."}],
       "evidence": [{"type": "file_change", "path": "src/app.py",
                     "operation": "modified", "source": "git diff"}]}

    Missing evidence is reported as unverified, never as proof that the claim is
    false. The app audits only file-change claims in this first version.
    """
    messages = session.get("messages", [])
    evidence = session.get("evidence", [])
    if not isinstance(messages, list) or not isinstance(evidence, list):
        raise ValueError("'messages' and 'evidence' must both be JSON lists.")

    file_changes: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        if not isinstance(item, dict) or item.get("type") != "file_change":
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        file_changes.setdefault(normalize_path(path), []).append(item)

    findings: list[dict[str, Any]] = []
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict) or str(message.get("role", "")).casefold() != "assistant":
            continue
        content = message.get("content", "")
        if not isinstance(content, str):
            continue
        for match in CLAIM_PATTERN.finditer(content):
            verb = match.group("verb").casefold()
            claimed_path = match.group("path").rstrip(".,;:)")
            matching_evidence = file_changes.get(normalize_path(claimed_path), [])
            allowed_operations = VERB_TO_OPERATION[verb]
            operation_matches = [
                item for item in matching_evidence
                if str(item.get("operation", "")).casefold() in allowed_operations
            ]
            if operation_matches:
                status = "Evidence match"
                explanation = (
                    "A supplied file-change record matches the claimed path and action. "
                    "A Git status snapshot does not identify who made the change."
                )
                supporting_records = operation_matches
            else:
                status = "Unverified"
                if matching_evidence:
                    explanation = "A record mentions this file, but its operation does not match the claim."
                    supporting_records = matching_evidence
                else:
                    explanation = "No matching file-change record was included. This does not prove the claim is false."
                    supporting_records = []
            findings.append({
                "status": status,
                "claim": match.group(0),
                "path": claimed_path,
                "message_index": message_index,
                "explanation": explanation,
                "evidence": supporting_records,
            })
    return findings


def detect_risky_commands(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Flag potentially destructive command text in assistant messages.

    A match only means the command appeared in the message. It does not mean
    that the command was executed or that any data was changed.
    """
    messages = session.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("'messages' must be a JSON list.")

    findings: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict) or str(message.get("role", "")).casefold() != "assistant":
            continue
        content = message.get("content", "")
        if not isinstance(content, str):
            continue
        for severity, category, pattern, explanation in RISKY_COMMAND_PATTERNS:
            for match in pattern.finditer(content):
                command = match.group(0).strip()
                key = (message_index, command.casefold())
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "severity": severity,
                    "category": category,
                    "command_text": command,
                    "message_index": message_index,
                    "status": "Potential risk mentioned; execution unverified",
                    "explanation": explanation,
                })
    return findings
