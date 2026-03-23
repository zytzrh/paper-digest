# Paper Digest

Automated daily research paper digest with citation tracking, PDF deep review, and personalized recommendations.

## Architecture

```
Collect (arXiv, Semantic Scholar, HuggingFace, Blogs/RSS)
    ↓
Keyword Filter
    ↓
Memory Dedup (skip papers from recent 14 days)
    ↓
Citation Network (verify seed paper citations)
    ↓
Two-Stage LLM Ranking
  ├─ Stage 1: Haiku coarse screen (30 → ~10 papers)
  └─ Stage 2: Sonnet fine ranking + Chinese insights
    ↓
PDF Deep Review (download & analyze top papers)
    ↓
External Enrichment (GitHub repos, community signals)
    ↓
Format + Email (with 👍/👎 feedback links)
```

## Features

### Data Sources
- **arXiv** — Daily papers from configured categories (cs.LG, cs.AI, cs.CL, stat.ML)
- **Semantic Scholar** — Citation tracking for seed papers + author following
- **HuggingFace Daily Papers** — Community trending papers with vote counts
- **Blogs/RSS** — 9 curated AI research blogs (Lilian Weng, OpenAI, DeepMind, Anthropic, etc.)

### Smart Filtering
- **Keyword matching** — Primary/secondary keywords with configurable exclusions
- **Citation verification** — Cross-checks Semantic Scholar citations against actual paper references to eliminate false positives
- **Short-term memory** — Tracks shown papers for 14 days to prevent repeated recommendations

### Two-Stage LLM Ranking
- **Stage 1 (Haiku)** — Cheap coarse screening, filters ~60-70% of irrelevant papers
- **Stage 2 (Sonnet)** — Precise ranking with tier assignment and Chinese research insights
- **Heuristic fallback** — Works even without API credits

### PDF Deep Review
- Downloads and extracts first 10 pages of must-read papers
- Generates detailed Chinese review covering:
  - Core method & contributions
  - Technical details (key formulas/algorithms)
  - Strengths & limitations
  - Connections to your research direction

### External Enrichment
- **GitHub** — Finds related repositories with star counts
- **Tavily** — Community discussions, blog posts, implementations (optional)
- **Semantic Scholar** — Citation count and influence metrics

### Feedback Loop
- Each paper in the digest includes 👍/👎 links
- Clicking creates a GitHub Issue with feedback label
- Daily Action processes feedback and updates learned seeds
- System personalizes over time based on your preferences

### Output Tiers

| Tier | Criteria | Detail Level |
|------|----------|--------------|
| Must Read | Cites seed / seed author / highly relevant | Full: insight + deep review + abstract |
| Worth Noting | Related to research direction | Brief: insight only |
| Trending | Community buzz (HF votes, GitHub stars) | Brief: reason only |

## Setup

### 1. Configure Research Interests

```yaml
# config/interests.yaml
keywords:
  primary:
    - flow matching
    - discrete diffusion
    - multi-agent
  secondary:
    - diffusion model
    - agent collaboration
```

### 2. Add Seed Papers

```yaml
# config/seeds.yaml
papers:
  - title: "Your Important Paper"
    arxiv_id: "2401.12345"
```

### 3. Set Environment Variables

```bash
# .env (local) or GitHub Secrets (Actions)
ANTHROPIC_API_KEY=sk-ant-xxx
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Optional
TAVILY_API_KEY=tvly-xxx  # for community search enrichment
```

### 4. Run

```bash
# Local
pip install -r requirements.txt
python src/main.py

# Or let GitHub Actions run daily at 6AM ET
```

## File Structure

```
paper-digest/
├── config/
│   ├── interests.yaml    # Keywords, categories, exclusions
│   ├── seeds.yaml        # Seed papers for citation tracking
│   └── blogs.yaml        # RSS/Atom feeds to follow
├── src/
│   ├── main.py           # Pipeline orchestrator (7 stages)
│   ├── collectors.py     # arXiv, Semantic Scholar, HuggingFace
│   ├── blog_collector.py # RSS/Atom blog feed collector
│   ├── filters.py        # Keyword + citation network filters
│   ├── memory.py         # Short-term dedup (14-day window)
│   ├── ranker.py         # Two-stage LLM ranking (Haiku + Sonnet)
│   ├── pdf_reader.py     # PDF download + deep review generation
│   ├── enricher.py       # GitHub + Tavily + S2 enrichment
│   ├── feedback.py       # Feedback link generation + seed management
│   ├── formatter.py      # Markdown digest formatter
│   ├── emailer.py        # Gmail SMTP sender
│   └── config_loader.py  # YAML config loader
├── scripts/
│   └── apply_feedback.py # Process GitHub Issue feedback
├── state/
│   ├── memory.json       # Recently shown papers
│   └── learned_seeds.json # User feedback preferences
├── output/               # Daily digest markdown files
└── .github/workflows/
    ├── daily_digest.yml  # Daily at 6AM ET
    └── apply_feedback.yml # Daily at 5AM ET (before digest)
```

## Cost Estimate

| Component | Model | Cost/day |
|-----------|-------|----------|
| Coarse filter | Haiku | ~$0.01 |
| Fine ranking | Sonnet | ~$0.05 |
| PDF deep review (2-3 papers) | Haiku | ~$0.03 |
| **Total** | | **~$0.10/day (~$3/month)** |
