from __future__ import annotations

import httpx

from . import config

_HEADERS = {"User-Agent": "job-apply-assistant/0.1"}


def fetch_readme(url: str = config.README_URL) -> str:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text


def fetch_source_readme_at_commit(source: config.Source, sha: str) -> str:
    return fetch_readme(source.readme_url_at(sha))


def fetch_latest_sha_for_source(source: config.Source) -> str:
    api = (
        f"https://api.github.com/repos/{source.repo}/commits"
        f"?path={source.readme_path}&sha={source.branch}&per_page=1"
    )
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(api, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"No commits found for {source.repo}:{source.readme_path}")
    return data[0]["sha"]
