from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .db import Job, job_id

README_SECTIONS = {
    "software-engineering": "Software Engineering",
    "product-management": "Product Management",
    "data-science": "Data Science, AI & ML",
    "quantitative-finance": "Quantitative Finance",
    "hardware-engineering": "Hardware Engineering",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def _extract_company(td) -> tuple[str, str]:
    text = _clean(td.get_text())
    flags = ""
    if "🔥" in text:
        flags += "hot "
    if "🛂" in text:
        flags += "no_sponsorship "
    if "🇺🇸" in text:
        flags += "us_citizenship "
    if "🎓" in text:
        flags += "advanced_degree "
    if text.startswith("↳"):
        flags += "sub_role "
    link = td.find("a")
    company = _clean(link.get_text()) if link else text.lstrip("↳🔥🛂🇺🇸🎓 ").strip()
    return company, flags.strip()


def _extract_links(td) -> tuple[str | None, str | None]:
    cell = _clean(td.get_text())
    if cell == "🔒" or "🔒" in cell and not td.find("a", href=True):
        return None, None

    apply_url = None
    simplify_url = None
    for anchor in td.find_all("a", href=True):
        href = anchor["href"].strip()
        if "simplify.jobs/p/" in href:
            simplify_url = href
        elif apply_url is None and "imgur.com" not in href:
            apply_url = href

    if cell == "🔒":
        return None, simplify_url
    return apply_url, simplify_url


def _category_for_position(content: str, row_html: str) -> str:
    pos = content.find(row_html)
    if pos == -1:
        return "Unknown"
    prefix = content[:pos]
    matches = list(re.finditer(r"## .+ Internship Roles", prefix))
    if not matches:
        return "Unknown"
    header = matches[-1].group(0)
    if "Software Engineering" in header:
        return "Software Engineering"
    if "Product Management" in header:
        return "Product Management"
    if "Data Science" in header or "Machine Learning" in header:
        return "Data Science, AI & ML"
    if "Quantitative Finance" in header:
        return "Quantitative Finance"
    if "Hardware Engineering" in header:
        return "Hardware Engineering"
    return "Unknown"


def parse_readme(content: str) -> list[Job]:
    soup = BeautifulSoup(content, "html.parser")
    jobs: list[Job] = []

    for row_index, row in enumerate(soup.find_all("tr")):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        company, flags = _extract_company(cells[0])
        role = _clean(cells[1].get_text())
        location = _clean(cells[2].get_text())
        terms = _clean(cells[3].get_text())
        apply_url, simplify_url = _extract_links(cells[4])
        age = _clean(cells[5].get_text())
        is_closed = apply_url is None

        if not company or not role:
            continue

        category = _category_for_position(content, str(row))
        jid = job_id(company, role, location)
        jobs.append(
            Job(
                id=jid,
                company=company,
                role=role,
                location=location,
                terms=terms,
                category=category,
                apply_url=apply_url,
                simplify_url=simplify_url,
                age=age,
                is_closed=is_closed,
                flags=flags,
                row_index=row_index,
            )
        )

    return jobs
