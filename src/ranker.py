"""
LLM-based paper ranking using Claude API.
"""

import os
import json
from typing import List, Dict

import anthropic


class LLMRanker:
    """Use Claude to score and tier papers."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    async def rank(self, papers: List[Dict], interests: Dict, seeds: Dict) -> List[Dict]:
        if not papers:
            return []

        # Pre-sort by heuristic score
        for p in papers:
            p["heuristic_score"] = (
                p.get("keyword_score", 0)
                + p.get("citation_boost", 0)
                + p.get("community_boost", 0)
            )
        papers.sort(key=lambda x: x["heuristic_score"], reverse=True)

        # Take top 30 for LLM scoring (save API costs)
        candidates = papers[:30]

        # Build prompt
        seed_titles = "\n".join(f"- {p['title']}" for p in seeds.get("papers", []))
        primary_kw = ", ".join(interests.get("keywords", {}).get("primary", []))

        papers_text = ""
        for i, p in enumerate(candidates):
            papers_text += f"\n[{i+1}] {p['title']}\n"
            papers_text += f"    Authors: {', '.join(p.get('authors', [])[:3])}\n"
            abstract = (p.get("abstract") or "")[:300]
            papers_text += f"    Abstract: {abstract}...\n"
            if p.get("cites_seed"):
                papers_text += f"    ** Cites seed paper: {p['cites_seed']} **\n"
            if p.get("seed_author"):
                papers_text += f"    ** New work by tracked author: {p['seed_author']} **\n"
            if p.get("hf_votes"):
                papers_text += f"    HuggingFace votes: {p['hf_votes']}\n"

        prompt = f"""You are a research paper recommender for a PhD student working on:
- Primary interests: {primary_kw}
- Seed papers (core research direction):
{seed_titles}

Below are {len(candidates)} candidate papers. Score each from 1-10 for relevance and assign a tier:
- "must_read": Directly relevant to current research, cites seed papers, or from tracked authors
- "worth_noting": Related to research direction, potentially useful
- "trending": Hot in the community but not directly related
- "skip": Not relevant enough

Papers:
{papers_text}

Respond in JSON format:
[
  {{"index": 1, "score": 9, "tier": "must_read", "reason": "brief reason"}},
  ...
]

Only include papers with tier != "skip". Be selective - must_read should have at most 2-3 papers."""

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        try:
            text = response.content[0].text
            # Extract JSON from response
            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            rankings = json.loads(text[json_start:json_end])

            for r in rankings:
                idx = r["index"] - 1
                if 0 <= idx < len(candidates):
                    candidates[idx]["llm_score"] = r["score"]
                    candidates[idx]["tier"] = r["tier"]
                    candidates[idx]["reason"] = r["reason"]
        except (json.JSONDecodeError, KeyError, IndexError):
            # Fallback: use heuristic scoring for tiers
            for p in candidates[:2]:
                p["tier"] = "must_read"
                p["reason"] = "High heuristic score"
            for p in candidates[2:7]:
                p["tier"] = "worth_noting"
                p["reason"] = "Keyword match"
            for p in candidates[7:10]:
                p["tier"] = "trending"
                p["reason"] = "Community interest"

        # Return only tiered papers
        return [p for p in candidates if p.get("tier") and p["tier"] != "skip"]
