#!/usr/bin/env python3
"""
Process GitHub Issues labeled 'feedback-positive' or 'feedback-negative'
and update learned seeds. Run by GitHub Actions.

Usage: python scripts/apply_feedback.py
Requires: GITHUB_TOKEN environment variable
"""

import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from feedback import FeedbackManager


def get_feedback_issues():
    """Fetch open feedback issues via gh CLI."""
    issues = []
    for label in ["feedback-positive", "feedback-negative"]:
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--label", label, "--state", "open", "--json", "title,body,number,labels"],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            for issue in data:
                sentiment = "positive" if "feedback-positive" in [l["name"] for l in issue.get("labels", [])] else "negative"
                # Parse title: remove emoji prefix
                title = issue["title"]
                for prefix in ["👍 ", "👎 ", "👍+", "👎+"]:
                    if title.startswith(prefix):
                        title = title[len(prefix):]
                        break

                # Parse arxiv_id from body
                body = issue.get("body", "")
                arxiv_id = ""
                if "arxiv_id:" in body:
                    arxiv_id = body.split("arxiv_id:")[-1].strip()

                issues.append({
                    "number": issue["number"],
                    "title": title,
                    "arxiv_id": arxiv_id,
                    "sentiment": sentiment,
                })
        except Exception as e:
            print(f"  Error fetching {label} issues: {e}")

    return issues


def close_issue(number):
    """Close a processed feedback issue."""
    try:
        subprocess.run(
            ["gh", "issue", "close", str(number), "--comment", "Feedback applied. Thanks!"],
            capture_output=True, check=True
        )
    except Exception as e:
        print(f"  Error closing issue #{number}: {e}")


def main():
    print("=== Applying Feedback ===\n")

    issues = get_feedback_issues()
    if not issues:
        print("No feedback issues found.")
        return

    manager = FeedbackManager()

    for issue in issues:
        title = issue["title"]
        arxiv_id = issue["arxiv_id"]
        sentiment = issue["sentiment"]

        if sentiment == "positive":
            manager.add_positive(title, arxiv_id)
            print(f"  👍 Added positive seed: {title}")
        else:
            manager.add_negative(title, arxiv_id)
            print(f"  👎 Added negative seed: {title}")

        close_issue(issue["number"])

    print(f"\nProcessed {len(issues)} feedback items.")
    print(f"  Positive seeds: {len(manager.seeds['positive'])}")
    print(f"  Negative seeds: {len(manager.seeds['negative'])}")


if __name__ == "__main__":
    main()
