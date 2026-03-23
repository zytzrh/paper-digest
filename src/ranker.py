"""
LLM-based paper ranking using Claude API.

Two-stage filtering:
  Stage 1 (Coarse): Haiku scores top 30 candidates (cheap, fast)
  Stage 2 (Fine):   Sonnet re-ranks survivors with full context (precise, insightful)
"""

import os
import json
import asyncio
from typing import List, Dict

import anthropic

from pdf_reader import deep_review

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-20250514"

COARSE_THRESHOLD = 5  # minimum Haiku score to advance to Stage 2


class LLMRanker:
    """Use Claude to score and tier papers via two-stage filtering."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

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

        # Shared context strings
        seed_titles = "\n".join(f"- {p['title']}" for p in seeds.get("papers", []))
        primary_kw = ", ".join(interests.get("keywords", {}).get("primary", []))

        # --- Stage 1: Coarse filter with Haiku ---
        try:
            survivors = self._stage1_coarse(candidates, seed_titles, primary_kw)
        except Exception as e:
            print(f"  Stage 1 (Haiku) failed ({e}), using heuristic fallback...")
            self._heuristic_rank(candidates)
            return [p for p in candidates if p.get("tier") and p["tier"] != "skip"]

        if not survivors:
            print("  Stage 1 filtered out all papers, using heuristic fallback...")
            self._heuristic_rank(candidates)
            return [p for p in candidates if p.get("tier") and p["tier"] != "skip"]

        print(f"  Stage 1: {len(candidates)} -> {len(survivors)} papers (threshold >= {COARSE_THRESHOLD})")

        # --- Stage 2: Fine ranking with Sonnet ---
        try:
            result = self._stage2_fine(survivors, seed_titles, primary_kw)
        except Exception as e:
            print(f"  Stage 2 (Sonnet) failed ({e}), using heuristic fallback on survivors...")
            self._heuristic_rank(survivors)
            result = [p for p in survivors if p.get("tier") and p["tier"] != "skip"]

        # Deep review for must_read papers
        must_reads = [p for p in result if p.get("tier") == "must_read" and p.get("arxiv_id")]

        if must_reads:
            interests_summary = primary_kw
            review_tasks = [
                deep_review(p["arxiv_id"], interests_summary) for p in must_reads
            ]
            reviews = await asyncio.gather(*review_tasks, return_exceptions=True)
            for p, review in zip(must_reads, reviews):
                if isinstance(review, str) and review:
                    p["deep_review"] = review

        return result

    # ------------------------------------------------------------------
    # Stage 1 – Coarse screening (Haiku, cheap)
    # ------------------------------------------------------------------

    def _stage1_coarse(self, candidates: List[Dict], seed_titles: str, primary_kw: str) -> List[Dict]:
        """Quick relevance scoring with Haiku. Returns papers with score >= threshold.

        Papers that cite a seed paper or are by a tracked author automatically
        pass through regardless of Haiku score.
        """
        papers_text = ""
        for i, p in enumerate(candidates):
            papers_text += f"\n[{i+1}] {p['title']}\n"
            # Only first 200 chars of abstract for cost savings
            abstract = (p.get("abstract") or "")[:200]
            papers_text += f"    Abstract: {abstract}...\n"
            if p.get("cites_seed"):
                papers_text += f"    ** Cites seed paper: {p['cites_seed']} **\n"
            if p.get("seed_author"):
                papers_text += f"    ** New work by tracked author: {p['seed_author']} **\n"

        prompt = f"""You are a research paper screener. The researcher works on:
- Primary interests: {primary_kw}
- Seed papers:
{seed_titles}

Score each paper 1-10 for relevance. Papers citing seed papers or by tracked authors should score higher.

Papers:
{papers_text}

Respond in JSON array only, no other text:
[{{"index": 1, "score": 7}}, ...]

Include ALL {len(candidates)} papers with their scores."""

        response = self.client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        json_start = text.find("[")
        json_end = text.rfind("]") + 1
        scores = json.loads(text[json_start:json_end])

        # Apply scores to candidates
        for r in scores:
            idx = r["index"] - 1
            if 0 <= idx < len(candidates):
                candidates[idx]["haiku_score"] = r["score"]

        # Determine survivors: score >= threshold OR special papers (cites_seed / seed_author)
        survivors = []
        for p in candidates:
            is_special = bool(p.get("cites_seed") or p.get("seed_author"))
            haiku_score = p.get("haiku_score", 0)
            if haiku_score >= COARSE_THRESHOLD or is_special:
                survivors.append(p)

        return survivors

    # ------------------------------------------------------------------
    # Stage 2 – Fine ranking (Sonnet, precise)
    # ------------------------------------------------------------------

    def _stage2_fine(self, survivors: List[Dict], seed_titles: str, primary_kw: str) -> List[Dict]:
        """Detailed scoring, tiering, and Chinese insight generation with Sonnet."""
        papers_text = ""
        for i, p in enumerate(survivors):
            papers_text += f"\n[{i+1}] {p['title']}\n"
            papers_text += f"    Authors: {', '.join(p.get('authors', [])[:3])}\n"
            # Full abstract for precise analysis
            abstract = p.get("abstract") or ""
            papers_text += f"    Abstract: {abstract}\n"
            if p.get("cites_seed"):
                papers_text += f"    ** Cites seed paper: {p['cites_seed']} **\n"
            if p.get("cites_seed_unverified"):
                papers_text += f"    ** Possibly cites seed paper (unverified): {p['cites_seed_unverified']} **\n"
            if p.get("seed_author"):
                papers_text += f"    ** New work by tracked author: {p['seed_author']} **\n"
            if p.get("hf_votes"):
                papers_text += f"    HuggingFace votes: {p['hf_votes']}\n"
            haiku = p.get("haiku_score")
            if haiku is not None:
                papers_text += f"    Stage-1 relevance score: {haiku}/10\n"

        prompt = f"""You are a research paper recommender for a PhD student working on:
- Primary interests: {primary_kw}
- Seed papers (core research direction):
{seed_titles}

These {len(survivors)} papers already passed an initial relevance screen. For each paper:
1. Score from 1-10 for relevance
2. Assign a tier:
   - "must_read": Directly relevant to current research, cites seed papers, or from tracked authors
   - "worth_noting": Related to research direction, potentially useful
   - "trending": Hot in the community but not directly related
   - "skip": Not relevant enough
3. Write an "insight" in Chinese that includes:
   - 核心方法/贡献（1-2句话）
   - 与我研究的潜在联系
   - 可以brainstorm的方向或启发（如果有的话）

Papers:
{papers_text}

Respond in JSON format:
[
  {{"index": 1, "score": 9, "tier": "must_read", "reason": "brief reason in English", "insight": "中文洞察：核心方法...与你研究的联系...可以思考的方向..."}},
  ...
]

Only include papers with tier != "skip". Be selective - must_read should have at most 2-3 papers.
For must_read papers, write detailed insights (3-5 sentences). For worth_noting, keep insights brief (1-2 sentences)."""

        response = self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        json_start = text.find("[")
        json_end = text.rfind("]") + 1
        rankings = json.loads(text[json_start:json_end])

        for r in rankings:
            idx = r["index"] - 1
            if 0 <= idx < len(survivors):
                survivors[idx]["llm_score"] = r["score"]
                survivors[idx]["tier"] = r["tier"]
                survivors[idx]["reason"] = r["reason"]
                survivors[idx]["insight"] = r.get("insight", "")

        return [p for p in survivors if p.get("tier") and p["tier"] != "skip"]

    # ------------------------------------------------------------------
    # Heuristic fallback (no LLM needed)
    # ------------------------------------------------------------------

    def _heuristic_rank(self, candidates: List[Dict]):
        """Fallback ranking when LLM is unavailable."""
        for p in candidates:
            score = p.get("heuristic_score", 0)

            # Must-read: cites seed or seed author or very high score
            if p.get("cites_seed") or p.get("seed_author") or score >= 10:
                p["tier"] = "must_read"
                if p.get("cites_seed"):
                    p["reason"] = f"Cites your seed paper: {p['cites_seed']}"
                elif p.get("seed_author"):
                    p["reason"] = f"New work by tracked author: {p['seed_author']}"
                else:
                    p["reason"] = "Strong keyword match"

            # Trending: high HF votes
            elif p.get("hf_votes", 0) >= 10:
                p["tier"] = "trending"
                p["reason"] = f"Community buzz ({p['hf_votes']} HF votes)"

            # Worth noting: moderate score
            elif score >= 3:
                p["tier"] = "worth_noting"
                p["reason"] = "Keyword match"

            else:
                p["tier"] = "skip"
