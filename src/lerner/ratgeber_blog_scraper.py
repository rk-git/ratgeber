"""
ratgeber_blog_scraper.py - LINBIT blog harvester

Fetches all posts from the LINBIT blog via WordPress REST API.
Cleans HTML, chunks into passages, and saves to data/docs/blog/
for ingestion by ingest_once.py into ChromaDB.

Part of the Lerner subsystem — feeds Ratgeber's fine-tuning pipeline
with expert knowledge from LINBIT solutions architects and developers.

BDD spec: docs/lerner/lerner.feature

copyright (c) 2026 Always Up Networks LLC. MIT License.

Usage:
  python src/lerner/ratgeber_blog_scraper.py
  python src/lerner/ratgeber_blog_scraper.py --from-cache
  python src/lerner/ratgeber_blog_scraper.py --dry-run
"""

import argparse
from typing import Final, Optional
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BLOG_API_URL  : Final[str]   = "https://linbit.com/wp-json/wp/v2/posts"
POSTS_PER_PAGE  : Final[int]  = 100          # WordPress max per page
CHUNK_SIZE_WORDS : Final[int]  = 500
REQUEST_DELAY  : Final[float]  = 1.0          # seconds between API calls — be polite

PROJECT_ROOT : Final[Path] = Path(__file__).parent.parent.parent
CACHE_DIR  : Final[Path]    = PROJECT_ROOT / ".cache" / "blog"
BLOG_DOCS_DIR : Final[Path] = PROJECT_ROOT / "data" / "docs" / "blog"
POSTS_CACHE  : Final[Path]  = PROJECT_ROOT / ".cache" / "blog_posts.json"

# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class BlogPost:
    post_id:    int
    title:      str
    date:       str
    url:        str
    content:    str     # cleaned plain text


@dataclass
class BlogChunk:
    post_id:     int
    post_title:  str
    post_date:   str
    post_url:    str
    chunk_index: int
    text:        str
    source:      str = "blog:linbit"

@dataclass
class ScrapeResult:
    post_id: int
    title: str
    status: str
    chunks: int = 0

class BlogScraper:
    POSTS_PER_PAGE: Final[int] = 100
    CHUNK_SIZE_WORDS: Final[int] = 500
    REQUEST_DELAY: Final[float] = 1.0
    PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent
    CACHE_DIR: Final[Path] = PROJECT_ROOT / ".cache" / "blog"
    POSTS_CACHE: Final[Path] = PROJECT_ROOT / ".cache" / "blog_posts.json"
    BLOG_DOCS_DIR: Final[Path] = PROJECT_ROOT / "data" / "docs" / "blog"

    def __init__(
        self,
        blog_url: str,
        use_cache: bool = False,
        dry_run: bool = False,
        post_id: int | None = None,
    ) -> None:
        self.blog_url = blog_url
        self.use_cache = use_cache
        self.dry_run = dry_run
        self.post_id = post_id
        self.results: list[ScrapeResult] = []
        self.total_posts = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_posts(self) -> list[BlogPost]:
        """
            Paginate through all LINBIT blog posts via WordPress REST API.
            Cached to .cache/blog_posts.json to avoid re-fetching.

            WordPress REST API returns posts newest-first by default.
            We fetch all pages until no more posts are returned.

            ENRICH: add category filtering — WordPress API supports
            ?categories=ID to fetch only DRBD/LINSTOR related posts.
            Fetch /wp-json/wp/v2/categories first to discover category IDs.
            """
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if self.use_cache and self.POSTS_CACHE.exists():
            self.logger.info("[fetch] loading posts from cache")
            raw = json.loads(self.POSTS_CACHE.read_text())
            posts = [BlogPost(**p) for p in raw]
            self.logger.info(f"[fetch] loaded {len(posts)} posts from cache")
            return posts

        self.logger.info(f"[fetch] fetching posts from {BLOG_API_URL}")
        posts = []
        page = 1

        while True:
            params = {
                "per_page": POSTS_PER_PAGE,
                "page": page,
                "_fields": "id,title,date,link,content",  # only fetch what we need
            }

            try:
                resp = requests.get(BLOG_API_URL, params=params, timeout=15)

                # WordPress returns 400 when page exceeds total pages
                if resp.status_code == 400:
                    self.logger.info(f"[fetch] reached end of posts at page {page}")
                    break

                resp.raise_for_status()
                batch = resp.json()

                if not batch:
                    break

                for post in batch:
                    posts.append(BlogPost(
                        post_id=post["id"],
                        title=post["title"]["rendered"],
                        date=post["date"],
                        url=post["link"],
                        content=post["content"]["rendered"],
                    ))

                self.logger.info(f"[fetch] page {page}: {len(batch)} posts fetched")
                page += 1
                time.sleep(REQUEST_DELAY)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"[fetch] network error on page {page}: {e}")
                break

        # Cache raw posts
        self.POSTS_CACHE.write_text(json.dumps(
            [p.__dict__ for p in posts], indent=2
        ))
        self.logger.info(f"[fetch] total posts fetched: {len(posts)}, cached to {self.POSTS_CACHE}")
        return posts


    def process_posts(self, posts: list[BlogPost]) -> None:
        if self.post_id is not None:
            posts = [p for p in posts if p.post_id == self.post_id]

        self.total_posts = len(posts)
        self.logger.info("[main] processing %d posts", len(posts))
        self.results: list[ScrapeResult] = []

        for i, post in enumerate(posts, 1):
            self.logger.info(
                "[main] %d/%d: %s",
                i,
                len(posts),
                post.title[:60],
            )

            self.results.append(
                self._process_post(post)
            )

    def print_summary(self) -> None:
        """Print a summary report of the scraping run."""

        ok = sum(
            1
            for r in self.results
            if r.status == "ok"
        )

        total_chunks = sum(
            r.chunks
            for r in self.results
        )

        skipped_done = sum(
            1
            for r in self.results
            if r.status == "skipped:already_scraped"
        )

        skipped_empty = sum(
            1
            for r in self.results
            if r.status == "skipped:empty_after_cleaning"
        )

        skipped_no_chunks = sum(
            1
            for r in self.results
            if r.status == "skipped:no_chunks"
        )

        dry_run_count = sum(
            1
            for r in self.results
            if r.status == "dry_run"
        )

        print("\n" + "=" * 60)
        print("BLOG SCRAPER SUMMARY")
        print("=" * 60)
        print(f"  Total posts processed:         {self.total_posts}")
        print(f"  Posts scraped and chunked:     {ok}")
        print(f"  Total chunks saved:            {total_chunks}")
        print(f"  Skipped — already scraped:     {skipped_done}")
        print(f"  Skipped — empty after clean:   {skipped_empty}")
        print(f"  Skipped — no chunks:           {skipped_no_chunks}")

        if dry_run_count:
            print(f"  Dry run (not saved):           {dry_run_count}")

        print("=" * 60)
        print()
        print(f"Chunks saved to: {self.BLOG_DOCS_DIR}")
        print("Run ingest_once.py to load into ChromaDB.")
        print()


    def _clean_html(self, html: str) -> str:
        """
            Strip HTML tags and extract clean plain text from WordPress post content.

            Uses BeautifulSoup to handle nested tags, tables, code blocks cleanly.
            Preserves paragraph breaks for readable chunking.

            ENRICH: extract code blocks separately and tag them as
            source: blog:linbit:code — these are high-value training examples
            showing actual DRBD/LINSTOR commands and configurations.
            """
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Get text with paragraph breaks preserved
        text = soup.get_text(separator="\n")

        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Strip leading/trailing whitespace per line
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        return text.strip()

    def _chunk_post(self, post: BlogPost) -> list[BlogChunk]:
        """
            Split cleaned post text into passages of ~CHUNK_SIZE_WORDS words.
            Splits on paragraph boundaries where possible for natural chunking.

            Each chunk retains post metadata for ChromaDB ingestion.
            """
        paragraphs = [p.strip() for p in re.split(r'\n+', post.content) if p.strip()]
        chunks = []
        buffer = []
        word_count = 0

        for para in paragraphs:
            words = len(para.split())

            buffer.append(para)
            word_count += words

            if word_count >= CHUNK_SIZE_WORDS:
                chunks.append(BlogChunk(
                    post_id=post.post_id,
                    post_title=post.title,
                    post_date=post.date,
                    post_url=post.url,
                    chunk_index=len(chunks),
                    text="\n\n".join(buffer),
                ))
                buffer = []
                word_count = 0

        # Flush remaining buffer
        if buffer:
            chunks.append(BlogChunk(
                post_id=post.post_id,
                post_title=post.title,
                post_date=post.date,
                post_url=post.url,
                chunk_index=len(chunks),
                text="\n\n".join(buffer),
            ))

        return chunks

    def _save_chunks(self, chunks: list[BlogChunk]) -> int:
        """
           Save each chunk as a .txt file to data/docs/blog/.
           Consistent format with transcript fetcher — metadata header + text.
           ingest_once.py picks these up automatically.

           Filename: blog_{post_id}_chunk_{n}.txt
           """
        self.BLOG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        saved = 0

        for chunk in chunks:
            filename = self.BLOG_DOCS_DIR / f"blog_{chunk.post_id}_chunk_{chunk.chunk_index:04d}.txt"

            content = (
                f"# source: {chunk.source}\n"
                f"# post_id: {chunk.post_id}\n"
                f"# post_title: {chunk.post_title}\n"
                f"# post_date: {chunk.post_date}\n"
                f"# post_url: {chunk.post_url}\n"
                f"# chunk_index: {chunk.chunk_index}\n\n"
                f"{chunk.text}"
            )

            filename.write_text(content, encoding="utf-8")
            saved += 1

        return saved

    def _already_scraped(self, post_id: int) -> bool:
        """Check if this post has already been scraped and chunked."""
        existing = list(self.BLOG_DOCS_DIR.glob(f"blog_{post_id}_chunk_*.txt"))
        return len(existing) > 0


    def _process_post(self, post: BlogPost) -> ScrapeResult:
        # Skip already scraped
        if self._already_scraped(post.post_id):
            self.logger.info(f"[skip] post {post.post_id} — already scraped")
            return ScrapeResult(post.post_id, post.title, "skipped:already_scraped")

        if self.dry_run:
            return ScrapeResult(post.post_id, post.title, "dry_run")

        clean_text = self._clean_html(post.content)
        if not clean_text:
            self.logger.warning(f"[clean] post {post.post_id} — empty after cleaning")
            return ScrapeResult(post.post_id, post.title, "skipped:empty_after_cleaning")

        post.content = clean_text
        chunks = self._chunk_post(post)
        if not chunks:
            return ScrapeResult(post.post_id, post.title, "skipped:no_chunks")

        saved = self._save_chunks(chunks)
        return ScrapeResult(post.post_id, post.title, "ok", chunks=saved)


    def run(self) -> None:
        posts = self.fetch_posts()
        if not posts:
            self.logger.error("No posts fetched")
            return
        self.process_posts(posts)
        self.print_summary()

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--post-id", type=int)
    args = parser.parse_args()

    BlogScraper(
        blog_url="https://linbit.com/wp-json/wp/v2/posts",
        use_cache=args.from_cache,
        dry_run=args.dry_run,
        post_id=args.post_id,
    ).run()

if __name__ == "__main__":
    main()
