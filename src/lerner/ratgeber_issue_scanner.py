#!/usr/bin/env python3
"""
ratgeber_issue_scanner.py

Scans DRBD/LINSTOR community sources for recurring pain points.
Outputs a ranked markdown report suitable as a Brian Hellman call agenda
and as seed topics for Ratgeber fine-tuning training data.

Sources:
  1. Linbit Community Forum (Discourse JSON API)
  2. GitHub Issues (LINBIT/drbd, LINBIT/linstor-server)
  3. Mailing list archive (mail-archive.com HTML scrape)

Usage:
  python ratgeber_issue_scanner.py --sources forum github mail --output report.md
  python ratgeber_issue_scanner.py --sources github --max-issues 200
"""

import argparse
import json
import time
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path

import requests
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# CONFIG — edit these or override via environment variables
# ---------------------------------------------------------------------------

CONFIG = {
    "discourse_base_url": "https://community.linbit.com",
    "github_repos": [
        "LINBIT/drbd",
        "LINBIT/linstor-server",
        "LINBIT/drbd-utils",
    ],
    "github_token": os.getenv("GITHUB_TOKEN", ""),          # optional, raises rate limit
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "anthropic_model": "claude-sonnet-4-20250514",
    "max_items_per_source": 300,    # cap to control API cost
    "batch_size": 20,               # items per Claude API call
    "output_dir": Path("./output"),
    "cache_dir": Path("./.cache"),  # raw fetched data cached here
    "rate_limit_delay": 1.0,        # seconds between HTTP requests
}

# ---------------------------------------------------------------------------
# CLASSIFICATION PROMPT — this is where you tune what categories emerge
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = """
You are analyzing DRBD and LINSTOR community support issues to identify recurring pain points.

For each batch of issues/threads I give you, extract the underlying problem category.
Use concise, reusable category names like:
  - split-brain recovery
  - initial sync performance
  - kernel module build / DKMS
  - LINSTOR controller failover
  - Kubernetes CSI integration
  - resource configuration errors
  - network partition handling
  - Proxmox integration
  - quorum / tiebreaker setup
  - snapshot / backup workflow
  - DRBD state machine confusion
  - performance tuning
  - drbd-reactor / promoter
  - installation / packaging
  - documentation gap

Return ONLY a JSON array. Each element:
{
  "id": "<original issue id or thread id>",
  "title": "<original title>",
  "category": "<your category label>",
  "severity": "high|medium|low",   // how painful this sounds
  "summary": "<one sentence describing the specific problem>"
}
"""

# ---------------------------------------------------------------------------
# SOURCE: Discourse Forum
# ---------------------------------------------------------------------------

def fetch_discourse_topics(config: dict) -> list[dict]:
    """
    Fetch recent topics from Linbit community Discourse.
    Discourse exposes /latest.json, /top.json, and category endpoints.
    
    ENRICH: Add category filtering — Discourse has per-category feeds.
    Fetch /categories.json first, find DRBD/LINSTOR category IDs,
    then fetch /c/{category_id}.json for focused results.
    """
    base = config["discourse_base_url"]
    topics = []

    # TODO: enrich — discover category IDs dynamically
    # For now, fetch top topics across all categories
    endpoints = [
        f"{base}/top.json?period=all",
        f"{base}/latest.json",
    ]

    for url in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            topic_list = data.get("topic_list", {}).get("topics", [])
            for t in topic_list:
                topics.append({
                    "id": f"discourse-{t['id']}",
                    "title": t.get("title", ""),
                    "excerpt": t.get("excerpt", ""),
                    "reply_count": t.get("reply_count", 0),
                    "views": t.get("views", 0),
                })
            time.sleep(config["rate_limit_delay"])
        except Exception as e:
            print(f"[discourse] fetch error {url}: {e}")

    # Deduplicate by id
    seen = set()
    unique = []
    for t in topics:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)

    print(f"[discourse] fetched {len(unique)} topics")
    return unique[:config["max_items_per_source"]]


# ---------------------------------------------------------------------------
# SOURCE: GitHub Issues
# ---------------------------------------------------------------------------

def fetch_github_issues(config: dict) -> list[dict]:
    """
    Fetch open + closed issues from configured LINBIT repos.
    
    ENRICH: Add label filtering — GitHub labels like 'bug', 'question'
    are high signal. Also fetch issue comments for richer context.
    """
    issues = []
    headers = {"Accept": "application/vnd.github+json"}
    if config["github_token"]:
        headers["Authorization"] = f"Bearer {config['github_token']}"

    for repo in config["github_repos"]:
        page = 1
        while len(issues) < config["max_items_per_source"]:
            url = f"https://api.github.com/repos/{repo}/issues"
            params = {
                "state": "all",         # open + closed
                "per_page": 100,
                "page": page,
                "sort": "comments",     # most discussed first = highest pain
                "direction": "desc",
            }
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                for issue in batch:
                    # Skip pull requests (GitHub returns them in issues endpoint)
                    if "pull_request" in issue:
                        continue
                    issues.append({
                        "id": f"gh-{repo.replace('/', '-')}-{issue['number']}",
                        "title": issue.get("title", ""),
                        "excerpt": (issue.get("body") or "")[:500],
                        "comments": issue.get("comments", 0),
                        "labels": [l["name"] for l in issue.get("labels", [])],
                        "state": issue.get("state", ""),
                    })
                page += 1
                time.sleep(config["rate_limit_delay"])
            except Exception as e:
                print(f"[github] fetch error {repo} page {page}: {e}")
                break

    print(f"[github] fetched {len(issues)} issues")
    return issues[:config["max_items_per_source"]]


# ---------------------------------------------------------------------------
# SOURCE: Mailing List Archive
# ---------------------------------------------------------------------------

def fetch_mailarchive_threads(config: dict) -> list[dict]:
    """
    Scrape thread subjects from mail-archive.com drbd-user archive.
    
    ENRICH: This is the thinnest scraper — it only gets subject lines.
    Enrich by fetching individual thread pages for body text.
    Also consider fetching the pipermail index at:
      https://lists.linbit.com/pipermail/drbd-user/
    which has monthly archives as downloadable .txt.gz files — 
    much richer than HTML scraping.
    """
    # TODO: implement HTML scraping of mail-archive.com
    # Suggested approach:
    #   1. GET https://www.mail-archive.com/drbd-user@lists.linbit.com/
    #   2. Parse <a> tags for thread subject lines
    #   3. Return list of {id, title, excerpt}
    #
    # Alternatively — download monthly .txt.gz from pipermail and parse locally.
    # That's the richer path and avoids scraping fragility.

    print("[mailarchive] scraper not yet implemented — returning empty")
    return []


# ---------------------------------------------------------------------------
# CLASSIFIER: Claude API
# ---------------------------------------------------------------------------

def classify_items(items: list[dict], config: dict) -> list[dict]:
    """
    Send batches of items to Claude for category extraction.
    Returns enriched items with 'category', 'severity', 'summary' fields.
    
    ENRICH: Tune CLASSIFICATION_SYSTEM_PROMPT categories to match
    what you actually find in the data after first run.
    """
    client = Anthropic(api_key=config["anthropic_api_key"])
    classified = []
    batch_size = config["batch_size"]

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        # Format batch as text for the prompt
        batch_text = "\n\n".join(
            f"ID: {item['id']}\nTitle: {item['title']}\nExcerpt: {item.get('excerpt', '')[:300]}"
            for item in batch
        )
        try:
            response = client.messages.create(
                model=config["anthropic_model"],
                max_tokens=2000,
                system=CLASSIFICATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": batch_text}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            classified.extend(parsed)
            print(f"[classify] batch {i//batch_size + 1}: classified {len(parsed)} items")
        except Exception as e:
            print(f"[classify] error on batch {i}: {e}")
        time.sleep(0.5)

    return classified


# ---------------------------------------------------------------------------
# AGGREGATOR: Build frequency table
# ---------------------------------------------------------------------------

def aggregate(classified: list[dict]) -> dict:
    """
    Count occurrences per category, weighted by severity.
    
    ENRICH: Add view/comment counts as weight multipliers so
    high-engagement issues rank above single-mention ones.
    """
    freq = defaultdict(lambda: {"count": 0, "high": 0, "examples": []})

    for item in classified:
        cat = item.get("category", "uncategorized")
        freq[cat]["count"] += 1
        if item.get("severity") == "high":
            freq[cat]["high"] += 1
        if len(freq[cat]["examples"]) < 3:
            freq[cat]["examples"].append(item.get("summary", item.get("title", "")))

    # Sort by count desc, then high-severity count desc
    sorted_cats = sorted(
        freq.items(),
        key=lambda x: (x[1]["count"], x[1]["high"]),
        reverse=True,
    )
    return dict(sorted_cats)


# ---------------------------------------------------------------------------
# REPORTER: Markdown output
# ---------------------------------------------------------------------------

def write_report(aggregated: dict, output_path: Path, sources_used: list[str]):
    """
    Write ranked markdown report.
    
    ENRICH: Add a second section formatted specifically as Brian call agenda —
    top 10 categories as open questions: "We see X as a top pain point —
    does that match your support ticket data?"
    """
    lines = [
        f"# DRBD/LINSTOR Community Pain Points",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Sources: {', '.join(sources_used)}",
        "",
        "## Ranked Issue Categories",
        "",
        "| Rank | Category | Count | High Severity | Example |",
        "|------|----------|-------|---------------|---------|",
    ]

    for rank, (cat, data) in enumerate(aggregated.items(), 1):
        example = data["examples"][0] if data["examples"] else ""
        example = example.replace("|", "/")[:80]
        lines.append(
            f"| {rank} | {cat} | {data['count']} | {data['high']} | {example} |"
        )

    lines += [
        "",
        "## Brian Hellman Call Agenda (draft)",
        "",
        "ENRICH: Generate this section from top 10 categories above,",
        "formatted as open-ended questions for validation.",
        "",
    ]

    output_path.write_text("\n".join(lines))
    print(f"\n[report] written to {output_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan DRBD/LINSTOR community for pain points")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["forum", "github", "mail"],
        default=["forum", "github"],
        help="Which sources to scan",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=CONFIG["max_items_per_source"],
        help="Max items per source",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="pain_points_report.md",
        help="Output markdown file name",
    )
    parser.add_argument(
        "--no-classify",
        action="store_true",
        help="Skip Claude classification, just fetch and dump raw data",
    )
    args = parser.parse_args()

    CONFIG["max_items_per_source"] = args.max_issues
    CONFIG["output_dir"].mkdir(exist_ok=True)
    CONFIG["cache_dir"].mkdir(exist_ok=True)

    all_items = []

    if "forum" in args.sources:
        all_items += fetch_discourse_topics(CONFIG)

    if "github" in args.sources:
        all_items += fetch_github_issues(CONFIG)

    if "mail" in args.sources:
        all_items += fetch_mailarchive_threads(CONFIG)

    print(f"\n[main] total items fetched: {len(all_items)}")

    # Cache raw fetch
    cache_file = CONFIG["cache_dir"] / "raw_items.json"
    cache_file.write_text(json.dumps(all_items, indent=2))
    print(f"[main] raw items cached to {cache_file}")

    if args.no_classify:
        print("[main] --no-classify set, skipping classification")
        return

    if not CONFIG["anthropic_api_key"]:
        print("[main] ANTHROPIC_API_KEY not set — cannot classify")
        return

    classified = classify_items(all_items, CONFIG)
    aggregated = aggregate(classified)

    output_path = CONFIG["output_dir"] / args.output
    write_report(aggregated, output_path, args.sources)


if __name__ == "__main__":
    main()
