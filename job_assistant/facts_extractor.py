from __future__ import annotations

import json
import re
from pathlib import Path


def extract_facts(resume_text: str) -> dict:
    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    employers: list[str] = []
    schools: list[str] = []
    degrees: list[str] = []
    date_ranges: list[str] = []
    skills: list[str] = []
    projects: list[str] = []
    metrics: list[str] = []

    for line in lines:
        for m in re.findall(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{4}\s*[–\-—]\s*"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{4}|"
            r"Expected\s+\w+\s+\d{4}|May\s+\d{4}",
            line,
            re.I,
        ):
            date_ranges.append(m if isinstance(m, str) else " ".join(m))

        for m in re.findall(r"\d+[KkMm]?\+?\s*(?:%|percent|users|sessions|dealerships|banks|firms)", line):
            metrics.append(m)

    in_skills = False
    for i, line in enumerate(lines):
        low = line.lower()
        if low == "skills" or line == "## Skills":
            in_skills = True
            continue
        if line.startswith("## ") and in_skills:
            in_skills = False
        if in_skills and line:
            parts = re.split(r"[,;|]", line)
            skills.extend(p.strip() for p in parts if p.strip())

        if line in ("Education", "## Education") and i + 1 < len(lines):
            schools.append(lines[i + 1])
        if "Bachelor" in line or "B.S." in line or "Computer Science" in line:
            degrees.append(line)

        if line in ("Experience", "## Experience", "Projects", "## Projects"):
            continue
        if re.match(r"^[A-Z][A-Za-z0-9 &.'()-]+$", line) and len(line) < 60:
            if i + 1 < len(lines) and re.search(r"\d{4}", lines[i + 1]):
                employers.append(line)
            if line not in employers and line not in schools and "Intern" not in line:
                if any(k in lines[max(0, i - 2) : i + 1] for k in ("Experience", "Projects")):
                    projects.append(line)

    return {
        "employers": sorted(set(employers)),
        "schools": sorted(set(schools)),
        "degrees": sorted(set(degrees)),
        "date_ranges": sorted(set(date_ranges)),
        "skills": sorted(set(skills))[:80],
        "projects": sorted(set(projects))[:30],
        "metrics": sorted(set(metrics))[:40],
    }


def load_or_build_facts(resume_path: Path, facts_path: Path) -> dict:
    if facts_path.exists():
        return json.loads(facts_path.read_text())
    text = resume_path.read_text()
    facts = extract_facts(text)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(json.dumps(facts, indent=2) + "\n")
    return facts
