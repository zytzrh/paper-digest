# Paper Digest

Daily research paper digest with citation tracking and smart filtering.

## Features

- **Seed-paper driven**: Track citations and new works from authors you follow
- **Multi-source**: arXiv daily, Semantic Scholar, HuggingFace Daily Papers
- **Smart filtering**: Keyword matching + citation network + LLM relevance scoring
- **Tiered output**: Must-read / Worth-noting / Trending
- **Self-evolving**: Feedback loop updates seed papers and preferences
- **Automated**: GitHub Actions runs daily at 6AM ET

## Setup

1. Configure your research interests in `config/interests.yaml`
2. Add seed papers in `config/seeds.yaml`
3. Set API keys as GitHub Secrets (or `.env` for local runs)
4. Run: `python src/main.py`

## Configuration

### `config/interests.yaml`
Define your research areas, keywords, and arXiv categories.

### `config/seeds.yaml`
List important papers that define your research direction. The system tracks:
- New papers that cite your seeds
- New papers by seed paper authors
- Papers semantically related to your seeds

## Output

### Email
Daily digest sent to your Gmail with tiered recommendations.

### Local
Markdown files saved to `output/YYYY-MM-DD.md`

## Output Tiers

| Tier | Criteria | Count |
|------|----------|-------|
| Must-read | Cites seed paper / seed author new work / highly relevant | 1-2 |
| Worth-noting | Direction-related, keyword match + LLM scoring | 3-5 |
| Trending | Community buzz (HF votes, GitHub stars) | 2-3 |
