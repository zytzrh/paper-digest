"""
DigestMemory - Short-term memory for paper deduplication.
Prevents recommending the same paper within a configurable window.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta


STATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'state')
MEMORY_FILE = os.path.join(STATE_DIR, 'memory.json')

# Papers shown within this window are considered "seen"
SEEN_WINDOW_DAYS = 14
# Records older than this are cleaned up
CLEANUP_AFTER_DAYS = 30


def _paper_key(paper: dict) -> str:
    """Generate a stable key for a paper. Prefer arxiv_id, fall back to title hash."""
    arxiv_id = paper.get("arxiv_id") or paper.get("id") or ""
    if arxiv_id:
        return arxiv_id.strip()
    title = paper.get("title", "").lower().strip()
    return "hash:" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]


class DigestMemory:
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        self.data: dict = self._load()

    def _load(self) -> dict:
        """Load memory from disk. Returns empty dict if file missing or corrupt."""
        if not os.path.exists(self.memory_file):
            return {}
        try:
            with open(self.memory_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self):
        """Persist memory to disk, creating directories if needed."""
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        with open(self.memory_file, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def is_seen(self, paper: dict) -> bool:
        """Check if a paper was shown within the recent SEEN_WINDOW_DAYS."""
        key = _paper_key(paper)
        record = self.data.get(key)
        if record is None:
            return False
        try:
            date_shown = datetime.fromisoformat(record["date_shown"])
        except (KeyError, ValueError):
            return False
        return (datetime.now() - date_shown) < timedelta(days=SEEN_WINDOW_DAYS)

    def filter_unseen(self, papers: list[dict]) -> tuple[list[dict], int]:
        """Filter out previously seen papers. Returns (unseen_papers, num_removed)."""
        unseen = []
        removed = 0
        for p in papers:
            if self.is_seen(p):
                removed += 1
            else:
                unseen.append(p)
        return unseen, removed

    def record(self, papers: list[dict]):
        """Record papers as shown today."""
        now = datetime.now().isoformat()
        for p in papers:
            key = _paper_key(p)
            self.data[key] = {
                "title": p.get("title", ""),
                "arxiv_id": p.get("arxiv_id") or p.get("id") or "",
                "tier": p.get("tier", ""),
                "date_shown": now,
            }
        self._save()

    def cleanup(self):
        """Remove records older than CLEANUP_AFTER_DAYS."""
        cutoff = datetime.now() - timedelta(days=CLEANUP_AFTER_DAYS)
        keys_to_remove = []
        for key, record in self.data.items():
            try:
                date_shown = datetime.fromisoformat(record["date_shown"])
                if date_shown < cutoff:
                    keys_to_remove.append(key)
            except (KeyError, ValueError):
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self.data[key]
        if keys_to_remove:
            self._save()
        return len(keys_to_remove)
