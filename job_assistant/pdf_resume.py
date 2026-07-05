from __future__ import annotations

import json
import re
from pathlib import Path

import fitz


def pdf_to_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text().strip() for page in doc if page.get_text().strip())
    finally:
        doc.close()


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert PDF resume text into simple markdown sections."""
    raw = pdf_to_text(pdf_path)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return ""

    sections = {
        "Education": [],
        "Experience": [],
        "Projects": [],
        "Skills": [],
        "_header": [],
    }
    current = "_header"
    section_names = set(sections) - {"_header"}

    for line in lines:
        if line in ("Education", "Experience", "Projects", "Skills"):
            current = line
            continue
        if line.endswith(":") and line.rstrip(":") in section_names:
            current = line.rstrip(":")
            continue
        sections[current].append(line)

    out: list[str] = []
    if sections["_header"]:
        out.extend(sections["_header"][:2])
        out.append("")
    for name in ("Education", "Experience", "Projects", "Skills"):
        if sections[name]:
            out.append(f"## {name}")
            for item in sections[name]:
                if item.startswith("•") or item.startswith("-"):
                    out.append(item if item.startswith("-") else f"- {item.lstrip('•').strip()}")
                elif re.match(r"^[A-Z].*[a-z]", item) and len(item) < 80 and not item[0].isdigit():
                    out.append(f"\n**{item}**")
                else:
                    out.append(item)
            out.append("")
    return "\n".join(out).strip() + "\n"


def import_resume_pdf(pdf_path: Path, out_md: Path) -> str:
    md = pdf_to_markdown(pdf_path)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md)
    return md
