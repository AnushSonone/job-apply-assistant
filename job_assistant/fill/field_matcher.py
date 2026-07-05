from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .page_snapshot import FormField, normalize_label


@dataclass
class MatchResult:
    action: str  # fill | skip | upload_file
    value: str | None = None
    rule_label: str = ""


def load_answer_bank(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        example = path.parent / "answer_bank.example.yaml"
        if example.exists():
            return yaml.safe_load(example.read_text()).get("rules", [])
        return []
    return yaml.safe_load(path.read_text()).get("rules", [])


def _profile_get(profile: dict, dotted: str) -> str | None:
    if not dotted.startswith("profile."):
        return None
    key = dotted.split(".", 1)[1]
    val = profile.get(key)
    return str(val) if val is not None else None


def match_field(field: FormField, rules: list[dict], profile: dict) -> MatchResult | None:
    norm = normalize_label(field.label)
    if not norm:
        return None

    for rule in rules:
        patterns = rule.get("match", [])
        if isinstance(patterns, str):
            patterns = [patterns]
        matched = False
        for pat in patterns:
            if pat.startswith("(?") or ".*" in pat or pat.startswith("^"):
                if re.search(pat, norm, re.I):
                    matched = True
                    break
            elif normalize_label(pat) in norm or norm in normalize_label(pat):
                matched = True
                break
        if not matched:
            continue

        action = rule.get("action", "fill")
        if action == "skip":
            return MatchResult(action="skip", rule_label=str(patterns))

        if action == "upload_file":
            return MatchResult(action="upload_file", rule_label=str(patterns))

        if "value" in rule:
            return MatchResult(action="fill", value=str(rule["value"]), rule_label=str(patterns))
        if "value_from" in rule:
            vf = rule["value_from"]
            if vf == "resume.latest_for_job":
                return MatchResult(action="upload_file", rule_label=str(patterns))
            pv = _profile_get(profile, vf)
            if pv:
                return MatchResult(action="fill", value=pv, rule_label=str(patterns))

    synonyms: dict[str, list[str]] = profile.get("field_synonyms", {})
    for key, patterns in synonyms.items():
        if key not in profile:
            continue
        if any(normalize_label(p) in norm for p in patterns):
            return MatchResult(action="fill", value=str(profile[key]), rule_label=key)

    for key in (
        "first_name", "last_name", "email", "phone", "linkedin", "github",
        "school", "degree", "graduation_date", "gpa", "location",
        "work_authorization", "require_sponsorship",
    ):
        if key in profile and key.replace("_", " ") in norm:
            return MatchResult(action="fill", value=str(profile[key]), rule_label=key)

    return None
