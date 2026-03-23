"""
Paper filtering: keyword matching and citation network analysis.
"""

import re
from typing import List, Dict


class KeywordFilter:
    """Filter papers by keyword matching against title and abstract."""

    def __init__(self, keywords: Dict, exclude_keywords: List[str]):
        self.primary = [kw.lower() for kw in keywords.get("primary", [])]
        self.secondary = [kw.lower() for kw in keywords.get("secondary", [])]
        self.exclude = [kw.lower() for kw in exclude_keywords]

    def filter(self, papers: List[Dict]) -> List[Dict]:
        results = []
        for paper in papers:
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()

            # Exclude
            if any(kw in text for kw in self.exclude):
                continue

            # Score by keyword matches
            primary_hits = sum(1 for kw in self.primary if kw in text)
            secondary_hits = sum(1 for kw in self.secondary if kw in text)

            # Keep if any keyword matches, or if from citation/HF source
            if primary_hits > 0 or secondary_hits > 0 or paper.get("cites_seed") or paper.get("seed_author") or paper.get("hf_votes", 0) > 5:
                paper["keyword_score"] = primary_hits * 3 + secondary_hits
                results.append(paper)

        return results


class CitationFilter:
    """Enrich papers with citation network information."""

    def __init__(self, seed_papers: List[Dict]):
        self.seed_titles = {p["title"].lower().strip() for p in seed_papers}
        self.seed_authors = set()
        # Will be populated by Semantic Scholar data

    def enrich(self, papers: List[Dict]) -> List[Dict]:
        for paper in papers:
            # Papers that cite seeds get a boost
            if paper.get("cites_seed"):
                paper["citation_boost"] = 10

            # Seed author new works get a boost
            if paper.get("seed_author"):
                paper["citation_boost"] = paper.get("citation_boost", 0) + 8

            # HuggingFace community signal
            hf_votes = paper.get("hf_votes", 0)
            if hf_votes > 0:
                paper["community_boost"] = min(hf_votes, 10)

        return papers
