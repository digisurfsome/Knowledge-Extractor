"""
Knowledge Extractor API
Flask API for extracting educational content from web pages.
Maintains relationships between images and their explanatory text.
"""

import os
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template
from extractor import KnowledgeExtractor
from crawler import SmartCrawler

app = Flask(__name__)

# Configuration
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/output")
MAX_PAGES = int(os.environ.get("MAX_PAGES", 50))

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "extractions"), exist_ok=True)


@app.route("/", methods=["GET"])
def home():
    """Dashboard UI."""
    return render_template('index.html')


@app.route("/api", methods=["GET"])
def api_info():
    """API info endpoint (always returns JSON)."""
    try:
        from browser import check_playwright_installed
        playwright_status = check_playwright_installed()
    except Exception:
        playwright_status = {"ready": False, "error": "Module not loaded"}

    return jsonify({
        "name": "Knowledge Extractor API",
        "version": "2.0.0",
        "playwright_ready": playwright_status.get("ready", False),
        "status": "running"
    })


@app.route("/extract", methods=["POST"])
def extract_single():
    """
    Extract content from a single URL.

    Request body:
    {
        "url": "https://example.com/tutorial",
        "include_images": true  // optional, default true
    }
    """
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"]
    include_images = data.get("include_images", True)
    use_browser = data.get("use_browser", False)  # Optional: force browser mode

    try:
        extractor = KnowledgeExtractor(OUTPUT_DIR)
        result = extractor.extract_page(url, download_images=include_images, use_browser=use_browser)

        # Save extraction
        extraction_id = _generate_extraction_id(url)
        output_path = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "extraction_id": extraction_id,
            "summary": {
                "page_title": result.get("page_title", "Unknown"),
                "sections_extracted": len(result.get("sections", [])),
                "images_downloaded": sum(1 for s in result.get("sections", []) if s.get("image"))
            },
            "data": result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/extract-browser", methods=["POST"])
def extract_with_browser():
    """
    Extract content using Playwright browser automation.
    Use this for sites with bot protection (Cloudflare, StudioBinder, etc.)

    Request body:
    {
        "url": "https://studiobinder.com/blog/...",
        "include_images": true  // optional, default true
    }
    """
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    # Check if Playwright is available
    try:
        from browser import check_playwright_installed
        status = check_playwright_installed()
        if not status.get("ready"):
            return jsonify({
                "error": "Playwright not available",
                "install_instructions": status.get("install_instructions"),
                "details": status
            }), 503
    except ImportError:
        return jsonify({
            "error": "Browser module not available",
            "install_instructions": "pip install playwright && playwright install chromium"
        }), 503

    url = data["url"]
    include_images = data.get("include_images", True)

    try:
        extractor = KnowledgeExtractor(OUTPUT_DIR)
        result = extractor.extract_with_browser(url, download_images=include_images)

        # Save extraction
        extraction_id = _generate_extraction_id(url + "_browser")
        output_path = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "extraction_id": extraction_id,
            "extraction_method": "browser",
            "summary": {
                "page_title": result.get("page_title", "Unknown"),
                "sections_extracted": len(result.get("sections", [])),
                "images_downloaded": sum(1 for s in result.get("sections", []) if s.get("image"))
            },
            "data": result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/extract-html", methods=["POST"])
def extract_from_html():
    """
    Extract content from raw HTML.
    Use this for manually saved pages or HTML from other sources.

    Request body:
    {
        "html": "<html>...</html>",
        "base_url": "https://original-site.com/page",  // for resolving image URLs
        "source_name": "studiobinder_lighting",  // optional identifier
        "include_images": true  // optional, default true
    }
    """
    data = request.get_json()

    if not data or "html" not in data:
        return jsonify({"error": "Missing 'html' in request body"}), 400

    html_content = data["html"]
    base_url = data.get("base_url", "")
    source_name = data.get("source_name", "uploaded_html")
    include_images = data.get("include_images", True)

    try:
        extractor = KnowledgeExtractor(OUTPUT_DIR)
        result = extractor.extract_from_html(
            html_content,
            base_url=base_url,
            download_images=include_images,
            source_name=source_name
        )

        # Save extraction
        extraction_id = _generate_extraction_id(source_name)
        output_path = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "extraction_id": extraction_id,
            "extraction_method": "html_upload",
            "summary": {
                "page_title": result.get("page_title", "Unknown"),
                "sections_extracted": len(result.get("sections", [])),
                "images_downloaded": sum(1 for s in result.get("sections", []) if s.get("image"))
            },
            "data": result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/extract-batch", methods=["POST"])
def extract_batch():
    """
    Extract content from multiple URLs in one request.

    Request body:
    {
        "urls": [
            "https://site1.com/page1",
            "https://site2.com/page2"
        ],
        "use_browser": false,  // optional, use Playwright for all URLs
        "include_images": true,  // optional, default true
        "combine_results": true  // optional, merge all sections into one result
    }
    """
    data = request.get_json()

    if not data or "urls" not in data:
        return jsonify({"error": "Missing 'urls' in request body"}), 400

    urls = data["urls"]
    if not isinstance(urls, list) or len(urls) == 0:
        return jsonify({"error": "'urls' must be a non-empty list"}), 400

    use_browser = data.get("use_browser", False)
    include_images = data.get("include_images", True)
    combine_results = data.get("combine_results", True)

    # Limit batch size
    max_batch = 20
    if len(urls) > max_batch:
        return jsonify({"error": f"Maximum {max_batch} URLs per batch"}), 400

    try:
        extractor = KnowledgeExtractor(OUTPUT_DIR)
        all_results = []
        all_sections = []
        errors = []

        for i, url in enumerate(urls):
            print(f"[Batch {i+1}/{len(urls)}] Processing: {url}")
            try:
                result = extractor.extract_page(url, download_images=include_images, use_browser=use_browser)
                all_results.append({
                    "url": url,
                    "success": True,
                    "page_title": result.get("page_title"),
                    "sections_count": len(result.get("sections", []))
                })

                # Add source info to each section
                for section in result.get("sections", []):
                    section["source_url"] = url
                    section["source_title"] = result.get("page_title")
                    all_sections.append(section)

            except Exception as e:
                print(f"  Error: {e}")
                all_results.append({
                    "url": url,
                    "success": False,
                    "error": str(e)
                })
                errors.append({"url": url, "error": str(e)})

        # Build response
        if combine_results:
            combined = {
                "extraction_type": "batch",
                "extracted_date": datetime.now().isoformat(),
                "urls_processed": len(urls),
                "urls_successful": len([r for r in all_results if r.get("success")]),
                "total_sections": len(all_sections),
                "results_summary": all_results,
                "sections": all_sections
            }

            # Save combined extraction
            extraction_id = _generate_extraction_id("batch_" + str(len(urls)))
            output_path = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, ensure_ascii=False)

            return jsonify({
                "success": True,
                "extraction_id": extraction_id,
                "summary": {
                    "urls_processed": len(urls),
                    "urls_successful": len([r for r in all_results if r.get("success")]),
                    "total_sections": len(all_sections),
                    "total_images": sum(1 for s in all_sections if s.get("image"))
                },
                "errors": errors if errors else None,
                "data": combined
            })
        else:
            return jsonify({
                "success": True,
                "results": all_results,
                "errors": errors if errors else None
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/status/playwright", methods=["GET"])
def playwright_status():
    """Check if Playwright browser automation is available."""
    try:
        from browser import check_playwright_installed
        status = check_playwright_installed()
        return jsonify(status)
    except ImportError:
        return jsonify({
            "playwright_package": False,
            "browsers_installed": False,
            "ready": False,
            "install_instructions": "pip install playwright && playwright install chromium"
        })


@app.route("/extract-course", methods=["POST"])
def extract_course():
    """
    Extract an entire course by intelligently following relevant links.

    Request body:
    {
        "url": "https://example.com/course-main-page",
        "course_description": "Photography lighting techniques course",  // helps AI determine relevance
        "max_pages": 20,  // optional, default 20
        "include_images": true,  // optional, default true
        "use_browser": false  // optional, use Playwright for bot-protected sites
    }
    """
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"]
    course_description = data.get("course_description", "")
    max_pages = min(data.get("max_pages", 20), MAX_PAGES)
    include_images = data.get("include_images", True)
    use_browser = data.get("use_browser", False)

    try:
        crawler = SmartCrawler(OUTPUT_DIR, max_pages=max_pages)
        extractor = KnowledgeExtractor(OUTPUT_DIR)

        # Get all relevant URLs
        print(f"Crawling course starting from: {url}")
        course_urls = crawler.crawl_course(url, course_description)
        print(f"Found {len(course_urls)} relevant pages")

        # Extract content from each URL
        all_sections = []
        pages_processed = []

        for i, page_url in enumerate(course_urls):
            print(f"[{i+1}/{len(course_urls)}] Extracting: {page_url}")
            try:
                result = extractor.extract_page(page_url, download_images=include_images, use_browser=use_browser)
                pages_processed.append({
                    "url": page_url,
                    "title": result.get("page_title", "Unknown"),
                    "sections_count": len(result.get("sections", []))
                })

                # Add page context to each section
                for section in result.get("sections", []):
                    section["source_page"] = page_url
                    section["source_title"] = result.get("page_title", "Unknown")
                    all_sections.append(section)

            except Exception as e:
                print(f"Error extracting {page_url}: {e}")
                pages_processed.append({
                    "url": page_url,
                    "error": str(e)
                })

        # Build combined result
        extraction_id = _generate_extraction_id(url + "_course")
        combined_result = {
            "extraction_type": "course",
            "source_url": url,
            "course_description": course_description,
            "extracted_date": datetime.now().isoformat(),
            "pages_crawled": len(course_urls),
            "pages_processed": pages_processed,
            "total_sections": len(all_sections),
            "sections": all_sections
        }

        # Save extraction
        output_path = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(combined_result, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "extraction_id": extraction_id,
            "summary": {
                "pages_crawled": len(course_urls),
                "total_sections": len(all_sections),
                "total_images": sum(1 for s in all_sections if s.get("image"))
            },
            "data": combined_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/extractions", methods=["GET"])
def list_extractions():
    """List all saved extractions."""
    extractions_dir = os.path.join(OUTPUT_DIR, "extractions")
    extractions = []

    if os.path.exists(extractions_dir):
        for filename in os.listdir(extractions_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(extractions_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    extractions.append({
                        "id": filename.replace(".json", ""),
                        "source_url": data.get("source_url", "Unknown"),
                        "extracted_date": data.get("extracted_date", "Unknown"),
                        "sections_count": len(data.get("sections", []))
                    })
                except Exception:
                    pass

    return jsonify({"extractions": extractions})


@app.route("/extractions/<extraction_id>", methods=["GET"])
def get_extraction(extraction_id):
    """Get a specific extraction by ID."""
    filepath = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Extraction not found"}), 404

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data)


@app.route("/extractions/<extraction_id>/download", methods=["GET"])
def download_extraction(extraction_id):
    """Download extraction as JSON file."""
    filepath = os.path.join(OUTPUT_DIR, "extractions", f"{extraction_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Extraction not found"}), 404

    return send_file(filepath, as_attachment=True, download_name=f"{extraction_id}.json")


@app.route("/images/<filename>", methods=["GET"])
def get_image(filename):
    """Serve a downloaded image."""
    filepath = os.path.join(OUTPUT_DIR, "images", filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "Image not found"}), 404

    return send_file(filepath)


def _generate_extraction_id(url: str) -> str:
    """Generate a unique extraction ID from URL and timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{timestamp}_{url_hash}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
