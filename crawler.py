"""
Smart Crawler - Intelligently crawls course/tutorial websites.
Determines which links are relevant to the course content.
"""

import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Optional


class SmartCrawler:
    """Intelligently crawls educational websites to find all course pages."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self, output_dir: str, max_pages: int = 20):
        """Initialize crawler."""
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.visited_urls = set()

    def crawl_course(self, start_url: str, course_description: str = "") -> list[str]:
        """
        Crawl a course starting from the main page.

        Args:
            start_url: The course main/index page URL
            course_description: Optional description to help determine relevance

        Returns:
            List of URLs that are part of the course
        """
        self.visited_urls = set()
        course_urls = [start_url]
        self.visited_urls.add(self._normalize_url(start_url))

        # Get the base domain for filtering
        base_domain = urlparse(start_url).netloc

        # Fetch the start page
        try:
            response = requests.get(start_url, headers=self.HEADERS, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Failed to fetch start page: {e}")
            return course_urls

        # Extract page context for relevance checking
        page_context = self._extract_page_context(soup)

        # Build relevance keywords from course description and page content
        relevance_keywords = self._build_relevance_keywords(course_description, page_context)

        # Find all links on the page
        links = self._extract_links(soup, start_url, base_domain)

        # Score and filter links by relevance
        scored_links = []
        for link_url, link_text, link_context in links:
            if self._normalize_url(link_url) in self.visited_urls:
                continue

            score = self._score_link_relevance(
                link_url, link_text, link_context, relevance_keywords, base_domain
            )

            if score > 0:
                scored_links.append((score, link_url, link_text))

        # Sort by relevance score (highest first)
        scored_links.sort(reverse=True, key=lambda x: x[0])

        # Take top links up to max_pages
        for score, link_url, link_text in scored_links:
            if len(course_urls) >= self.max_pages:
                break

            normalized = self._normalize_url(link_url)
            if normalized not in self.visited_urls:
                course_urls.append(link_url)
                self.visited_urls.add(normalized)
                print(f"  Found relevant page (score={score}): {link_text[:50]}...")

            # Be polite - small delay between decisions
            time.sleep(0.1)

        return course_urls

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        parsed = urlparse(url)
        # Remove trailing slash, fragments, and some common query params
        path = parsed.path.rstrip("/")
        return f"{parsed.netloc}{path}".lower()

    def _extract_page_context(self, soup: BeautifulSoup) -> dict:
        """Extract context information from a page."""
        # Get title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()

        # Get h1
        h1 = ""
        h1_tag = soup.find("h1")
        if h1_tag:
            h1 = h1_tag.get_text().strip()

        # Get meta description
        description = ""
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        # Get all headings
        headings = []
        for h in soup.find_all(["h2", "h3"]):
            headings.append(h.get_text().strip())

        return {
            "title": title,
            "h1": h1,
            "description": description,
            "headings": headings
        }

    def _build_relevance_keywords(self, course_description: str, page_context: dict) -> set[str]:
        """Build a set of keywords that indicate relevance."""
        keywords = set()

        # Add words from course description
        if course_description:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", course_description.lower())
            keywords.update(words)

        # Add words from page title and h1
        for text in [page_context.get("title", ""), page_context.get("h1", "")]:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            keywords.update(words)

        # Add words from headings
        for heading in page_context.get("headings", []):
            words = re.findall(r"\b[a-zA-Z]{3,}\b", heading.lower())
            keywords.update(words)

        # Remove common stop words
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can", "was",
            "her", "she", "has", "had", "this", "that", "with", "have", "from",
            "they", "will", "what", "about", "which", "when", "make", "like",
            "been", "more", "some", "time", "very", "just", "know", "take",
            "come", "could", "than", "first", "other", "into", "only", "new",
            "these", "also", "back", "after", "most", "read", "article", "post",
            "home", "contact", "privacy", "terms", "page", "click", "here"
        }
        keywords -= stop_words

        return keywords

    def _extract_links(
        self, soup: BeautifulSoup, base_url: str, base_domain: str
    ) -> list[tuple[str, str, str]]:
        """
        Extract all links with their text and context.

        Returns:
            List of (url, link_text, surrounding_context) tuples
        """
        links = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]

            # Skip empty, javascript, mailto, tel links
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Convert to absolute URL
            full_url = urljoin(base_url, href)

            # Skip external domains
            if urlparse(full_url).netloc != base_domain:
                continue

            # Skip non-page URLs
            if self._is_non_page_url(full_url):
                continue

            # Get link text
            link_text = anchor.get_text().strip()
            if not link_text:
                # Try to get from title or aria-label
                link_text = anchor.get("title", "") or anchor.get("aria-label", "")

            # Get surrounding context
            context = self._get_link_context(anchor)

            links.append((full_url, link_text, context))

        return links

    def _is_non_page_url(self, url: str) -> bool:
        """Check if URL is not a page (image, file, etc.)."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        non_page_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
            ".zip", ".rar", ".tar", ".gz",
            ".mp3", ".mp4", ".avi", ".mov",
            ".css", ".js", ".xml", ".json"
        }

        return any(path.endswith(ext) for ext in non_page_extensions)

    def _get_link_context(self, anchor) -> str:
        """Get text context around a link."""
        context_parts = []

        # Get parent text
        parent = anchor.parent
        if parent and parent.name in ["li", "p", "div", "td"]:
            parent_text = parent.get_text().strip()
            if len(parent_text) < 200:
                context_parts.append(parent_text)

        # Get any title attribute
        title = anchor.get("title", "")
        if title:
            context_parts.append(title)

        return " ".join(context_parts)

    def _score_link_relevance(
        self,
        url: str,
        link_text: str,
        context: str,
        keywords: set[str],
        base_domain: str
    ) -> int:
        """
        Score how relevant a link is to the course content.

        Returns:
            Relevance score (0 = not relevant, higher = more relevant)
        """
        score = 0

        # Combine text for analysis
        combined = f"{link_text} {context} {url}".lower()

        # Check for keyword matches
        for keyword in keywords:
            if keyword in combined:
                score += 2

        # Bonus for educational/tutorial patterns in URL
        educational_patterns = [
            r"/lesson", r"/chapter", r"/tutorial", r"/guide",
            r"/learn", r"/course", r"/module", r"/part-\d",
            r"/step-\d", r"/technique", r"/how-to", r"/tips"
        ]
        for pattern in educational_patterns:
            if re.search(pattern, url.lower()):
                score += 5

        # Bonus for numbered content (suggests series)
        if re.search(r"part[-\s]?\d|chapter[-\s]?\d|lesson[-\s]?\d|\d+[-\s]?of[-\s]?\d", combined):
            score += 3

        # Penalty for navigation/utility pages
        penalty_patterns = [
            r"/tag/", r"/category/", r"/author/", r"/page/\d",
            r"/search", r"/login", r"/register", r"/cart",
            r"/shop", r"/product", r"/buy", r"/checkout",
            r"/comment", r"/reply", r"/share", r"/print"
        ]
        for pattern in penalty_patterns:
            if re.search(pattern, url.lower()):
                score -= 10

        # Penalty for social/external links in text
        social_keywords = ["facebook", "twitter", "instagram", "pinterest", "subscribe", "newsletter"]
        for keyword in social_keywords:
            if keyword in combined:
                score -= 5

        # Penalty for very short link text (likely "Read more" etc.)
        if len(link_text) < 5:
            score -= 2

        # Bonus for descriptive link text
        if len(link_text) > 20:
            score += 2

        return max(0, score)


class CourseSitemap:
    """Utility for extracting course structure from sitemap or index pages."""

    @staticmethod
    def extract_from_toc(soup: BeautifulSoup, base_url: str) -> list[str]:
        """
        Extract URLs from a table of contents or index page.

        Looks for common TOC patterns like:
        - Ordered/unordered lists with links
        - Navigation menus with chapter links
        - Numbered sections
        """
        urls = []

        # Look for TOC containers
        toc_selectors = [
            ".toc", ".table-of-contents", "#toc", "#table-of-contents",
            ".course-outline", ".lesson-list", ".chapter-list",
            "nav.course", ".curriculum", ".syllabus"
        ]

        for selector in toc_selectors:
            toc = soup.select_one(selector)
            if toc:
                for link in toc.find_all("a", href=True):
                    full_url = urljoin(base_url, link["href"])
                    if full_url not in urls:
                        urls.append(full_url)
                if urls:
                    return urls

        # Look for ordered lists with multiple links
        for ol in soup.find_all("ol"):
            list_links = ol.find_all("a", href=True)
            if len(list_links) >= 3:  # Likely a course list
                for link in list_links:
                    full_url = urljoin(base_url, link["href"])
                    if full_url not in urls:
                        urls.append(full_url)

        return urls
