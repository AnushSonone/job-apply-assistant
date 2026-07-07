from __future__ import annotations

import httpx

from . import config

_HEADERS = {"User-Agent": "job-apply-assistant/0.1"}


def fetch_readme(url: str = config.README_URL) -> str:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text


def fetch_readme_at_commit(sha: str) -> str:
    url = (
        f"https://raw.githubusercontent.com/{config.UPSTREAM_REPO}/"
        f"{sha}/{config.README_PATH}"
    )
    return fetch_readme(url)


def fetch_latest_upstream_sha() -> str:
    api = (
        f"https://api.github.com/repos/{config.UPSTREAM_REPO}/commits"
        f"?path={config.README_PATH}&sha={config.UPSTREAM_BRANCH}&per_page=1"
    )
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(api, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    if not data:
        raise RuntimeError("No commits found for upstream README")
    return data[0]["sha"]
