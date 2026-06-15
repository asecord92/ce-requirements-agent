"""Web search and page fetching tools exposed to the agent."""
from __future__ import annotations

import re
import time
import warnings

import requests
import urllib3
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

_PAGE_CHAR_LIMIT = 16000
_SEARCH_PAUSE = 2.0  # seconds between searches to avoid rate limiting
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def web_search(query: str, max_results: int = 6) -> list[dict]:
    """
    Search DuckDuckGo and return up to max_results hits.

    Each result: {title, href, body}
    """
    time.sleep(_SEARCH_PAUSE)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title", ""), "href": r.get("href", ""), "body": r.get("body", "")} for r in results]
    except Exception as exc:
        return [{"title": "Search error", "href": "", "body": str(exc)}]


def fetch_page(url: str) -> dict:
    """
    Fetch a URL and return cleaned text content (truncated to ~16000 chars).

    Returns: {url, content, error}
    SSL verification is relaxed to handle state boards with certificate issues.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, headers=_HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove nav/footer/script/style noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()

        # Detect JS-only pages (no useful text rendered server-side)
        if len(text) < 200:
            return {
                "url": url,
                "content": "",
                "error": "Page appears to be JavaScript-rendered (no server-side text). Try a different URL or search for a cached/PDF version.",
            }

        if len(text) > _PAGE_CHAR_LIMIT:
            text = text[:_PAGE_CHAR_LIMIT] + "\n\n[...content truncated...]"

        return {"url": url, "content": text, "error": None}
    except Exception as exc:
        return {"url": url, "content": "", "error": str(exc)}
