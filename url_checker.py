"""
URL Status Checker - Traffic Light System
Quickly checks if URLs are accessible and categorizes them:
- GREEN: Accessible via standard HTTP
- YELLOW: Blocked by HTTP but may work with Browser Mode (Playwright)
- RED: Not accessible by any method
"""

import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Optional
import concurrent.futures

# Status constants
GREEN = "green"   # Standard HTTP works
YELLOW = "yellow" # Needs browser mode
RED = "red"       # Can't access

# Known problematic domains (from experience)
KNOWN_BROWSER_REQUIRED = {
    "studiobinder.com",
    "masterclass.com",
    "skillshare.com",
    "linkedin.com/learning",
}

KNOWN_BLOCKED = {
    "photopills.com",  # Aggressive blocking
}


class URLChecker:
    """Checks URL accessibility and maintains a cache of results."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Cache is permanent (no expiry) - user can manually re-check if needed
    CACHE_EXPIRY_DAYS = None  # None = permanent

    def __init__(self, cache_dir: str):
        """Initialize with cache directory."""
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "url_status_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load URL status cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        """Save URL status cache to file."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")
        except Exception:
            return url

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL (by domain, not full URL)."""
        domain = self._get_domain(url)
        return hashlib.md5(domain.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """Check if cache entry is still valid. Always valid since cache is permanent."""
        # Cache is permanent - always valid if it exists
        return "checked_date" in cache_entry

    def get_cached_status(self, url: str) -> Optional[dict]:
        """Get cached status for URL if available and valid."""
        cache_key = self._get_cache_key(url)
        domain = self._get_domain(url)

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if self._is_cache_valid(entry):
                return {
                    "url": url,
                    "domain": domain,
                    "status": entry["status"],
                    "reason": entry["reason"],
                    "suggestion": entry["suggestion"],
                    "from_cache": True,
                    "cache_date": entry["checked_date"]
                }
        return None

    def check_url(self, url: str, use_cache: bool = True) -> dict:
        """
        Check a single URL's accessibility.

        Returns dict with:
        - status: green/yellow/red
        - reason: Why this status
        - suggestion: What to do
        - from_cache: Whether result is cached
        """
        domain = self._get_domain(url)

        # Check cache first
        if use_cache:
            cached = self.get_cached_status(url)
            if cached:
                return cached

        # Check known lists first (instant)
        for blocked_domain in KNOWN_BLOCKED:
            if blocked_domain in domain:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": RED,
                    "reason": "Known blocked site - aggressive bot protection",
                    "suggestion": "Use HTML Upload: manually save the page in your browser, then paste the HTML",
                    "from_cache": False
                }
                self._update_cache(url, result)
                return result

        for browser_domain in KNOWN_BROWSER_REQUIRED:
            if browser_domain in domain:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": YELLOW,
                    "reason": "Known to require browser - Cloudflare or similar protection",
                    "suggestion": "Use Browser Mode tab - Playwright can bypass this",
                    "from_cache": False
                }
                self._update_cache(url, result)
                return result

        # Actually test the URL
        try:
            # Quick HEAD request first
            response = requests.head(url, headers=self.HEADERS, timeout=10, allow_redirects=True)

            # If HEAD doesn't work, try GET
            if response.status_code >= 400:
                response = requests.get(url, headers=self.HEADERS, timeout=10, allow_redirects=True)

            status_code = response.status_code

            # Check for Cloudflare/bot protection signatures
            content_check = ""
            if response.request.method == "GET":
                content_check = response.text[:5000].lower() if hasattr(response, 'text') else ""

            # Analyze response
            if status_code == 200:
                # Check for soft blocks (page loads but shows challenge)
                if any(sig in content_check for sig in ["cloudflare", "challenge-platform", "cf-browser-verification", "just a moment"]):
                    result = {
                        "url": url,
                        "domain": domain,
                        "status": YELLOW,
                        "reason": f"Cloudflare protection detected (status {status_code})",
                        "suggestion": "Use Browser Mode tab - Playwright can handle Cloudflare challenges",
                        "from_cache": False
                    }
                elif any(sig in content_check for sig in ["access denied", "blocked", "forbidden", "not allowed"]):
                    result = {
                        "url": url,
                        "domain": domain,
                        "status": YELLOW,
                        "reason": "Soft block detected - page returns but access denied",
                        "suggestion": "Try Browser Mode first. If that fails, use HTML Upload",
                        "from_cache": False
                    }
                else:
                    result = {
                        "url": url,
                        "domain": domain,
                        "status": GREEN,
                        "reason": "Accessible via standard HTTP",
                        "suggestion": "Ready to extract - will process automatically",
                        "from_cache": False
                    }

            elif status_code == 403:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": YELLOW,
                    "reason": f"HTTP 403 Forbidden - bot protection likely",
                    "suggestion": "Use Browser Mode tab - Playwright may bypass this",
                    "from_cache": False
                }

            elif status_code == 503:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": YELLOW,
                    "reason": f"HTTP 503 - often Cloudflare challenge page",
                    "suggestion": "Use Browser Mode tab - Playwright handles these",
                    "from_cache": False
                }

            elif status_code == 404:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": RED,
                    "reason": "HTTP 404 - Page not found",
                    "suggestion": "Check if the URL is correct - page doesn't exist",
                    "from_cache": False
                }

            elif status_code >= 500:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": RED,
                    "reason": f"HTTP {status_code} - Server error",
                    "suggestion": "Server is having issues - try again later",
                    "from_cache": False
                }

            else:
                result = {
                    "url": url,
                    "domain": domain,
                    "status": YELLOW,
                    "reason": f"HTTP {status_code} - Unusual response",
                    "suggestion": "Try Browser Mode - might work better",
                    "from_cache": False
                }

        except requests.exceptions.Timeout:
            result = {
                "url": url,
                "domain": domain,
                "status": YELLOW,
                "reason": "Request timed out - slow or blocking",
                "suggestion": "Try Browser Mode - it waits longer for pages to load",
                "from_cache": False
            }

        except requests.exceptions.SSLError:
            result = {
                "url": url,
                "domain": domain,
                "status": YELLOW,
                "reason": "SSL/Certificate error",
                "suggestion": "Try Browser Mode - it handles SSL differently",
                "from_cache": False
            }

        except requests.exceptions.ConnectionError:
            result = {
                "url": url,
                "domain": domain,
                "status": RED,
                "reason": "Connection failed - site may be down",
                "suggestion": "Check if the site is online - can't connect at all",
                "from_cache": False
            }

        except Exception as e:
            result = {
                "url": url,
                "domain": domain,
                "status": RED,
                "reason": f"Error: {str(e)[:100]}",
                "suggestion": "Unknown issue - try HTML Upload as fallback",
                "from_cache": False
            }

        # Cache the result
        self._update_cache(url, result)
        return result

    def _update_cache(self, url: str, result: dict):
        """Update cache with new result."""
        cache_key = self._get_cache_key(url)
        self.cache[cache_key] = {
            "domain": result["domain"],
            "status": result["status"],
            "reason": result["reason"],
            "suggestion": result["suggestion"],
            "checked_date": datetime.now().isoformat()
        }
        self._save_cache()

    def check_urls(self, urls: list, use_cache: bool = True) -> dict:
        """
        Check multiple URLs in parallel.

        Returns dict with:
        - green: list of green URLs
        - yellow: list of yellow URLs
        - red: list of red URLs
        - all_results: list of all results with details
        """
        results = {
            "green": [],
            "yellow": [],
            "red": [],
            "all_results": []
        }

        # Check URLs in parallel for speed
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {
                executor.submit(self.check_url, url, use_cache): url
                for url in urls
            }

            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    result = future.result()
                    results["all_results"].append(result)

                    if result["status"] == GREEN:
                        results["green"].append(result)
                    elif result["status"] == YELLOW:
                        results["yellow"].append(result)
                    else:
                        results["red"].append(result)

                except Exception as e:
                    url = future_to_url[future]
                    error_result = {
                        "url": url,
                        "domain": self._get_domain(url),
                        "status": RED,
                        "reason": f"Check failed: {str(e)[:100]}",
                        "suggestion": "Try HTML Upload as fallback",
                        "from_cache": False
                    }
                    results["all_results"].append(error_result)
                    results["red"].append(error_result)

        # Sort results by status (green first, then yellow, then red)
        results["all_results"] = (
            sorted(results["green"], key=lambda x: x["url"]) +
            sorted(results["yellow"], key=lambda x: x["url"]) +
            sorted(results["red"], key=lambda x: x["url"])
        )

        return results

    def get_cache_stats(self) -> dict:
        """Get statistics about the URL cache."""
        stats = {
            "total_domains": len(self.cache),
            "green": 0,
            "yellow": 0,
            "red": 0,
            "expired": 0
        }

        for entry in self.cache.values():
            if self._is_cache_valid(entry):
                status = entry.get("status", "")
                if status == GREEN:
                    stats["green"] += 1
                elif status == YELLOW:
                    stats["yellow"] += 1
                elif status == RED:
                    stats["red"] += 1
            else:
                stats["expired"] += 1

        return stats

    def clear_cache(self):
        """Clear the URL status cache."""
        self.cache = {}
        self._save_cache()

    def get_history(self, status_filter: str = None, search: str = None) -> list:
        """
        Get URL check history with optional filtering.

        Args:
            status_filter: Filter by status ('green', 'yellow', 'red', or None for all)
            search: Search term to filter domains

        Returns:
            List of cached URL statuses sorted by date (newest first)
        """
        results = []

        for cache_key, entry in self.cache.items():
            # Apply status filter
            if status_filter and entry.get("status") != status_filter:
                continue

            # Apply search filter
            if search:
                search_lower = search.lower()
                domain = entry.get("domain", "").lower()
                if search_lower not in domain:
                    continue

            results.append({
                "cache_key": cache_key,
                "domain": entry.get("domain", "Unknown"),
                "status": entry.get("status", "unknown"),
                "reason": entry.get("reason", ""),
                "suggestion": entry.get("suggestion", ""),
                "checked_date": entry.get("checked_date", "")
            })

        # Sort by date (newest first)
        results.sort(key=lambda x: x.get("checked_date", ""), reverse=True)

        return results

    def delete_from_cache(self, domain: str) -> bool:
        """Delete a specific domain from cache."""
        cache_key = hashlib.md5(domain.encode()).hexdigest()
        if cache_key in self.cache:
            del self.cache[cache_key]
            self._save_cache()
            return True
        return False
