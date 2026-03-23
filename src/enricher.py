"""
External enrichment: search for GitHub repos, community discussions, and blog posts
related to papers using web search.
"""

import os
import aiohttp
from typing import List, Dict


class PaperEnricher:
    """Enrich papers with external signals like GitHub repos and community discussions."""

    def __init__(self):
        self.tavily_key = os.environ.get("TAVILY_API_KEY")

    async def enrich(self, papers: List[Dict]) -> List[Dict]:
        """Enrich papers with external context. Only enriches must_read and worth_noting papers."""
        enrichable = [p for p in papers if p.get("tier") in ("must_read", "worth_noting")]

        if not enrichable:
            return papers

        async with aiohttp.ClientSession() as session:
            for paper in enrichable:
                title = paper.get("title", "")
                if not title:
                    continue

                signals = []

                # Search for GitHub repos
                github_results = await self._search_github(session, title)
                if github_results:
                    signals.append(f"GitHub: {github_results}")

                # Search for community discussions (Twitter/X, Reddit, blog posts)
                if self.tavily_key:
                    community = await self._search_tavily(session, title)
                    if community:
                        signals.append(community)
                else:
                    # Fallback: search Semantic Scholar for citation count and influence
                    influence = await self._get_paper_influence(session, paper)
                    if influence:
                        signals.append(influence)

                if signals:
                    paper["external_signals"] = " | ".join(signals)

        return papers

    async def _search_github(self, session: aiohttp.ClientSession, title: str) -> str:
        """Search GitHub for repositories related to the paper."""
        # Use first few significant words from title for search
        query = " ".join(title.split()[:8])
        url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "stars", "per_page": 3}
        headers = {"Accept": "application/vnd.github.v3+json"}

        # Add GitHub token if available
        gh_token = os.environ.get("GITHUB_TOKEN")
        if gh_token:
            headers["Authorization"] = f"token {gh_token}"

        try:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    if items:
                        # Filter for repos that seem genuinely related (stars > 5)
                        relevant = [
                            f"[{r['full_name']}]({r['html_url']}) ⭐{r['stargazers_count']}"
                            for r in items
                            if r.get("stargazers_count", 0) >= 5
                        ]
                        if relevant:
                            return ", ".join(relevant[:2])
        except Exception:
            pass
        return ""

    async def _search_tavily(self, session: aiohttp.ClientSession, title: str) -> str:
        """Search Tavily for community discussions and blog posts about the paper."""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_key,
            "query": f"{title} paper discussion implementation",
            "search_depth": "basic",
            "max_results": 3,
            "include_domains": [
                "reddit.com", "twitter.com", "x.com",
                "huggingface.co", "medium.com", "lilianweng.github.io",
                "paperswithcode.com"
            ],
        }

        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        summaries = []
                        for r in results[:2]:
                            domain = r.get("url", "").split("/")[2] if "/" in r.get("url", "") else ""
                            summaries.append(f"[{domain}]({r['url']})")
                        return "Community: " + ", ".join(summaries)
        except Exception:
            pass
        return ""

    async def _get_paper_influence(self, session: aiohttp.ClientSession, paper: Dict) -> str:
        """Fallback: get citation count and influential citation count from Semantic Scholar."""
        arxiv_id = paper.get("arxiv_id", "")
        if not arxiv_id:
            return ""

        url = f"https://api.semanticscholar.org/graph/v1/paper/ArXiv:{arxiv_id}"
        params = {"fields": "citationCount,influentialCitationCount,referenceCount"}

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    citations = data.get("citationCount", 0)
                    influential = data.get("influentialCitationCount", 0)
                    if citations > 0:
                        return f"Citations: {citations} (influential: {influential})"
        except Exception:
            pass
        return ""
