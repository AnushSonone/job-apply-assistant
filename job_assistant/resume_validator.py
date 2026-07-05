from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _section_present(text: str, name: str) -> bool:
    return bool(re.search(rf"^#{{1,2}}\s*{re.escape(name)}\b", text, re.I | re.M))


def validate_tailored(
    master: str,
    tailored: str,
    facts: dict,
    max_drift_pct: float = 10.0,
) -> ValidationResult:
    result = ValidationResult(ok=True)

    master_wc = _word_count(master)
    tailored_wc = _word_count(tailored)
    if master_wc > 0:
        drift = abs(tailored_wc - master_wc) / master_wc * 100
        if drift > max_drift_pct:
            result.errors.append(f"Word count drift {drift:.1f}% exceeds {max_drift_pct}%")

    for section in ("Education", "Experience", "Skills"):
        if _section_present(master, section) and not _section_present(tailored, section):
            result.errors.append(f"Missing required section: {section}")

    whitelist_employers = {e.lower() for e in facts.get("employers", [])}
    for line in tailored.splitlines():
        for emp in whitelist_employers:
            continue
        match = re.match(r"^\*\*([A-Z][^*]+)\*\*", line.strip())
        if match:
            name = match.group(1).strip().lower()
            known = any(name in e or e in name for e in whitelist_employers)
            if not known and len(name) > 3 and name not in ("education", "experience", "projects", "skills"):
                result.warnings.append(f"Possible new entity in output: {match.group(1)}")

    if result.errors:
        result.ok = False
    return result
