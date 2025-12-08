# Knowledge Extractor

A **Swiss Army knife** web API for extracting educational content from web pages. Maintains the relationship between images and their explanatory text, turning any tutorial into a structured knowledge base that AI can learn from.

## Features

- **Multiple Extraction Methods**:
  - Standard HTTP requests (fast, works for most sites)
  - Playwright browser automation (bypasses Cloudflare/bot protection)
  - Direct HTML input (for manually saved pages)
  - Batch processing (multiple URLs at once)
- **Smart Course Crawling**: Intelligently follows relevant links to extract entire courses
- **Image Downloading**: Downloads all images locally with descriptive naming
- **Structured Output**: JSON format optimized for AI consumption
- **Smart Text Association**: Links images to headings, captions, and surrounding explanations

## API Endpoints

### Health Check
```
GET /
```
Returns API info, available endpoints, and Playwright status.

### Extract Single Page (Standard HTTP)
```
POST /extract
Content-Type: application/json

{
  "url": "https://example.com/tutorial-page",
  "include_images": true,
  "use_browser": false  // optional: force browser mode
}
```

### Extract with Browser Automation (for blocked sites)
```
POST /extract-browser
Content-Type: application/json

{
  "url": "https://studiobinder.com/blog/...",
  "include_images": true
}
```
Use this for sites with bot protection (Cloudflare, StudioBinder, etc.)

### Extract from Raw HTML
```
POST /extract-html
Content-Type: application/json

{
  "html": "<html>...</html>",
  "base_url": "https://original-site.com/page",
  "source_name": "studiobinder_lighting",
  "include_images": true
}
```
Use this for manually saved pages or HTML from other sources.

### Batch Extract (Multiple URLs)
```
POST /extract-batch
Content-Type: application/json

{
  "urls": [
    "https://site1.com/page1",
    "https://site2.com/page2"
  ],
  "use_browser": false,
  "include_images": true,
  "combine_results": true
}
```

### Extract Entire Course
```
POST /extract-course
Content-Type: application/json

{
  "url": "https://example.com/course-main-page",
  "course_description": "Photography lighting techniques",
  "max_pages": 20,
  "include_images": true,
  "use_browser": false
}
```

### List All Extractions
```
GET /extractions
```

### Get Specific Extraction
```
GET /extractions/<extraction_id>
```

### Download Extraction JSON
```
GET /extractions/<extraction_id>/download
```

### Get Downloaded Image
```
GET /images/<filename>
```

### Check Playwright Status
```
GET /status/playwright
```

## Output Format

```json
{
  "source_url": "https://example.com/tutorial",
  "page_title": "5 Common Key Light Patterns",
  "extracted_date": "2024-12-08T10:30:00",
  "extraction_method": "http",
  "sections": [
    {
      "id": 1,
      "heading": "Butterfly Lighting",
      "term": "Butterfly Lighting",
      "definition": "Light positioned directly in front and above the subject...",
      "visual_indicators": "Creates butterfly-shaped shadow under nose",
      "surrounding_text": "The most notable shadow, and where this pattern gets its name...",
      "image": {
        "local_file": "images/001_butterfly_lighting.jpg",
        "original_url": "https://example.com/images/butterfly.jpg",
        "alt_text": "Portrait showing butterfly shadow",
        "caption": "Butterfly Lighting Example"
      }
    }
  ]
}
```

## Deploy to Railway

### Option 1: One-Click Deploy
1. Fork this repository
2. Go to [Railway](https://railway.app)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your forked repository
5. Railway will automatically detect the Procfile and deploy

### Option 2: Railway CLI
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

### Adding Persistent Storage
1. In Railway dashboard, go to your project
2. Click "New" → "Volume"
3. Set mount path to `/app/output`
4. Redeploy your service

### Enabling Browser Automation (Optional)
To extract from sites with bot protection:

1. SSH into your Railway service or modify the Dockerfile
2. Install Playwright:
```bash
pip install playwright
playwright install chromium
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port (set by Railway) |
| `OUTPUT_DIR` | /app/output | Where to store extractions |
| `MAX_PAGES` | 50 | Maximum pages to crawl per course |
| `DEBUG` | false | Enable debug mode |

## Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/knowledge-extractor.git
cd knowledge-extractor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# (Optional) Install browser automation
pip install playwright
playwright install chromium

# Run locally
python app.py
```

The API will be available at `http://localhost:8080`

## Example Usage

### Standard Extraction
```bash
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.slrlounge.com/common-key-light-patterns/"}'
```

### Browser Extraction (for blocked sites)
```bash
curl -X POST http://localhost:8080/extract-browser \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.studiobinder.com/blog/three-point-lighting-setup/"}'
```

### Batch Extraction
```bash
curl -X POST http://localhost:8080/extract-batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://nofilmschool.com/camera-angles",
      "https://nofilmschool.com/3-point-lighting",
      "https://nofilmschool.com/establishing-shot"
    ],
    "combine_results": true
  }'
```

### HTML Upload (for manually saved pages)
```bash
# Save a blocked page in your browser, then upload the HTML
curl -X POST http://localhost:8080/extract-html \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<html>...your saved HTML...</html>",
    "base_url": "https://studiobinder.com/blog/film-lighting/",
    "source_name": "studiobinder_lighting"
  }'
```

### Python Example
```python
import requests

API = "http://localhost:8080"

# Extract single page
result = requests.post(f"{API}/extract", json={
    "url": "https://www.slrlounge.com/common-key-light-patterns/"
}).json()

# Batch extract multiple pages
result = requests.post(f"{API}/extract-batch", json={
    "urls": [
        "https://nofilmschool.com/camera-angles",
        "https://nofilmschool.com/3-point-lighting"
    ]
}).json()

# Get extraction for AI to study
extraction_id = result["extraction_id"]
knowledge = requests.get(f"{API}/extractions/{extraction_id}").json()

# Feed to your AI
for section in knowledge["sections"]:
    print(f"Term: {section['term']}")
    print(f"Definition: {section['definition']}")
    if section.get("image"):
        print(f"Image: {section['image']['local_file']}")
```

## Use Case: AI Image/Video Generation

Build "knowledge bases" that AI studies before generating content:

```
1. EXTRACT: Photography/cinematography tutorials with visual examples
2. STUDY: AI loads the JSON and views each image
3. LEARN: AI connects terminology to visual appearance
4. GENERATE: Images/videos with accurate professional descriptions
```

### Supported Sources

| Source | Method | Content |
|--------|--------|---------|
| SLR Lounge | HTTP | Photography lighting patterns |
| Digital Photography School | HTTP | Aperture, depth of field |
| No Film School | HTTP | Camera shots, cinematography |
| StudioBinder | Browser/HTML | Film techniques (requires Playwright or manual save) |

## Handling Blocked Sites

Some sites (StudioBinder, PhotoPills) have bot protection. Options:

1. **Use `/extract-browser`** - Playwright browser automation (requires setup)
2. **Manual save + `/extract-html`** - Save page in browser, upload HTML
3. **Batch with `use_browser: true`** - Process multiple blocked URLs

## Architecture

```
knowledge-extractor/
├── app.py              # Flask API endpoints
├── extractor.py        # Core extraction logic
├── crawler.py          # Smart course crawling
├── browser.py          # Playwright browser automation
├── requirements.txt    # Dependencies
├── Procfile            # Railway deployment
└── output/             # Extracted content
    ├── images/         # Downloaded images
    └── extractions/    # JSON results
```

## License

MIT License - Use freely for your projects.
