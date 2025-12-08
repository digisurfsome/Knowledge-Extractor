"""
Browser Automation Module
Uses Playwright for sites with bot protection (Cloudflare, etc.)
Falls back gracefully if Playwright isn't installed.
"""

import os
import time
from typing import Optional

# Try to import Playwright - it's optional
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


class BrowserFetcher:
    """
    Fetches web pages using a real browser to bypass bot protection.
    Uses Playwright with Chromium in headless mode.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize browser fetcher.

        Args:
            headless: Run browser in headless mode (no GUI)
            timeout: Page load timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout

    @staticmethod
    def is_available() -> bool:
        """Check if Playwright is installed and available."""
        return PLAYWRIGHT_AVAILABLE

    def fetch_page(self, url: str, wait_for_selector: Optional[str] = None) -> Optional[str]:
        """
        Fetch a page using a real browser.

        Args:
            url: The URL to fetch
            wait_for_selector: Optional CSS selector to wait for before returning

        Returns:
            The page HTML content, or None if failed
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
            )

        html_content = None

        try:
            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch(headless=self.headless)

                # Create context with realistic settings
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self.HEADERS["User-Agent"],
                    locale="en-US",
                    timezone_id="America/New_York"
                )

                # Create page
                page = context.new_page()

                # Navigate to URL
                print(f"[Browser] Navigating to: {url}")
                page.goto(url, timeout=self.timeout, wait_until="networkidle")

                # Wait for specific selector if provided
                if wait_for_selector:
                    print(f"[Browser] Waiting for selector: {wait_for_selector}")
                    page.wait_for_selector(wait_for_selector, timeout=self.timeout)

                # Additional wait for dynamic content
                time.sleep(2)

                # Scroll down to trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.5)

                # Get the HTML
                html_content = page.content()
                print(f"[Browser] Got {len(html_content)} bytes of HTML")

                # Clean up
                context.close()
                browser.close()

        except PlaywrightTimeout:
            print(f"[Browser] Timeout loading {url}")
        except Exception as e:
            print(f"[Browser] Error: {e}")

        return html_content

    def fetch_multiple(self, urls: list[str], delay: float = 2.0) -> dict[str, Optional[str]]:
        """
        Fetch multiple pages efficiently using the same browser instance.

        Args:
            urls: List of URLs to fetch
            delay: Delay between requests in seconds

        Returns:
            Dict mapping URL to HTML content (or None if failed)
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed")

        results = {}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self.HEADERS["User-Agent"],
                    locale="en-US"
                )
                page = context.new_page()

                for i, url in enumerate(urls):
                    print(f"[Browser] [{i+1}/{len(urls)}] Fetching: {url}")

                    try:
                        page.goto(url, timeout=self.timeout, wait_until="networkidle")
                        time.sleep(1)

                        # Scroll to trigger lazy loading
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(0.5)

                        results[url] = page.content()
                        print(f"[Browser] Success: {len(results[url])} bytes")

                    except Exception as e:
                        print(f"[Browser] Failed: {e}")
                        results[url] = None

                    # Polite delay between requests
                    if i < len(urls) - 1:
                        time.sleep(delay)

                context.close()
                browser.close()

        except Exception as e:
            print(f"[Browser] Fatal error: {e}")
            # Fill remaining URLs with None
            for url in urls:
                if url not in results:
                    results[url] = None

        return results

    def save_page(self, url: str, output_path: str) -> bool:
        """
        Fetch a page and save the HTML to a file.

        Args:
            url: The URL to fetch
            output_path: Where to save the HTML file

        Returns:
            True if successful, False otherwise
        """
        html = self.fetch_page(url)
        if html:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[Browser] Saved to: {output_path}")
            return True
        return False


class LocalHTMLLoader:
    """
    Loads HTML from local files or directories.
    Useful for processing manually saved pages.
    """

    @staticmethod
    def load_file(file_path: str) -> Optional[str]:
        """Load HTML from a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"[Local] Error loading {file_path}: {e}")
            return None

    @staticmethod
    def load_directory(dir_path: str, extensions: tuple = (".html", ".htm")) -> dict[str, str]:
        """
        Load all HTML files from a directory.

        Args:
            dir_path: Path to directory
            extensions: File extensions to include

        Returns:
            Dict mapping filename to HTML content
        """
        results = {}

        if not os.path.isdir(dir_path):
            print(f"[Local] Directory not found: {dir_path}")
            return results

        for filename in os.listdir(dir_path):
            if filename.lower().endswith(extensions):
                file_path = os.path.join(dir_path, filename)
                content = LocalHTMLLoader.load_file(file_path)
                if content:
                    results[filename] = content
                    print(f"[Local] Loaded: {filename} ({len(content)} bytes)")

        return results


def check_playwright_installed() -> dict:
    """
    Check if Playwright is properly installed with browsers.

    Returns:
        Status dict with installation info
    """
    status = {
        "playwright_package": PLAYWRIGHT_AVAILABLE,
        "browsers_installed": False,
        "ready": False,
        "install_instructions": None
    }

    if not PLAYWRIGHT_AVAILABLE:
        status["install_instructions"] = "pip install playwright && playwright install chromium"
        return status

    # Try to check if browsers are installed
    try:
        with sync_playwright() as p:
            # This will fail if chromium isn't installed
            browser = p.chromium.launch(headless=True)
            browser.close()
            status["browsers_installed"] = True
            status["ready"] = True
    except Exception as e:
        status["browsers_installed"] = False
        status["install_instructions"] = "playwright install chromium"
        status["error"] = str(e)

    return status
