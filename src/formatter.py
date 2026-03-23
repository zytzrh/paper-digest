"""
Format ranked papers into a readable digest.
"""

from datetime import datetime
from typing import List, Dict

from feedback import generate_feedback_links


class DigestFormatter:
    """Format papers into a tiered markdown digest."""

    def format(self, papers: List[Dict]) -> str:
        # Generate feedback links for all papers
        self._feedback_links = generate_feedback_links(papers)
        date_str = datetime.now().strftime("%Y-%m-%d (%A)")

        must_read = [p for p in papers if p.get("tier") == "must_read"]
        worth_noting = [p for p in papers if p.get("tier") == "worth_noting"]
        trending = [p for p in papers if p.get("tier") == "trending"]

        lines = [
            f"# Paper Digest - {date_str}\n",
        ]

        # Must Read
        if must_read:
            lines.append("## Must Read\n")
            for p in must_read:
                lines.append(self._format_paper(p, detailed=True))

        # Worth Noting
        if worth_noting:
            lines.append("## Worth Noting\n")
            for p in worth_noting:
                lines.append(self._format_paper(p, detailed=False))

        # Trending
        if trending:
            lines.append("## Trending\n")
            for p in trending:
                lines.append(self._format_paper(p, detailed=False))

        # Stats
        lines.append("---\n")
        lines.append(f"*Generated at {datetime.now().strftime('%H:%M')} | ")
        lines.append(f"Must-read: {len(must_read)} | Worth-noting: {len(worth_noting)} | Trending: {len(trending)}*\n")

        return "\n".join(lines)

    def _format_paper(self, paper: Dict, detailed: bool = False) -> str:
        title = paper.get("title", "Untitled")
        authors = ", ".join(paper.get("authors", [])[:3])
        if len(paper.get("authors", [])) > 3:
            authors += " et al."
        arxiv_id = paper.get("arxiv_id", "")
        reason = paper.get("reason", "")

        lines = [f"### {title}\n"]
        lines.append(f"**Authors:** {authors}")

        if paper.get("blog_url"):
            lines.append(f"**Link:** [{paper.get('blog_name', 'Blog')}]({paper['blog_url']})")
        elif arxiv_id:
            lines.append(f"**Link:** [arXiv:{arxiv_id}](https://arxiv.org/abs/{arxiv_id})")

        if paper.get("cites_seed"):
            lines.append(f"**Cites:** {paper['cites_seed']}")
        if paper.get("seed_author"):
            lines.append(f"**Tracked author:** {paper['seed_author']}")
        if paper.get("hf_votes"):
            lines.append(f"**HF votes:** {paper['hf_votes']}")

        if reason:
            lines.append(f"**Why:** {reason}")

        if paper.get("insight"):
            lines.append(f"\n💡 **Insight:** {paper['insight']}\n")

        if paper.get("deep_review"):
            lines.append(f"📖 **Deep Review:**\n{paper['deep_review']}\n")

        if paper.get("external_signals"):
            lines.append(f"🔗 **External:** {paper['external_signals']}\n")

        # Feedback links
        fb = self._feedback_links.get(title, {})
        if fb:
            lines.append(f"[👍 Useful]({fb['thumbs_up']}) | [👎 Not relevant]({fb['thumbs_down']})\n")

        if detailed and paper.get("abstract"):
            abstract = paper["abstract"][:500]
            lines.append(f"\n> {abstract}...\n")

        lines.append("")
        return "\n".join(lines)
