# Knowledge Extractor

A web API that extracts educational content from web pages while maintaining the relationship between images and their explanatory text. Turn any tutorial webpage into a structured knowledge base that AI can read and learn from.

## Features

- **Single Page Extraction**: Extract content from any URL
- **Course Crawling**: Intelligently follow links to extract entire courses
- **Image Downloading**: Downloads all images locally with proper naming
- **Structured Output**: JSON format optimized for AI consumption
- **Smart Text Association**: Links images to their headings, captions, and surrounding explanations

## API Endpoints

### Health Check
```
GET /
```
Returns API info and status.

### Extract Single Page
```
POST /extract
Content-Type: application/json

{
  "url": "https://example.com/tutorial-page",
  "include_images": true
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
  "include_images": true
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

## Output Format

```json
{
  "source_url": "https://example.com/tutorial",
  "page_title": "5 Common Key Light Patterns",
  "extracted_date": "2024-12-08T10:30:00",
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
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize and deploy
railway init
railway up
```

### Adding Persistent Storage
To persist extractions across deployments:

1. In Railway dashboard, go to your project
2. Click "New" → "Volume"
3. Set mount path to `/app/output`
4. Redeploy your service

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
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

The API will be available at `http://localhost:8080`

## Example Usage

### Using curl

```bash
# Extract a single page
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.slrlounge.com/common-key-light-patterns/"}'

# Extract a course
curl -X POST http://localhost:8080/extract-course \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://digital-photography-school.com/aperture/",
    "course_description": "Photography aperture and depth of field tutorials",
    "max_pages": 10
  }'
```

### Using Python

```python
import requests

# Extract single page
response = requests.post(
    "http://localhost:8080/extract",
    json={"url": "https://www.slrlounge.com/common-key-light-patterns/"}
)
data = response.json()
print(f"Extracted {len(data['data']['sections'])} sections")

# Get the extraction for AI to use
extraction_id = data["extraction_id"]
knowledge = requests.get(f"http://localhost:8080/extractions/{extraction_id}").json()

# Now feed this to your AI
for section in knowledge["sections"]:
    print(f"Term: {section['term']}")
    print(f"Definition: {section['definition']}")
    if section.get("image"):
        print(f"Image: {section['image']['local_file']}")
```

## Use Case: AI Image Generation Training

This tool is perfect for building "knowledge bases" that AI can study before generating content:

1. **Extract** photography tutorials with image examples
2. **Feed** the structured JSON to your AI before image generation
3. **AI learns** proper terminology and visual indicators
4. **Generate** images with accurate professional descriptions

```python
# Before generating images, have AI "study" the knowledge base
knowledge = requests.get(f"{API_URL}/extractions/{extraction_id}").json()

# Feed each section (text + image) to multimodal AI
for section in knowledge["sections"]:
    # AI reads the definition
    # AI views the reference image
    # AI connects terminology to visual appearance
```

## License

MIT License - Use freely for your projects.
