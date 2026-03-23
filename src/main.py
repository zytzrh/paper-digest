"""
Paper Digest - Daily research paper digest with citation tracking and smart filtering.
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from collectors import ArxivCollector, SemanticScholarCollector, HuggingFaceCollector
from blog_collector import BlogCollector
from filters import KeywordFilter, CitationFilter
from ranker import LLMRanker
from enricher import PaperEnricher
from formatter import DigestFormatter
from emailer import send_digest
from config_loader import load_config
from memory import DigestMemory


async def main():
    print(f"=== Paper Digest - {datetime.now().strftime('%Y-%m-%d')} ===\n")

    # Load configuration
    interests = load_config("config/interests.yaml")
    seeds = load_config("config/seeds.yaml")
    blogs_config = load_config("config/blogs.yaml")

    # Step 1: Collect papers from all sources
    print("[1/7] Collecting papers...")
    collectors = [
        ArxivCollector(interests["arxiv_categories"]),
        SemanticScholarCollector(seeds["papers"]),
        HuggingFaceCollector(),
        BlogCollector(blogs_config.get("blogs", [])),
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
    print("\n[2/7] Keyword filtering...")
    kw_filter = KeywordFilter(interests["keywords"], interests.get("exclude_keywords", []))
    filtered = kw_filter.filter(unique_papers)
    print(f"  After keyword filter: {len(filtered)}")

    # Step 3: Short-term memory deduplication
    print("\n[3/7] Memory deduplication...")
    memory = DigestMemory()
    cleaned = memory.cleanup()
    if cleaned:
        print(f"  Cleaned {cleaned} stale memory entries")
    filtered, num_dupes = memory.filter_unseen(filtered)
    if num_dupes > 0:
        print(f"  Removed {num_dupes} papers seen in recent digests")
    print(f"  After dedup: {len(filtered)}")

    # Step 4: Citation network filtering
    print("\n[4/7] Citation network analysis...")
    cite_filter = CitationFilter(seeds["papers"])
    filtered = cite_filter.enrich(filtered)
    print(f"  Papers citing seeds: {sum(1 for p in filtered if p.get('cites_seed'))}")
    print(f"  Seed author new works: {sum(1 for p in filtered if p.get('seed_author'))}")

    # Step 5: LLM ranking (two-stage: Haiku coarse + Sonnet fine + PDF deep review)
    print("\n[5/7] LLM ranking...")
    ranker = LLMRanker()
    ranked = await ranker.rank(filtered, interests, seeds)

    # Step 6: External enrichment
    print("\n[6/7] External enrichment...")
    enricher = PaperEnricher()
    ranked = await enricher.enrich(ranked)
    enriched_count = sum(1 for p in ranked if p.get("external_signals"))
    print(f"  Enriched {enriched_count} papers with external signals")

    # Step 7: Format and output
    print("\n[7/7] Generating digest...")
    formatter = DigestFormatter()
    digest = formatter.format(ranked)

    # Record shown papers in memory
    memory.record(ranked)

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
