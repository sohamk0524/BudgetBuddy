"""
Local deals loader and matcher for BudgetBuddy.

Reads curated deal files from documents/deals/{school_slug}.md,
caches parsed results, and scores deals by tag overlap with keywords.
"""

import os
import re
from typing import Dict, Any, List, Optional

# Module-level cache: school_slug -> list of deal dicts
_deals_cache: Dict[str, List[Dict[str, Any]]] = {}

_DEALS_DIR = os.path.join(os.path.dirname(__file__), "..", "documents", "deals")


def _parse_deals_file(filepath: str) -> List[Dict[str, Any]]:
    """Parse a ---delimited markdown deals file into a list of dicts.

    Each entry is separated by a line starting with ``---``.
    Fields are ``key: value`` pairs. Markdown link syntax in URLs is stripped.
    The ``tags`` value is split into a list of lowercase strings.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Split on separator lines (--- possibly followed by dashes)
    blocks = re.split(r"^-{3,}.*$", text, flags=re.MULTILINE)

    deals: List[Dict[str, Any]] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        entry: Dict[str, Any] = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            match = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                entry[key] = value

        if not entry.get("name"):
            continue

        # Strip markdown link syntax from url: [text](actual_url) -> actual_url
        url = entry.get("url", "")
        link_match = re.search(r"\((https?://[^)]+)\)", url)
        if link_match:
            entry["url"] = link_match.group(1)

        # Split tags into a list
        tags_str = entry.get("tags", "")
        entry["tags"] = [t.strip().lower() for t in tags_str.split(",") if t.strip()]

        deals.append(entry)

    return deals


def get_deals(school_slug: str) -> List[Dict[str, Any]]:
    """Return parsed deals for a school slug, caching after first load.

    Returns an empty list if no deals file exists for the school.
    """
    if school_slug in _deals_cache:
        return _deals_cache[school_slug]

    filepath = os.path.join(_DEALS_DIR, f"{school_slug}.md")
    if not os.path.isfile(filepath):
        _deals_cache[school_slug] = []
        return []

    deals = _parse_deals_file(filepath)
    _deals_cache[school_slug] = deals
    return deals


def match_deals(
    school_slug: str,
    keywords: List[str],
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """Score deals by tag overlap with *keywords* and return top matches.

    Each keyword is compared case-insensitively against each deal's tags.
    Deals with zero overlap are excluded.
    """
    deals = get_deals(school_slug)
    if not deals or not keywords:
        return []

    lower_keywords = {kw.lower() for kw in keywords}

    scored: List[tuple] = []
    for deal in deals:
        overlap = len(lower_keywords & set(deal.get("tags", [])))
        if overlap > 0:
            scored.append((overlap, deal))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [deal for _, deal in scored[:max_results]]
