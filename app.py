"""
Knowledge Extractor API
Flask API for extracting educational content from web pages.
Maintains relationships between images and their explanatory text.
"""

import os
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file
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
    """Health check and API info."""
    return jsonify({
        "name": "Knowledge Extractor API",
        "version": "1.0.0",
        "endpoints": {
            "POST /extract": "Extract content from a single URL",
            "POST /extract-course": "Extract entire course (follows relevant links)",
            "GET /extractions": "List all extractions",
            "GET /extractions/<id>": "Get specific extraction",
            "GET /images/<filename>": "Get downloaded image"
        },
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

    try:
        extractor = KnowledgeExtractor(OUTPUT_DIR)
        result = extractor.extract_page(url, download_images=include_images)

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


@app.route("/extract-course", methods=["POST"])
def extract_course():
    """
    Extract an entire course by intelligently following relevant links.

    Request body:
    {
        "url": "https://example.com/course-main-page",
        "course_description": "Photography lighting techniques course",  // helps AI determine relevance
        "max_pages": 20,  // optional, default 20
        "include_images": true  // optional, default true
    }
    """
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"]
    course_description = data.get("course_description", "")
    max_pages = min(data.get("max_pages", 20), MAX_PAGES)
    include_images = data.get("include_images", True)

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
                result = extractor.extract_page(page_url, download_images=include_images)
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
