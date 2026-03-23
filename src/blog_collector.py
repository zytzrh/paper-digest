"""
Blog/RSS feed collector for curated AI research blogs.
"""

import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict


class BlogCollector:
    """Collect recent posts from curated AI research blogs via RSS/Atom feeds."""

    name = "Blogs/RSS"

    def __init__(self, blogs: List[Dict]):
        """
        blogs: list of dicts with keys: name, url (RSS feed URL), optional: category
        """
        self.blogs = blogs or []

    async def collect(self) -> List[Dict]:
        if not self.blogs:
            return []

        papers = []
        cutoff = datetime.now() - timedelta(days=3)  # Posts from last 3 days

        async with aiohttp.ClientSession() as session:
            for blog in self.blogs:
                try:
                    posts = await self._fetch_feed(session, blog, cutoff)
                    papers.extend(posts)
                except Exception:
                    continue

        return papers

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, blog: Dict, cutoff: datetime
    ) -> List[Dict]:
        """Fetch and parse an RSS/Atom feed."""
        url = blog.get("feed_url", "")
        blog_name = blog.get("name", "Unknown Blog")

        if not url:
            return []

        posts = []
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "PaperDigest/1.0"},
            ) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
        except Exception:
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        # Try RSS 2.0 format
        items = root.findall(".//item")
        if items:
            for item in items[:10]:  # Max 10 per feed
                title = self._get_text(item, "title")
                link = self._get_text(item, "link")
                description = self._get_text(item, "description")
                pub_date = self._get_text(item, "pubDate")

                if not title:
                    continue

                # Parse date and filter by cutoff
                parsed_date = self._parse_date(pub_date)
                if parsed_date and parsed_date < cutoff:
                    continue

                posts.append({
                    "title": f"[Blog] {title}",
                    "abstract": self._clean_html(description or ""),
                    "authors": [blog_name],
                    "arxiv_id": "",
                    "source": "blog",
                    "blog_name": blog_name,
                    "blog_url": link,
                    "published": pub_date,
                })
            return posts

        # Try Atom format
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        if not entries:
            # Try without namespace
            entries = root.findall("entry")

        for entry in entries[:10]:
            title = self._get_text(entry, "atom:title", ns) or self._get_text(entry, "title")
            link_el = entry.find("atom:link", ns) or entry.find("link")
            link = link_el.get("href", "") if link_el is not None else ""
            summary = (
                self._get_text(entry, "atom:summary", ns)
                or self._get_text(entry, "atom:content", ns)
                or self._get_text(entry, "summary")
                or self._get_text(entry, "content")
            )
            updated = (
                self._get_text(entry, "atom:updated", ns)
                or self._get_text(entry, "atom:published", ns)
                or self._get_text(entry, "updated")
                or self._get_text(entry, "published")
            )

            if not title:
                continue

            parsed_date = self._parse_date(updated)
            if parsed_date and parsed_date < cutoff:
                continue

            posts.append({
                "title": f"[Blog] {title}",
                "abstract": self._clean_html(summary or ""),
                "authors": [blog_name],
                "arxiv_id": "",
                "source": "blog",
                "blog_name": blog_name,
                "blog_url": link,
                "published": updated,
            })

        return posts

    @staticmethod
    def _get_text(element, tag, ns=None):
        """Get text content of a child element."""
        if ns:
            el = element.find(tag, ns)
        else:
            el = element.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    @staticmethod
    def _parse_date(date_str: str):
        """Try to parse a date string."""
        if not date_str:
            return None
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",     # RSS: Mon, 01 Jan 2024 00:00:00 +0000
            "%a, %d %b %Y %H:%M:%S %Z",     # RSS variant
            "%Y-%m-%dT%H:%M:%S%z",           # Atom: 2024-01-01T00:00:00+00:00
            "%Y-%m-%dT%H:%M:%SZ",            # Atom UTC
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                continue
        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        import re
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean)
        return clean[:500].strip()
