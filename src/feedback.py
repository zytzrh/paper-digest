"""
Feedback system: collect user feedback via GitHub Issues and update seed preferences.

Workflow:
1. Digest email contains 👍/👎 links that create GitHub Issues
2. GitHub Action runs apply_feedback.py to process issues and update seeds
3. Seeds influence future Semantic Scholar recommendations
"""

import json
import os
from datetime import datetime


STATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'state')
SEEDS_FILE = os.path.join(STATE_DIR, 'learned_seeds.json')


class FeedbackManager:
    """Manage learned paper preferences from user feedback."""

    def __init__(self):
        self.seeds = self._load()

    def _load(self) -> dict:
        if not os.path.exists(SEEDS_FILE):
            return {"positive": [], "negative": []}
        try:
            with open(SEEDS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"positive": [], "negative": []}

    def _save(self):
        os.makedirs(os.path.dirname(SEEDS_FILE), exist_ok=True)
        with open(SEEDS_FILE, "w") as f:
            json.dump(self.seeds, f, indent=2, ensure_ascii=False)

    def add_positive(self, title: str, arxiv_id: str = ""):
        """User liked this paper — boost similar papers in future."""
        entry = {
            "title": title,
            "arxiv_id": arxiv_id,
            "added": datetime.now().isoformat(),
        }
        # Avoid duplicates
        existing_titles = {s["title"].lower() for s in self.seeds["positive"]}
        if title.lower() not in existing_titles:
            self.seeds["positive"].append(entry)
            self._save()

    def add_negative(self, title: str, arxiv_id: str = ""):
        """User disliked this paper — suppress similar papers in future."""
        entry = {
            "title": title,
            "arxiv_id": arxiv_id,
            "added": datetime.now().isoformat(),
        }
        existing_titles = {s["title"].lower() for s in self.seeds["negative"]}
        if title.lower() not in existing_titles:
            self.seeds["negative"].append(entry)
            self._save()

    def get_boost_titles(self) -> list:
        """Get titles of papers user liked (for keyword boosting)."""
        return [s["title"] for s in self.seeds.get("positive", [])]

    def get_suppress_titles(self) -> list:
        """Get titles of papers user disliked (for suppression)."""
        return [s["title"] for s in self.seeds.get("negative", [])]

    def get_extra_seed_arxiv_ids(self) -> list:
        """Get arxiv IDs of liked papers to use as extra seeds for citation tracking."""
        return [s["arxiv_id"] for s in self.seeds.get("positive", []) if s.get("arxiv_id")]


def generate_feedback_links(papers: list, repo: str = "zytzrh/paper-digest") -> dict:
    """Generate GitHub Issue creation links for feedback on each paper.

    Returns dict mapping paper title -> {thumbs_up_url, thumbs_down_url}
    """
    links = {}
    for p in papers:
        title = p.get("title", "")
        arxiv_id = p.get("arxiv_id", "")
        encoded_title = title.replace(" ", "+")

        up_title = f"👍+{encoded_title}"
        down_title = f"👎+{encoded_title}"
        body = f"arxiv_id: {arxiv_id}" if arxiv_id else ""

        base = f"https://github.com/{repo}/issues/new"
        links[title] = {
            "thumbs_up": f"{base}?title={up_title}&body={body}&labels=feedback-positive",
            "thumbs_down": f"{base}?title={down_title}&body={body}&labels=feedback-negative",
        }
    return links
