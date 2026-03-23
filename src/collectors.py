"""
Paper collectors from various sources.
"""

import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict


class ArxivCollector:
    """Collect papers from arXiv daily listings."""

    name = "arXiv"

    def __init__(self, categories: List[str]):
        self.categories = categories
        self.base_url = "http://export.arxiv.org/api/query"

    async def collect(self) -> List[Dict]:
        papers = []
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        today = datetime.now().strftime("%Y%m%d")

        cat_query = " OR ".join(f"cat:{cat}" for cat in self.categories)
        query = f"({cat_query})"

        params = {
            "search_query": query,
            "start": 0,
            "max_results": 200,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()

        root = ET.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]
            published = entry.find("atom:published", ns).text
            categories = [c.get("term") for c in entry.findall("atom:category", ns)]
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            papers.append({
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "arxiv_id": arxiv_id,
                "published": published,
                "categories": categories,
                "pdf_url": pdf_url,
                "source": "arxiv",
            })

        return papers


class SemanticScholarCollector:
    """Collect papers that cite seed papers, and new works by seed authors."""

    name = "Semantic Scholar"

    def __init__(self, seed_papers: List[Dict]):
        self.seed_papers = seed_papers
        self.base_url = "https://api.semanticscholar.org/graph/v1"

    async def collect(self) -> List[Dict]:
        papers = []
        async with aiohttp.ClientSession() as session:
            for seed in self.seed_papers:
                arxiv_id = seed.get("arxiv_id")
                if not arxiv_id:
                    continue

                # Get citations of seed paper
                url = f"{self.base_url}/paper/ArXiv:{arxiv_id}/citations"
                params = {
                    "fields": "title,abstract,authors,externalIds,year,citationCount",
                    "limit": 50,
                }
                try:
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for item in data.get("data", []):
                                citing = item.get("citingPaper", {})
                                if not citing.get("title"):
                                    continue
                                ext_ids = citing.get("externalIds", {})
                                papers.append({
                                    "title": citing["title"],
                                    "abstract": citing.get("abstract", ""),
                                    "authors": [a["name"] for a in citing.get("authors", [])],
                                    "arxiv_id": ext_ids.get("ArXiv", ""),
                                    "citation_count": citing.get("citationCount", 0),
                                    "source": "semantic_scholar",
                                    "cites_seed": seed["title"],
                                })
                except Exception:
                    continue

                # Get seed paper's authors' recent works
                try:
                    paper_url = f"{self.base_url}/paper/ArXiv:{arxiv_id}"
                    params = {"fields": "authors.authorId,authors.name"}
                    async with session.get(paper_url, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for author in data.get("authors", [])[:3]:  # Top 3 authors
                                author_id = author.get("authorId")
                                if not author_id:
                                    continue
                                author_url = f"{self.base_url}/author/{author_id}/papers"
                                params = {
                                    "fields": "title,abstract,externalIds,year",
                                    "limit": 10,
                                }
                                async with session.get(author_url, params=params) as resp2:
                                    if resp2.status == 200:
                                        author_data = await resp2.json()
                                        for p in author_data.get("data", []):
                                            if p.get("year") and p["year"] >= 2025:
                                                ext_ids = p.get("externalIds", {})
                                                papers.append({
                                                    "title": p["title"],
                                                    "abstract": p.get("abstract", ""),
                                                    "authors": [author["name"]],
                                                    "arxiv_id": ext_ids.get("ArXiv", ""),
                                                    "source": "semantic_scholar",
                                                    "seed_author": author["name"],
                                                })
                except Exception:
                    continue

        return papers


class HuggingFaceCollector:
    """Collect trending papers from HuggingFace Daily Papers."""

    name = "HuggingFace Daily Papers"

    async def collect(self) -> List[Dict]:
        papers = []
        url = "https://huggingface.co/api/daily_papers"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            paper = item.get("paper", {})
                            papers.append({
                                "title": paper.get("title", ""),
                                "abstract": paper.get("summary", ""),
                                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                                "arxiv_id": paper.get("id", ""),
                                "hf_votes": item.get("numUpvotes", 0),
                                "source": "huggingface",
                            })
            except Exception:
                pass

        return papers
