"""
Paper Digest - Daily research paper digest with citation tracking and smart filtering.
"""

import asyncio
from datetime import datetime

from collectors import ArxivCollector, SemanticScholarCollector, HuggingFaceCollector
from filters import KeywordFilter, CitationFilter
from ranker import LLMRanker
from formatter import DigestFormatter
from emailer import send_digest
from config_loader import load_config


async def main():
    print(f"=== Paper Digest - {datetime.now().strftime('%Y-%m-%d')} ===\n")

    # Load configuration
    interests = load_config("config/interests.yaml")
    seeds = load_config("config/seeds.yaml")

    # Step 1: Collect papers from all sources
    print("[1/5] Collecting papers...")
    collectors = [
        ArxivCollector(interests["arxiv_categories"]),
        SemanticScholarCollector(seeds["papers"]),
        HuggingFaceCollector(),
    ]
    all_papers = []
    for collector in collectors:
        papers = await collector.collect()
        print(f"  - {collector.name}: {len(papers)} papers")
        all_papers.extend(papers)

    # Deduplicate by title
    seen = set()
    unique_papers = []
    for p in all_papers:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_papers.append(p)
    print(f"  Total unique: {len(unique_papers)}")

    # Step 2: Keyword filtering
    print("\n[2/5] Keyword filtering...")
    kw_filter = KeywordFilter(interests["keywords"], interests.get("exclude_keywords", []))
    filtered = kw_filter.filter(unique_papers)
    print(f"  After keyword filter: {len(filtered)}")

    # Step 3: Citation network filtering
    print("\n[3/5] Citation network analysis...")
    cite_filter = CitationFilter(seeds["papers"])
    filtered = cite_filter.enrich(filtered)
    print(f"  Papers citing seeds: {sum(1 for p in filtered if p.get('cites_seed'))}")
    print(f"  Seed author new works: {sum(1 for p in filtered if p.get('seed_author'))}")

    # Step 4: LLM ranking
    print("\n[4/5] LLM ranking...")
    ranker = LLMRanker()
    ranked = await ranker.rank(filtered, interests, seeds)

    # Step 5: Format and output
    print("\n[5/5] Generating digest...")
    formatter = DigestFormatter()
    digest = formatter.format(ranked)

    # Save to local file
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = f"output/{date_str}.md"
    with open(output_path, "w") as f:
        f.write(digest)
    print(f"  Saved to {output_path}")

    # Send email
    try:
        send_digest(digest, date_str)
        print("  Email sent!")
    except Exception as e:
        print(f"  Email failed: {e}")

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
