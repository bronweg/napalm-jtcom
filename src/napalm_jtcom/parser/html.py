"""Base HTML parsing utilities shared across all parsers."""

from __future__ import annotations

from bs4 import BeautifulSoup


def parse_html(html: str, parser: str = "lxml") -> BeautifulSoup:
    """Parse an HTML string and return a BeautifulSoup document.

    Args:
        html: Raw HTML content from the switch response.
        parser: Parser library to use (default: ``lxml``).

    Returns:
        Parsed BeautifulSoup document.
    """
    return BeautifulSoup(html, parser)
