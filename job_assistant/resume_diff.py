from __future__ import annotations

import difflib


def summarize_changes(master: str, tailored: str, company: str) -> str:
    master_lines = [ln.rstrip() for ln in master.splitlines() if ln.strip()]
    tailored_lines = [ln.rstrip() for ln in tailored.splitlines() if ln.strip()]

    changes: list[str] = []
    differ = difflib.SequenceMatcher(None, master_lines, tailored_lines)

    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for old, new in zip(master_lines[i1:i2], tailored_lines[j1:j2]):
                if old != new:
                    changes.append(f"• Reworded: {old[:70]}…" if len(old) > 70 else f"• Reworded: {old}")
        elif tag == "insert":
            for new in tailored_lines[j1:j2]:
                if new.startswith("-") or new.startswith("•"):
                    changes.append(f"• Added/emphasized bullet: {new[:80]}")
        elif tag == "delete" and i2 - i1 <= 2:
            for old in master_lines[i1:i2]:
                changes.append(f"• Removed/de-emphasized: {old[:80]}")

    if not changes:
        changes.append("• Minor keyword and ordering adjustments")

    header = f"📝 Resume changes for {company}:"
    body = "\n".join(changes[:12])
    footer = "\n\nReview before applying. When ready at your laptop:\n  python -m job_assistant autofill --job-id <id>"
    return f"{header}\n{body}{footer}"
