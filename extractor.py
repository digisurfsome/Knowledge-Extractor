"""
Knowledge Extractor - Core extraction logic.
Extracts images and their associated text from web pages.
"""

import os
import re
import time
import hashlib
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import Optional
from bs4 import BeautifulSoup, Tag


class KnowledgeExtractor:
    """Extracts structured knowledge from web pages."""

    # User agent to avoid bot blocking
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Minimum image dimensions to filter out icons/spacers
    MIN_IMAGE_SIZE = 100

    # Supported image formats
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

    def __init__(self, output_dir: str):
        """Initialize extractor with output directory."""
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def extract_page(self, url: str, download_images: bool = True) -> dict:
        """
        Extract all content from a single page.

        Args:
            url: The URL to extract from
            download_images: Whether to download images locally

        Returns:
            Structured dict with all extracted content
        """
        print(f"Fetching: {url}")

        # Fetch the page
        response = requests.get(url, headers=self.HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Get page metadata
        page_title = self._get_page_title(soup)

        # Find all content sections with images
        sections = self._extract_sections(soup, url, download_images)

        return {
            "source_url": url,
            "page_title": page_title,
            "extracted_date": datetime.now().isoformat(),
            "sections": sections
        }

    def _get_page_title(self, soup: BeautifulSoup) -> str:
        """Extract the page title."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try regular title tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()

        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        return "Unknown"

    def _extract_sections(self, soup: BeautifulSoup, base_url: str, download_images: bool) -> list:
        """
        Extract all content sections, grouping images with their related text.
        """
        sections = []
        section_id = 0

        # Remove unwanted elements
        for unwanted in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            unwanted.decompose()

        # Find main content area
        main_content = self._find_main_content(soup)

        # Find all images in main content
        images = main_content.find_all("img")

        for img in images:
            # Skip tiny images (icons, spacers)
            if self._is_small_image(img):
                continue

            # Skip images that look like ads or tracking
            if self._is_ad_image(img):
                continue

            section_id += 1
            section = self._extract_section_for_image(img, base_url, section_id, download_images)

            if section:
                sections.append(section)

        # Also extract text-only sections with headings (no images)
        # This captures definitions and explanations that might not have images
        text_sections = self._extract_text_sections(main_content, base_url, section_id)

        # Merge, avoiding duplicates
        existing_headings = {s.get("heading", "").lower() for s in sections}
        for ts in text_sections:
            if ts.get("heading", "").lower() not in existing_headings:
                section_id += 1
                ts["id"] = section_id
                sections.append(ts)

        return sections

    def _find_main_content(self, soup: BeautifulSoup) -> Tag:
        """Find the main content area of the page."""
        # Try common main content selectors
        selectors = [
            "article",
            "main",
            "[role='main']",
            ".post-content",
            ".entry-content",
            ".article-content",
            ".content",
            "#content",
            ".post",
            ".article"
        ]

        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                return content

        # Fallback to body
        return soup.body or soup

    def _is_small_image(self, img: Tag) -> bool:
        """Check if image is too small (likely icon/spacer)."""
        width = img.get("width", "")
        height = img.get("height", "")

        try:
            if width and int(str(width).replace("px", "")) < self.MIN_IMAGE_SIZE:
                return True
            if height and int(str(height).replace("px", "")) < self.MIN_IMAGE_SIZE:
                return True
        except ValueError:
            pass

        # Check for common icon classes
        img_class = " ".join(img.get("class", []))
        if any(x in img_class.lower() for x in ["icon", "logo", "avatar", "emoji"]):
            return True

        return False

    def _is_ad_image(self, img: Tag) -> bool:
        """Check if image looks like an ad or tracking pixel."""
        src = img.get("src", "") or img.get("data-src", "") or ""
        src_lower = src.lower()

        ad_indicators = [
            "ad.", "ads.", "advertisement", "tracking", "pixel",
            "analytics", "doubleclick", "googlesyndication",
            "facebook.com/tr", "amazon-adsystem"
        ]

        return any(indicator in src_lower for indicator in ad_indicators)

    def _extract_section_for_image(
        self, img: Tag, base_url: str, section_id: int, download_images: bool
    ) -> Optional[dict]:
        """Extract a content section centered around an image."""

        # Get image URL
        img_src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not img_src:
            return None

        # Convert to absolute URL
        img_url = urljoin(base_url, img_src)

        # Get alt text
        alt_text = img.get("alt", "").strip() or "no_alt"

        # Get caption
        caption = self._get_image_caption(img)

        # Get surrounding heading
        heading = self._get_nearest_heading(img)

        # Get surrounding paragraph text
        surrounding_text = self._get_surrounding_text(img)

        # Try to extract term and definition from the context
        term, definition = self._extract_term_and_definition(heading, surrounding_text, caption)

        # Download image if requested
        local_file = None
        if download_images:
            local_file = self._download_image(img_url, section_id, term or heading or "image")
            # Add delay to be polite to servers
            time.sleep(0.5)

        return {
            "id": section_id,
            "heading": heading,
            "term": term,
            "definition": definition,
            "surrounding_text": surrounding_text,
            "visual_indicators": self._extract_visual_indicators(surrounding_text, caption),
            "image": {
                "local_file": local_file,
                "original_url": img_url,
                "alt_text": alt_text,
                "caption": caption
            }
        }

    def _get_image_caption(self, img: Tag) -> str:
        """Find caption for an image."""
        # Check for figcaption
        figure = img.find_parent("figure")
        if figure:
            figcaption = figure.find("figcaption")
            if figcaption:
                return figcaption.get_text().strip()

        # Check for wp-caption-text (WordPress)
        parent = img.parent
        if parent:
            caption_div = parent.find(class_=re.compile(r"caption|wp-caption-text"))
            if caption_div:
                return caption_div.get_text().strip()

        # Check next sibling for caption-like content
        next_sib = img.find_next_sibling()
        if next_sib and next_sib.name in ["em", "small", "span"]:
            text = next_sib.get_text().strip()
            if len(text) < 200:  # Reasonable caption length
                return text

        return ""

    def _get_nearest_heading(self, img: Tag) -> str:
        """Find the nearest heading above the image."""
        # Walk up and back to find headings
        for heading_tag in ["h2", "h3", "h4", "h5"]:
            # Check previous siblings
            heading = img.find_previous(heading_tag)
            if heading:
                return heading.get_text().strip()

        return ""

    def _get_surrounding_text(self, img: Tag) -> str:
        """Get paragraph text surrounding the image."""
        texts = []

        # Get text from parent paragraph
        parent_p = img.find_parent("p")
        if parent_p:
            text = parent_p.get_text().strip()
            if text:
                texts.append(text)

        # Get previous paragraphs (up to 2)
        prev_count = 0
        for prev in img.find_all_previous("p"):
            if prev_count >= 2:
                break
            text = prev.get_text().strip()
            if text and len(text) > 20:
                texts.insert(0, text)
                prev_count += 1

        # Get next paragraphs (up to 2)
        next_count = 0
        for next_p in img.find_all_next("p"):
            if next_count >= 2:
                break
            text = next_p.get_text().strip()
            if text and len(text) > 20:
                texts.append(text)
                next_count += 1

        return " ".join(texts)

    def _extract_term_and_definition(
        self, heading: str, surrounding_text: str, caption: str
    ) -> tuple[str, str]:
        """Try to extract a term and its definition from the context."""
        term = ""
        definition = ""

        # Use heading as term if it looks like one
        if heading:
            # Clean up heading
            term = re.sub(r"^\d+[\.\)]\s*", "", heading)  # Remove numbering
            term = term.strip()

        # Look for definition patterns in surrounding text
        combined_text = f"{surrounding_text} {caption}"

        # Pattern: "X is Y" or "X refers to Y"
        definition_patterns = [
            rf"{re.escape(term)}\s+is\s+(.+?\.)",
            rf"{re.escape(term)}\s+refers to\s+(.+?\.)",
            rf"{re.escape(term)}[:\-]\s*(.+?\.)",
        ]

        for pattern in definition_patterns:
            if term:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    definition = match.group(1).strip()
                    break

        # If no definition found, use first sentence of surrounding text
        if not definition and surrounding_text:
            sentences = re.split(r"(?<=[.!?])\s+", surrounding_text)
            if sentences:
                definition = sentences[0]

        return term, definition

    def _extract_visual_indicators(self, surrounding_text: str, caption: str) -> str:
        """Extract visual indicators - what to look for in the image."""
        combined = f"{surrounding_text} {caption}".lower()

        # Look for phrases that describe visual elements
        indicator_patterns = [
            r"look for[:\s]+([^.]+)",
            r"notice[:\s]+([^.]+)",
            r"you can see[:\s]+([^.]+)",
            r"creates?\s+(?:a\s+)?([^.]+shadow[^.]*)",
            r"characterized by[:\s]+([^.]+)",
            r"features?\s+([^.]+)"
        ]

        indicators = []
        for pattern in indicator_patterns:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            indicators.extend(matches)

        return ". ".join(indicators) if indicators else ""

    def _download_image(self, url: str, section_id: int, name_hint: str) -> Optional[str]:
        """Download an image and return the local filename."""
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=30, stream=True)
            response.raise_for_status()

            # Determine file extension
            content_type = response.headers.get("content-type", "")
            ext = self._get_extension_from_url_or_type(url, content_type)

            # Create clean filename
            clean_name = re.sub(r"[^\w\s-]", "", name_hint.lower())
            clean_name = re.sub(r"[\s]+", "_", clean_name)[:50]

            filename = f"{section_id:03d}_{clean_name}{ext}"
            filepath = os.path.join(self.images_dir, filename)

            # Download
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  Downloaded: {filename}")
            return f"images/{filename}"

        except Exception as e:
            print(f"  Failed to download {url}: {e}")
            return None

    def _get_extension_from_url_or_type(self, url: str, content_type: str) -> str:
        """Get file extension from URL or content-type."""
        # Try URL first
        parsed = urlparse(url)
        path = parsed.path.lower()

        for ext in self.IMAGE_EXTENSIONS:
            if path.endswith(ext):
                return ext

        # Try content-type
        type_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg"
        }

        for mime, ext in type_map.items():
            if mime in content_type:
                return ext

        return ".jpg"  # Default

    def _extract_text_sections(self, content: Tag, base_url: str, start_id: int) -> list:
        """Extract text-only sections with headings (educational content without images)."""
        sections = []

        # Find all headings
        for heading in content.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text().strip()
            if not heading_text:
                continue

            # Get text content after this heading until next heading
            text_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ["h2", "h3", "h4"]:
                    break
                if sibling.name == "p":
                    text = sibling.get_text().strip()
                    if text:
                        text_parts.append(text)

            if text_parts:
                combined_text = " ".join(text_parts)
                term, definition = self._extract_term_and_definition(heading_text, combined_text, "")

                sections.append({
                    "id": 0,  # Will be set by caller
                    "heading": heading_text,
                    "term": term,
                    "definition": definition,
                    "surrounding_text": combined_text,
                    "visual_indicators": self._extract_visual_indicators(combined_text, ""),
                    "image": None  # No image for this section
                })

        return sections
